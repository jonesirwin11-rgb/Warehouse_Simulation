from ultralytics import YOLO

# Load your currently trained weights
model = YOLO("best.pt")

# Point this to the folder containing your 5000 extracted dock frames
image_folder = "D:\\Warehouse_Management\\front_view_frames.zip\\my_warehouse_raw"

# Run batch prediction and save the labels
results = model.predict(
    source=image_folder,
    conf=0.6,             # Only save boxes it is highly confident about
    save_txt=True,        # Generates the YOLO .txt files automatically
    save_conf=True,       # Saves the confidence score in the text file
    project="auto_labels", 
    name="dock_view_pass1"
)

print("Auto-annotation complete! Check the auto_labels/dock_view_pass1/labels folder.")