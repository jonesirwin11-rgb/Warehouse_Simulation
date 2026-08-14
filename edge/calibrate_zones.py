import cv2
import argparse
import sys
import copy

def main():
    parser = argparse.ArgumentParser(description="Calibrate Zones for Camera by finding Line Entry and Exit coords.")
    parser.add_argument("--video", type=str, required=True, help="Path to the video file")
    args = parser.parse_args()
    
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Error: Cannot open {args.video}")
        sys.exit(1)
        
    ret, frame = cap.read()
    if not ret:
        print("Error: Could not read a frame from the video.")
        sys.exit(1)
        
    cap.release()
    
    # Global variables for drawing
    lines = []
    current_line = []
    frame_copy = frame.copy()
    
    def click_event(event, x, y, flags, param):
        nonlocal current_line, frame_copy
        if event == cv2.EVENT_LBUTTONDOWN:
            current_line.append((x, y))
            cv2.circle(frame_copy, (x, y), 5, (0, 0, 255), -1)
            
            if len(current_line) == 2:
                cv2.line(frame_copy, current_line[0], current_line[1], (0, 255, 0), 2)
                lines.append(current_line)
                name = "LINE_ENTRY" if len(lines) == 1 else "LINE_EXIT" if len(lines) == 2 else f"LINE_{len(lines)}"
                print(f"{name} = sv.Point({current_line[0][0]}, {current_line[0][1]}), sv.Point({current_line[1][0]}, {current_line[1][1]})")
                current_line = []
            
            cv2.imshow("Zone Calibration - Click to draw lines (Press 'q' to quit, 'c' to clear)", frame_copy)

    print("Instructions:")
    print("1. Click at the start and end of a line.")
    print("2. The first line you draw will be considered LINE_ENTRY.")
    print("3. The second line you draw will be considered LINE_EXIT.")
    print("4. Press 'c' to clear and retry.")
    print("5. Press 'q' or 'ESC' to quit, or close the window.")
    
    cv2.imshow("Zone Calibration - Click to draw lines (Press 'q' to quit, 'c' to clear)", frame_copy)
    cv2.setMouseCallback("Zone Calibration - Click to draw lines (Press 'q' to quit, 'c' to clear)", click_event)
    
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break
        elif key == ord('c'):
            frame_copy = frame.copy()
            lines = []
            current_line = []
            cv2.imshow("Zone Calibration - Click to draw lines (Press 'q' to quit, 'c' to clear)", frame_copy)
            
    cv2.destroyAllWindows()
    
    print("\nCalibration Complete. You can use the printed coordinates in your config.py.")

if __name__ == "__main__":
    main()
