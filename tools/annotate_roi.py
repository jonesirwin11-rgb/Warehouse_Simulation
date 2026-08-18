import cv2

points = []
def on_click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))
        print(f"Point added: ({x}, {y})")

def annotate(video_path, frame_number=0):
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError("Could not read frame")
    cv2.namedWindow("Click ROI points, press 'q' when done")
    cv2.setMouseCallback("Click ROI points, press 'q' when done", on_click)
    while True:
        disp = frame.copy()
        for p in points:
            cv2.circle(disp, p, 4, (0, 255, 0), -1)
        if len(points) >= 2:
            cv2.polylines(disp, [__import__('numpy').array(points)], False, (0, 255, 0), 2)
        cv2.imshow("Click ROI points, press 'q' when done", disp)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cv2.destroyAllWindows()
    print("Final polygon:", points)
    return points

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        annotate(sys.argv[1])
    else:
        print("Usage: python annotate_roi.py <video_path>")
