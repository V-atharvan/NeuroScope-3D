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


def compute_binary_metrics(pred_binary: np.ndarray, gt_binary: np.ndarray) -> Tuple[float, float]:
    """
    Computes Dice Similarity Coefficient and Sensitivity (True Positive Rate) for two binary masks.
    Handles empty ground truth and empty prediction edge cases deterministically:
    - If |GT| == 0 and |Pred| == 0: Dice = 1.0, Sensitivity = 1.0 (True Negative agreement)
    - If |GT| == 0 and |Pred| > 0:  Dice = 0.0, Sensitivity = 1.0 (Penalized in Dice)
    - If |GT| > 0 and |Pred| == 0:  Dice = 0.0, Sensitivity = 0.0 (Missed target)
    """
    pred_pos = int(np.sum(pred_binary > 0))
    gt_pos = int(np.sum(gt_binary > 0))
    intersection = int(np.sum((pred_binary > 0) & (gt_binary > 0)))

    if gt_pos == 0 and pred_pos == 0:
        return 1.0, 1.0
    if gt_pos == 0 and pred_pos > 0:
        return 0.0, 1.0
    if gt_pos > 0 and pred_pos == 0:
        return 0.0, 0.0

    dice = (2.0 * intersection) / float(pred_pos + gt_pos)
    sensitivity = float(intersection) / float(gt_pos)
    return float(dice), float(sensitivity)


def evaluate_case(pred_label_map: np.ndarray, gt_label_map: np.ndarray) -> Dict[str, Dict[str, float]]:
    """
    Evaluates a single 3D case across WT, TC, and ET regions adhering to BraTS 2021 labels:
    - WT (Whole Tumour): labels {1, 2, 4}
    - TC (Tumour Core): labels {1, 4}
    - ET (Enhancing Tumour): label {4}
    """
    if pred_label_map.shape != gt_label_map.shape:
        raise ValueError(
            f"Shape mismatch: Prediction {pred_label_map.shape} vs Ground Truth {gt_label_map.shape}"
        )

    regions = {
        "WT": (np.isin(pred_label_map, [1, 2, 4]), np.isin(gt_label_map, [1, 2, 4])),
        "TC": (np.isin(pred_label_map, [1, 4]), np.isin(gt_label_map, [1, 4])),
        "ET": (pred_label_map == 4, gt_label_map == 4),
    }

    results = {}
    for region_name, (pred_mask, gt_mask) in regions.items():
        dice, sensitivity = compute_binary_metrics(pred_mask, gt_mask)
        results[region_name] = {
            "dice": round(float(dice), 4),
            "sensitivity": round(float(sensitivity), 4)
        }

    return results


def evaluate_nifti_files(pred_path: str, gt_path: str) -> Dict[str, Dict[str, float]]:
    """Loads two NIfTI segmentation files and computes per-region evaluation metrics."""
    if not os.path.exists(pred_path):
        raise FileNotFoundError(f"Predicted mask not found: {pred_path}")
    if not os.path.exists(gt_path):
        raise FileNotFoundError(f"Ground-truth mask not found: {gt_path}")

    pred_data = nib.load(pred_path).get_fdata().astype(np.uint8)
    gt_data = nib.load(gt_path).get_fdata().astype(np.uint8)
    return evaluate_case(pred_data, gt_data)


def evaluate_cohort(
    case_entries: List[Dict[str, str]],
    cohort_name: str = "Held-out Validation Cohort"
) -> Dict[str, Any]:
    """
    Evaluates a cohort of patient cases split by patient/case (never by slice).
    Each entry is: {"case_id": "...", "pred_path": "...", "gt_path": "..."}
    Computes individual case scores and aggregate statistics (mean +/- std).
    """
    case_results = []
    region_scores: Dict[str, Dict[str, List[float]]] = {
        "WT": {"dice": [], "sensitivity": []},
        "TC": {"dice": [], "sensitivity": []},
        "ET": {"dice": [], "sensitivity": []},
    }

    for entry in case_entries:
        cid = entry.get("case_id", "unknown_case")
        metrics = evaluate_nifti_files(entry["pred_path"], entry["gt_path"])
        case_results.append({
            "case_id": cid,
            "metrics": metrics,
        })

        for reg in ["WT", "TC", "ET"]:
            region_scores[reg]["dice"].append(metrics[reg]["dice"])
            region_scores[reg]["sensitivity"].append(metrics[reg]["sensitivity"])

    # Compute summary statistics
    aggregate = {}
    for reg in ["WT", "TC", "ET"]:
        d_vals = region_scores[reg]["dice"]
        s_vals = region_scores[reg]["sensitivity"]
        aggregate[reg] = {
            "mean_dice": round(float(np.mean(d_vals)), 4) if d_vals else 0.0,
            "std_dice": round(float(np.std(d_vals)), 4) if d_vals else 0.0,
            "mean_sensitivity": round(float(np.mean(s_vals)), 4) if s_vals else 0.0,
            "std_sensitivity": round(float(np.std(s_vals)), 4) if s_vals else 0.0,
        }

    return {
        "cohort_name": cohort_name,
        "total_cases": len(case_entries),
        "split_methodology": "Patient/case-level split (not by slice)",
        "training_overlap_disclosure": TRAINING_OVERLAP_DISCLOSURE,
        "aggregate_metrics": aggregate,
        "individual_cases": case_results,
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
