# Vision AI Warehouse Management System (WMS) 📦

An automated, event-driven Vision AI pipeline that analyzes static warehouse dock CCTV footage to track inventory movement, count boxes, and calculate the turnaround time (TAT) of loading and unloading operations.

This Proof of Concept (POC) acts as a vision-based digital twin module for Industry 4.0 logistics. It mimics a distributed architecture where edge AI cameras process footage locally and stream lightweight payload events to a central inventory backend.

## 📁 Project Structure

* **`backend/`**: Contains the central Flask server (`app.py`) with an SQLite database (`inventory_state.db`) acting as the inventory source-of-truth.
* **`dashboard/`**: Contains a web-based GUI for end-to-end processing demonstrations (uploading videos, visually drawing tripwires). Features a modern light theme and Chart.js trend analysis.
* **`edge/`**: Contains the simulated edge node (`edge_node.py` and `box_state_machine.py`) that captures video, runs YOLO + tracker, and pushes events to the backend.
* **`models/`**: House the YOLOv8 weights (e.g., `best.pt`).
* **`tests/`**: Unit tests for backend logic and edge tracking state machines.
* **`tools/`**: Utilities for dataset management, model training, and ROI annotation.
* **`videos/`**: Directory for test video footage.
* **`architecture_overview.md`**: High-level system architecture and integration details.

## 🚀 Key Features

* **Event-Driven Edge Architecture:** Video processing happens at the "edge". Nodes only send JSON HTTP payloads (like `TRUCK_EXIT_EVENT`) to the central backend, protecting network bandwidth.
* **Custom Object Tracking:** Uses a fine-tuned YOLOv8 model for cardboard cartons, paired with conditionally tuned ByteTrack parameters (handling high occlusion for truck views, and low confidence thresholds for distant staging views).
* **State Machine Hard-Lock & Static Snapshot Engine:** Implements custom tracking logic to permanently lock box IDs once they cross a tripwire. Uses Settle-and-Snapshot for staging areas to reliably count stationary boxes.
* **Modern Web Dashboard:** A beautiful, responsive light-themed UI to upload videos, point-and-click to calibrate tripwires, run the tracking pipeline in the background. Features real-time trend analysis using Chart.js to visualize throughput and download session TAT reports.
* **Browser Transcode Compliance:** Automatic backend pipeline to force `imageio_ffmpeg` conversion ensuring annotated results play smoothly on the dashboard.

## ⚙️ Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/jonesirwin11-rgb/Warehouse_Simulation.git
   cd Warehouse_Simulation
   ```

2. **Create the Conda environment using the provided configuration:**
   This project uses a standard `environment.yml` to guarantee Python 3.10 and dependency compatibility.

   *Option A (Recommended): Create globally*
   ```bash
   conda env create -f environment.yml
   conda activate warehouse-vision
   ```

   *Option B: Create locally inside the project folder*
   ```bash
   conda env create -f environment.yml --prefix .\warehouse_env
   conda activate .\warehouse_env
   ```

   *Alternatively, using pip:*
   ```bash
   pip install -r requirements.txt
   ```

*Note: The YOLOv8 model weights should be placed inside the `models/` directory (e.g., `models/best.pt`). Video footage should be placed in `videos/`.*

## 🖥️ Usage Guide

There are three ways to use this POC.

### 1. Web Dashboard (Recommended for demos)
The dashboard provides a visual interface to try out the tracking logic.
```bash
python backend/app.py
```
* Open `http://localhost:5000` in your browser.
* Upload a video from the `videos/` folder.
* Click to draw the entry/exit line and run the pipeline.
* Visualize the trend analysis with operational metrics.

### 2. Distributed Architecture (Backend + Edge Nodes)
Simulate a real-world warehouse by turning on the backend server and running camera nodes.

**Start the Backend:**
```bash
python backend/app.py
```

**Start the Edge Nodes:** (In separate terminals)
```bash
# Camera 1: Truck View
python edge/edge_node.py --camera 1

# Camera 2: Staging Area View
python edge/edge_node.py --camera 2
```
*Press `c` on the camera feed window to live-calibrate the tripwire.*

### 3. Development and Testing
You can run the included test suite to validate the system logic:
```bash
pytest tests/
```

## 📊 Outputs & Deliverables
* **`wms_annotated_output.mp4`**: Rendered tracker video with bounding boxes and HUD stats.
* **`wms_session_report.csv`**: Automated TAT analytics of loading/unloading sessions.
* **SQLite Persistence**: Cross-session persistent inventory state tracking via `inventory_state.db`.

## 📝 License
This project is created as an evaluation Proof of Concept (POC).