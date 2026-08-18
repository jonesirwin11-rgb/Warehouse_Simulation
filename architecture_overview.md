# Warehouse Management System (WMS) - System Architecture

This document maps out the comprehensive end-to-end architecture of the automated Warehouse Management System pipeline. The overarching goal of the system is real-time inventory monitoring and auditing utilizing edge AI visual nodes and a centralized Flask hub.

## 1. High-Level Architecture
The system consists of three distinct tiers:
1. **Edge Vision Tier (`edge/`)**: Lightweight video ingestion and AI bounding tracking nodes. Depending on the scenario (moving vs stationary), it filters YOLO output over time and pushes events.
2. **Central Backend API (`backend/`)**: A Flask server bridging events from multiple edge nodes into a unified SQLite state mapping, exposing inventory metrics globally.
3. **Web Dashboard (`dashboard/`)**: The operator GUI providing visualizations, real-time metrics, event timelines, and calibration inputs.

---

## 2. Code Breakdown by File

### 🔴 Edge Vision Pipeline (`edge/`)

**`edge/edge_node.py`**
* **Responsibility**: The core entrypoint for video analysis natively running Ultralytics YOLOv8. It loops over video frames (or RTSP streams), extracts bounding boxes, and orchestrates the tracking mechanism before annotating the results to localized MP4 records.
* **Current Implementation**:
  - Contains routing logic for two completely distinct camera behaviors. 
  - **Camera 1 (Truck Exit)**: Instantiates `sv.ByteTrack` to continuously match YOLO bounding boxes across frames.
  - **Camera 2 (Staging Arrival)**: Bypasses ByteTracker altogether. Hands the raw visual frames exclusively to the static snapshot engine to watch for motion.

**`edge/box_state_machine.py`**
* **Responsibility**: Provides the State Machine layers governing how bounding boxes convert into `EVENTS`.
* **Current Implementation**:
  - **`BoxStateMachine`**: Designed for moving objects (Truck Exit). Evaluates tracker age, minimum pixel displacement, and cross-pollination against an `ENTRY` and `EXIT` vector line. Triggers `TRUCK_EXIT_EVENT`.
  - **`StagingSnapshotEngine`**: Brand new implementation mapped for dense static staging palettes. Because YOLO merges dense boxes inconsistently over time, this uses OpenCV (`cv2.absdiff`) to measure pixel noise in the isolated ROI. Once 3 seconds of perfect stillness occurs (`SETTLED`), it triggers one extremely strict YOLO pass (`conf=0.10, iou=0.82`) calculating the final box load at once, skipping accumulation entirely. Triggers `STAGING_ARRIVAL_EVENT`.
  - Helper functions for event API dispatching.

**`edge/config.py`**
* **Responsibility**: Global constants storage.
* **Current Implementation**: Retains coordinates for Camera 1 entry/exit tripwires, Camera 2 `CAM2_STAGING_ROI` bounds (tightened entirely around the focal forklift zone), backend API routes, and 3D palette configuration (`KNOWN_CARTON_DIMENSIONS`).

### 🔵 Central Backend Hub (`backend/`)

**`backend/app.py`**
* **Responsibility**: The central persistence layer and web host. 
* **Current Implementation**:
  - Initializes `inventory_state.db` holding the ongoing tally of pallets, keeping state sticky across system reboots.
  - Exposes `/api/events` allowing `edge_node.py` to POST JSON quantities. Contains explicit unique-ID checks dropping duplicate tracking attempts.
  - Exposes an `/api/upload` endpoint allowing the Web UI to push isolated MP4 footages mimicking live stream behaviors. This endpoint boots a daemon thread, executes `edge_node.py`, and crucially leverages `ffmpeg` (transcoding to `libx264` + `yuv420p`) enforcing that processed videos run cleanly inside standard browser players.

**`backend/audit.py`**
* **Responsibility**: An advisory backup-layer sanity checker.
* **Current Implementation**: `StaticStackAudit` actively retrieves the last physical JPEG frame processed by the edge node. It takes a raw localized count and scales it by the depth configuration (e.g., 2 boxes deep) to flag explicit discrepancies between the moving edge metrics and the assumed physical structure. Generates `PASS` or `WARNING` tags logically sent back to Web UI.

### 🟢 Web UI Dashboard (`dashboard/`)

**`dashboard/templates/index.html` & `dashboard/static/app.js`**
* **Responsibility**: The interface allowing the user to read system status and execute manual inputs.
* **Current Implementation**:
  - **Live Inventory polling**: Pings `/api/inventory` repeatedly to map the `staged_boxes` state to dashboard widgets.
  - **Live Calibration**: Interactive HTML5 Canvas mapped atop the video uploads allows users to redraw Entry and Exit line arrays, bridging seamlessly back into `config.py` modifications cleanly syncing the AI layout to the literal UI inputs.
  - **Event Logs & System Resetting**: Full visibility into system states plus a deep purge utility breaking Python file-locks for debugging continuity.
  - Uses modern gradient glassmorphism UI.

---

## 3. Summary of Currently Applied Integrations

1. **Resolution of Duplicate Overcounts on Static Targets**: Abandoned generic IoU overlap matching for Camera 2 locally, switching the entire subsystem to **Settle-And-Snapshot**, ensuring one solitary clean extraction maps exactly what was left by the worker over hundreds of unstable tracking frames.
2. **Undercount Safety for Moving Targets**: Added minimum tracker displacements and loosened exit-confirmation logic specifically over the Truck Line Camera mapping so stacked moving objects reliably hit their expected output mappings dynamically. 
3. **Database Integrity**: Inserted strict SQLite mapping preventing frontend crashes or node desyncs from clearing the physical box tally mid-shift.
4. **Browser Transcode Compliance**: Integrated dynamic `imageio_ffmpeg` mapping forcing edge nodes' OpenCV visual outputs natively back into `yuv420p` compatible MP4s.
