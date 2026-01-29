import yaml
import json
import boto3
import sys
from pathlib import Path
from botocore.exceptions import ClientError

# --- CONFIGURATION ---
BUCKET_NAME = "resume-recommender-mlops-storage"
PROJECT_ROOT = Path(__file__).resolve().parent

def get_s3_key(dvc_hash):
    """Converts a DVC MD5 hash to an S3 key."""
    return f"files/md5/{dvc_hash[:2]}/{dvc_hash[2:]}"

def load_dvc_lock():
    """Parses dvc.lock to find all pipeline outputs (raw, processed, vectors)."""
    lock_path = PROJECT_ROOT / "dvc.lock"
    if not lock_path.exists():
        print("⚠️  dvc.lock not found. Skipping pipeline verification.")
        return []
    
    with open(lock_path) as f:
        lock_data = yaml.safe_load(f)
    
    artifacts = []
    if 'stages' in lock_data:
        for stage_name, stage_data in lock_data['stages'].items():
            for out in stage_data.get('outs', []):
                artifacts.append({
                    "name": f"Stage: {stage_name} -> {out['path']}",
                    "hash": out['md5'],
                    "path": out['path']
                })
    return artifacts

def load_standalone_dvc_files():
    """Finds all .dvc files (like models/all-mpnet-base-v2.dvc)."""
    artifacts = []
    for dvc_file in PROJECT_ROOT.rglob("*.dvc"):
        # CRITICAL FIX: Skip the .dvc directory itself
        if not dvc_file.is_file():
            continue

        # Skip files inside the hidden .dvc folder
        if ".dvc" in str(dvc_file.parent): continue
        
        with open(dvc_file) as f:
            data = yaml.safe_load(f)
        
        # Standalone .dvc files usually have 'outs' list
        for out in data.get('outs', []):
            artifacts.append({
                "name": f"Artifact: {dvc_file.stem}",
                "hash": out['md5'],
                "path": out['path']
            })
    return artifacts

def check_s3_existence(s3_client, dvc_hash, description):
    """
    Checks if a file (or directory of files) exists on S3.
    Returns (success_count, fail_count, total_size_mb)
    """
    is_dir = dvc_hash.endswith(".dir")
    files_to_check = []

    if is_dir:
        # Load directory listing from local cache
        dir_cache_path = PROJECT_ROOT / ".dvc/cache/files/md5" / dvc_hash[:2] / dvc_hash[2:]
        if not dir_cache_path.exists():
            print(f"   ⚠️  Local cache missing for directory map: {dvc_hash}. Cannot verify contents.")
            return 0, 1, 0
        
        with open(dir_cache_path) as f:
            dir_content = json.load(f)
            # Check up to 5 random files in the directory to save time, or all if small
            files_to_check = [f['md5'] for f in dir_content]
    else:
        files_to_check = [dvc_hash]

    success = 0
    fail = 0
    total_size = 0

    # Batch check (or singular)
    for file_hash in files_to_check:
        key = get_s3_key(file_hash)
        try:
            obj = s3_client.head_object(Bucket=BUCKET_NAME, Key=key)
            success += 1
            total_size += obj['ContentLength']
        except ClientError:
            print(f"      ❌ Missing Object: {key} (Hash: {file_hash})")
            fail += 1

    # Visual feedback
    if fail == 0:
        print(f"   ✅ {description} [Checked {len(files_to_check)} files]")
    else:
        print(f"   ❌ {description} [Missing {fail}/{len(files_to_check)} files]")

    return success, fail, total_size

def main():
    print(f"🕵️  Starting Comprehensive S3 Audit for bucket: {BUCKET_NAME}\n")
    s3 = boto3.client('s3')

    # 1. Gather all targets
    pipeline_artifacts = load_dvc_lock()
    standalone_artifacts = load_standalone_dvc_files()
    all_items = pipeline_artifacts + standalone_artifacts

    if not all_items:
        print("No DVC tracked files found.")
        return

    total_success = 0
    total_fail = 0
    total_bytes = 0

    # 2. Verify each
    for item in all_items:
        s, f, size = check_s3_existence(s3, item['hash'], item['name'])
        total_success += s
        total_fail += f
        total_bytes += size

    # 3. Final Report
    print("-" * 50)
    print(f"📊 Audit Complete.")
    print(f"   Files Verified: {total_success}")
    print(f"   Files Missing:  {total_fail}")
    print(f"   Total Cloud Size: {total_bytes / (1024*1024):.2f} MB")
    
    if total_fail == 0:
        print("\n🎉 SYSTEM INTEGRITY: 100%. Your Infrastructure is Resilient.")
    else:
        print("\n🔥 SYSTEM CRITICAL: Data is missing from S3. Do not deploy.")

if __name__ == "__main__":
    main()