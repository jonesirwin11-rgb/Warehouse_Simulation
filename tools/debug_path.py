# debug_paths.py
import os, glob

print("Checking downloaded source directories:")
for ds in ["ds1", "ds2", "ds3"]:
    if os.path.exists(ds):
        pattern1 = f"{ds}/train/images/*"
        pattern2 = f"{ds}/images/train/*"
        pattern3 = f"{ds}/train/*"
        
        count1 = len(glob.glob(pattern1))
        count2 = len(glob.glob(pattern2))
        count3 = len(glob.glob(pattern3))
        
        print(f"[{ds}]")
        print(f"  {ds}/train/images/* -> Found {count1} files")
        print(f"  {ds}/images/train/* -> Found {count2} files")
        print(f"  {ds}/train/*        -> Found {count3} files")
    else:
        print(f"[{ds}] Folder does NOT exist. (Did download_datasets.py finish successfully?)")