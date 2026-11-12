from flask import Flask, request, jsonify, render_template, send_from_directory, send_file
from flask_cors import CORS
from audit import StaticStackAudit
import os
import sqlite3
import json
import requests
import datetime
import threading
import subprocess
import time
import werkzeug.utils
import imageio_ffmpeg
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from edge.config import KNOWN_CARTON_DIMENSIONS

STATIC_FOLDER = os.path.join(BASE_DIR, "dashboard", "static")
TEMPLATE_FOLDER = os.path.join(BASE_DIR, "dashboard", "templates")

app = Flask(__name__, static_folder=STATIC_FOLDER, template_folder=TEMPLATE_FOLDER)
CORS(app)  # Allow frontend to poll this API

# ==========================================
# Task 5 — SQLite Persistence
# ==========================================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventory_state.db")

DEFAULT_STATE = {
    "staged_boxes": 0,
    "truck_exit_events": 0,
    "staging_arrival_events": 0,
    "last_event": None,
    "last_audit": None,
}


def init_db(db_path=None):
    """Initialize (or open) the SQLite database and ensure schema exists."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            state_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_log (
            event_id TEXT PRIMARY KEY,
            camera_id TEXT,
            event_type TEXT,
            quantity INTEGER,
            tracker_ids TEXT,
            video_t_sec TEXT,
            confidence REAL,
            received_at TEXT
        )
    """)
    conn.commit()
    return conn


def save_state(conn, state: dict):
    """Persist inventory state to SQLite (single-row upsert)."""
    conn.execute(
        "INSERT INTO inventory_state (id, state_json, updated_at) VALUES (1, ?, datetime('now')) "
        "ON CONFLICT(id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at",
        (json.dumps(state),),
    )
    conn.commit()

def log_event(conn, event: dict):
    """Log individual confirmed events for playback review."""
    conn.execute(
        "INSERT OR IGNORE INTO event_log "
        "(event_id, camera_id, event_type, quantity, tracker_ids, video_t_sec, confidence, received_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
        (
            event["event_id"], event["camera_id"], event["event_type"],
            event["quantity"], json.dumps(event.get("tracker_ids", [])),
            json.dumps(event.get("video_t_sec", [])), event.get("confidence", 0.0),
        ),
    )
    conn.commit()


def load_state(conn) -> dict:
    """Load persisted inventory state, returning empty dict if none exists."""
    row = conn.execute("SELECT state_json FROM inventory_state WHERE id=1").fetchone()
    return json.loads(row[0]) if row else {}


# ==========================================
# Phase 7 - Live Inventory Logic
# ==========================================
db_lock = threading.Lock()
db_conn = init_db()
_persisted = load_state(db_conn)
LIVE_INVENTORY_STATE = {**DEFAULT_STATE, **_persisted} if _persisted else {**DEFAULT_STATE}

# In-memory deduplication of events
processed_event_ids = set()

audit_module = StaticStackAudit()


def _trolley_for_camera(camera_id: str) -> str:
    """Map logical camera IDs (e.g. T1_CAM01, T2_CAM02, CAM01) to a trolley bucket."""
    if camera_id and camera_id.startswith("T2_"):
        return "trolley_2"
    return "trolley_1"


def compute_trolley_analysis(conn) -> dict:
    """Compute per-trolley box counts and turnaround time directly from persisted events."""
    stats = {
        "trolley_1": {"dock_boxes": 0, "side_boxes": 0, "boxes": 0, "timestamps": []},
        "trolley_2": {"dock_boxes": 0, "side_boxes": 0, "boxes": 0, "timestamps": []},
    }
    with db_lock:
        rows = conn.execute(
            "SELECT camera_id, event_type, quantity, video_t_sec FROM event_log"
        ).fetchall()

    for camera_id, event_type, quantity, video_t_sec_raw in rows:
        bucket = stats[_trolley_for_camera(camera_id)]
        qty = int(quantity or 0)
        if event_type == "TRUCK_EXIT_EVENT":
            bucket["dock_boxes"] += qty
        elif event_type == "STAGING_ARRIVAL_EVENT":
            bucket["side_boxes"] += qty

        try:
            ts_list = json.loads(video_t_sec_raw or "[]")
            for ts in ts_list:
                if ts is not None:
                    bucket["timestamps"].append(float(ts))
        except (TypeError, ValueError):
            pass

    stack_depth = int(KNOWN_CARTON_DIMENSIONS.get("depth", 3))
    for key in ("trolley_1", "trolley_2"):
        b = stats[key]
        b["boxes"] = (b["dock_boxes"] * stack_depth) if b["dock_boxes"] > 0 else b["side_boxes"]

    t1_time = round(max(stats["trolley_1"]["timestamps"]), 1) if stats["trolley_1"]["timestamps"] else 0.0
    t2_time = round(max(stats["trolley_2"]["timestamps"]), 1) if stats["trolley_2"]["timestamps"] else 0.0
    total_time = round(t1_time + t2_time, 1)
    total_boxes = stats["trolley_1"]["boxes"] + stats["trolley_2"]["boxes"]
    total_sec_int = int(round(total_time))
    tat_formatted = f"{total_sec_int // 60}m {total_sec_int % 60}s"

    return {
        "trolley_1": {
            "dock_boxes": stats["trolley_1"]["dock_boxes"],
            "side_boxes": stats["trolley_1"]["side_boxes"],
            "boxes": stats["trolley_1"]["boxes"],
            "time_sec": t1_time,
        },
        "trolley_2": {
            "dock_boxes": stats["trolley_2"]["dock_boxes"],
            "side_boxes": stats["trolley_2"]["side_boxes"],
            "boxes": stats["trolley_2"]["boxes"],
            "time_sec": t2_time,
        },
        "total": {
            "boxes": total_boxes,
            "time_sec": total_time,
            "tat_formatted": tat_formatted,
        },
    }


@app.route('/')
def index():
    return render_template("index.html")


@app.route('/results')
def results_page():
    return render_template("results.html")


@app.route('/api/events', methods=['POST'])
def handle_event():
    event = request.json
    event_id = event.get("event_id")
    event_type = event.get("event_type")
    quantity = event.get("quantity", 0)

    if not event_id or not event_type:
        return jsonify({"error": "Malformed event payload"}), 400

    with db_lock:
        # Phase 10: Deduplicate
        if event_id in processed_event_ids:
            print(f"[BACKEND] Ignored duplicate event {event_id}")
            return jsonify({"status": "duplicate_ignored"}), 200

        processed_event_ids.add(event_id)

        # Task 3: Log individual event immediately
        log_event(db_conn, event)

        # Process counts based on the strict architectural rules
        if event_type == "STAGING_ARRIVAL_EVENT":
            LIVE_INVENTORY_STATE["staging_arrival_events"] += quantity
            LIVE_INVENTORY_STATE["staged_boxes"] += quantity
            print(f"[BACKEND] Staging count increased +{quantity} | Staged Total: {LIVE_INVENTORY_STATE['staged_boxes']}")
            
        elif event_type == "TRUCK_EXIT_EVENT":
            LIVE_INVENTORY_STATE["truck_exit_events"] += quantity
            print(f"[BACKEND] Truck Exit observed +{quantity} | Exited Total: {LIVE_INVENTORY_STATE['truck_exit_events']}")

        LIVE_INVENTORY_STATE["last_event"] = event_id

        # Task 5: persist immediately after every mutation
        save_state(db_conn, LIVE_INVENTORY_STATE)

    return jsonify({"status": "success", "live_state": LIVE_INVENTORY_STATE}), 200


@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    return jsonify(LIVE_INVENTORY_STATE), 200


@app.route('/api/analysis', methods=['GET'])
def get_analysis():
    return jsonify(compute_trolley_analysis(db_conn)), 200

@app.route('/api/events/log', methods=['GET'])
def get_event_log():
    with db_lock:
        rows = db_conn.execute(
            "SELECT event_id, camera_id, event_type, quantity, tracker_ids, "
            "video_t_sec, confidence, received_at FROM event_log ORDER BY received_at DESC"
        ).fetchall()
    return jsonify([
        {
            "event_id": r[0], "camera_id": r[1], "event_type": r[2],
            "quantity": r[3], "tracker_ids": json.loads(r[4]),
            "video_t_sec": json.loads(r[5] or "[]"), "confidence": r[6],
            "received_at": r[7],
        }
        for r in rows
    ]), 200

@app.route('/api/runs', methods=['GET'])
def list_runs():
    """List saved annotated video files available for review (newest first)."""
    videos_dir = os.path.join(BASE_DIR, "videos")
    if not os.path.isdir(videos_dir):
        return jsonify([]), 200
    files = [f for f in os.listdir(videos_dir) if f.endswith(".mp4") and "annotated" in f]
    files.sort(key=lambda f: os.path.getmtime(os.path.join(videos_dir, f)), reverse=True)
    return jsonify(files), 200

@app.route('/videos/<path:filename>')
def serve_video(filename):
    """Serve an annotated video for playback. Path-restricted to videos/ dir."""
    videos_dir = os.path.join(BASE_DIR, "videos")
    # prevent path traversal
    safe_path = os.path.normpath(os.path.join(videos_dir, filename))
    if not safe_path.startswith(os.path.normpath(videos_dir)):
        return jsonify({"error": "invalid path"}), 400
    return send_from_directory(videos_dir, filename)

UPLOAD_FOLDER = os.path.join(BASE_DIR, "videos", "uploads", "_jobs")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

PROCESSING_STATE = {
    "1": False,
    "2": False,
    "t1_cam1": False,
    "t1_cam2": False,
    "t2_cam1": False,
    "t2_cam2": False,
}


def process_video_worker(source_path, camera_id, entry_line=None, exit_line=None, trolley_id="1", slot_id=None):
    slot_key = slot_id or f"t{trolley_id}_cam{camera_id}"
    camera_name = f"T{trolley_id}_CAM0{camera_id}"
    PROCESSING_STATE[slot_key] = True
    if slot_key.startswith("t1_"):
        PROCESSING_STATE[str(camera_id)] = True
    try:
        filename = os.path.basename(source_path)
        base_name = os.path.splitext(filename)[0]
        raw_output = os.path.join(BASE_DIR, "videos", f"{slot_key}_{base_name}_raw_annotated.mp4")
        final_output = os.path.join(BASE_DIR, "videos", f"{slot_key}_{base_name}_annotated.mp4")
        export_frame_path = os.path.join(BASE_DIR, "videos", f"stream_{slot_key}.jpg")
        
        cmd = [
            sys.executable, os.path.join(BASE_DIR, "edge", "edge_node.py"),
            "--camera", str(camera_id),
            "--camera-name", camera_name,
            "--headless",
            "--source", source_path,
            "--save-video", raw_output,
            "--export-frame", export_frame_path
        ]
        if entry_line:
            cmd.extend(["--entry-line", entry_line])
        if exit_line:
            cmd.extend(["--exit-line", exit_line])
            
        print(f"[WORKER] Starting YOLO edge_node.py ({camera_name}) over {source_path}...")
        subprocess.run(cmd)

        print(f"[WORKER] Edge node complete. Transcoding to H.264 browser-compatible format...")
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        transcode_cmd = [
            ffmpeg_path, "-y", "-i", raw_output, "-vcodec", "libx264", "-pix_fmt", "yuv420p", "-acodec", "aac", final_output
        ]
        subprocess.run(transcode_cmd)
        
        if os.path.exists(raw_output):
            os.remove(raw_output)
        
        print(f"[WORKER] Processing completed successfully! Video saved to {final_output}")
    finally:
        PROCESSING_STATE[slot_key] = False
        if slot_key.startswith("t1_"):
            PROCESSING_STATE[str(camera_id)] = False
        cleanup_path = os.path.join(BASE_DIR, "videos", f"stream_{slot_key}.jpg")
        if os.path.exists(cleanup_path):
            try:
                os.remove(cleanup_path)
            except Exception:
                pass


@app.route('/api/status/<slot_id>', methods=['GET'])
def get_stream_status(slot_id):
    return jsonify({"processing": PROCESSING_STATE.get(str(slot_id), False)}), 200


@app.route('/api/stream/<slot_id>', methods=['GET'])
def get_stream(slot_id):
    safe_slot = werkzeug.utils.secure_filename(str(slot_id))
    candidates = [
        os.path.join(BASE_DIR, "videos", f"stream_{safe_slot}.jpg"),
        os.path.join(BASE_DIR, "videos", f"stream_cam{safe_slot}.jpg"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return send_file(path, mimetype='image/jpeg', max_age=0)
    return jsonify({"error": "No stream active"}), 404


@app.route('/api/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    camera_id = request.form.get('camera_id', '1')
    trolley_id = request.form.get('trolley_id', '1')
    slot_id = request.form.get('slot_id') or f"t{trolley_id}_cam{camera_id}"
    entry_line = request.form.get('entry_line')
    exit_line = request.form.get('exit_line')
        
    safe_filename = werkzeug.utils.secure_filename(file.filename)
    timestamped_name = f"{int(time.time())}_{safe_filename}"
    upload_path = os.path.join(UPLOAD_FOLDER, timestamped_name)
    
    file.save(upload_path)
    
    # Spawn background worker
    threading.Thread(
        target=process_video_worker,
        args=(upload_path, camera_id, entry_line, exit_line, trolley_id, slot_id),
        daemon=True,
    ).start()
    
    return jsonify({
        "status": "processing_started",
        "slot_id": slot_id,
        "message": "Video is being processed in the background.",
    }), 200

@app.route('/api/audit', methods=['POST'])
def trigger_audit():
    # 1. Run inference on the latest camera 2 frame
    estimation = audit_module.estimate_count()
    if "error" in estimation:
        return jsonify(estimation), 400

    # 2. Reconcile with Phase 10 Logic
    live_count = LIVE_INVENTORY_STATE["staged_boxes"]
    audit_count = estimation["estimated_count"]
    
    reconciliation_result = audit_module.reconcile(live_count, audit_count)
    reconciliation_result["confidence"] = estimation["confidence"]

    # Task 6: audit is advisory only — store result but never overwrite tracked count
    LIVE_INVENTORY_STATE["last_audit"] = reconciliation_result

    print(f"[AUDIT] Tracked: {live_count} | Estimated: {audit_count} -> "
          f"{reconciliation_result['status']} (needs_review={reconciliation_result.get('needs_review', False)})")

    return jsonify(reconciliation_result), 200

@app.route('/api/reset', methods=['POST'])
def reset_system():
    global LIVE_INVENTORY_STATE, processed_event_ids
    
    with db_lock:
        # Reset tracking state
        LIVE_INVENTORY_STATE = {**DEFAULT_STATE}
        processed_event_ids.clear()
        
        # Wipe database state
        db_conn.execute("DELETE FROM inventory_state")
        db_conn.execute("DELETE FROM event_log")
        db_conn.commit()
        save_state(db_conn, LIVE_INVENTORY_STATE)
    
    # Clear historic annotated outputs and temp upload job copies
    videos_dir = os.path.join(BASE_DIR, "videos")
    if os.path.isdir(videos_dir):
        for f in os.listdir(videos_dir):
            if f.endswith(".mp4") and "annotated" in f:
                try:
                    os.remove(os.path.join(videos_dir, f))
                except Exception as e:
                    print(f"[ERROR] Could not delete {f}: {e}")
    if os.path.isdir(UPLOAD_FOLDER):
        for f in os.listdir(UPLOAD_FOLDER):
            try:
                os.remove(os.path.join(UPLOAD_FOLDER, f))
            except Exception as e:
                print(f"[ERROR] Could not delete temp upload {f}: {e}")
                    
    return jsonify({"status": "success", "message": "System purged completely."}), 200


if __name__ == '__main__':
    # Phase 0: Make sure data directory exists for the latest_staging.jpg
    os.makedirs("data", exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
