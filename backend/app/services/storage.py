"""
NeuroScope 3D - Ephemeral Case Storage & Lifecycle Service
Manages private temporary case files, SHA-256 checksums, and 24-hour automatic retention purge.
Adheres strictly to PRD_BASE.md (FR-9) and ARCHITECTURE.md.
"""
from typing import Dict, Any, Optional, Tuple
import os
import shutil
import time
import uuid
import json
import hashlib

STORAGE_BASE_DIR = os.getenv("STORAGE_DIR", "./storage/cases")
RETENTION_HOURS = int(os.getenv("TEMP_RETENTION_HOURS", "24"))


def compute_file_sha256(file_path: str) -> str:
    """Computes hexadecimal SHA-256 hash of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_case_dir(case_id: str) -> str:
    """Returns absolute path to a case's private storage directory."""
    return os.path.abspath(os.path.join(STORAGE_BASE_DIR, case_id))


def create_case_workspace() -> Tuple[str, str]:
    """
    Creates a unique private directory for an uploaded case.
    Returns (case_id, case_dir).
    """
    case_id = f"case_{uuid.uuid4()}"
    case_dir = get_case_dir(case_id)
    os.makedirs(case_dir, exist_ok=True)
    return case_id, case_dir


def save_case_metadata(case_id: str, metadata: Dict[str, Any]) -> None:
    """Saves state and results to case_state.json inside private case directory."""
    case_dir = get_case_dir(case_id)
    if os.path.exists(case_dir):
        state_file = os.path.join(case_dir, "case_state.json")
        with open(state_file, "w") as f:
            json.dump(metadata, f, indent=2)


def load_case_metadata(case_id: str) -> Optional[Dict[str, Any]]:
    """Loads state and results from case_state.json if available."""
    case_dir = get_case_dir(case_id)
    state_file = os.path.join(case_dir, "case_state.json")
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            return json.load(f)
    return None


def cleanup_expired_cases(max_age_hours: int = RETENTION_HOURS) -> int:
    """
    Automatically purges temporary case directories older than max_age_hours (default: 24h).
    Returns count of cleaned cases.
    """
    if not os.path.exists(STORAGE_BASE_DIR):
        return 0

    now = time.time()
    cutoff_seconds = max_age_hours * 3600
    cleaned_count = 0

    for item in os.listdir(STORAGE_BASE_DIR):
        item_path = os.path.join(STORAGE_BASE_DIR, item)
        if os.path.isdir(item_path):
            dir_mtime = os.path.getmtime(item_path)
            if (now - dir_mtime) > cutoff_seconds:
                try:
                    shutil.rmtree(item_path)
                    cleaned_count += 1
                except Exception:
                    pass

    return cleaned_count
