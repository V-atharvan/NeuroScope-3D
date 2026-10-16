"""
NeuroScope 3D - Voxel-Level Expert Agreement Overlay Service
============================================================
Generates 4-class confusion/agreement volumes comparing model predictions with expert ground truth:
 - 0: True Negative (TN) / Background tissue (Transparent)
 - 1: True Positive (TP)  / Concordant tumour prediction (Green #10B981)
 - 2: False Positive (FP) / Over-segmentation / false alarm (Coral #EF4444)
 - 3: False Negative (FN) / Under-segmentation / missed boundary (Purple #8B5CF6)
"""
from typing import Dict, Any, Tuple
import os
import numpy as np
import nibabel as nib


def get_region_binary_mask(label_map: np.ndarray, region: str) -> np.ndarray:
    """Extracts binary mask for a target clinical BraTS 2021 target region."""
    reg = region.upper()
    if reg == "WT":
        return np.isin(label_map, [1, 2, 4])
    elif reg == "TC":
        return np.isin(label_map, [1, 4])
    elif reg == "ET":
        return label_map == 4
    else:
        raise ValueError(f"Unknown region '{region}'. Must be 'WT', 'TC', or 'ET'.")


def generate_agreement_volume(
    pred_label_map: np.ndarray,
    gt_label_map: np.ndarray,
    region: str = "WT"
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Computes a 4-class categorical agreement mask between prediction and ground truth.
    Returns (agreement_array, stats_dict).
    """
    if pred_label_map.shape != gt_label_map.shape:
        raise ValueError(f"Shape mismatch: {pred_label_map.shape} vs {gt_label_map.shape}")

    pred_bin = get_region_binary_mask(pred_label_map, region)
    gt_bin = get_region_binary_mask(gt_label_map, region)

    tp_mask = pred_bin & gt_bin
    fp_mask = pred_bin & (~gt_bin)
    fn_mask = (~pred_bin) & gt_bin

    agreement_map = np.zeros(pred_label_map.shape, dtype=np.uint8)
    agreement_map[tp_mask] = 1  # True Positive
    agreement_map[fp_mask] = 2  # False Positive
    agreement_map[fn_mask] = 3  # False Negative

    tp_count = int(np.count_nonzero(tp_mask))
    fp_count = int(np.count_nonzero(fp_mask))
    fn_count = int(np.count_nonzero(fn_mask))
    total_foreground = tp_count + fp_count + fn_count

    dice = (2.0 * tp_count) / float(2 * tp_count + fp_count + fn_count) if total_foreground > 0 else 1.0

    stats = {
        "region": region.upper(),
        "tp_voxels": tp_count,
        "fp_voxels": fp_count,
        "fn_voxels": fn_count,
        "dice": round(float(dice), 4),
        "sensitivity": round(float(tp_count / (tp_count + fn_count)), 4) if (tp_count + fn_count) > 0 else (1.0 if fp_count == 0 else None),
    }

    return agreement_map, stats


def export_agreement_nifti(
    pred_path: str,
    gt_path: str,
    output_path: str,
    region: str = "WT"
) -> str:
    """Loads prediction and ground-truth NIfTI files and writes agreement NIfTI mask."""
    pred_nii = nib.load(pred_path)
    gt_nii = nib.load(gt_path)

    pred_data = np.asanyarray(pred_nii.dataobj).astype(np.uint8)
    gt_data = np.asanyarray(gt_nii.dataobj).astype(np.uint8)

    agreement_data, _ = generate_agreement_volume(pred_data, gt_data, region=region)

    out_nii = nib.Nifti1Image(agreement_data, pred_nii.affine, header=pred_nii.header)
    nib.save(out_nii, output_path)
    return output_path
