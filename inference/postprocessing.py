"""
NeuroScope 3D - Standalone Inference Postprocessing Module
Enforces nesting constraints, maps nested subregion channels to BraTS 2021 labels,
and restores the segmentation onto the original reference grid and affine.
"""
from typing import Dict, Any, Tuple
import numpy as np
from scipy.ndimage import zoom


class PostprocessingError(Exception):
    """Raised when postprocessing or validation fails."""
    pass


def enforce_nesting_and_convert_labels(
    raw_channels: np.ndarray,
    threshold: float = 0.5,
    is_logits: bool = True
) -> np.ndarray:
    r"""
    Processes the 3-channel model output:
      Channel 0: TC (Tumor Core)
      Channel 1: WT (Whole Tumor)
      Channel 2: ET (Enhancing Tumor)

    Enforces logical nesting: ET ⊆ TC ⊆ WT
    Maps to BraTS 2021 tissue labels:
      0 = Background
      1 = NCR (Necrotic and non-enhancing tumor core) = TC \ ET
      2 = ED (Peritumoral oedema) = WT \ TC
      4 = ET (Enhancing tumor) = ET

    Returns:
        label_map: np.ndarray of shape (H, W, D) with uint8 labels in {0, 1, 2, 4}.
    """
    if raw_channels.ndim != 4 or raw_channels.shape[0] != 3:
        raise PostprocessingError(
            f"Expected 3-channel array of shape (3, H, W, D), got {raw_channels.shape}"
        )

    # 1. Convert logits to probabilities if necessary
    if is_logits:
        probs = 1.0 / (1.0 + np.exp(-np.clip(raw_channels, -30.0, 30.0)))
    else:
        probs = raw_channels

    tc_binary = probs[0] >= threshold
    wt_binary = probs[1] >= threshold
    et_binary = probs[2] >= threshold

    # 2. Enforce strict nesting: ET ⊆ TC ⊆ WT
    et_nested = et_binary
    tc_nested = tc_binary | et_nested
    wt_nested = wt_binary | tc_nested

    # 3. Construct categorical BraTS 2021 label map
    # Matches: torch.where(x[2] > 0, 4, torch.where(x[0] > 0, 1, torch.where(x[1] > 0, 2, 0)))
    label_map = np.zeros(raw_channels.shape[1:], dtype=np.uint8)
    label_map[wt_nested] = 2  # ED (Whole Tumor base)
    label_map[tc_nested] = 1  # NCR (Tumor Core overrides ED)
    label_map[et_nested] = 4  # ET (Enhancing Tumor overrides NCR)

    return label_map


def restore_original_grid(
    resampled_label_map: np.ndarray,
    target_shape: Tuple[int, int, int]
) -> np.ndarray:
    """
    Resamples a categorical label map to the target image dimensions using
    label-preserving nearest-neighbour interpolation (order=0).
    """
    current_shape = resampled_label_map.shape
    if current_shape == target_shape:
        return resampled_label_map.copy()

    # Calculate zoom factors along each spatial dimension
    zoom_factors = [
        target_shape[i] / float(current_shape[i]) for i in range(3)
    ]

    # order=0 strictly guarantees nearest-neighbour label preservation
    restored = zoom(
        resampled_label_map,
        zoom=zoom_factors,
        order=0,
        mode="nearest",
        prefilter=False
    ).astype(np.uint8)

    return restored


def validate_label_map(
    label_map: np.ndarray,
    expected_shape: Tuple[int, int, int]
) -> None:
    """
    Validates that the final segmentation meets all BraTS 2021 criteria:
    - Exactly 3D
    - Matches expected shape
    - Contains ONLY allowed labels {0, 1, 2, 4}
    """
    if label_map.ndim != 3:
        raise PostprocessingError(f"Output mask must be 3D, got {label_map.ndim}D")

    if label_map.shape != expected_shape:
        raise PostprocessingError(
            f"Output mask shape {label_map.shape} does not match reference shape {expected_shape}"
        )

    unique_labels = set(np.unique(label_map).tolist())
    allowed_labels = {0, 1, 2, 4}
    invalid_labels = unique_labels - allowed_labels
    if invalid_labels:
        raise PostprocessingError(
            f"Segmentation contains invalid label values {invalid_labels}. Allowed: {allowed_labels}"
        )


def derive_region_masks(label_map: np.ndarray) -> Dict[str, np.ndarray]:
    """
    Derives boolean region masks adhering to BraTS 2021 evaluation conventions:
    - WT (Whole Tumour): labels {1, 2, 4}
    - TC (Tumour Core): labels {1, 4}
    - ET (Enhancing Tumour): label {4}
    """
    return {
        "WT": np.isin(label_map, [1, 2, 4]),
        "TC": np.isin(label_map, [1, 4]),
        "ET": (label_map == 4),
    }
