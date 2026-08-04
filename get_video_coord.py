import cv2

WINDOW_NAME = "Click twice to draw tripwire | 'r' to reset | any other key to quit"

points = []
clean_frame = None  # untouched copy of the first frame, used to redraw on reset


def get_clicks(event, x, y, flags, param):
    if event != cv2.EVENT_LBUTTONDOWN:
        return

    # Once two points are set, ignore further clicks instead of silently
    # appending to `points` (which used to corrupt the printed line, since
    # only points[0]/points[1] were read but the list kept growing).
    if len(points) >= 2:
        print("Already have 2 points. Press 'r' to reset, or any other key to quit.")
        return

    points.append((x, y))
    cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
    cv2.imshow(WINDOW_NAME, frame)

    if len(points) == 2:
        cv2.line(frame, points[0], points[1], (0, 255, 0), 2)
        cv2.imshow(WINDOW_NAME, frame)
        print("\nCopy and paste these exact lines into demo_wms.py:")
        print("-" * 50)
        print(f"LINE_START = sv.Point({points[0][0]}, {points[0][1]})")
        print(f"LINE_END   = sv.Point({points[1][0]}, {points[1][1]})")
        print("-" * 50)
        print("Press 'r' to redo the line, or any other key to close the window.")


# Load the first frame of the video
cap = cv2.VideoCapture("generate_demo.mp4")
ret, frame = cap.read()
cap.release()

if ret:
    clean_frame = frame.copy()
    print("Window opened! Click two points to draw your line.")
    cv2.imshow(WINDOW_NAME, frame)
    cv2.setMouseCallback(WINDOW_NAME, get_clicks)

    while True:
        key = cv2.waitKey(0) & 0xFF
        if key == ord("r"):
            # Reset: clear points and redraw the untouched frame.
            points.clear()
            frame = clean_frame.copy()
            cv2.imshow(WINDOW_NAME, frame)
            print("Reset. Click two new points.")
            continue
        break

    cv2.destroyAllWindows()
else:
    print("Error: Could not read generate_demo.mp4. Check the file path.")