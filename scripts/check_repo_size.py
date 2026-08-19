#!/usr/bin/env python3
"""
Repository Size Audit Script for Guardian AI
Enforces repository storage budget (< 9 MB).
"""
import os
import sys

# Budget constants (in Megabytes)
PASS_THRESHOLD_MB = 7.0
WARN_THRESHOLD_MB = 8.5
FAIL_THRESHOLD_MB = 9.0

# Folders and file patterns to ignore during repo size check (simulating clean git tree)
IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    "data_raw",
    "data/raw",
    ".gemini"
}

IGNORED_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".xlsx",
    ".log"
}

def get_repo_size(root_dir="."):
    total_bytes = 0
    file_list = []

    for root, dirs, files in os.walk(root_dir):
        # Prune ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".venv")]
        
        # Check relative path
        rel_root = os.path.relpath(root, root_dir)
        if any(ignored in rel_root.split(os.sep) for ignored in IGNORED_DIRS):
            continue

        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in IGNORED_EXTENSIONS:
                continue
            
            filepath = os.path.join(root, f)
            try:
                size = os.path.getsize(filepath)
                total_bytes += size
                file_list.append((filepath, size))
            except OSError:
                pass

    return total_bytes, file_list

def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    total_bytes, file_list = get_repo_size(root)
    total_mb = total_bytes / (1024 * 1024)

    print("=" * 60)
    print(" GUARDIAN AI — REPOSITORY SIZE AUDIT")
    print("=" * 60)
    print(f"Target Root:       {root}")
    print(f"Total Files:       {len(file_list)}")
    print(f"Total Size:        {total_mb:.3f} MB ({total_bytes:,} bytes)")
    print(f"Hard Limit:        {FAIL_THRESHOLD_MB:.1f} MB")
    print(f"Target Goal:       < {PASS_THRESHOLD_MB:.1f} MB")
    print("-" * 60)

    # Sort largest 10 files
    file_list.sort(key=lambda x: x[1], reverse=True)
    if file_list:
        print("Top 10 Largest Tracked Files:")
        for fp, sz in file_list[:10]:
            rel = os.path.relpath(fp, root)
            print(f"  {sz / 1024:8.1f} KB  {rel}")
    print("-" * 60)

    if total_mb < PASS_THRESHOLD_MB:
        print(f"STATUS: [PASS] Repository size ({total_mb:.2f} MB) is well within the safe budget (< {PASS_THRESHOLD_MB} MB).")
        return 0
    elif total_mb < WARN_THRESHOLD_MB:
        print(f"STATUS: [WARNING] Repository size ({total_mb:.2f} MB) is near budget limit (< {WARN_THRESHOLD_MB} MB).")
        return 0
    elif total_mb < FAIL_THRESHOLD_MB:
        print(f"STATUS: [FAIL] Repository size ({total_mb:.2f} MB) exceeds warning threshold!")
        return 1
    else:
        print(f"STATUS: [HARD FAIL] Repository size ({total_mb:.2f} MB) exceeds hard limit of {FAIL_THRESHOLD_MB} MB!")
        return 2

if __name__ == "__main__":
    sys.exit(main())
