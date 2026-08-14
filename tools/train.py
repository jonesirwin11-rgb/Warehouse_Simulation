import torch
from ultralytics import YOLO

# Enable TF32 precision for Ada Lovelace GPUs (RTX 4060)
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

def main():
    # Initialize the base YOLOv8s model
    model = YOLO("yolov8s.pt")

    # Train the model with all custom parameters
    results = model.train(
        data="dataset/data.yaml",
        epochs=150,
        imgsz=640,
        batch=-1,            # Autobatch: max size that fits ~60% VRAM
        amp=True,            # Mixed precision (FP16)
        patience=30,         # Early stopping patience
        cache=True,          # Cache images in RAM for faster iteration
        workers=4,           # Dataloader workers
        cos_lr=True,         # Cosine learning rate scheduler
        warmup_epochs=5,     # Warmup period
        mosaic=1.0,          # Augmentation: Mosaic
        copy_paste=0.15,     # Augmentation: Copy-paste instances
        mixup=0.1,           # Augmentation: MixUp
        scale=0.6,           # Scale jitter (+/- 60%)
        hsv_v=0.5,           # HSV-Value brightness jitter
        degrees=5.0,         # Rotation jitter (+/- 5 degrees)
        project="runs/box_demo",
        name="v1",
        device=0             # Use GPU 0 (RTX 4060)
    )

if __name__ == "__main__":
    main()