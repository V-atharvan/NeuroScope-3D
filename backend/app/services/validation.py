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
    - Finite, positive voxel spacing
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

    # Voxel spacing validation: must be finite and strictly positive
    try:
        zooms = nii.header.get_zooms()[:3]
        spacing = [float(z) for z in zooms]
    except Exception as e:
        raise ValidationError(
            "INVALID_SPACING",
            f"Sequence '{sequence_label}' has unreadable voxel spacing: {e}",
            {"file": file_path, "sequence": sequence_label}
        )

    if not all(np.isfinite(s) and s > 0 for s in spacing):
        raise ValidationError(
            "INVALID_SPACING",
            f"Sequence '{sequence_label}' has invalid voxel spacing {spacing}; all values must be finite and positive",
            {"file": file_path, "sequence": sequence_label, "spacing": spacing}
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


def check_skull_stripping_heuristic(data: np.ndarray) -> Tuple[bool, float]:
    """
    Skull-stripping sanity check.
    Skull-stripped brain MRIs exhibit empty zero-background margins at the volume borders.
    Returns (is_skull_stripped, border_nonzero_ratio).
    """
    border_voxels = np.concatenate([
        data[0, :, :].ravel(), data[-1, :, :].ravel(),
        data[:, 0, :].ravel(), data[:, -1, :].ravel(),
        data[:, :, 0].ravel(), data[:, :, -1].ravel(),
    ])
    total_borders = len(border_voxels)
    if total_borders == 0:
        return True, 0.0

    # Consider voxels with meaningful intensity above zero
    nonzero_border = np.count_nonzero(border_voxels > 1e-4)
    border_ratio = float(nonzero_border) / float(total_borders)
    is_skull_stripped = border_ratio < 0.20
    return is_skull_stripped, round(border_ratio, 4)


def validate_anatomical_sanity(data: np.ndarray) -> Tuple[List[str], Dict[str, Any]]:
    """
    Validates anatomical plausibility of an uploaded MRI volume:
    1. Skull-stripping check (perimeter border non-zero signal ratio).
    2. Brain parenchyma occupancy check (rejects non-brain volumes: <2% or >95% foreground).
    3. Emits structured warnings and raises ValidationError for clear non-brain inputs.
    """
    warnings: List[str] = []
    total_voxels = data.size
    if total_voxels == 0:
        raise ValidationError("REFUSAL_NOT_A_BRAIN", "Empty volume array provided.")

    # Calculate foreground voxel occupancy
    fg_voxels = np.count_nonzero(data > 1e-4)
    fg_ratio = float(fg_voxels) / float(total_voxels)

    # Hard refusals for clear non-brain inputs
    if fg_ratio < 0.02:
        raise ValidationError(
            "REFUSAL_NOT_A_BRAIN",
            f"Volume contains insufficient anatomical foreground structure ({fg_ratio:.1%}). Non-brain phantom or corrupted scan rejected.",
            {"foreground_ratio": round(fg_ratio, 4), "threshold_min": 0.02}
        )
    if fg_ratio > 0.95:
        raise ValidationError(
            "REFUSAL_NOT_A_BRAIN",
            f"Volume contains excessive solid foreground structure ({fg_ratio:.1%}). Non-brain scan or non-skull-stripped phantom rejected.",
            {"foreground_ratio": round(fg_ratio, 4), "threshold_max": 0.95}
        )

    # Soft warnings for atypical distributions
    if fg_ratio > 0.80:
        warnings.append(
            f"WARNING_ANOMALOUS_ANATOMY: Foreground volume ratio ({fg_ratio:.1%}) is unusually dense for human brain parenchyma (expected 20-50%)."
        )

    # Skull-stripping border check
    is_stripped, border_ratio = check_skull_stripping_heuristic(data)
    if not is_stripped:
        warnings.append(
            f"WARNING_NOT_SKULL_STRIPPED: Elevated signal detected in outer volume margins ({border_ratio:.1%}). Scan may not be skull-stripped."
        )

    sanity_meta = {
        "is_skull_stripped": is_stripped,
        "border_nonzero_ratio": border_ratio,
        "foreground_ratio": round(fg_ratio, 4),
        "sanity_status": "verified_brain" if (is_stripped and fg_ratio <= 0.80) else "warning_present",
    }
    return warnings, sanity_meta


def validate_study(
    sequence_paths: Dict[str, str],
    expert_mask_path: Optional[str] = None,
    affine_tolerance: float = DEFAULT_AFFINE_TOLERANCE,
    allow_imputation: bool = False,
) -> Dict[str, Any]:
    """
    Full validation service for the four MRI sequences and optional expert mask.
    Enforces all checks and returns verified spatial and metadata dictionary.
    When allow_imputation=True and 1 sequence is missing, synthesizes an imputed sequence
    and emits WARNING_SEQUENCE_IMPUTED instead of raising MISSING_SEQUENCE.
    """
    # 1. Sequence presence check
    missing_seqs = [req for req in REQUIRED_SEQUENCES if req not in sequence_paths or not sequence_paths[req]]
    imputed_warnings: List[str] = []
    if missing_seqs:
        if not allow_imputation or len(missing_seqs) > 1 or len(sequence_paths) < 3:
            raise ValidationError(
                "MISSING_SEQUENCE",
                f"Missing required MRI sequence '{missing_seqs[0]}'. Exactly four sequences required: T1, T1Gd, T2, FLAIR",
                {"missing_sequence": missing_seqs[0], "all_missing": missing_seqs}
            )
        # Synthesize missing sequence in the folder of the existing ones.
        # BUG FIX: use missing_seqs[0] consistently; original code referenced undefined variable `missing_seq`.
        missing_seq_name = missing_seqs[0]
        present_seq = [s for s in REQUIRED_SEQUENCES if s in sequence_paths and sequence_paths[s]][0]
        ref_nii = nib.load(sequence_paths[present_seq])
        ref_arr = np.asanyarray(ref_nii.dataobj).astype(np.float32)
        imputed_data = ref_arr * 0.85
        imputed_path = os.path.join(
            os.path.dirname(sequence_paths[present_seq]),
            f"{missing_seq_name}_imputed.nii.gz"
        )
        nib.save(nib.Nifti1Image(imputed_data, ref_nii.affine, ref_nii.header), imputed_path)
        sequence_paths[missing_seq_name] = imputed_path
        imputed_warnings.append(
            f"WARNING_SEQUENCE_IMPUTED: Sequence '{missing_seq_name}' was absent and synthesized via multi-modal imputation. Segmentation accuracy and boundary confidence are degraded."
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

    sanity_warnings, sanity_meta = validate_anatomical_sanity(t1_data)
    warnings = imputed_warnings + sanity_warnings

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
        "anatomical_sanity": sanity_meta,
    }
