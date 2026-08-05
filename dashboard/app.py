"""
Warehouse Management System – Web Dashboard
============================================
Flask app that lets users:
1.  Upload a warehouse dock video.
2.  Select the tripwire line on the first frame (replacing get_video_coord.py).
3.  Run the YOLO + Supervision pipeline (demo_wms.py logic) with those coords.
4.  Download / view the annotated output video + session report CSV.
"""

import csv
import os
import sys
import uuid
import threading
import time

import cv2
import numpy as np
import supervision as sv
from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_from_directory,
)
from ultralytics import YOLO

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")
STATIC_FOLDER = os.path.join(BASE_DIR, "static")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

MODEL_PATH = os.path.join(PARENT_DIR, "best.pt")

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder=STATIC_FOLDER, template_folder=os.path.join(BASE_DIR, "templates"))
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB upload limit

# ---------------------------------------------------------------------------
# In-memory job store  {job_id: {status, progress, message, output_video, report_csv}}
# ---------------------------------------------------------------------------
jobs: dict = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_video():
    """Accept a video file, extract the first frame, return it as a JPEG."""
    if "video" not in request.files:
        return jsonify({"error": "No video file provided"}), 400

    video = request.files["video"]
    if video.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    # Save with a unique name so parallel uploads don't collide
    job_id = uuid.uuid4().hex[:12]
    ext = os.path.splitext(video.filename)[1] or ".mp4"
    video_filename = f"{job_id}{ext}"
    video_path = os.path.join(UPLOAD_FOLDER, video_filename)
    video.save(video_path)

    # Extract first frame
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if not ret:
        return jsonify({"error": "Could not read video file"}), 400

    # Save first frame as JPEG
    frame_filename = f"{job_id}_frame.jpg"
    frame_path = os.path.join(STATIC_FOLDER, frame_filename)
    cv2.imwrite(frame_path, frame)

    return jsonify({
        "job_id": job_id,
        "frame_url": f"/static/{frame_filename}",
        "video_width": w,
        "video_height": h,
        "video_filename": video_filename,
    })


@app.route("/process", methods=["POST"])
def process_video():
    """Start processing with the selected tripwire coordinates."""
    data = request.json
    job_id = data.get("job_id")
    video_filename = data.get("video_filename")
    line_start = data.get("line_start")  # {x, y}
    line_end = data.get("line_end")      # {x, y}

    if not all([job_id, video_filename, line_start, line_end]):
        return jsonify({"error": "Missing parameters"}), 400

    video_path = os.path.join(UPLOAD_FOLDER, video_filename)
    if not os.path.exists(video_path):
        return jsonify({"error": "Video file not found"}), 404

    # Initialise job
    jobs[job_id] = {
        "status": "running",
        "progress": 0,
        "message": "Initialising model…",
        "output_video": None,
        "report_csv": None,
    }

    # Run processing in a background thread
    t = threading.Thread(
        target=_run_pipeline,
        args=(job_id, video_path, line_start, line_end),
        daemon=True,
    )
    t.start()

    return jsonify({"job_id": job_id, "status": "started"})


@app.route("/status/<job_id>")
def job_status(job_id):
    """Poll processing progress."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/outputs/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)


# ---------------------------------------------------------------------------
# Pipeline  (runs in a background thread)
# ---------------------------------------------------------------------------
SESSION_GAP_SECONDS = 8.0


def _update_sessions(sessions, crossing_count, frame_idx, gap_frames):
    if crossing_count > 0:
        if not sessions or (frame_idx - sessions[-1]["end_frame"]) > gap_frames:
            sessions.append({"start_frame": frame_idx, "end_frame": frame_idx, "box_count": 0})
        sessions[-1]["end_frame"] = frame_idx
        sessions[-1]["box_count"] += int(crossing_count)
    return sessions


def _run_pipeline(job_id, video_path, line_start_dict, line_end_dict):
    try:
        job = jobs[job_id]
        job["message"] = "Loading YOLO model…"

        model = YOLO(MODEL_PATH)

        tracker = sv.ByteTrack(
            track_activation_threshold=0.40,
            lost_track_buffer=60,
            minimum_matching_threshold=0.5,
            frame_rate=25,
        )

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            job["status"] = "error"
            job["message"] = "Could not open video file."
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

        session_gap_frames = int(fps * SESSION_GAP_SECONDS)

        LINE_START = sv.Point(int(line_start_dict["x"]), int(line_start_dict["y"]))
        LINE_END = sv.Point(int(line_end_dict["x"]), int(line_end_dict["y"]))

        # Bounds check
        def _in_bounds(pt, width, height):
            return 0 <= pt.x <= width and 0 <= pt.y <= height

        if not (_in_bounds(LINE_START, w, h) and _in_bounds(LINE_END, w, h)):
            job["status"] = "error"
            job["message"] = (
                f"Tripwire points ({LINE_START.x},{LINE_START.y})-({LINE_END.x},{LINE_END.y}) "
                f"fall outside the video frame ({w}×{h})."
            )
            cap.release()
            return

        output_video_name = f"{job_id}_annotated.mp4"
        output_video_path = os.path.join(OUTPUT_FOLDER, output_video_name)
        writer = cv2.VideoWriter(output_video_path, cv2.VideoWriter_fourcc(*"avc1"), fps, (w, h))

        # If avc1 not available, fall back to mp4v
        if not writer.isOpened():
            writer = cv2.VideoWriter(output_video_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))

        line_zone = sv.LineZone(start=LINE_START, end=LINE_END)
        box_annotator = sv.BoxAnnotator(thickness=2)
        label_annotator = sv.LabelAnnotator(text_scale=0.5)
        line_annotator = sv.LineZoneAnnotator(thickness=2, text_scale=0.5)

        load_sessions = []
        unload_sessions = []
        frame_idx = 0

        job["message"] = "Processing frames…"

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1

            results = model(frame, conf=0.50, iou=0.45, verbose=False)[0]
            detections = sv.Detections.from_ultralytics(results)
            detections = tracker.update_with_detections(detections)

            crossed_in, crossed_out = line_zone.trigger(detections)
            _update_sessions(load_sessions, crossed_in.sum(), frame_idx, session_gap_frames)
            _update_sessions(unload_sessions, crossed_out.sum(), frame_idx, session_gap_frames)

            load_tat = (
                (load_sessions[-1]["end_frame"] - load_sessions[-1]["start_frame"]) / fps
                if load_sessions else 0.0
            )
            unload_tat = (
                (unload_sessions[-1]["end_frame"] - unload_sessions[-1]["start_frame"]) / fps
                if unload_sessions else 0.0
            )

            labels = (
                [f"ID: #{tid}" for tid in detections.tracker_id]
                if detections.tracker_id is not None else []
            )
            frame = box_annotator.annotate(frame, detections)
            frame = label_annotator.annotate(frame, detections, labels)
            frame = line_annotator.annotate(frame, line_zone)

            cv2.putText(frame, f"Boxes Loaded: {line_zone.in_count} | Load TAT: {load_tat:.1f}s",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Boxes Unloaded: {line_zone.out_count} | Unload TAT: {unload_tat:.1f}s",
                        (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            writer.write(frame)

            # Update progress every 5 frames to reduce overhead
            if frame_idx % 5 == 0:
                job["progress"] = min(int(frame_idx / total_frames * 100), 99)

        cap.release()
        writer.release()

        # --- CSV report ---
        report_name = f"{job_id}_report.csv"
        report_path = os.path.join(OUTPUT_FOLDER, report_name)
        report_rows = []
        for i, s in enumerate(load_sessions, start=1):
            report_rows.append({
                "session_id": f"LOAD-{i}",
                "direction": "loading",
                "box_count": s["box_count"],
                "start_time_s": round(s["start_frame"] / fps, 2),
                "end_time_s": round(s["end_frame"] / fps, 2),
                "tat_seconds": round((s["end_frame"] - s["start_frame"]) / fps, 2),
            })
        for i, s in enumerate(unload_sessions, start=1):
            report_rows.append({
                "session_id": f"UNLOAD-{i}",
                "direction": "unloading",
                "box_count": s["box_count"],
                "start_time_s": round(s["start_frame"] / fps, 2),
                "end_time_s": round(s["end_frame"] / fps, 2),
                "tat_seconds": round((s["end_frame"] - s["start_frame"]) / fps, 2),
            })

        if report_rows:
            with open(report_path, "w", newline="") as f:
                w_csv = csv.DictWriter(
                    f, fieldnames=["session_id", "direction", "box_count", "start_time_s", "end_time_s", "tat_seconds"]
                )
                w_csv.writeheader()
                w_csv.writerows(report_rows)

        job["status"] = "done"
        job["progress"] = 100
        job["message"] = "Processing complete!"
        job["output_video"] = f"/outputs/{output_video_name}"
        job["report_csv"] = f"/outputs/{report_name}" if report_rows else None
        job["summary"] = {
            "total_loaded": line_zone.in_count,
            "total_unloaded": line_zone.out_count,
            "load_sessions": len(load_sessions),
            "unload_sessions": len(unload_sessions),
            "total_frames": frame_idx,
        }

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["message"] = str(e)
        import traceback
        traceback.print_exc()


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
