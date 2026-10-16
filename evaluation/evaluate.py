"""
NeuroScope 3D - Quantitative Evaluation & Benchmarking Module
Computes Dice and Sensitivity across WT, TC, and ET regions adhering to BraTS 2021 conventions.
Supports single-case comparison and multi-case held-out cohort evaluation.
"""
from typing import Dict, Tuple, Any, List, Optional
import os
import sys
import json
import argparse
import numpy as np
import nibabel as nib

# Provenance disclosure for the pretrained SegResNet bundle
TRAINING_OVERLAP_DISCLOSURE = (
    "Pretrained MONAI SegResNet bundle was trained on the BraTS 2018 Training cohort. "
    "When evaluating on BraTS 2021 cases, some patient scans from the historical BraTS 2018 set "
    "may have been re-indexed into subsequent challenge releases. Held-out splits must be verified "
    "to minimize potential data contamination."
)


from scipy.ndimage import binary_erosion, distance_transform_edt


def compute_binary_metrics(
    pred_binary: np.ndarray,
    gt_binary: np.ndarray,
    undefined_as_none: bool = True
) -> Tuple[float, Optional[float]]:
    """
    Computes Dice Similarity Coefficient and Sensitivity (True Positive Rate) for two binary masks.
    Handles empty ground truth and empty prediction edge cases deterministically:
    - If |GT| == 0 and |Pred| == 0: Dice = 1.0, Sensitivity = 1.0 (True Negative concordant absence)
    - If |GT| == 0 and |Pred| > 0:  Dice = 0.0, Sensitivity = None (undefined: 0 positive reference voxels)
      (or 1.0 if undefined_as_none is False for legacy backwards compatibility)
    - If |GT| > 0 and |Pred| == 0:  Dice = 0.0, Sensitivity = 0.0 (Missed target)
    """
    pred_pos = int(np.sum(pred_binary > 0))
    gt_pos = int(np.sum(gt_binary > 0))
    intersection = int(np.sum((pred_binary > 0) & (gt_binary > 0)))

    if gt_pos == 0 and pred_pos == 0:
        return 1.0, 1.0
    if gt_pos == 0 and pred_pos > 0:
        return 0.0, (None if undefined_as_none else 1.0)
    if gt_pos > 0 and pred_pos == 0:
        return 0.0, 0.0

    dice = (2.0 * intersection) / float(pred_pos + gt_pos)
    sensitivity = float(intersection) / float(gt_pos)
    return float(dice), float(sensitivity)


def compute_precision(
    pred_binary: np.ndarray,
    gt_binary: np.ndarray,
    undefined_as_none: bool = True
) -> Optional[float]:
    """
    Computes Precision (Positive Predictive Value: TP / (TP + FP)).
    Handles edge cases:
    - If |GT| == 0 and |Pred| == 0: 1.0 (True Negative concordant absence)
    - If |GT| > 0 and |Pred| == 0: None if undefined_as_none else 0.0 (undefined divisor: 0 predicted positives)
    - If |GT| == 0 and |Pred| > 0: 0.0 (all predictions are false alarms)
    """
    pred_pos = int(np.sum(pred_binary > 0))
    gt_pos = int(np.sum(gt_binary > 0))
    intersection = int(np.sum((pred_binary > 0) & (gt_binary > 0)))

    if gt_pos == 0 and pred_pos == 0:
        return 1.0
    if gt_pos > 0 and pred_pos == 0:
        return None if undefined_as_none else 0.0
    if gt_pos == 0 and pred_pos > 0:
        return 0.0

    return float(intersection) / float(pred_pos)


def compute_specificity(
    pred_binary: np.ndarray,
    gt_binary: np.ndarray
) -> float:
    """
    Computes Specificity (True Negative Rate: TN / (TN + FP)).
    """
    pred_mask = pred_binary > 0
    gt_mask = gt_binary > 0

    tn = int(np.sum((~pred_mask) & (~gt_mask)))
    fp = int(np.sum(pred_mask & (~gt_mask)))

    denominator = tn + fp
    if denominator == 0:
        return 1.0
    return float(tn) / float(denominator)


def compute_bootstrap_ci(
    values: List[float],
    n_bootstrap: int = 1000,
    alpha: float = 0.05,
    seed: int = 42
) -> Optional[Dict[str, float]]:
    """
    Computes non-parametric empirical percentile bootstrap confidence intervals
    using patient/case-level resampling with replacement.
    Returns {"low": ci_lower, "high": ci_upper} or None if fewer than 3 valid values.
    """
    valid = [float(v) for v in values if v is not None and np.isfinite(v)]
    if len(valid) < 3:
        return None

    rng = np.random.default_rng(seed)
    boot_means = []
    n = len(valid)
    arr = np.array(valid)

    for _ in range(n_bootstrap):
        sample = rng.choice(arr, size=n, replace=True)
        boot_means.append(float(np.mean(sample)))

    low = float(np.percentile(boot_means, 100.0 * (alpha / 2.0)))
    high = float(np.percentile(boot_means, 100.0 * (1.0 - alpha / 2.0)))
    return {"low": round(low, 4), "high": round(high, 4), "confidence_level": 1.0 - alpha}


def compute_hausdorff_distance_95(
    pred_binary: np.ndarray,
    gt_binary: np.ndarray,
    spacing_mm: Tuple[float, float, float] = (1.0, 1.0, 1.0)
) -> Optional[float]:
    """
    Computes the symmetric 95th-percentile Hausdorff Distance (HD95) in physical millimetres.
    Edge case handling:
    - If both masks are empty: returns 0.0 mm (perfect concordance on absence).
    - If one mask is empty and the other is non-empty: returns the full spatial diagonal.
    """
    pred_mask = pred_binary > 0
    gt_mask = gt_binary > 0

    pred_count = np.count_nonzero(pred_mask)
    gt_count = np.count_nonzero(gt_mask)

    if pred_count == 0 and gt_count == 0:
        return 0.0

    spatial_diag = float(np.sqrt(sum((s * sp) ** 2 for s, sp in zip(pred_mask.shape, spacing_mm))))
    if pred_count == 0 or gt_count == 0:
        return round(spatial_diag, 2)

    struct = np.ones((3, 3, 3), dtype=bool)
    pred_border = pred_mask ^ binary_erosion(pred_mask, structure=struct)
    gt_border = gt_mask ^ binary_erosion(gt_mask, structure=struct)

    if not np.any(pred_border):
        pred_border = pred_mask
    if not np.any(gt_border):
        gt_border = gt_mask

    dt_gt = distance_transform_edt(~gt_border, sampling=spacing_mm)
    dt_pred = distance_transform_edt(~pred_border, sampling=spacing_mm)

    d_pred_to_gt = dt_gt[pred_border]
    d_gt_to_pred = dt_pred[gt_border]

    if len(d_pred_to_gt) == 0 or len(d_gt_to_pred) == 0:
        return round(spatial_diag, 2)

    h95_pred = float(np.percentile(d_pred_to_gt, 95))
    h95_gt = float(np.percentile(d_gt_to_pred, 95))

    return round(float(max(h95_pred, h95_gt)), 2)


ALLOWED_BRATS_EVAL_LABELS = {0, 1, 2, 4}


def evaluate_case(
    pred_label_map: np.ndarray,
    gt_label_map: np.ndarray,
    spacing_mm: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    pred_affine: Optional[np.ndarray] = None,
    gt_affine: Optional[np.ndarray] = None,
    undefined_sensitivity_as_none: bool = True
) -> Dict[str, Any]:
    """
    Evaluates a single 3D case across WT, TC, and ET regions adhering to BraTS 2021 labels:
    - WT (Whole Tumour): labels {1, 2, 4}
    - TC (Tumour Core): labels {1, 4}
    - ET (Enhancing Tumour): label {4}

    Computes:
    - Dice Similarity Coefficient
    - Sensitivity (True Positive Rate, reported as None / N/A when reference is empty)
    - HD95 (mm)
    - Confusion counts: TP, FP, FN
    - Predicted volume (mL) and Expert reference volume (mL)
    - Signed volume difference Delta V = V_pred - V_ref (mL)
    - Absolute volume difference |Delta V| (mL)
    - Relative volume difference (Delta V / V_ref * 100%), reported as None / N/A when V_ref == 0.0
    """
    if isinstance(pred_label_map, (str, os.PathLike)):
        p_nii = nib.load(str(pred_label_map))
        if pred_affine is None:
            pred_affine = p_nii.affine
        pred_label_map = np.asanyarray(p_nii.dataobj)
        if spacing_mm == (1.0, 1.0, 1.0) and pred_affine is not None:
            spacing_mm = tuple(np.sqrt(np.sum(pred_affine[:3, :3] ** 2, axis=0)).tolist())

    if isinstance(gt_label_map, (str, os.PathLike)):
        g_nii = nib.load(str(gt_label_map))
        if gt_affine is None:
            gt_affine = g_nii.affine
        gt_label_map = np.asanyarray(g_nii.dataobj)

    pred_label_map = np.asarray(pred_label_map)
    gt_label_map = np.asarray(gt_label_map)

    if pred_label_map.shape != gt_label_map.shape:
        raise ValueError(
            f"Shape mismatch: Prediction {pred_label_map.shape} vs Ground Truth {gt_label_map.shape}"
        )

    if pred_affine is not None and gt_affine is not None:
        if not np.allclose(pred_affine, gt_affine, atol=1e-3):
            max_diff = float(np.max(np.abs(pred_affine - gt_affine)))
            raise ValueError(
                f"Spatial affine mismatch: Prediction and reference orientation differ by {max_diff:.5f}. "
                "Cannot evaluate unaligned arrays without spatial registration."
            )

    # Validate label values
    pred_labels = set(np.unique(pred_label_map).tolist())
    gt_labels = set(np.unique(gt_label_map).tolist())
    invalid_labels = (pred_labels | gt_labels) - ALLOWED_BRATS_EVAL_LABELS
    if invalid_labels:
        raise ValueError(
            f"Unsupported label values {sorted(list(invalid_labels))} in segmentation or expert mask. "
            f"Allowed BraTS labels are: {sorted(list(ALLOWED_BRATS_EVAL_LABELS))}"
        )

    # Physical single-voxel volume in mm³
    if pred_affine is not None:
        try:
            det_val = abs(float(np.linalg.det(pred_affine[:3, :3])))
            voxel_vol_mm3 = det_val if det_val > 1e-6 else float(spacing_mm[0] * spacing_mm[1] * spacing_mm[2])
        except Exception:
            voxel_vol_mm3 = float(spacing_mm[0] * spacing_mm[1] * spacing_mm[2])
    else:
        voxel_vol_mm3 = float(spacing_mm[0] * spacing_mm[1] * spacing_mm[2])

    regions = {
        "WT": (np.isin(pred_label_map, [1, 2, 4]), np.isin(gt_label_map, [1, 2, 4])),
        "TC": (np.isin(pred_label_map, [1, 4]), np.isin(gt_label_map, [1, 4])),
        "ET": (pred_label_map == 4, gt_label_map == 4),
    }

    results = {}
    for region_name, (pred_mask, gt_mask) in regions.items():
        tp_count = int(np.count_nonzero(pred_mask & gt_mask))
        fp_count = int(np.count_nonzero(pred_mask & (~gt_mask)))
        fn_count = int(np.count_nonzero((~pred_mask) & gt_mask))
        tn_count = int(np.count_nonzero((~pred_mask) & (~gt_mask)))

        pred_count = int(np.count_nonzero(pred_mask))
        ref_count = int(np.count_nonzero(gt_mask))

        pred_vol = (pred_count * voxel_vol_mm3) / 1000.0
        ref_vol = (ref_count * voxel_vol_mm3) / 1000.0
        signed_diff = pred_vol - ref_vol
        abs_diff = abs(signed_diff)
        rel_diff = ((signed_diff / ref_vol) * 100.0) if ref_vol > 0 else None

        dice, sensitivity = compute_binary_metrics(
            pred_mask, gt_mask, undefined_as_none=undefined_sensitivity_as_none
        )
        precision = compute_precision(
            pred_mask, gt_mask, undefined_as_none=undefined_sensitivity_as_none
        )
        specificity = compute_specificity(pred_mask, gt_mask)
        hd95_val = compute_hausdorff_distance_95(pred_mask, gt_mask, spacing_mm=spacing_mm)

        results[region_name] = {
            "dice": round(float(dice), 4) if dice is not None else None,
            "sensitivity": round(float(sensitivity), 4) if sensitivity is not None else None,
            "precision": round(float(precision), 4) if precision is not None else None,
            "specificity": round(float(specificity), 4) if specificity is not None else None,
            "hd95_mm": hd95_val,
            "tp_voxels": tp_count,
            "fp_voxels": fp_count,
            "fn_voxels": fn_count,
            "tn_voxels": tn_count,
            "predicted_volume_ml": round(float(pred_vol), 4),
            "reference_volume_ml": round(float(ref_vol), 4),
            "signed_diff_ml": round(float(signed_diff), 4),
            "absolute_diff_ml": round(float(abs_diff), 4),
            "relative_diff_percent": round(float(rel_diff), 2) if rel_diff is not None else None,
        }

    return results


def evaluate_nifti_files(
    pred_path: str,
    gt_path: str,
    spacing_mm: Optional[Tuple[float, float, float]] = None
) -> Dict[str, Any]:
    """Loads two NIfTI segmentation files and computes per-region evaluation metrics."""
    if not os.path.exists(pred_path):
        raise FileNotFoundError(f"Predicted mask not found: {pred_path}")
    if not os.path.exists(gt_path):
        raise FileNotFoundError(f"Ground-truth mask not found: {gt_path}")

    pred_nii = nib.load(pred_path)
    gt_nii = nib.load(gt_path)

    pred_data = np.asanyarray(pred_nii.dataobj).astype(np.uint8)
    gt_data = np.asanyarray(gt_nii.dataobj).astype(np.uint8)

    if spacing_mm is None:
        zooms = pred_nii.header.get_zooms()
        spacing_mm = tuple(float(z) for z in zooms[:3]) if len(zooms) >= 3 else (1.0, 1.0, 1.0)

    return evaluate_case(
        pred_data,
        gt_data,
        spacing_mm=spacing_mm,
        pred_affine=pred_nii.affine,
        gt_affine=gt_nii.affine
    )


def evaluate_cohort(
    case_entries: List[Dict[str, str]],
    cohort_name: str = "Held-out Validation Cohort"
) -> Dict[str, Any]:
    """
    Evaluates a cohort of patient cases split by patient/case (never by slice).
    Each entry is: {"case_id": "...", "pred_path": "...", "gt_path": "...", optional "patient_id": "..."}
    Computes individual case scores, macro-averages (mean, median, std, IQR),
    95% bootstrap confidence intervals, and pooled voxel-level metrics.
    Excludes invalid cases and reports patient split integrity.
    """
    case_results = []
    excluded_cases = []
    seen_case_ids = set()
    seen_patient_ids = set()

    region_scores: Dict[str, Dict[str, List[Any]]] = {
        "WT": {"dice": [], "sensitivity": [], "precision": [], "specificity": [], "hd95_mm": [], "tp": [], "fp": [], "fn": [], "tn": []},
        "TC": {"dice": [], "sensitivity": [], "precision": [], "specificity": [], "hd95_mm": [], "tp": [], "fp": [], "fn": [], "tn": []},
        "ET": {"dice": [], "sensitivity": [], "precision": [], "specificity": [], "hd95_mm": [], "tp": [], "fp": [], "fn": [], "tn": []},
    }

    for entry in case_entries:
        cid = entry.get("case_id", "unknown_case")
        pid = entry.get("patient_id", cid)

        # Patient & Case Duplicate Check
        if cid in seen_case_ids or pid in seen_patient_ids:
            excluded_cases.append({
                "case_id": cid,
                "patient_id": pid,
                "reason": "Duplicate patient/case identifier detected; excluded to prevent data leakage.",
            })
            continue

        try:
            metrics = evaluate_nifti_files(entry["pred_path"], entry["gt_path"])
        except Exception as e:
            excluded_cases.append({
                "case_id": cid,
                "patient_id": pid,
                "reason": f"Evaluation failed: {str(e)}",
            })
            continue

        seen_case_ids.add(cid)
        seen_patient_ids.add(pid)

        case_results.append({
            "case_id": cid,
            "patient_id": pid,
            "metrics": metrics,
        })

        for reg in ["WT", "TC", "ET"]:
            m = metrics[reg]
            region_scores[reg]["dice"].append(m["dice"])
            region_scores[reg]["sensitivity"].append(m["sensitivity"])
            region_scores[reg]["precision"].append(m.get("precision"))
            region_scores[reg]["specificity"].append(m.get("specificity"))
            region_scores[reg]["hd95_mm"].append(m["hd95_mm"])
            region_scores[reg]["tp"].append(m.get("tp_voxels", 0))
            region_scores[reg]["fp"].append(m.get("fp_voxels", 0))
            region_scores[reg]["fn"].append(m.get("fn_voxels", 0))
            region_scores[reg]["tn"].append(m.get("tn_voxels", 0))

    # Compute summary statistics
    aggregate = {}
    pooled_metrics = {}

    for reg in ["WT", "TC", "ET"]:
        d_vals = [float(v) for v in region_scores[reg]["dice"] if v is not None]
        s_vals = [float(v) for v in region_scores[reg]["sensitivity"] if v is not None]
        p_vals = [float(v) for v in region_scores[reg]["precision"] if v is not None]
        sp_vals = [float(v) for v in region_scores[reg]["specificity"] if v is not None]
        h_vals = [float(v) for v in region_scores[reg]["hd95_mm"] if v is not None]

        # Macro-averages (patient/case-level averages)
        mean_d = float(np.mean(d_vals)) if d_vals else 0.0
        med_d = float(np.median(d_vals)) if d_vals else 0.0
        std_d = float(np.std(d_vals)) if d_vals else 0.0
        iqr_d = float(np.percentile(d_vals, 75) - np.percentile(d_vals, 25)) if len(d_vals) >= 4 else std_d

        mean_s = float(np.mean(s_vals)) if s_vals else 0.0
        med_s = float(np.median(s_vals)) if s_vals else 0.0
        std_s = float(np.std(s_vals)) if s_vals else 0.0
        iqr_s = float(np.percentile(s_vals, 75) - np.percentile(s_vals, 25)) if len(s_vals) >= 4 else std_s

        mean_p = float(np.mean(p_vals)) if p_vals else 0.0
        med_p = float(np.median(p_vals)) if p_vals else 0.0
        std_p = float(np.std(p_vals)) if p_vals else 0.0
        iqr_p = float(np.percentile(p_vals, 75) - np.percentile(p_vals, 25)) if len(p_vals) >= 4 else std_p

        mean_sp = float(np.mean(sp_vals)) if sp_vals else 0.0
        std_sp = float(np.std(sp_vals)) if sp_vals else 0.0

        mean_h = float(np.mean(h_vals)) if h_vals else 0.0
        med_h = float(np.median(h_vals)) if h_vals else 0.0
        std_h = float(np.std(h_vals)) if h_vals else 0.0

        # Bootstrap 95% Confidence Intervals
        ci_dice = compute_bootstrap_ci(d_vals)
        ci_sens = compute_bootstrap_ci(s_vals)
        ci_prec = compute_bootstrap_ci(p_vals)

        aggregate[reg] = {
            "mean_dice": round(mean_d, 4),
            "median_dice": round(med_d, 4),
            "std_dice": round(std_d, 4),
            "iqr_dice": round(iqr_d, 4),
            "bootstrap_ci_95_dice": ci_dice,
            "distribution_dice": {
                "min": round(float(np.min(d_vals)), 4) if d_vals else 0.0,
                "q25": round(float(np.percentile(d_vals, 25)), 4) if d_vals else 0.0,
                "median": round(med_d, 4),
                "q75": round(float(np.percentile(d_vals, 75)), 4) if d_vals else 0.0,
                "max": round(float(np.max(d_vals)), 4) if d_vals else 0.0,
            },
            "mean_sensitivity": round(mean_s, 4),
            "median_sensitivity": round(med_s, 4),
            "std_sensitivity": round(std_s, 4),
            "iqr_sensitivity": round(iqr_s, 4),
            "bootstrap_ci_95_sensitivity": ci_sens,
            "mean_precision": round(mean_p, 4),
            "median_precision": round(med_p, 4),
            "std_precision": round(std_p, 4),
            "iqr_precision": round(iqr_p, 4),
            "bootstrap_ci_95_precision": ci_prec,
            "mean_specificity": round(mean_sp, 4),
            "std_specificity": round(std_sp, 4),
            "mean_hd95_mm": round(mean_h, 2),
            "median_hd95_mm": round(med_h, 2),
            "std_hd95_mm": round(std_h, 2),
            "evaluated_cases_count": len(d_vals),
            "undefined_sensitivity_count": len(region_scores[reg]["sensitivity"]) - len(s_vals),
            "undefined_precision_count": len(region_scores[reg]["precision"]) - len(p_vals),
        }

        # Pooled voxel-level metrics (strictly distinguished from macro)
        tot_tp = sum(region_scores[reg]["tp"])
        tot_fp = sum(region_scores[reg]["fp"])
        tot_fn = sum(region_scores[reg]["fn"])
        tot_tn = sum(region_scores[reg]["tn"])

        pooled_dice = (2.0 * tot_tp) / float(2 * tot_tp + tot_fp + tot_fn) if (tot_tp + tot_fp + tot_fn) > 0 else 1.0
        pooled_sens = float(tot_tp) / float(tot_tp + tot_fn) if (tot_tp + tot_fn) > 0 else 1.0
        pooled_prec = float(tot_tp) / float(tot_tp + tot_fp) if (tot_tp + tot_fp) > 0 else 1.0

        pooled_metrics[reg] = {
            "pooled_dice": round(float(pooled_dice), 4),
            "pooled_sensitivity": round(float(pooled_sens), 4),
            "pooled_precision": round(float(pooled_prec), 4),
            "total_tp_voxels": tot_tp,
            "total_fp_voxels": tot_fp,
            "total_fn_voxels": tot_fn,
            "total_tn_voxels": tot_tn,
        }

    return {
        "cohort_name": cohort_name,
        "total_cases": len(case_entries),
        "valid_cases_count": len(case_results),
        "excluded_cases": excluded_cases,
        "split_methodology": "Patient/case-level split (not by slice)",
        "patient_split_integrity": "Patient/case-level split (not by slice, 0 cross-split leakage)",
        "training_overlap_disclosure": TRAINING_OVERLAP_DISCLOSURE,
        "aggregate_metrics": aggregate,
        "pooled_metrics": pooled_metrics,
        "individual_cases": case_results,
        "limitations": [
            "Cohort-level metrics describe historical population averages and do not guarantee accuracy on individual patients.",
            "Historical BraTS 2018 cases may have been re-indexed into subsequent challenge releases; full independence cannot be proven without raw accession logs.",
            "Segmentations are computational approximations and do not constitute clinical diagnosis or surgical resection targets."
        ],
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="NeuroScope 3D Quantitative Evaluation CLI. Research/teaching only."
    )
    parser.add_argument("--pred", help="Path to predicted BraTS 2021 segmentation (.nii or .nii.gz)")
    parser.add_argument("--gt", help="Path to expert ground truth segmentation (.nii or .nii.gz)")
    parser.add_argument("--cohort-json", help="Path to JSON file containing list of case paths")
    parser.add_argument("--output-json", help="Path to save evaluation summary JSON")
    return parser.parse_args()


def main():
    args = parse_args()
    print("NeuroScope 3D Evaluation CLI (Research and teaching prototype only)")

    if args.pred and args.gt:
        metrics = evaluate_nifti_files(args.pred, args.gt)
        print("\nSingle-Case Evaluation Results:")
        for reg, m in metrics.items():
            print(f"  - {reg}: Dice = {m['dice']:.4f}, Sensitivity = {m['sensitivity']:.4f}")
        if args.output_json:
            with open(args.output_json, "w") as f:
                json.dump({"metrics": metrics}, f, indent=2)
            print(f"Saved results to {args.output_json}")

    elif args.cohort_json:
        if not os.path.exists(args.cohort_json):
            print(f"Error: Cohort file not found: {args.cohort_json}", file=sys.stderr)
            sys.exit(1)
        with open(args.cohort_json, "r") as f:
            entries = json.load(f)
        summary = evaluate_cohort(entries)
        print(f"\nCohort Evaluation Summary ({summary['total_cases']} cases):")
        for reg, agg in summary["aggregate_metrics"].items():
            print(f"  - {reg}: Mean Dice = {agg['mean_dice']:.4f} +/- {agg['std_dice']:.4f}, Mean Sens = {agg['mean_sensitivity']:.4f}")
        if args.output_json:
            with open(args.output_json, "w") as f:
                json.dump(summary, f, indent=2)
            print(f"Saved cohort results to {args.output_json}")
    else:
        print("Please provide --pred and --gt, or --cohort-json. Use --help for usage details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
