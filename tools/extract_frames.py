import os
import cv2

def extract_frames(video_path, output_folder="my_warehouse_raw", sample_interval_sec=1.0):
    """
    Extracts frames from a warehouse camera video file every `sample_interval_sec` seconds.
    """
    if not os.path.exists(video_path):
        print(f"Error: Video file '{video_path}' not found.")
        return

    os.makedirs(output_folder, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    frame_interval = int(fps * sample_interval_sec)

    count = 0
    saved = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if count % frame_interval == 0:
            frame_filename = os.path.join(output_folder, f"frame_{saved:04d}.jpg")
            cv2.imwrite(frame_filename, frame)
            saved += 1
        count += 1

    cap.release()
    print(f"Successfully extracted {saved} frames to '{output_folder}/'")

if __name__ == "__main__":
    import sys
    video_file = sys.argv[1] if len(sys.argv) > 1 else "generate_demo.mp4"
    
    if len(sys.argv) > 2:
        out_folder = sys.argv[2]
    else:
        base_name = os.path.splitext(os.path.basename(video_file))[0].lower()
        out_folder = f"{base_name}_raw"

    extract_frames(video_file, output_folder=out_folder)