"""
NeuroScope 3D - Standalone Inference Preprocessing Module
Strictly enforces verified MONAI SegResNet bundle requirements:
- Channel Order: [0: T1Gd, 1: T1, 2: T2, 3: FLAIR]
- Nonzero voxel channel-wise z-score normalization (NormalizeIntensityd)
- Retention of reference spatial geometry and affine for exact grid inversion
"""
from typing import Dict, Any, Tuple
import os
import numpy as np
import nibabel as nib


class PreprocessingError(Exception):
    """Raised when sequence validation or preprocessing fails."""
    pass


def load_and_validate_nifti(file_path: str, sequence_name: str) -> Tuple[np.ndarray, np.ndarray, nib.Nifti1Header]:
    """
    Loads a single NIfTI file, ensuring it exists, is 3-dimensional,
    and has valid numeric intensities.
    """
    if not os.path.exists(file_path):
        raise PreprocessingError(f"File not found for sequence {sequence_name}: {file_path}")

    try:
        nii = nib.load(file_path)
    except Exception as e:
        raise PreprocessingError(f"Failed to parse NIfTI image for {sequence_name} ({file_path}): {e}")

    affine = nii.affine
    header = nii.header

    try:
        data = nii.get_fdata(dtype=np.float32)
    except Exception as e:
        raise PreprocessingError(f"Failed to read image array for {sequence_name}: {e}")

    if data.ndim != 3:
        raise PreprocessingError(f"Sequence {sequence_name} must be 3D, but has shape {data.shape}")

    if not np.isfinite(data).all():
        raise PreprocessingError(f"Sequence {sequence_name} contains non-finite (NaN/Inf) values")

    return data, affine, header


def normalize_intensity_nonzero(volume: np.ndarray) -> np.ndarray:
    """
    Applies channel-wise nonzero intensity normalization:
    (x - mean(x[x > 0])) / std(x[x > 0])
    Matches MONAI's NormalizeIntensityd(nonzero=True, channel_wise=True).
    """
    normalized = np.zeros_like(volume, dtype=np.float32)
    nonzero_mask = volume > 0

    if np.any(nonzero_mask):
        mean = np.mean(volume[nonzero_mask])
        std = np.std(volume[nonzero_mask])
        if std > 1e-7:
            normalized[nonzero_mask] = (volume[nonzero_mask] - mean) / std
        else:
            normalized[nonzero_mask] = volume[nonzero_mask] - mean

    return normalized


def preprocess_study(
    sequence_paths: Dict[str, str],
    affine_tolerance: float = 1e-3,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Loads and preprocesses the four required MRI sequences.
    Strict channel order for MONAI brats_mri_segmentation:
    [0: T1Gd (T1CE), 1: T1, 2: T2, 3: FLAIR]

    Returns:
        preprocessed_tensor: np.ndarray of shape (4, H, W, D) with float32 normalized intensities.
        meta_dict: Dictionary containing original reference affine, header, shape, and voxel spacing.
    """
    required_keys = ["t1gd", "t1", "t2", "flair"]
    for k in required_keys:
        if k not in sequence_paths or not sequence_paths[k]:
            raise PreprocessingError(f"Missing required MRI sequence: '{k}'")

    # 1. Load reference sequence (T1) first to establish canonical geometry
    t1_data, ref_affine, ref_header = load_and_validate_nifti(sequence_paths["t1"], "t1")
    ref_shape = t1_data.shape

    # 2. Load and validate other sequences against reference geometry
    loaded_volumes = {"t1": t1_data}
    for seq_key in ["t1gd", "t2", "flair"]:
        data, affine, _ = load_and_validate_nifti(sequence_paths[seq_key], seq_key)
        if data.shape != ref_shape:
            raise PreprocessingError(
                f"Shape mismatch: {seq_key} has shape {data.shape}, expected {ref_shape} (matching t1)"
            )
        if not np.allclose(affine, ref_affine, atol=affine_tolerance):
            diff = np.max(np.abs(affine - ref_affine))
            raise PreprocessingError(
                f"Incompatible spatial affine: {seq_key} differs from t1 reference by {diff:.5f} (tol={affine_tolerance})"
            )
        loaded_volumes[seq_key] = data

    # 3. Apply nonzero intensity normalization per channel
    # Verified channel ordering: 0: T1Gd, 1: T1, 2: T2, 3: FLAIR
    norm_t1gd = normalize_intensity_nonzero(loaded_volumes["t1gd"])
    norm_t1 = normalize_intensity_nonzero(loaded_volumes["t1"])
    norm_t2 = normalize_intensity_nonzero(loaded_volumes["t2"])
    norm_flair = normalize_intensity_nonzero(loaded_volumes["flair"])

    # Stack along first channel axis -> shape (4, H, W, D)
    stacked_tensor = np.stack([norm_t1gd, norm_t1, norm_t2, norm_flair], axis=0).astype(np.float32)

    # 4. Record original spatial metadata for lossless inverse projection
    voxel_spacing = [float(s) for s in ref_header.get_zooms()[:3]]

    meta_dict = {
        "original_shape": list(ref_shape),
        "original_affine": ref_affine.tolist(),
        "voxel_spacing_mm": voxel_spacing,
        "ref_header": ref_header,
        "ref_affine_np": ref_affine,
    }

    return stacked_tensor, meta_dict
