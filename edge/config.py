import supervision as sv

# ==========================================
# SYSTEM CONFIGURATION
# ==========================================

# Backend Settings
BACKEND_URL = "http://127.0.0.1:5000/api/events"
INVENTORY_URL = "http://127.0.0.1:5000/api/inventory"
AUDIT_URL = "http://127.0.0.1:5000/api/audit"

# ==========================================
# CAMERA 1: TRUCK VIEW
# ==========================================
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAM1_ID = "CAM01"
CAM1_VIDEO_SOURCE = os.path.join(BASE_DIR, "videos", "dock_video.mp4") # Update to actual paths or RTSP urls

# Calibration coordinates (Tight tripwire - 100px apart to instantly confirm lifts)
CAM1_LINE_ENTRY = (sv.Point(0, 650), sv.Point(1920, 650))
CAM1_LINE_EXIT = (sv.Point(0, 750), sv.Point(1920, 750))

# ==========================================
# CAMERA 2: STAGING VIEW
# ==========================================
CAM2_ID = "CAM02"
CAM2_VIDEO_SOURCE = os.path.join(BASE_DIR, "videos", "staging_view.mp4") # Update to actual paths or RTSP urls

# Calibration coordinates (Mathematically perfectly span the entire X-axis of the warehouse)
CAM2_LINE_ENTRY = (sv.Point(0, 300), sv.Point(1920, 300))
CAM2_LINE_EXIT = (sv.Point(0, 700), sv.Point(1920, 700))

# ==========================================
# AUDIT CONFIGURATION
# ==========================================
LATEST_STAGING_OUTPUT = "data/latest_staging.jpg"
AUDIT_THRESHOLD = 3
KNOWN_CARTON_DIMENSIONS = {"width": 0.5, "height": 0.4, "depth": 3} # Meters or arbitrary units
