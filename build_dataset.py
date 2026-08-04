# build_dataset.py
import os, shutil, glob, random, yaml

random.seed(42)  # reproducible sampling

# Quotas for training split
QUOTA = {
    "ds1": 2000,
    "ds2": 1200,
    "ds3": 500,
}

# Create output directories
for split in ["train", "val", "test"]:
    os.makedirs(f"dataset/images/{split}", exist_ok=True)
    os.makedirs(f"dataset/labels/{split}", exist_ok=True)

def copy_split(src_name, split, files, prefix):
    copied = 0
    for img_path_str in files:
        # Normalize slashes for Windows compatibility
        img_path_str = img_path_str.replace("\\", "/")
        stem = os.path.splitext(os.path.basename(img_path_str))[0]
        ext  = os.path.splitext(img_path_str)[1]
        
        # Replace /images/ with /labels/ and set extension to .txt
        lbl_path_str = img_path_str.replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt"
        
        if not os.path.exists(lbl_path_str):
            continue  # skip if label file doesn't exist
            
        new_stem = f"{prefix}_{stem}"
        shutil.copy(img_path_str, f"dataset/images/{split}/{new_stem}{ext}")
        shutil.copy(lbl_path_str, f"dataset/labels/{split}/{new_stem}.txt")
        copied += 1
    return copied

for src, quota in QUOTA.items():
    def get_images(src_dir, split_names):
        files = []
        for s in split_names:
            files.extend(glob.glob(f"{src_dir}/{s}/images/*"))
        return files

    all_train = get_images(src, ["train"])
    random.shuffle(all_train)
    train_files = all_train[:quota]
    
    all_val = get_images(src, ["valid", "val"])
    random.shuffle(all_val)
    
    val_quota = max(50, int(quota * 0.15))
    test_files = all_val[val_quota:val_quota + 50]
    val_files  = all_val[:val_quota]
    
    c_train = copy_split(src, "train", train_files, src)
    c_val   = copy_split(src, "val",   val_files,   src)
    c_test  = copy_split(src, "test",  test_files,  src)
    print(f"[{src}] Copied -> Train: {c_train}, Val: {c_val}, Test: {c_test}")

# Print summary counts
for split in ["train", "val", "test"]:
    n = len(glob.glob(f"dataset/images/{split}/*"))
    print(f"Final dataset split '{split}': {n} images")

# Generate final YAML configuration
with open("dataset/data.yaml", "w") as f:
    yaml.dump({
        "path": os.path.abspath("dataset"),
        "train": "images/train",
        "val":   "images/val",
        "test":  "images/test",
        "nc": 1,
        "names": ["box"],
    }, f)

print("Dataset successfully built!")