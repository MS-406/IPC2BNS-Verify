"""
reproducibility.py — Phase 28: Reproducibility Utilities

Reproducibility utilities:
- Global seed setting
- Dataset hash verification
- Environment snapshot
- Manifest export
"""

import os
import sys
import random
import numpy as np
import hashlib
import platform
import json
from typing import Dict, Any, List

import logging
log = logging.getLogger("reproducibility")


def set_seed(seed: int = 42):
    """Set global seeds for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
            # Make CuDNN deterministic
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
    except ImportError:
        pass
        
    log.info(f"Set global random seed to {seed}")

def get_env_snapshot() -> Dict[str, Any]:
    """Capture environment details."""
    snapshot = {
        "platform": platform.platform(),
        "python_version": sys.version,
    }
    
    try:
        import torch
        snapshot["torch_version"] = torch.__version__
        snapshot["cuda_available"] = torch.cuda.is_available()
    except ImportError:
        snapshot["torch_version"] = "not_installed"
        
    try:
        import transformers
        snapshot["transformers_version"] = transformers.__version__
    except ImportError:
        snapshot["transformers_version"] = "not_installed"
        
    return snapshot

def compute_dataset_hash(files: List[str]) -> str:
    """Compute hash of dataset files."""
    hasher = hashlib.md5()
    for fpath in sorted(files):
        if os.path.exists(fpath):
            with open(fpath, "rb") as f:
                hasher.update(f.read())
    return hasher.hexdigest()

def export_manifest(path: str, data: Dict[str, Any]):
    """Export a reproducibility manifest to JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    log.info(f"Exported reproducibility manifest to {path}")
