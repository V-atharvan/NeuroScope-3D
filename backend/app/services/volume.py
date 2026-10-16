"""
NeuroScope 3D - Physical Volume Calculation Service
Calculates physical tissue volumes in mL and bounding boxes on the original image grid.
Adheres strictly to PRD_BASE.md (FR-6) and docs/API_CONTRACT.md.
"""
from typing import Dict, Any, Tuple, Optional, List
import numpy as np


def compute_physical_volume_ml(
    voxel_count: int,
    voxel_spacing: Optional[Tuple[float, float, float]] = None,
    affine: Optional[np.ndarray] = None,
    spacing_mm: Optional[Tuple[float, float, float]] = None,
) -> float:
    """
    Computes physical volume in millilitres (mL) from voxel count and physical voxel spacing or affine matrix:
    If affine matrix A is provided, voxel volume in mm³ is |det(A[:3, :3])|
    Otherwise, volume_mL = voxel_count * spacing_x * spacing_y * spacing_z / 1000
    """
<<<<<<< HEAD
    effective_spacing = voxel_spacing or spacing_mm or (1.0, 1.0, 1.0)
    if affine is not None:
        try:
            det_val = abs(float(np.linalg.det(affine[:3, :3])))
            if det_val > 1e-6:
                single_voxel_mm3 = det_val
            else:
                sx, sy, sz = effective_spacing
                single_voxel_mm3 = float(sx * sy * sz)
        except Exception:
            sx, sy, sz = effective_spacing
            single_voxel_mm3 = float(sx * sy * sz)
    else:
        sx, sy, sz = effective_spacing
        single_voxel_mm3 = float(sx * sy * sz)

=======
    if voxel_spacing is None or len(voxel_spacing) != 3:
        raise ValueError(f"voxel_spacing must be a 3-element tuple, got {voxel_spacing}")
    sx, sy, sz = voxel_spacing
    if sx <= 0 or sy <= 0 or sz <= 0 or not (np.isfinite(sx) and np.isfinite(sy) and np.isfinite(sz)):
        raise ValueError(f"voxel_spacing components must be positive finite numbers, got {voxel_spacing}")
    single_voxel_mm3 = float(sx * sy * sz)
>>>>>>> 88bbae3efca21eaa3c92160af619bcc0fb01fb82
    volume_ml = (voxel_count * single_voxel_mm3) / 1000.0
    return float(volume_ml)


def compute_bounding_box(binary_mask: np.ndarray) -> Optional[Dict[str, List[int]]]:
    """
    Finds axis-aligned bounding box [min, max] coordinates for a boolean region mask.
    Returns None if region has zero positive voxels.
    """
    indices = np.argwhere(binary_mask)
    if indices.shape[0] == 0:
        return None

    min_coords = indices.min(axis=0).tolist()
    max_coords = indices.max(axis=0).tolist()
    return {"min": min_coords, "max": max_coords}


def compute_centroid_voxel(binary_mask: np.ndarray) -> Optional[List[int]]:
    """
    Finds discrete integer voxel centroid [x, y, z] of positive voxels in binary mask.
    Returns None if region has zero positive voxels.
    """
    indices = np.argwhere(binary_mask)
    if indices.shape[0] == 0:
        return None
    centroid = np.round(np.mean(indices, axis=0)).astype(int).tolist()
    return centroid


ALLOWED_BRATS_LABELS = {0, 1, 2, 4}


def calculate_region_volumes(
    label_map: np.ndarray,
    voxel_spacing: Tuple[float, float, float],
    affine: Optional[np.ndarray] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Calculates derived region volumes, voxel counts, bounding boxes, and centroids from BraTS 2021 label map:
    - WT (Whole Tumour): labels {1, 2, 4} (NCR + ED + ET)
    - TC (Tumour Core): labels {1, 4} (NCR + ET)
    - ET (Enhancing Tumour): label {4} (ET)

    Formula:
    If affine matrix A is given: single_voxel_mm3 = |det(A[:3, :3])|
    Otherwise: single_voxel_mm3 = sx * sy * sz
    volume_mL = N * single_voxel_mm3 / 1000.0

    Mathematical assertions:
    - Label map contains only valid BraTS discrete labels {0, 1, 2, 4}.
    - WT volume >= TC volume >= ET volume.
    - All volumes are non-negative and finite.
    """
    if label_map.ndim != 3:
        raise ValueError(f"label_map must be 3-dimensional, got {label_map.ndim}D")

    if not np.all(np.isfinite(label_map)):
        raise ValueError("label_map contains non-finite (NaN or Inf) values.")

    # Validate label integrity against BraTS 2021 convention
    unique_labels = set(np.unique(label_map).tolist())
    invalid_labels = unique_labels - ALLOWED_BRATS_LABELS
    if invalid_labels:
        raise ValueError(
            f"label_map contains unsupported label values {sorted(list(invalid_labels))}. "
            f"Allowed BraTS labels are: {sorted(list(ALLOWED_BRATS_LABELS))}"
        )

    # Compute voxel volume in mm³
    effective_spacing = voxel_spacing or (1.0, 1.0, 1.0)
    formula_str = "V_mL = (N * sx * sy * sz) / 1000.0"
    if affine is not None:
        try:
            det_val = abs(float(np.linalg.det(affine[:3, :3])))
            if det_val > 1e-6:
                single_voxel_mm3 = det_val
                formula_str = "V_mL = (N * |det(A_3x3)|) / 1000.0"
            else:
                sx, sy, sz = effective_spacing
                single_voxel_mm3 = float(sx * sy * sz)
        except Exception:
            sx, sy, sz = effective_spacing
            single_voxel_mm3 = float(sx * sy * sz)
    else:
        sx, sy, sz = effective_spacing
        single_voxel_mm3 = float(sx * sy * sz)

    # Define derived subregions based on BraTS 2021 convention
    wt_mask = np.isin(label_map, [1, 2, 4])
    tc_mask = np.isin(label_map, [1, 4])
    et_mask = (label_map == 4)

    masks = {
        "WT": wt_mask,
        "TC": tc_mask,
        "ET": et_mask,
    }

    results = {}
    for region_name, mask in masks.items():
        count = int(np.sum(mask))
        vol_ml = (count * single_voxel_mm3) / 1000.0
        bbox = compute_bounding_box(mask)
        centroid = compute_centroid_voxel(mask)

        results[region_name] = {
            "voxel_count": count,
            "volume_ml": round(float(vol_ml), 4),
            "voxel_volume_mm3": round(float(single_voxel_mm3), 6),
            "formula": formula_str,
            "measurement_status": "valid" if count > 0 else "empty_region",
            "bounding_box_voxel": bbox,
            "centroid_voxel": centroid,
        }

    # Strict mathematical consistency checks
    wt_vol = results["WT"]["volume_ml"]
    tc_vol = results["TC"]["volume_ml"]
    et_vol = results["ET"]["volume_ml"]

    if not (wt_vol >= tc_vol - 1e-5 and tc_vol >= et_vol - 1e-5):
        raise ValueError(
            f"Mathematical hierarchy violation: WT ({wt_vol:.4f} mL) >= TC ({tc_vol:.4f} mL) >= ET ({et_vol:.4f} mL)"
        )

    for r_k, r_val in results.items():
        if r_val["volume_ml"] < 0 or not np.isfinite(r_val["volume_ml"]):
            raise ValueError(f"Invalid volume calculated for {r_k}: {r_val['volume_ml']}")

    return results

