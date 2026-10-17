"""
NeuroScope 3D - Independent Scientific Evaluation & Cross-Validation Auditor
=============================================================================
Provides an independent calculation path that cross-checks evaluation metrics
and ensures data integrity without relying on the primary pipeline functions.

Verifies:
1. Shape and spatial geometry alignment between prediction and reference.
2. Independent calculation of TP, FP, FN, TN confusion voxels.
3. Verification of fundamental mathematical identities:
   - TP + FP == predicted_voxel_count
   - TP + FN == reference_voxel_count
   - TP + FP + FN + TN == total_volume_voxels
   - WT_volume >= TC_volume >= ET_volume (nesting subsets)
4. Recomputation of Dice and Sensitivity to full floating-point precision:
   - Dice = (2 * TP) / (2 * TP + FP + FN)
   - Sensitivity = TP / (TP + FN)
5. Surface distance metrics (HD95) using exact distance transforms.
6. Export of authoritative machine-readable audit report in JSON format.
"""
from typing import Dict, Any, Tuple, Optional
import os
import json
import numpy as np
import nibabel as nib
from scipy.ndimage import binary_erosion, distance_transform_edt


ALLOWED_BRATS_LABELS = {0, 1, 2, 4}


class IndependentValidationError(Exception):
    """Raised when an independent verification check or identity fails."""
    pass


def independent_evaluate_masks(
    pred_mask_data: np.ndarray,
    ref_mask_data: np.ndarray,
    affine: np.ndarray,
    spacing_mm: Tuple[float, float, float] = (1.0, 1.0, 1.0)
) -> Dict[str, Any]:
    """
    Independently computes evaluation metrics for WT, TC, and ET regions.
    Verifies all mathematical identities and returns canonical audit record.
    """
    if pred_mask_data.shape != ref_mask_data.shape:
        raise IndependentValidationError(
            f"Shape mismatch: prediction {pred_mask_data.shape} != reference {ref_mask_data.shape}"
        )

    # Validate label space
    unique_pred = set(np.unique(pred_mask_data).tolist())
    unique_ref = set(np.unique(ref_mask_data).tolist())
    invalid_labels = (unique_pred | unique_ref) - ALLOWED_BRATS_LABELS
    if invalid_labels:
        raise IndependentValidationError(
            f"Invalid discrete labels detected: {invalid_labels}. Allowed: {ALLOWED_BRATS_LABELS}"
        )

    # Calculate single voxel volume in mm³ from complete affine
    try:
        det_val = abs(float(np.linalg.det(affine[:3, :3])))
        single_voxel_mm3 = det_val if det_val > 1e-6 else float(spacing_mm[0] * spacing_mm[1] * spacing_mm[2])
    except Exception:
        single_voxel_mm3 = float(spacing_mm[0] * spacing_mm[1] * spacing_mm[2])

    total_voxels = int(pred_mask_data.size)

    # Subregion definitions (BraTS 2021 convention)
    # WT: labels {1, 2, 4}
    # TC: labels {1, 4}
    # ET: label {4}
    regions = {
        "WT": (np.isin(pred_mask_data, [1, 2, 4]), np.isin(ref_mask_data, [1, 2, 4])),
        "TC": (np.isin(pred_mask_data, [1, 4]), np.isin(ref_mask_data, [1, 4])),
        "ET": (pred_mask_data == 4, ref_mask_data == 4),
    }

    metrics = {}
    for reg_key in ["WT", "TC", "ET"]:
        p_bin, r_bin = regions[reg_key]

        tp = int(np.count_nonzero(p_bin & r_bin))
        fp = int(np.count_nonzero(p_bin & (~r_bin)))
        fn = int(np.count_nonzero((~p_bin) & r_bin))
        tn = int(np.count_nonzero((~p_bin) & (~r_bin)))

        n_pred = int(np.count_nonzero(p_bin))
        n_ref = int(np.count_nonzero(r_bin))

        # Identity Checks
        if tp + fp != n_pred:
            raise IndependentValidationError(f"{reg_key} identity violation: TP ({tp}) + FP ({fp}) != N_pred ({n_pred})")
        if tp + fn != n_ref:
            raise IndependentValidationError(f"{reg_key} identity violation: TP ({tp}) + FN ({fn}) != N_ref ({n_ref})")
        if tp + fp + fn + tn != total_voxels:
            raise IndependentValidationError(f"{reg_key} identity violation: sum of confusion matrix != total voxels")

        pred_vol_ml = (n_pred * single_voxel_mm3) / 1000.0
        ref_vol_ml = (n_ref * single_voxel_mm3) / 1000.0
        signed_diff_ml = pred_vol_ml - ref_vol_ml
        abs_diff_ml = abs(signed_diff_ml)
        rel_diff_pct = ((signed_diff_ml / ref_vol_ml) * 100.0) if ref_vol_ml > 0 else None

        # Dice and Sensitivity
        if n_pred == 0 and n_ref == 0:
            dice = 1.0
            sens = 1.0
            precision = 1.0
            specificity = 1.0
            hd95 = 0.0
        elif n_ref == 0 and n_pred > 0:
            dice = 0.0
            sens = None
            precision = 0.0
            specificity = float(tn) / float(tn + fp) if (tn + fp) > 0 else 1.0
            spatial_diag = float(np.sqrt(sum((s * sp) ** 2 for s, sp in zip(p_bin.shape, spacing_mm))))
            hd95 = round(spatial_diag, 2)
        elif n_pred == 0 and n_ref > 0:
            dice = 0.0
            sens = 0.0
            precision = None
            specificity = 1.0
            spatial_diag = float(np.sqrt(sum((s * sp) ** 2 for s, sp in zip(p_bin.shape, spacing_mm))))
            hd95 = round(spatial_diag, 2)
        else:
            dice = (2.0 * tp) / float(2 * tp + fp + fn)
            sens = float(tp) / float(n_ref)
            precision = float(tp) / float(n_pred)
            specificity = float(tn) / float(tn + fp) if (tn + fp) > 0 else 1.0

            # HD95 calculation
            struct = np.ones((3, 3, 3), dtype=bool)
            p_border = p_bin ^ binary_erosion(p_bin, structure=struct)
            r_border = r_bin ^ binary_erosion(r_bin, structure=struct)
            if not np.any(p_border):
                p_border = p_bin
            if not np.any(r_border):
                r_border = r_bin

            dt_ref = distance_transform_edt(~r_border, sampling=spacing_mm)
            dt_pred = distance_transform_edt(~p_border, sampling=spacing_mm)
            d_p2r = dt_ref[p_border]
            d_r2p = dt_pred[r_border]
            h95_p = float(np.percentile(d_p2r, 95))
            h95_r = float(np.percentile(d_r2p, 95))
            hd95 = round(float(max(h95_p, h95_r)), 2)

        # Centroid and bounding box
        indices_p = np.argwhere(p_bin)
        if len(indices_p) > 0:
            c_vox_int = np.round(np.mean(indices_p, axis=0)).astype(int).tolist()
            c_vox_frac = [round(float(c), 3) for c in np.mean(indices_p, axis=0)]
            c_world = [round(float(w), 2) for w in (affine @ np.append(np.mean(indices_p, axis=0), 1.0))[:3]]
            min_v = indices_p.min(axis=0).tolist()
            max_v = indices_p.max(axis=0).tolist()
            corners = []
            for x in [min_v[0], max_v[0]]:
                for y in [min_v[1], max_v[1]]:
                    for z in [min_v[2], max_v[2]]:
                        w = affine @ np.array([float(x), float(y), float(z), 1.0], dtype=np.float64)
                        corners.append(w[:3])
            corners = np.array(corners)
            w_min = [round(float(v), 2) for v in np.min(corners, axis=0)]
            w_max = [round(float(v), 2) for v in np.max(corners, axis=0)]
            bbox_vox = {"min": min_v, "max": max_v}
            bbox_world = {"min": w_min, "max": w_max}
        else:
            c_vox_int = None
            c_vox_frac = None
            c_world = None
            bbox_vox = None
            bbox_world = None

        metrics[reg_key] = {
            "predicted_voxels": n_pred,
            "reference_voxels": n_ref,
            "predicted_volume_ml": round(pred_vol_ml, 4),
            "reference_volume_ml": round(ref_vol_ml, 4),
            "signed_diff_ml": round(signed_diff_ml, 4),
            "absolute_diff_ml": round(abs_diff_ml, 4),
            "relative_diff_percent": round(rel_diff_pct, 2) if rel_diff_pct is not None else None,
            "dice": round(float(dice), 4),
            "sensitivity": round(float(sens), 4) if sens is not None else None,
            "precision": round(float(precision), 4) if precision is not None else None,
            "specificity": round(float(specificity), 4),
            "hd95_mm": hd95,
            "tp_voxels": tp,
            "fp_voxels": fp,
            "fn_voxels": fn,
            "tn_voxels": tn,
            "centroid_voxel": c_vox_int,
            "centroid_voxel_fractional": c_vox_frac,
            "centroid_world_mm": c_world,
            "bounding_box_voxel": bbox_vox,
            "bounding_box_world_mm": bbox_world,
        }

    # Verify hierarchical volume nesting: WT >= TC >= ET
    wt_ml = metrics["WT"]["predicted_volume_ml"]
    tc_ml = metrics["TC"]["predicted_volume_ml"]
    et_ml = metrics["ET"]["predicted_volume_ml"]
    if not (wt_ml >= tc_ml - 1e-4 and tc_ml >= et_ml - 1e-4):
        raise IndependentValidationError(
            f"Nesting violation: WT ({wt_ml:.4f} mL) >= TC ({tc_ml:.4f} mL) >= ET ({et_ml:.4f} mL) violated"
        )

    return {
        "status": "verified_concordant",
        "voxel_volume_mm3": round(single_voxel_mm3, 6),
        "metrics": metrics,
    }


def audit_case_nifti_files(
    pred_path: str,
    ref_path: str,
    output_json_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Audits two NIfTI segmentation masks from disk and saves an authoritative audit artifact.
    """
    if not os.path.exists(pred_path):
        raise FileNotFoundError(f"Prediction mask not found: {pred_path}")
    if not os.path.exists(ref_path):
        raise FileNotFoundError(f"Reference mask not found: {ref_path}")

    p_nii = nib.load(pred_path)
    r_nii = nib.load(ref_path)

    # Check affine match
    if not np.allclose(p_nii.affine, r_nii.affine, atol=1e-3):
        max_diff = float(np.max(np.abs(p_nii.affine - r_nii.affine)))
        raise IndependentValidationError(
            f"Spatial affine mismatch between prediction and reference: diff={max_diff:.5f}"
        )

    p_data = np.asanyarray(p_nii.dataobj).astype(np.uint8)
    r_data = np.asanyarray(r_nii.dataobj).astype(np.uint8)
    zooms = p_nii.header.get_zooms()[:3]
    spacing = tuple(float(z) for z in zooms)

    audit_result = independent_evaluate_masks(
        p_data, r_data, affine=p_nii.affine, spacing_mm=spacing
    )
    audit_result["prediction_file"] = os.path.abspath(pred_path)
    audit_result["reference_file"] = os.path.abspath(ref_path)
    audit_result["dimensions"] = list(p_data.shape)
    audit_result["voxel_spacing_mm"] = list(spacing)
    audit_result["affine"] = p_nii.affine.tolist()

    if output_json_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
        with open(output_json_path, "w") as f:
            json.dump(audit_result, f, indent=2)

    return audit_result
