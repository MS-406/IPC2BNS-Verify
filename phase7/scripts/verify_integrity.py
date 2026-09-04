"""
verify_integrity.py — Pre/Post Phase 7 Integrity Checker

Verifies that all original project files are unmodified by comparing
SHA-256 checksums against the pre-Phase7 manifest.

Usage:
    python phase7/scripts/verify_integrity.py
"""

import hashlib
import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MANIFEST_PATH = os.path.join(PROJECT_ROOT, "phase7", "original_artifact_manifest.json")


def verify():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    
    all_ok = True
    print("Verifying original artifact integrity...\n")
    
    for key, entry in manifest["files"].items():
        rel_path = entry["path"]
        abs_path = os.path.join(PROJECT_ROOT, rel_path)
        expected = entry["sha256"]
        
        if not os.path.exists(abs_path):
            print(f"  MISSING  : {key} ({rel_path})")
            all_ok = False
            continue
        
        h = hashlib.sha256()
        with open(abs_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        actual = h.hexdigest()
        
        if actual == expected:
            print(f"  OK       : {key}")
        else:
            print(f"  CHANGED! : {key}")
            print(f"    Expected: {expected}")
            print(f"    Actual:   {actual}")
            all_ok = False
    
    print()
    if all_ok:
        print("INTEGRITY CHECK: PASSED — All original files unmodified.")
    else:
        print("INTEGRITY CHECK: FAILED — Some original files have changed!")
        sys.exit(1)
    
    return all_ok


if __name__ == "__main__":
    verify()
