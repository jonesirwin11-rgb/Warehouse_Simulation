import csv
import os
import cv2
import supervision as sv
from ultralytics import YOLO

# 1. Define Paths
MODEL_PATH = "best.pt"
VIDEO_PATH = "generate_demo.mp4" # give the file patch here
OUTPUT_PATH = "wms_annotated_output.mp4"
REPORT_PATH = "wms_session_report.csv"

# How long (seconds) with no crossings before we consider the current
# load/unload session finished and the next crossing starts a new one.
# This lets a single video contain multiple trucks/sessions instead of
# collapsing everything into one first-to-last TAT.
SESSION_GAP_SECONDS = 8.0

# Initialize Model
model = YOLO(MODEL_PATH)

# 2. Optimized ByteTrack (From analysis: looser matching, better occlusion handling)
tracker = sv.ByteTrack(
    track_activation_threshold=0.40,  # Raised to avoid false background tracks
    lost_track_buffer=60,             # High memory for workers blocking boxes
    minimum_matching_threshold=0.5,   # Lowered from 0.8 to prevent ID switching
    frame_rate=25
)

# Video I/O Setup
cap = cv2.VideoCapture(VIDEO_PATH)
fps = cap.get(cv2.CAP_PROP_FPS) or 25
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
writer = cv2.VideoWriter(OUTPUT_PATH, cv2.VideoWriter_fourcc(*"avc1"), fps, (w, h))

SESSION_GAP_FRAMES = int(fps * SESSION_GAP_SECONDS)

# 3. Perfectly Vertical Tripwire (Dynamic to video height)
# Placed at X=350, spanning from Y=0 (top) to Y=h (bottom)
LINE_START = sv.Point(900, 4)
LINE_END   = sv.Point(904, 718)

# Guard against a tripwire that was drawn on a different video resolution
# (e.g. LINE_START/LINE_END copied from get_video_coord.py run on another file).
# An out-of-bounds line silently never gets crossed, so counts/TAT stay at
# zero all video with no visible error otherwise.
def _in_bounds(point, width, height):
    return 0 <= point.x <= width and 0 <= point.y <= height

if not (_in_bounds(LINE_START, w, h) and _in_bounds(LINE_END, w, h)):
    print(
        f"CRITICAL ERROR: Tripwire points {LINE_START}, {LINE_END} fall outside "
        f"the video frame ({w}x{h}). Re-run get_video_coord.py on this exact "
        f"video and update LINE_START/LINE_END before continuing."
    )
    cap.release()
    exit()

# Setup Supervision Annotators
line_zone = sv.LineZone(start=LINE_START, end=LINE_END)
box_annotator = sv.BoxAnnotator(thickness=2)
label_annotator = sv.LabelAnnotator(text_scale=0.5)
line_annotator = sv.LineZoneAnnotator(thickness=2, text_scale=0.5)

# Per-session TAT tracking. Each session is a dict:
#   {"start_frame": int, "end_frame": int, "box_count": int}
# A new session starts whenever a crossing follows a gap of more than
# SESSION_GAP_FRAMES since the previous crossing of the same direction.
load_sessions = []
unload_sessions = []

frame_idx = 0

print("Starting optimized video processing...")

# Add a failsafe to immediately alert you if the video path is wrong
if not cap.isOpened():
    print(f"CRITICAL ERROR: OpenCV could not open {VIDEO_PATH}. Check the file name and path.")
    exit()


def _update_sessions(sessions, crossing_count, frame_idx, gap_frames):
    """Append to the current session or start a new one if the gap since
    the last crossing exceeds gap_frames. Returns the live TAT (seconds)
    for the session currently in progress."""
    if crossing_count > 0:
        if not sessions or (frame_idx - sessions[-1]["end_frame"]) > gap_frames:
            sessions.append({"start_frame": frame_idx, "end_frame": frame_idx, "box_count": 0})
        sessions[-1]["end_frame"] = frame_idx
        sessions[-1]["box_count"] += int(crossing_count)
    return sessions


while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_idx += 1

    # 4. YOLO Detection (Confidence raised to 0.50 to stop false positives)
    results = model(frame, conf=0.50, iou=0.45, verbose=False)[0]
    detections = sv.Detections.from_ultralytics(results)

    # Update Tracker
    detections = tracker.update_with_detections(detections)

    # Trigger Line Zone
    crossed_in, crossed_out = line_zone.trigger(detections)

    # Per-session TAT logic: groups crossings into sessions using a gap
    # threshold so multiple trucks in one video get separate TATs instead
    # of being merged into a single first-to-last measurement.
    _update_sessions(load_sessions, crossed_in.sum(), frame_idx, SESSION_GAP_FRAMES)
    _update_sessions(unload_sessions, crossed_out.sum(), frame_idx, SESSION_GAP_FRAMES)

    load_tat = (
        (load_sessions[-1]["end_frame"] - load_sessions[-1]["start_frame"]) / fps
        if load_sessions else 0.0
    )
    unload_tat = (
        (unload_sessions[-1]["end_frame"] - unload_sessions[-1]["start_frame"]) / fps
        if unload_sessions else 0.0
    )

    # Draw Overlays
    labels = [f"ID: #{tid}" for tid in detections.tracker_id] if detections.tracker_id is not None else []
    frame = box_annotator.annotate(frame, detections)
    frame = label_annotator.annotate(frame, detections, labels)
    frame = line_annotator.annotate(frame, line_zone)

    # HUD (shows totals + the TAT of whichever session is currently active)
    cv2.putText(frame, f"Boxes Loaded: {line_zone.in_count} | Load TAT: {load_tat:.1f}s",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, f"Boxes Unloaded: {line_zone.out_count} | Unload TAT: {unload_tat:.1f}s",
                (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    writer.write(frame)

cap.release()
writer.release()

print("\n--- Session Summary ---")
print(f"Total Loaded (In): {line_zone.in_count}")
print(f"Total Unloaded (Out): {line_zone.out_count}")
print(f"Loading sessions detected: {len(load_sessions)}")
print(f"Unloading sessions detected: {len(unload_sessions)}")
print(f"Annotated video saved to: {OUTPUT_PATH}")

# --- Per-session summary report (CSV) ---
# One row per load/unload session, with frame range converted to
# timestamps and TAT in seconds, so this can be handed off as the POC's
# per-session report deliverable without extra post-processing.
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
    with open(REPORT_PATH, "w", newline="") as f:
        writer_csv = csv.DictWriter(
            f, fieldnames=["session_id", "direction", "box_count", "start_time_s", "end_time_s", "tat_seconds"]
        )
        writer_csv.writeheader()
        writer_csv.writerows(report_rows)
    print(f"Per-session report saved to: {os.path.abspath(REPORT_PATH)}")
else:
    print("No load/unload sessions detected; skipping report file.")