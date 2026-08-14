# download_datasets.py
import os
from dotenv import load_dotenv
from roboflow import Roboflow

# Load environment variables from the .env file
load_dotenv()

# Securely fetch the API key
API_KEY = os.getenv("ROBOFLOW_API_KEY")
rf = Roboflow(api_key=API_KEY)

# Source 1: ~8,355 images
rf.workspace("instance-segmentation-zza7a") \
  .project("cardboard-box-detection-rjrm9") \
  .version(1).download("yolov8", location="ds1")

# Source 2: ~4,304 images
rf.workspace("carboard-box") \
  .project("carboard-box") \
  .version(4).download("yolov8", location="ds2")

# Source 3: ~2,405 images
rf.workspace("harshuu") \
  .project("cardboard-box-detection-kh0qu") \
  .version(1).download("yolov8", location="ds3")