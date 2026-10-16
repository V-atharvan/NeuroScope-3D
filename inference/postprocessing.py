"""
NeuroScope 3D - Postprocessing Module
Enforces nesting constraints (ET ⊆ TC ⊆ WT), maps nested regions to
BraTS 2021 integer labels (0, 1, 2, 4), and inverts spatial transforms to
restore original grid and affine.
"""
from typing import Dict, Any


def convert_regions_to_brats_labels(region_masks: Dict[str, Any]) -> Any:
    r"""
    Converts nested WT, TC, ET predictions into BraTS 2021 labels:
    - Label 0: Background
    - Label 1: NCR (Necrotic core) = TC \ ET
    - Label 2: ED (Oedema) = WT \ TC
    - Label 4: ET (Enhancing tumour) = ET
    """
    raise NotImplementedError("To be implemented on feature/ai-pipeline.")


def restore_original_grid(resampled_mask: Any, original_meta: Dict[str, Any]) -> Any:
    """
    Invert spatial transformations using label-preserving (nearest-neighbour) interpolation.
    """
    raise NotImplementedError("To be implemented on feature/ai-pipeline.")
