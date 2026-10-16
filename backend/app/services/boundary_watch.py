"""
NeuroScope 3D - Boundary Watch & Segmentation Quality Assurance Service
======================================================================
Identifies suspicious characteristics of predicted tumor segmentations using
measurable geometric, topological, and spatial continuity checks:

1. Disconnected Components: Detects isolated satellite clusters and fragmentation.
2. Slice-to-Slice Discontinuity: Detects abrupt stepped jumps in cross-sectional area.
3. Field of View (FOV) Border Contact: Detects potential tumor truncation against image edges.
4. Micro-Volume & Empty Subregions: Flags punctate noise vs. absent subregions.
5. Hierarchical Nesting Integrity: Mathematically verifies ET ⊆ TC ⊆ WT containment.
6. Overall Quality Risk Rating: Classifies risk as OPTIMAL, ATTENTION_ADVISED, or HIGH_DISCREPANCY_RISK.

Adheres strictly to the principle that warnings are diagnostic signals for radiologist
review and never automatically discard genuine multifocal or atypical anatomy.
"""
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import scipy.ndimage


def get_region_mask(label_map: np.ndarray, region: str) -> np.ndarray:
    """Extracts binary mask for a clinical BraTS region."""
    reg = region.upper()
    if reg == "WT":
        return np.isin(label_map, [1, 2, 4])
    elif reg == "TC":
        return np.isin(label_map, [1, 4])
    elif reg == "ET":
        return (label_map == 4)
    else:
        raise ValueError(f"Unknown region '{region}'. Must be 'WT', 'TC', or 'ET'.")


def analyze_connected_components(
    binary_mask: np.ndarray,
    voxel_volume_ml: float,
    region_name: str
) -> Dict[str, Any]:
    """
    Analyzes 3D connected components (islands) in a binary segmentation mask.
    Identifies primary lesion mass versus satellite foci.
    """
    if np.count_nonzero(binary_mask) == 0:
        return {
            "component_count": 0,
            "primary_volume_ml": 0.0,
            "satellite_count": 0,
            "satellite_volume_ml": 0.0,
            "fragmentation_ratio": 0.0,
            "satellite_centroids": [],
            "flagged": False,
            "message": f"{region_name} subregion is absent.",
        }

    # 26-connectivity 3D neighborhood structure
    struct_26 = np.ones((3, 3, 3), dtype=bool)
    labeled, num_features = scipy.ndimage.label(binary_mask, structure=struct_26)

    if num_features <= 1:
        total_vol = float(np.count_nonzero(binary_mask) * voxel_volume_ml)
        return {
            "component_count": 1,
            "primary_volume_ml": round(total_vol, 3),
            "satellite_count": 0,
            "satellite_volume_ml": 0.0,
            "fragmentation_ratio": 0.0,
            "satellite_centroids": [],
            "flagged": False,
            "message": f"Single contiguous {region_name} lesion detected (optimal continuity).",
        }

    # Multiple components: calculate size distribution
    component_sizes = scipy.ndimage.sum(binary_mask, labeled, range(1, num_features + 1))
    sorted_indices = np.argsort(component_sizes)[::-1]  # descending
    sorted_sizes = [int(component_sizes[i]) for i in sorted_indices]

    primary_voxels = sorted_sizes[0]
    primary_vol = float(primary_voxels * voxel_volume_ml)
    satellite_voxels = sum(sorted_sizes[1:])
    satellite_vol = float(satellite_voxels * voxel_volume_ml)
    total_voxels = primary_voxels + satellite_voxels
    fragmentation = float(satellite_voxels / total_voxels) if total_voxels > 0 else 0.0

    # Extract centroids of the top 3 satellite clusters for navigation
    satellite_centroids: List[List[int]] = []
    for comp_idx in sorted_indices[1:4]:  # Top 3 satellites
        label_id = comp_idx + 1
        comp_coords = np.argwhere(labeled == label_id)
        if len(comp_coords) > 0:
            c = np.round(np.mean(comp_coords, axis=0)).astype(int).tolist()
            satellite_centroids.append(c)

    # Flag if excessive fragmentation (> 3 components or satellite volume > 15%)
    flagged = (num_features > 3) or (fragmentation > 0.15 and satellite_vol > 0.2)
    severity = "WARNING" if flagged else "INFO"

    msg = (
        f"{num_features} disconnected components detected ({satellite_vol:.2f} mL satellite burden). "
        f"Inspect whether satellite clusters represent multifocal tumor foci or peripheral noise."
        if flagged
        else f"{num_features} discrete foci detected ({primary_vol:.2f} mL primary, {satellite_vol:.2f} mL satellite)."
    )

    return {
        "component_count": int(num_features),
        "primary_volume_ml": round(primary_vol, 3),
        "satellite_count": int(num_features - 1),
        "satellite_volume_ml": round(satellite_vol, 3),
        "fragmentation_ratio": round(fragmentation, 3),
        "satellite_centroids": satellite_centroids,
        "flagged": flagged,
        "severity": severity,
        "message": msg,
    }


def analyze_slice_continuity(
    binary_mask: np.ndarray,
    region_name: str
) -> Dict[str, Any]:
    """
    Detects abrupt through-plane stepped discontinuities along axial slices (Z-axis).
    Calculates relative slice-to-slice area jumps: |A_{z} - A_{z-1}| / max(A_z, A_{z-1}).
    """
    if np.count_nonzero(binary_mask) == 0:
        return {
            "max_jump_ratio": 0.0,
            "abrupt_discontinuities": [],
            "flagged": False,
            "message": f"No {region_name} voxels to inspect for slice continuity.",
        }

    # Sum along axial slices (Z is axis 2 in shape [H, W, D])
    slice_counts = np.sum(binary_mask, axis=(0, 1)).astype(int)
    non_zero_slices = np.where(slice_counts > 0)[0]

    if len(non_zero_slices) <= 2:
        return {
            "max_jump_ratio": 0.0,
            "abrupt_discontinuities": [],
            "flagged": False,
            "message": f"{region_name} spans <= 2 axial slices.",
        }

    discontinuities = []
    max_jump = 0.0

    # Compare consecutive non-empty slices
    for i in range(len(non_zero_slices) - 1):
        z1 = non_zero_slices[i]
        z2 = non_zero_slices[i + 1]

        # If there's an empty gap slice in between, that's an immediate jump
        if z2 - z1 > 1:
            discontinuities.append({
                "slice_z": int(z1),
                "next_slice_z": int(z2),
                "type": "GAP_SLICE",
                "jump_ratio": 1.0,
                "message": f"Tumor mask disappears at slice Z={z1+1} then reappears at Z={z2}."
            })
            max_jump = 1.0
            continue

        c1 = slice_counts[z1]
        c2 = slice_counts[z2]
        denom = max(c1, c2)
        diff = abs(c2 - c1)
        jump_ratio = float(diff / denom) if denom > 0 else 0.0

        if jump_ratio > max_jump:
            max_jump = jump_ratio

        # Flag significant sudden steps (>70% drop/gain with significant volume difference >= 30 voxels)
        if jump_ratio > 0.70 and diff >= 30:
            discontinuities.append({
                "slice_z": int(z1),
                "next_slice_z": int(z2),
                "type": "STEPPED_DISCONTINUITY",
                "area_current_voxels": int(c1),
                "area_next_voxels": int(c2),
                "jump_ratio": round(jump_ratio, 2),
                "message": f"Abrupt {int(jump_ratio*100)}% area shift between Axial Z={z1} ({c1} voxels) and Z={z2} ({c2} voxels)."
            })

    flagged = len(discontinuities) > 0
    return {
        "max_jump_ratio": round(float(max_jump), 2),
        "discontinuity_count": len(discontinuities),
        "abrupt_discontinuities": discontinuities[:4],  # limit to top 4
        "flagged": flagged,
        "message": (
            f"Detected {len(discontinuities)} stepped slice discontinuities in {region_name}. Check for slice motion or partial-volume stepping."
            if flagged
            else f"Smooth slice-to-slice volumetric transition in {region_name}."
        ),
    }


def analyze_border_contact(
    binary_mask: np.ndarray,
    region_name: str
) -> Dict[str, Any]:
    """
    Detects if predicted mask touches the outermost 1-voxel bounding boundary of the 3D volume.
    Touches on perimeter suggest field-of-view cutoff or truncation artifacts.
    """
    if np.count_nonzero(binary_mask) == 0:
        return {
            "border_voxels": 0,
            "border_touching": False,
            "flagged": False,
            "message": f"No {region_name} voxels present.",
        }

    H, W, D = binary_mask.shape
    border_voxels = (
        np.count_nonzero(binary_mask[0, :, :]) +
        np.count_nonzero(binary_mask[H - 1, :, :]) +
        np.count_nonzero(binary_mask[:, 0, :]) +
        np.count_nonzero(binary_mask[:, W - 1, :]) +
        np.count_nonzero(binary_mask[:, :, 0]) +
        np.count_nonzero(binary_mask[:, :, D - 1])
    )

    border_touching = border_voxels > 0
    flagged = border_voxels >= 3

    return {
        "border_voxels": int(border_voxels),
        "border_touching": bool(border_touching),
        "flagged": bool(flagged),
        "message": (
            f"{region_name} boundary touches the acquisition perimeter ({border_voxels} perimeter voxels). Potential field-of-view truncation."
            if flagged
            else f"{region_name} is fully contained within the field-of-view margin."
        ),
    }


def analyze_nesting_integrity(label_map: np.ndarray) -> Dict[str, Any]:
    """
    Mathematically verifies the hierarchical containment rule:
    ET ⊆ TC ⊆ WT
    Identifies any orphan voxels violating nesting constraints.
    """
    wt_mask = np.isin(label_map, [1, 2, 4])
    tc_mask = np.isin(label_map, [1, 4])
    et_mask = (label_map == 4)

    # Violations:
    # 1. TC voxels not inside WT: TC \ WT
    tc_outside_wt = tc_mask & (~wt_mask)
    tc_violations = int(np.count_nonzero(tc_outside_wt))

    # 2. ET voxels not inside TC: ET \ TC
    et_outside_tc = et_mask & (~tc_mask)
    et_violations = int(np.count_nonzero(et_outside_tc))

    total_violations = tc_violations + et_violations
    is_valid = (total_violations == 0)

    return {
        "is_nesting_valid": is_valid,
        "total_violations": total_violations,
        "tc_outside_wt_voxels": tc_violations,
        "et_outside_tc_voxels": et_violations,
        "flagged": not is_valid,
        "message": (
            "Strict hierarchical nesting verified: ET ⊆ TC ⊆ WT (0 logical violations)."
            if is_valid
            else f"Nesting violation: {total_violations} orphan voxels outside expected hierarchy."
        ),
    }


def analyze_boundary_watch(
    label_map: np.ndarray,
    voxel_spacing: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    affine: Optional[np.ndarray] = None
) -> Dict[str, Any]:
    """
    Executes the full Boundary Watch quality assurance protocol on a 3D predicted label map.
    Returns structured flags, spatial anomalies, and an overall quality risk rating.
    """
    if affine is not None:
        try:
            det = abs(float(np.linalg.det(affine[:3, :3])))
            voxel_volume_ml = det / 1000.0 if det > 1e-6 else (voxel_spacing[0] * voxel_spacing[1] * voxel_spacing[2]) / 1000.0
        except Exception:
            voxel_volume_ml = (voxel_spacing[0] * voxel_spacing[1] * voxel_spacing[2]) / 1000.0
    else:
        voxel_volume_ml = (voxel_spacing[0] * voxel_spacing[1] * voxel_spacing[2]) / 1000.0

    wt_mask = get_region_mask(label_map, "WT")
    tc_mask = get_region_mask(label_map, "TC")
    et_mask = get_region_mask(label_map, "ET")

    # 1. Connected components analysis
    wt_components = analyze_connected_components(wt_mask, voxel_volume_ml, "Whole Tumour (WT)")
    tc_components = analyze_connected_components(tc_mask, voxel_volume_ml, "Tumour Core (TC)")
    et_components = analyze_connected_components(et_mask, voxel_volume_ml, "Enhancing Tumour (ET)")

    # 2. Slice continuity analysis
    wt_continuity = analyze_slice_continuity(wt_mask, "Whole Tumour (WT)")
    tc_continuity = analyze_slice_continuity(tc_mask, "Tumour Core (TC)")
    et_continuity = analyze_slice_continuity(et_mask, "Enhancing Tumour (ET)")

    # 3. Border contact analysis
    wt_border = analyze_border_contact(wt_mask, "Whole Tumour (WT)")
    tc_border = analyze_border_contact(tc_mask, "Tumour Core (TC)")
    et_border = analyze_border_contact(et_mask, "Enhancing Tumour (ET)")

    # 4. Hierarchical nesting check
    nesting_check = analyze_nesting_integrity(label_map)

    # 5. Micro-volume check
    wt_vol_ml = float(np.count_nonzero(wt_mask) * voxel_volume_ml)
    tc_vol_ml = float(np.count_nonzero(tc_mask) * voxel_volume_ml)
    et_vol_ml = float(np.count_nonzero(et_mask) * voxel_volume_ml)

    micro_volume_flags = []
    if 0 < wt_vol_ml < 0.2:
        micro_volume_flags.append({
            "region": "WT",
            "volume_ml": round(wt_vol_ml, 3),
            "message": f"Punctate Whole Tumour volume ({wt_vol_ml:.3f} mL). Check for threshold noise."
        })
    if 0 < et_vol_ml < 0.05:
        micro_volume_flags.append({
            "region": "ET",
            "volume_ml": round(et_vol_ml, 3),
            "message": f"Micro-enhancing focus ({et_vol_ml:.3f} mL). Verify with post-contrast T1Gd subtraction."
        })

    # 6. Overall Quality Score computation
    risk_points = 0
    active_warnings = []

    if wt_border["flagged"]:
        risk_points += 35
        active_warnings.append(wt_border["message"])
    if wt_continuity["flagged"]:
        risk_points += 25
        active_warnings.append(wt_continuity["message"])
    if wt_components["flagged"]:
        risk_points += 20
        active_warnings.append(wt_components["message"])
    elif wt_components["component_count"] > 1:
        risk_points += 5
    if tc_components["flagged"]:
        risk_points += 15
        active_warnings.append(tc_components["message"])
    if len(micro_volume_flags) > 0:
        risk_points += 10
        active_warnings.extend([f["message"] for f in micro_volume_flags])
    if nesting_check["flagged"]:
        risk_points += 40
        active_warnings.append(nesting_check["message"])

    if risk_points <= 15:
        risk_category = "OPTIMAL_QUALITY"
        risk_badge = "Optimal Quality"
        risk_color = "#10B981"
        recommendation = "Segmentation displays smooth boundaries, contiguous anatomy, and clean FOV containment."
    elif risk_points <= 45:
        risk_category = "ATTENTION_ADVISED"
        risk_badge = "Attention Advised"
        risk_color = "#F59E0B"
        recommendation = "Minor morphological irregularities or satellite foci detected. Visual inspection of highlighted slices recommended."
    else:
        risk_category = "HIGH_DISCREPANCY_RISK"
        risk_badge = "High Discrepancy Risk"
        risk_color = "#EF4444"
        recommendation = "Significant boundary discontinuity, perimeter touching, or heavy fragmentation detected. Careful radiologist review required."

    return {
        "quality_risk_category": risk_category,
        "quality_risk_badge": risk_badge,
        "quality_risk_color": risk_color,
        "risk_score": risk_points,
        "active_warnings": active_warnings,
        "recommendation": recommendation,
        "checks": {
            "disconnected_components": {
                "WT": wt_components,
                "TC": tc_components,
                "ET": et_components,
            },
            "slice_continuity": {
                "WT": wt_continuity,
                "TC": tc_continuity,
                "ET": et_continuity,
            },
            "border_contact": {
                "WT": wt_border,
                "TC": tc_border,
                "ET": et_border,
            },
            "nesting_integrity": nesting_check,
            "micro_volumes": micro_volume_flags,
        },
        "disclaimer": (
            "RESEARCH QUALITY FLAGS ONLY: Geometric quality checks highlight areas of potential "
            "model uncertainty or morphological complexity and do not prove or disprove true pathology."
        )
    }
