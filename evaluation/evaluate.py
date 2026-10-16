"""
NeuroScope 3D - Quantitative Evaluation Module
Computes Dice and Sensitivity across WT, TC, and ET regions adhering to BraTS 2021 conventions.
"""
from typing import Dict, Tuple, Any
import numpy as np


def compute_binary_metrics(pred_binary: np.ndarray, gt_binary: np.ndarray) -> Tuple[float, float]:
    """
    Computes Dice coefficient and Sensitivity for two binary masks.
    Handles empty ground truth and empty prediction edge cases deterministically.
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

    dice = (2.0 * intersection) / (pred_pos + gt_pos)
    sensitivity = float(intersection) / float(gt_pos)
    return float(dice), float(sensitivity)


def evaluate_case(pred_label_map: np.ndarray, gt_label_map: np.ndarray) -> Dict[str, Dict[str, float]]:
    """
    Evaluates a single case across WT, TC, and ET regions.
    - WT: labels {1, 2, 4}
    - TC: labels {1, 4}
    - ET: label {4}
    """
    regions = {
        "WT": (np.isin(pred_label_map, [1, 2, 4]), np.isin(gt_label_map, [1, 2, 4])),
        "TC": (np.isin(pred_label_map, [1, 4]), np.isin(gt_label_map, [1, 4])),
        "ET": (pred_label_map == 4, gt_label_map == 4),
    }

    results = {}
    for region_name, (pred_mask, gt_mask) in regions.items():
        dice, sensitivity = compute_binary_metrics(pred_mask, gt_mask)
        results[region_name] = {
            "dice": round(dice, 4),
            "sensitivity": round(sensitivity, 4)
        }

    return results
