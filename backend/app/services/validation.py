"""
NeuroScope 3D - Study and NIfTI Validation Service
Validates input sequences, geometries, data integrity, and failure cases
according to PRD_BASE.md (FR-2), ARCHITECTURE.md, and docs/API_CONTRACT.md.
"""
from typing import Dict, Any, Tuple, Optional, List, Set
import os
import gzip
import numpy as np
import nibabel as nib

MAX_FILE_SIZE_BYTES = 1024 * 1024 * 1024  # 1.0 GB limit
DEFAULT_AFFINE_TOLERANCE = 1e-3
ALLOWED_BRATS_LABELS = {0, 1, 2, 4}
REQUIRED_SEQUENCES = ["t1", "t1gd", "t2", "flair"]


class ValidationError(Exception):
    """Structured validation error containing standard error code and message."""
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def check_file_size(file_path: str, max_bytes: int = MAX_FILE_SIZE_BYTES) -> int:
    """Verifies file size on disk before loading into memory."""
    if not os.path.exists(file_path):
        raise ValidationError("FILE_NOT_FOUND", f"File does not exist: {file_path}")
    size = os.path.getsize(file_path)
    if size > max_bytes:
        raise ValidationError(
            "FILE_TOO_LARGE",
            f"File '{os.path.basename(file_path)}' exceeds maximum allowed size of 1 GB ({size} bytes)",
            {"file": file_path, "size_bytes": size, "limit_bytes": max_bytes}
        )
    return size


def verify_gzip_integrity(file_path: str) -> None:
    """Checks whether a .gz file has intact gzip headers and blocks."""
    if file_path.endswith(".gz"):
        try:
            with gzip.open(file_path, "rb") as gz:
                # Read a small buffer to verify gzip magic numbers and header
                _ = gz.read(1024)
        except Exception as e:
            raise ValidationError(
                "CORRUPT_GZIP",
                f"File '{os.path.basename(file_path)}' has corrupt gzip streams or headers: {e}",
                {"file": file_path}
            )


def load_and_verify_single_volume(
    file_path: str,
    sequence_label: str
) -> Tuple[np.ndarray, np.ndarray, nib.Nifti1Header]:
    """
    Validates actual NIfTI file contents:
    - Size within 1GB
    - Gzip integrity (if compressed)
    - Valid NIfTI parsing (magic bytes, header)
    - Strictly 3-dimensional
    - Finite numerical values (no NaN / Inf)
    - Non-constant intensities (rejects all-zero or uniform constants)
    """
    check_file_size(file_path)
    verify_gzip_integrity(file_path)

    try:
        nii = nib.load(file_path)
    except Exception as e:
        raise ValidationError(
            "INVALID_NIFTI",
            f"Failed to parse '{os.path.basename(file_path)}' as a valid NIfTI image: {e}",
            {"file": file_path, "sequence": sequence_label}
        )

    # Dimensionality check: must be exactly 3D
    shape = nii.shape
    if len(shape) != 3:
        raise ValidationError(
            "DIMENSION_MISMATCH_NOT_3D",
            f"Sequence '{sequence_label}' has {len(shape)} dimensions {shape}; expected 3D volume (H, W, D)",
            {"file": file_path, "shape": list(shape), "sequence": sequence_label}
        )

    # Load numerical array safely
    try:
        data = nii.get_fdata(dtype=np.float32)
    except Exception as e:
        raise ValidationError(
            "INVALID_NIFTI",
            f"Failed to read image array data from '{os.path.basename(file_path)}': {e}",
            {"file": file_path, "sequence": sequence_label}
        )

    # Check finite numbers
    if not np.all(np.isfinite(data)):
        raise ValidationError(
            "NON_FINITE_VALUES",
            f"Sequence '{sequence_label}' contains non-finite (NaN or Inf) values",
            {"file": file_path, "sequence": sequence_label}
        )

    # Check non-constant intensities (reject all-zeros or uniform constants)
    val_min = float(np.min(data))
    val_max = float(np.max(data))
    if val_min == val_max or np.std(data) < 1e-7:
        raise ValidationError(
            "CONSTANT_VOLUME",
            f"Sequence '{sequence_label}' is constant (min={val_min}, max={val_max}); zero informative signal",
            {"file": file_path, "sequence": sequence_label, "min": val_min, "max": val_max}
        )

    return data, nii.affine, nii.header


def check_skull_stripping_heuristic(data: np.ndarray) -> bool:
    """
    Conservative skull-stripping sanity check.
    Skull-stripped brain MRIs typically exhibit empty zero-background margins at the volume borders.
    If border slices have high foreground occupancy (>85%), issue a warning.
    """
    border_voxels = np.concatenate([
        data[0, :, :].ravel(), data[-1, :, :].ravel(),
        data[:, 0, :].ravel(), data[:, -1, :].ravel(),
        data[:, :, 0].ravel(), data[:, :, -1].ravel(),
    ])
    border_nonzero_ratio = np.count_nonzero(border_voxels > 0) / float(len(border_voxels))
    # Returns True if borders look like typical skull-stripped margins (mostly zero)
    return border_nonzero_ratio < 0.20


def validate_study(
    sequence_paths: Dict[str, str],
    expert_mask_path: Optional[str] = None,
    affine_tolerance: float = DEFAULT_AFFINE_TOLERANCE
) -> Dict[str, Any]:
    """
    Full validation service for the four MRI sequences and optional expert mask.
    Enforces all checks and returns verified spatial and metadata dictionary.
    """
    # 1. Sequence presence check
    for req in REQUIRED_SEQUENCES:
        if req not in sequence_paths or not sequence_paths[req]:
            raise ValidationError(
                "MISSING_SEQUENCE",
                f"Missing required MRI sequence '{req}'. Exactly four sequences required: T1, T1Gd, T2, FLAIR",
                {"missing_sequence": req}
            )

    # 2. Load reference sequence (T1)
    t1_data, ref_affine, ref_header = load_and_verify_single_volume(sequence_paths["t1"], "t1")
    ref_shape = list(t1_data.shape)
    voxel_spacing = [float(s) for s in ref_header.get_zooms()[:3]]

    # 3. Load and cross-validate remaining sequences against reference geometry
    verified_files = {
        "t1": {
            "path": sequence_paths["t1"],
            "shape": ref_shape,
            "size_bytes": os.path.getsize(sequence_paths["t1"]),
        }
    }

    warnings = []
    if not check_skull_stripping_heuristic(t1_data):
        warnings.append("Volume borders contain elevated intensities; verify skull-stripping status.")

    for seq_name in ["t1gd", "t2", "flair"]:
        fpath = sequence_paths[seq_name]
        data, affine, _ = load_and_verify_single_volume(fpath, seq_name)

        if list(data.shape) != ref_shape:
            raise ValidationError(
                "MISMATCHED_SHAPES",
                f"Shape mismatch: '{seq_name}' has shape {list(data.shape)}, which does not match reference 't1' {ref_shape}",
                {"sequence": seq_name, "found_shape": list(data.shape), "expected_shape": ref_shape}
            )

        if not np.allclose(affine, ref_affine, atol=affine_tolerance):
            max_diff = float(np.max(np.abs(affine - ref_affine)))
            raise ValidationError(
                "MISMATCHED_AFFINES",
                f"Affine mismatch: '{seq_name}' spatial orientation differs from reference 't1' by {max_diff:.5f} (tol={affine_tolerance})",
                {"sequence": seq_name, "max_difference": max_diff, "tolerance": affine_tolerance}
            )

        verified_files[seq_name] = {
            "path": fpath,
            "shape": list(data.shape),
            "size_bytes": os.path.getsize(fpath),
        }

    # 4. Validate optional expert mask if provided
    has_expert_mask = False
    if expert_mask_path and os.path.exists(expert_mask_path):
        check_file_size(expert_mask_path)
        verify_gzip_integrity(expert_mask_path)

        try:
            mask_nii = nib.load(expert_mask_path)
            mask_data = mask_nii.get_fdata(dtype=np.float32)
        except Exception as e:
            raise ValidationError(
                "INVALID_EXPERT_MASK",
                f"Failed to read expert mask NIfTI: {e}",
                {"file": expert_mask_path}
            )

        if len(mask_data.shape) != 3 or list(mask_data.shape) != ref_shape:
            raise ValidationError(
                "INVALID_EXPERT_MASK_GEOMETRY",
                f"Expert mask shape {list(mask_data.shape)} does not match study reference shape {ref_shape}",
                {"found_shape": list(mask_data.shape), "expected_shape": ref_shape}
            )

        if not np.allclose(mask_nii.affine, ref_affine, atol=affine_tolerance):
            raise ValidationError(
                "INVALID_EXPERT_MASK_GEOMETRY",
                "Expert mask spatial affine does not match MRI study reference affine",
                {"tolerance": affine_tolerance}
            )

        unique_labels = set(np.unique(mask_data.astype(np.int64)).tolist())
        invalid_labels = unique_labels - ALLOWED_BRATS_LABELS
        if invalid_labels:
            raise ValidationError(
                "INVALID_EXPERT_MASK_LABELS",
                f"Expert mask contains invalid label values {invalid_labels}. Allowed BraTS 2021 labels: {ALLOWED_BRATS_LABELS}",
                {"invalid_labels": list(invalid_labels), "allowed_labels": list(ALLOWED_BRATS_LABELS)}
            )

        has_expert_mask = True
        verified_files["expert_mask"] = {
            "path": expert_mask_path,
            "shape": list(mask_data.shape),
            "unique_labels": sorted(list(unique_labels)),
            "size_bytes": os.path.getsize(expert_mask_path),
        }

    return {
        "status": "passed",
        "spatial_metadata": {
            "shape": ref_shape,
            "spacing_mm": voxel_spacing,
            "reference_affine": ref_affine.tolist(),
        },
        "has_expert_mask": has_expert_mask,
        "files": verified_files,
        "warnings": warnings,
    }
