# Vision AI Warehouse Management System (WMS) 📦

An automated Vision AI pipeline that analyzes static warehouse dock CCTV footage to track inventory movement, count boxes, and calculate the turnaround time (TAT) of loading and unloading operations. 

This Proof of Concept (POC) acts as a vision-based digital twin module for Industry 4.0 logistics, minimizing manual counting errors and providing automated operational visibility.

---

## 🚀 Key Features

*   **Custom Object Detection:** Utilizes a fine-tuned YOLOv8s model trained specifically on industrial cardboard cartons (e.g., Bajaj cartons) to operate accurately in high-contrast dock lighting.
*   **Advanced Occlusion Handling:** Implements ByteTrack optimized for dense logistics environments. The tracker maintains object memory (`lost_track_buffer=60`) to preserve box IDs even when workers temporarily block the camera's view.
*   **Directional Counting:** Uses a precise virtual tripwire (`sv.LineZone`) to accurately differentiate between loading (In) and unloading (Out) operations.
*   **Multi-Session TAT Analytics:** Dynamically segments continuous video footage into distinct loading/unloading sessions based on inactivity thresholds, calculating the exact Turnaround Time for each burst of activity.
*   **Automated CSV Reporting:** Automatically generates a `wms_session_report.csv` detailing session IDs, directions, timestamps, and total counts for seamless integration into broader WMS/TMS dashboards.

---

## 🛠️ Technical Stack

*   **Computer Vision:** OpenCV (`cv2`)
*   **Deep Learning / Object Detection:** Ultralytics (YOLOv8)
*   **Object Tracking & Analytics:** Supervision (`ByteTrack`, `LineZone`)
*   **Language:** Python 3.x

---

## ⚙️ Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/your-username/your-repository-name.git](https://github.com/your-username/your-repository-name.git)
   cd your-repository-name
Create and activate a virtual environment (Recommended):

Bash
python -m venv warehouse_env
# On Windows:
warehouse_env\Scripts\activate
# On WSL/Linux:
source warehouse_env/bin/activate
Install the required dependencies:

Bash
pip install -r requirements.txt
Note: The proprietary dataset used to train the YOLOv8 model is kept private and is not included in this repository. However, the custom trained weights (best.pt) are provided to test the pipeline.

🖥️ Usage Guide
1. Configure the Virtual Tripwire
Because camera angles vary, you must define the X/Y pixel coordinates of the virtual tripwire for your specific video.

Update VIDEO_PATH in the helper script to point to your test video.

Run the coordinate helper:

Bash
python get_coords.py
Click twice on the video frame to draw a vertical line representing the dock threshold.

Copy the outputted sv.Point coordinates and paste them into LINE_START and LINE_END inside demo_wms.py.

2. Run the Analytics Pipeline
Run the main pipeline to process the video, track the cartons, and calculate the TAT.

Bash
python demo_wms.py
3. Generate Synthetic Test Data (Optional)
If you do not have CCTV footage available, you can generate a synthetic sliding-box video to test the tracker and tripwire logic programmatically:

Bash
python make_synthetic_video.py
📊 Outputs & Deliverables
Running the main pipeline will generate two primary outputs:

wms_annotated_output.mp4: A rendered video file featuring bounding boxes, unique tracking IDs, the virtual tripwire, and a live Heads-Up Display (HUD) showing current counts and session TAT. (Default codec is H.264/avc1 for high compatibility).

wms_session_report.csv: A structured data report summarizing all detected logistics sessions, formatted for easy stakeholder review.

📝 License
This project is created as an evaluation Proof of Concept (POC).
