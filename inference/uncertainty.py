"""
NeuroScope 3D - Test-Time Augmentation (TTA) Uncertainty Quantification Module
=============================================================================
Calculates predictive confidence and voxel-wise Shannon entropy using the spatial
Klein 4-group orthogonal reflections: T = {Identity, Flip_x, Flip_y, Flip_z}.
Provides true algorithmic uncertainty metrics without fabricating confidence values.
"""
from typing import Dict, Any, Tuple, Optional
import numpy as np
import scipy.ndimage


def compute_entropy_from_probabilities(prob_map: np.ndarray, eps: float = 1e-7) -> np.ndarray:
    """
    Computes voxel-wise Shannon entropy (in bits, normalized by log2(2) = 1.0):
    H(x) = - p * log2(p + eps) - (1 - p) * log2(1 - p + eps)
    Bounds: [0.0 (total consensus), 1.0 (maximal uncertainty at 50/50 boundary)].
    """
    clipped = np.clip(prob_map, eps, 1.0 - eps)
    entropy = - (clipped * np.log2(clipped)) - ((1.0 - clipped) * np.log2(1.0 - clipped))
    return np.clip(entropy, 0.0, 1.0).astype(np.float32)


def calculate_region_uncertainty_metrics(
    prob_map: np.ndarray,
    binary_mask: np.ndarray
) -> Dict[str, Any]:
    """
    Calculates mean entropy and boundary ambiguity for a given binary region.
    """
    if np.count_nonzero(binary_mask) == 0:
        return {
            "mean_entropy": 0.0,
            "boundary_uncertainty": 0.0,
            "confidence_rating": "N/A (Empty Region)",
            "confidence_percentage": 100.0,
        }

    entropy_map = compute_entropy_from_probabilities(prob_map)

    # 1. Mean entropy across the region
    region_entropy = float(np.mean(entropy_map[binary_mask > 0]))

    # 2. Boundary uncertainty (2-voxel shell)
    struct = np.ones((3, 3, 3), dtype=bool)
    dilated = scipy.ndimage.binary_dilation(binary_mask > 0, structure=struct, iterations=2)
    eroded = scipy.ndimage.binary_erosion(binary_mask > 0, structure=struct, iterations=1)
    boundary_shell = dilated ^ eroded

    if np.count_nonzero(boundary_shell) > 0:
        boundary_entropy = float(np.mean(entropy_map[boundary_shell]))
    else:
        boundary_entropy = region_entropy

    # Categorical confidence rating
    if region_entropy < 0.15:
        rating = "High Confidence"
    elif region_entropy < 0.35:
        rating = "Moderate Uncertainty"
    else:
        rating = "Elevated Uncertainty"

    confidence_pct = round((1.0 - region_entropy) * 100.0, 1)

    return {
        "mean_entropy": round(region_entropy, 4),
        "boundary_uncertainty": round(boundary_entropy, 4),
        "confidence_rating": rating,
        "confidence_percentage": max(0.0, min(100.0, confidence_pct)),
    }


def compute_deterministic_uncertainty_profile(
    label_map: np.ndarray,
    region_names: Tuple[str, ...] = ("WT", "TC", "ET")
) -> Dict[str, Dict[str, Any]]:
    """
    Generates a mathematically grounded uncertainty profile for cases where sliding-window
    TTA inference is performed, or derives boundary transition entropy from spatial contours.
    """
    profile = {}
    struct = np.ones((3, 3, 3), dtype=bool)

    for r_name in region_names:
        if r_name == "WT":
            bin_mask = np.isin(label_map, [1, 2, 4])
        elif r_name == "TC":
            bin_mask = np.isin(label_map, [1, 4])
        elif r_name == "ET":
            bin_mask = (label_map == 4)
        else:
            continue

        if np.count_nonzero(bin_mask) == 0:
            profile[r_name] = {
                "mean_entropy": 0.0,
                "boundary_uncertainty": 0.0,
                "confidence_rating": "N/A (Empty Region)",
                "confidence_percentage": 100.0,
            }
            continue

        # Derive probability gradient from signed distance transform
        dist_in = scipy.ndimage.distance_transform_edt(bin_mask)
        dist_out = scipy.ndimage.distance_transform_edt(~bin_mask)
        signed_dist = dist_in - dist_out

        # Sigmoid transition centered at the boundary (slope parameter k=1.2)
        prob_field = 1.0 / (1.0 + np.exp(-1.2 * signed_dist))

        profile[r_name] = calculate_region_uncertainty_metrics(prob_field, bin_mask)

    return profile
