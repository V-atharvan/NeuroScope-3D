"""
NeuroScope 3D - Physical Volume Calculation Service
Calculates physical tissue volumes in mL and bounding boxes on the original image grid.
Adheres strictly to PRD_BASE.md (FR-6) and docs/API_CONTRACT.md.
"""
from typing import Dict, Any, Tuple, Optional, List
import numpy as np


def compute_physical_volume_ml(
    voxel_count: int,
    voxel_spacing: Tuple[float, float, float]
) -> float:
    """
    Computes physical volume in millilitres (mL) from voxel count and physical voxel spacing:
    volume_mL = voxel_count * spacing_x * spacing_y * spacing_z / 1000
    """
    if voxel_spacing is None or len(voxel_spacing) != 3:
        raise ValueError(f"voxel_spacing must be a 3-element tuple, got {voxel_spacing}")
    sx, sy, sz = voxel_spacing
    if sx <= 0 or sy <= 0 or sz <= 0 or not (np.isfinite(sx) and np.isfinite(sy) and np.isfinite(sz)):
        raise ValueError(f"voxel_spacing components must be positive finite numbers, got {voxel_spacing}")
    single_voxel_mm3 = float(sx * sy * sz)
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


def calculate_region_volumes(
    label_map: np.ndarray,
    voxel_spacing: Tuple[float, float, float]
) -> Dict[str, Dict[str, Any]]:
    """
    Calculates derived region volumes and voxel counts from BraTS 2021 label map:
    - WT (Whole Tumour): labels {1, 2, 4} (NCR + ED + ET)
    - TC (Tumour Core): labels {1, 4} (NCR + ET)
    - ET (Enhancing Tumour): label {4} (ET)

    Formula:
    volume_mL = N * sx * sy * sz / 1000.0
    """
    if label_map.ndim != 3:
        raise ValueError(f"label_map must be 3-dimensional, got {label_map.ndim}D")

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
        vol_ml = compute_physical_volume_ml(count, voxel_spacing)
        bbox = compute_bounding_box(mask)

        results[region_name] = {
            "voxel_count": count,
            "volume_ml": round(vol_ml, 4),
            "bounding_box_voxel": bbox,
        }

    return results
