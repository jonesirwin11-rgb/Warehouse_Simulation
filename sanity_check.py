# sanity_check.py
import glob, os

train_imgs   = set(os.path.splitext(os.path.basename(f))[0] for f in glob.glob("dataset/images/train/*"))
train_labels = set(os.path.splitext(os.path.basename(f))[0] for f in glob.glob("dataset/labels/train/*.txt"))

print(f"Orphaned Images (No Label): {len(train_imgs - train_labels)}")
print(f"Orphaned Labels (No Image): {len(train_labels - train_imgs)}")