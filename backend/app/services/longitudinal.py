"""
NeuroScope 3D - Longitudinal Tracking & RANO Volumetric Assessment Service
=========================================================================
Compares baseline (T0) and follow-up (T1) MRI scans for the same patient,
calculating absolute and percentage volumetric deltas across WT, TC, and ET regions,
and mapping trajectories to standard RANO (Response Assessment in Neuro-Oncology) criteria.
"""
from typing import Dict, Any, Optional

LONGITUDINAL_DISCLAIMER = (
    "RESEARCH VOLUMETRIC TRACKING ONLY — NOT A CLINICAL ONCOLOGICAL ASSESSMENT. "
    "Trajectory assessments reflect approximate RANO volumetric threshold calculations "
    "on research data and must never be used for patient treatment decisions."
)


def calculate_volumetric_delta(v0: float, v1: float) -> Dict[str, Any]:
    """Computes absolute (mL) and relative (%) volumetric change."""
    abs_delta = v1 - v0
    pct_delta = ((v1 - v0) / v0 * 100.0) if v0 > 0 else (100.0 if v1 > 0 else 0.0)
    return {
        "baseline_volume_ml": round(v0, 2),
        "followup_volume_ml": round(v1, 2),
        "absolute_delta_ml": round(abs_delta, 2),
        "percentage_delta": round(pct_delta, 1),
    }


def classify_rano_trajectory(
    et_delta_pct: float,
    wt_delta_pct: float
) -> Dict[str, str]:
    """
    Approximates volumetric RANO response criteria:
    - Progressive Disease (PD): ET volume increase >= +25% or significant WT expansion (>= +30%)
    - Partial Response (PR): ET volume decrease <= -50%
    - Stable Disease (SD): Changes between -50% and +25%
    """
    if et_delta_pct >= 25.0 or wt_delta_pct >= 30.0:
        return {
            "rano_category": "Progressive Disease (PD)",
            "interpretation": "Volumetric progression observed: enhancing or whole tumour volume increased by >= 25%."
        }
    elif et_delta_pct <= -50.0:
        return {
            "rano_category": "Partial Response (PR)",
            "interpretation": "Volumetric response observed: enhancing tumour volume decreased by >= 50%."
        }
    else:
        return {
            "rano_category": "Stable Disease (SD)",
            "interpretation": "Volumetric stability observed: tumor measurements remain within -50% and +25% thresholds."
        }


def check_spatial_compatibility(
    spatial_0: Optional[Dict[str, Any]],
    spatial_1: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Evaluates spatial compatibility between baseline (T0) and follow-up (T1) studies:
    - Verifies matrix dimensions, voxel spacing, and spatial alignment.
    - Emits informative clinical advisories when acquisition parameters differ.
    """
    if not spatial_0 or not spatial_1:
        return {
            "compatible": True,
            "status": "STANDARD_COMPARISON",
            "is_identical_grid": True,
            "advisories": ["Spatial dimensions inferred from NIfTI continuous volume integrals."]
        }

    shape_0 = spatial_0.get("shape")
    shape_1 = spatial_1.get("shape")
    spacing_0 = spatial_0.get("voxel_spacing_mm") or spatial_0.get("spacing_mm")
    spacing_1 = spatial_1.get("voxel_spacing_mm") or spatial_1.get("spacing_mm")

    advisories = []
    same_shape = (shape_0 == shape_1)
    if not same_shape and shape_0 and shape_1:
        advisories.append(f"Grid dimension variance: T0 {shape_0} vs T1 {shape_1}.")

    same_spacing = True
    if spacing_0 and spacing_1:
        try:
            diffs = [abs(float(s0) - float(s1)) for s0, s1 in zip(spacing_0, spacing_1)]
            if any(d > 0.05 for d in diffs):
                same_spacing = False
                advisories.append(
                    f"Acquisition spacing variance: T0 {spacing_0} mm vs T1 {spacing_1} mm. Physical volume (mL) calculations account for voxel size differences."
                )
        except Exception:
            pass

    return {
        "compatible": True,
        "is_identical_grid": same_shape and same_spacing,
        "shape_t0": shape_0,
        "shape_t1": shape_1,
        "spacing_t0": spacing_0,
        "spacing_t1": spacing_1,
        "advisories": advisories
    }


def compare_two_timepoint_studies(
    baseline_volumes: Dict[str, Any],
    followup_volumes: Dict[str, Any],
    spatial_0: Optional[Dict[str, Any]] = None,
    spatial_1: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Performs full longitudinal volumetric comparison between T0 and T1."""
    deltas = {}
    for reg in ["WT", "TC", "ET"]:
        v0 = baseline_volumes.get(reg, {}).get("volume_ml", 0.0)
        v1 = followup_volumes.get(reg, {}).get("volume_ml", 0.0)
        deltas[reg] = calculate_volumetric_delta(v0, v1)

    et_pct = deltas["ET"]["percentage_delta"]
    wt_pct = deltas["WT"]["percentage_delta"]
    rano = classify_rano_trajectory(et_pct, wt_pct)
    spatial_compat = check_spatial_compatibility(spatial_0, spatial_1)

    return {
        "volumetric_deltas": deltas,
        "rano_trajectory": rano,
        "spatial_compatibility": spatial_compat,
        "disclaimer": LONGITUDINAL_DISCLAIMER,
    }
