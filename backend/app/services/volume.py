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
    spatial_units: Any = "mm",
) -> float:
    """
    Computes physical volume in millilitres (mL) from voxel count and physical voxel spacing or affine matrix.
    If spatial units are non-millimeter (e.g. meter, micron), converts correctly to mm³ before calculating mL:
    If affine matrix A is provided, voxel volume in mm³ is |det(A[:3, :3])| * (unit_factor ** 3)
    Otherwise, volume_mL = voxel_count * (sx * sy * sz * unit_factor ** 3) / 1000.0
    """
    unit_scale = get_spatial_unit_scale_factor(spatial_units)
    unit_vol_scale = unit_scale ** 3

    if voxel_spacing is not None:
        if len(voxel_spacing) != 3:
            raise ValueError(f"voxel_spacing must be a 3-element tuple, got {voxel_spacing}")
        sx, sy, sz = voxel_spacing
        if sx <= 0 or sy <= 0 or sz <= 0 or not (np.isfinite(sx) and np.isfinite(sy) and np.isfinite(sz)):
            raise ValueError(f"voxel_spacing components must be positive finite numbers, got {voxel_spacing}")
        effective_spacing = voxel_spacing
    elif spacing_mm is not None:
        effective_spacing = spacing_mm
    else:
        effective_spacing = (1.0, 1.0, 1.0)

    if affine is not None:
        try:
            det_val = abs(float(np.linalg.det(affine[:3, :3])))
            if det_val > 1e-6:
                single_voxel_mm3 = det_val * unit_vol_scale
            else:
                sx, sy, sz = effective_spacing
                single_voxel_mm3 = float(sx * sy * sz) * unit_vol_scale
        except Exception:
            sx, sy, sz = effective_spacing
            single_voxel_mm3 = float(sx * sy * sz) * unit_vol_scale
    else:
        sx, sy, sz = effective_spacing
        single_voxel_mm3 = float(sx * sy * sz) * unit_vol_scale

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


def get_spatial_unit_scale_factor(units: Any) -> float:
    """
    Returns linear scale factor from NIfTI declared spatial units to millimeters (mm).
    - 'mm' or code 2: 1.0
    - 'meter', 'm', or code 1: 1000.0
    - 'micron', 'um', or code 3: 0.001
    """
    if units is None:
        return 1.0
    if isinstance(units, (tuple, list)):
        units = units[0] if len(units) > 0 else "mm"
    if isinstance(units, str):
        u_str = units.strip().lower()
        if u_str in ("mm", "millimeter", "millimeters"):
            return 1.0
        elif u_str in ("m", "meter", "meters"):
            return 1000.0
        elif u_str in ("um", "micron", "microns", "micrometer", "micrometers"):
            return 0.001
    elif isinstance(units, (int, np.integer)):
        if units == 2:  # NIFTI_UNITS_MM
            return 1.0
        elif units == 1:  # NIFTI_UNITS_METER
            return 1000.0
        elif units == 3:  # NIFTI_UNITS_MICRON
            return 0.001
    return 1.0


def compute_bounding_box_world(
    bbox_voxel: Optional[Dict[str, List[int]]],
    affine: Optional[np.ndarray] = None,
    voxel_spacing: Optional[Tuple[float, float, float]] = None,
    use_voxel_boundary: bool = False
) -> Optional[Dict[str, List[float]]]:
    """
    Computes physical/world space axis-aligned bounding box [min, max] in millimeters.
    Transforms all 8 corners of the voxel bounding box using the 4x4 affine matrix.
    If use_voxel_boundary is True, expands voxel extents to encompass full voxel volumes [-0.5, +0.5].
    """
    if not bbox_voxel:
        return None

    min_v = bbox_voxel["min"]
    max_v = bbox_voxel["max"]

    if affine is not None:
        try:
            aff = np.asarray(affine, dtype=np.float64)
            corners = []
            offset = 0.5 if use_voxel_boundary else 0.0
            x_vals = [float(min_v[0]) - offset, float(max_v[0]) + offset]
            y_vals = [float(min_v[1]) - offset, float(max_v[1]) + offset]
            z_vals = [float(min_v[2]) - offset, float(max_v[2]) + offset]

            for x in x_vals:
                for y in y_vals:
                    for z in z_vals:
                        w = aff @ np.array([x, y, z, 1.0], dtype=np.float64)
                        corners.append(w[:3])
            corners = np.array(corners)
            w_min = [round(float(v), 2) for v in np.min(corners, axis=0)]
            w_max = [round(float(v), 2) for v in np.max(corners, axis=0)]
            return {"min": w_min, "max": w_max}
        except Exception:
            pass

    if voxel_spacing is not None:
        w_min = [round(float(min_v[i] * voxel_spacing[i]), 2) for i in range(3)]
        w_max = [round(float(max_v[i] * voxel_spacing[i]), 2) for i in range(3)]
        return {"min": w_min, "max": w_max}
    return {
        "min": [float(v) for v in min_v],
        "max": [float(v) for v in max_v]
    }


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


def compute_centroid_fractional(binary_mask: np.ndarray) -> Optional[List[float]]:
    """
    Finds exact floating-point voxel centroid [x, y, z] of positive voxels in binary mask.
    Returns None if region has zero positive voxels.
    """
    indices = np.argwhere(binary_mask)
    if indices.shape[0] == 0:
        return None
    centroid = [round(float(c), 3) for c in np.mean(indices, axis=0)]
    return centroid


def compute_centroid_world(
    centroid_coords: Optional[List[Any]],
    affine: Optional[np.ndarray] = None,
    voxel_spacing: Optional[Tuple[float, float, float]] = None
) -> Optional[List[float]]:
    """
    Computes physical/world space centroid [x, y, z] in millimeters.
    Transforms voxel coordinates using the 4x4 affine matrix.
    """
    if centroid_coords is None:
        return None

    if affine is not None:
        try:
            aff = np.asarray(affine, dtype=np.float64)
            cx, cy, cz = centroid_coords
            w = aff @ np.array([float(cx), float(cy), float(cz), 1.0], dtype=np.float64)
            return [round(float(v), 2) for v in w[:3]]
        except Exception:
            pass

    if voxel_spacing is not None:
        return [round(float(centroid_coords[i] * voxel_spacing[i]), 2) for i in range(3)]
    return [float(v) for v in centroid_coords]


ALLOWED_BRATS_LABELS = {0, 1, 2, 4}


def calculate_region_volumes(
    label_map: np.ndarray,
    voxel_spacing: Tuple[float, float, float],
    affine: Optional[np.ndarray] = None,
    spatial_units: Any = "mm"
) -> Dict[str, Dict[str, Any]]:
    """
    Calculates derived region volumes, voxel counts, bounding boxes, and centroids from BraTS 2021 label map:
    - WT (Whole Tumour): labels {1, 2, 4} (NCR + ED + ET)
    - TC (Tumour Core): labels {1, 4} (NCR + ET)
    - ET (Enhancing Tumour): label {4} (ET)

    Formula:
    If affine matrix A is given: single_voxel_mm3 = |det(A[:3, :3])| * (unit_factor ** 3)
    Otherwise: single_voxel_mm3 = sx * sy * sz * (unit_factor ** 3)
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

    unit_scale = get_spatial_unit_scale_factor(spatial_units)
    unit_vol_scale = unit_scale ** 3

    if voxel_spacing is not None:
        if len(voxel_spacing) != 3:
            raise ValueError(f"voxel_spacing must be a 3-element tuple, got {voxel_spacing}")
        sx, sy, sz = voxel_spacing
        if sx <= 0 or sy <= 0 or sz <= 0 or not (np.isfinite(sx) and np.isfinite(sy) and np.isfinite(sz)):
            raise ValueError(f"voxel_spacing components must be positive finite numbers, got {voxel_spacing}")
        effective_spacing = voxel_spacing
    else:
        effective_spacing = (1.0, 1.0, 1.0)
    formula_str = "V_mL = (N * sx * sy * sz) / 1000.0"
    if affine is not None:
        try:
            det_val = abs(float(np.linalg.det(affine[:3, :3])))
            if det_val > 1e-6:
                single_voxel_mm3 = det_val * unit_vol_scale
                formula_str = "V_mL = (N * |det(A_3x3)|) / 1000.0"
            else:
                sx, sy, sz = effective_spacing
                single_voxel_mm3 = float(sx * sy * sz) * unit_vol_scale
        except Exception:
            sx, sy, sz = effective_spacing
            single_voxel_mm3 = float(sx * sy * sz) * unit_vol_scale
    else:
        sx, sy, sz = effective_spacing
        single_voxel_mm3 = float(sx * sy * sz) * unit_vol_scale

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
        centroid_frac = compute_centroid_fractional(mask)

        bbox_world = compute_bounding_box_world(bbox, affine=affine, voxel_spacing=effective_spacing, use_voxel_boundary=False)
        bbox_world_bounds = compute_bounding_box_world(bbox, affine=affine, voxel_spacing=effective_spacing, use_voxel_boundary=True)
        centroid_world = compute_centroid_world(centroid_frac or centroid, affine=affine, voxel_spacing=effective_spacing)

        results[region_name] = {
            "voxel_count": count,
            "volume_ml": round(float(vol_ml), 4),
            "voxel_volume_mm3": round(float(single_voxel_mm3), 6),
            "formula": formula_str,
            "measurement_status": "valid" if count > 0 else "empty_region",
            "bounding_box_voxel": bbox,
            "centroid_voxel": centroid,
            "centroid_voxel_fractional": centroid_frac,
            "bounding_box_world_mm": bbox_world,
            "bounding_box_world_bounds_mm": bbox_world_bounds,
            "centroid_world_mm": centroid_world,
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

