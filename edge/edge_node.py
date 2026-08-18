import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import argparse
import sys
import logging
import cv2
from ultralytics import YOLO
import supervision as sv

from config import (
    BACKEND_URL,
    CAM1_ID, CAM1_VIDEO_SOURCE, CAM1_LINE_ENTRY, CAM1_LINE_EXIT,
    CAM2_ID, CAM2_VIDEO_SOURCE, CAM2_LINE_ENTRY, CAM2_LINE_EXIT, CAM2_STAGING_ROI,
    LATEST_STAGING_OUTPUT
)
from box_state_machine import BoxStateMachine, StagingSnapshotEngine
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def resolve_box_class_id(model_names: dict) -> int:
    """Resolve the integer class ID for 'box' by name lookup.
    Exits loudly if the class is missing — running without a resolved
    box class would silently detect the wrong objects."""
    for k, v in model_names.items():
        if v == "box":
            logging.info(f"Resolved 'box' class to id={k} from model.names")
            return k
    logging.error(
        f"FATAL: 'box' class not found in model.names={model_names}. "
        "Refusing to start -- running without a resolved box class would "
        "silently detect the wrong objects."
    )
    sys.exit(1)


def update_config_file(camera_id, points):
    # Rewrite config.py with the new coordinates
    config_path = "config.py"
    if not os.path.exists(config_path):
        return
    with open(config_path, "r") as f:
        content = f.read()

    prefix = "CAM1" if camera_id == CAM1_ID else "CAM2"
    entry_str = f'{prefix}_LINE_ENTRY = (sv.Point({points[0][0]}, {points[0][1]}), sv.Point({points[1][0]}, {points[1][1]}))'
    exit_str = f'{prefix}_LINE_EXIT = (sv.Point({points[2][0]}, {points[2][1]}), sv.Point({points[3][0]}, {points[3][1]}))'

    content = re.sub(rf'{prefix}_LINE_ENTRY\s*=\s*.*', entry_str, content)
    content = re.sub(rf'{prefix}_LINE_EXIT\s*=\s*.*', exit_str, content)
    
    with open(config_path, "w") as f:
        f.write(content)
    print(f"\n[INFO] {prefix} Coordinates dynamically saved to config.py!")

is_calibrating = False
calib_pts = []

import numpy as np

def apply_roi_mask(frame, roi_polygon):
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [np.array(roi_polygon, dtype=np.int32)], 255)
    masked = cv2.bitwise_and(frame, frame, mask=mask)
    return masked

def mouse_callback(event, x, y, flags, param):
    global is_calibrating, calib_pts
    if is_calibrating and event == cv2.EVENT_LBUTTONDOWN:
        if len(calib_pts) < 4:
            calib_pts.append((x, y))

def main():
    parser = argparse.ArgumentParser(description="Warehouse Edge Node")
    parser.add_argument("--camera", type=int, choices=[1, 2], required=True, 
                        help="Select camera stream to run (1 for Truck, 2 for Staging)")
    parser.add_argument("--headless", action="store_true",
                        help="Run without GUI windows (for headless/server environments)")
    parser.add_argument("--save-video", type=str, default=None, dest="save_video",
                        help="Path to save annotated output video (e.g. out.mp4)")
    parser.add_argument("--export-frame", type=str, default=None, dest="export_frame",
                        help="Path to actively dump single JPEG frames on loop")
    parser.add_argument("--source", type=str, default=None, dest="source",
                        help="Override default config video source with dynamic path")
    parser.add_argument("--entry-line", type=str, default=None, dest="entry_line",
                        help="Optional override: x1,y1,x2,y2 for entry tripwire")
    parser.add_argument("--exit-line", type=str, default=None, dest="exit_line",
                        help="Optional override: x1,y1,x2,y2 for exit tripwire")
    args = parser.parse_args()

    # Apply configuration for chosen camera
    if args.camera == 1:
        CAMERA_ID = CAM1_ID
        VIDEO_SOURCE = CAM1_VIDEO_SOURCE
        ENTRY_COORDS = CAM1_LINE_ENTRY
        EXIT_COORDS = CAM1_LINE_EXIT
        EVENT_TYPE = "TRUCK_EXIT_EVENT"
    else:
        CAMERA_ID = CAM2_ID
        VIDEO_SOURCE = CAM2_VIDEO_SOURCE
        ENTRY_COORDS = CAM2_LINE_ENTRY
        EXIT_COORDS = CAM2_LINE_EXIT
        EVENT_TYPE = "STAGING_ARRIVAL_EVENT"

    if args.source:
        VIDEO_SOURCE = args.source

    if args.entry_line:
        pts = list(map(int, args.entry_line.split(',')))
        ENTRY_COORDS = (sv.Point(pts[0], pts[1]), sv.Point(pts[2], pts[3]))
        
    if args.exit_line:
        pts = list(map(int, args.exit_line.split(',')))
        EXIT_COORDS = (sv.Point(pts[0], pts[1]), sv.Point(pts[2], pts[3]))

    print(f"Starting Edge Node for {CAMERA_ID}...")
    print(f"Video Source: {VIDEO_SOURCE}")
    print(f"Event Target: {EVENT_TYPE}")

    # ==================================
    # 1. Initialize YOLO and ByteTrack
    # ==================================
    model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "best.pt")
    model = YOLO(model_path)

    # Task 4: dynamic class resolution — defense in depth
    box_class_id = resolve_box_class_id(model.names)
    logging.info(f"Full model.names mapping: {model.names}")

    if args.camera == 1:
        tracker = sv.ByteTrack(
            track_activation_threshold=0.25,
            lost_track_buffer=300,
            minimum_matching_threshold=0.8,
            frame_rate=25,
        )
    else:
        tracker = sv.ByteTrack(
            track_activation_threshold=0.40,
            lost_track_buffer=60,
            minimum_matching_threshold=0.5,
            frame_rate=25,
        )

    # ==================================
    # 2. Initialize State Machine
    # ==================================
    if args.camera == 2:
        state_machine = StagingSnapshotEngine(
            roi_polygon=CAM2_STAGING_ROI,
            camera_id=CAMERA_ID,
            api_url=BACKEND_URL,
            target_event_type=EVENT_TYPE,
            video_source=VIDEO_SOURCE
        )
    else:
        state_machine = BoxStateMachine(
            entry_coords=ENTRY_COORDS,
            exit_coords=EXIT_COORDS,
            camera_id=CAMERA_ID,
            api_url=BACKEND_URL,
            target_event_type=EVENT_TYPE,
            video_source=VIDEO_SOURCE
        )

    # ==================================
    # 3. Visualization Annotators
    # ==================================
    box_annotator = sv.BoxAnnotator(thickness=2)
    label_annotator = sv.LabelAnnotator(text_scale=0.5)
    trace_annotator = sv.TraceAnnotator(thickness=2, trace_length=30)
    line_annotator = sv.LineZoneAnnotator(thickness=2, text_thickness=1, text_scale=0.5)

    # ==================================
    # 4. Processing Loop
    # ==================================
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    
    if not cap.isOpened():
        print(f"Error: Could not open {VIDEO_SOURCE}")
        sys.exit(1)

    window_name = f"Edge Pipeline - {CAMERA_ID}"
    if not args.headless:
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, mouse_callback)

    # Video writer for --save-video
    video_writer = None
    if args.save_video:
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_writer = cv2.VideoWriter(args.save_video, fourcc, fps, (w, h))
        print(f"[INFO] Saving annotated video to {args.save_video} ({w}x{h} @ {fps}fps)")

    global is_calibrating, calib_pts

    frame_idx = 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

    while True:
        if is_calibrating and not args.headless:
            calib_frame = frame.copy()
            cv2.putText(calib_frame, "CALIBRATION MODE: Click 4 points", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
            cv2.putText(calib_frame, "1&2 = Entry Line | 3&4 = Exit Line. Press 'c' to cancel.", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
            
            for i, pt in enumerate(calib_pts):
                cv2.circle(calib_frame, pt, 6, (0,0,255), -1)
                
            if len(calib_pts) >= 2:
                cv2.line(calib_frame, calib_pts[0], calib_pts[1], (0,255,0), 3)
            if len(calib_pts) == 4:
                cv2.line(calib_frame, calib_pts[2], calib_pts[3], (0,255,0), 3)
                
                # Apply new points to state machine
                state_machine.line_entry = sv.LineZone(start=sv.Point(*calib_pts[0]), end=sv.Point(*calib_pts[1]))
                state_machine.line_exit = sv.LineZone(start=sv.Point(*calib_pts[2]), end=sv.Point(*calib_pts[3]))
                
                update_config_file(CAMERA_ID, calib_pts)
                
                is_calibrating = False
                calib_pts.clear()
            
            cv2.imshow(window_name, calib_frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('c'):
                is_calibrating = False
                calib_pts.clear()
            
            continue


        ret, frame = cap.read()
        if not ret:
            print("Video source reached end or disconnected.")
            break
            
        # Optional: Save latest staging frame periodically
        if args.camera == 2:
            os.makedirs("data", exist_ok=True)
            cv2.imwrite(LATEST_STAGING_OUTPUT, frame)

        if args.camera == 1:
            results = model(frame, conf=0.50, iou=0.45, verbose=False)[0]
            detections = sv.Detections.from_ultralytics(results)
            detections = detections[detections.class_id == box_class_id]
            
            detections = tracker.update_with_detections(detections)
            confirmed_ids = state_machine.update(detections, frame_idx, fps)
            
            frame_idx += 1
            if confirmed_ids:
                state_machine.confirm_and_publish(confirmed_ids)

            annotated_frame = frame.copy()
            labels = []
            if detections.tracker_id is not None:
                for tracker_id in detections.tracker_id:
                    state_info = state_machine.states.get(tracker_id, {"state": "UNKNOWN"})
                    labels.append(f"#{tracker_id} {state_info['state']}")
            
            annotated_frame = trace_annotator.annotate(scene=annotated_frame, detections=detections)
            annotated_frame = box_annotator.annotate(scene=annotated_frame, detections=detections)
            annotated_frame = label_annotator.annotate(scene=annotated_frame, detections=detections, labels=labels)
            
            if state_machine.line_entry and state_machine.line_exit:
                annotated_frame = line_annotator.annotate(annotated_frame, line_counter=state_machine.line_entry)
                annotated_frame = line_annotator.annotate(annotated_frame, line_counter=state_machine.line_exit)

        else:
            video_t_sec = frame_idx / fps if fps else 0.0
            st_detections = state_machine.update(frame, video_t_sec, model, box_class_id)
            frame_idx += 1
            
            annotated_frame = frame.copy()
            cv2.polylines(annotated_frame, [np.array(CAM2_STAGING_ROI).astype(np.int32)], True, (255, 0, 0), 2)
            cv2.putText(annotated_frame, f"State: {state_machine.state} Timer: {state_machine.timer_val:.1f}s", 
                        (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            if st_detections is not None:
                annotated_frame = box_annotator.annotate(scene=annotated_frame, detections=st_detections)

        # Info bar
        cv2.putText(annotated_frame, f"Node: {CAMERA_ID} | Mode: {EVENT_TYPE}", 
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(annotated_frame, "Press 'c' to live-calibrate lines", 
                    (20, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                    
        # Save annotated frame to video if requested
        if video_writer is not None:
            video_writer.write(annotated_frame)
            
        # Export frame dynamically for web streams
        if args.export_frame:
            cv2.imwrite(args.export_frame, annotated_frame)

        # Show GUI window if not headless
        if not args.headless:
            cv2.imshow(window_name, annotated_frame)
        
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('c'):
                is_calibrating = True
                calib_pts.clear()

    if video_writer is not None:
        video_writer.release()
        print(f"[INFO] Annotated video saved.")
    cap.release()
    cv2.destroyAllWindows()
    
    state_machine.print_diagnostics()

if __name__ == "__main__":
    main()