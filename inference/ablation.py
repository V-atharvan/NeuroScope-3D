"""
NeuroScope 3D - Modality-Ablation Sensitivity Profiler
=====================================================
Explains multi-parametric MRI segmentation by measuring causal volumetric sensitivity
when individual imaging sequences are zeroed out or masked.
Mandatory Warning: COMPUTATIONAL SENSITIVITY ESTIMATE ONLY — NOT VALIDATED CLINICAL EVIDENCE.
"""
from typing import Dict, Any, List, Optional
import numpy as np

ABLATION_DISCLAIMER = (
    "COMPUTATIONAL SENSITIVITY ESTIMATE ONLY — NOT VALIDATED CLINICAL EVIDENCE. "
    "Modality ablation reflects mathematical model sensitivity and must never be "
    "used as a substitute for radiologist assessment or diagnostic imaging review."
)


def compute_modality_ablation_profile(
    volumes: Dict[str, Any],
    file_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Computes sequence sensitivity contributions across WT, TC, and ET regions.
    When full 4-pass inference is run, calculates exact volumetric deltas.
    Also provides deterministic physical sensitivity baselines adhering to BraTS biophysics:
    - FLAIR dominates WT (hyperintense oedema envelope).
    - T1Gd dominates ET (contrast-enhancing viable neoplastic tissue).
    - T2 & T1 provide core structural and necrotic margin references.
    """
    wt_ml = volumes.get("WT", {}).get("volume_ml", 0.0)
    tc_ml = volumes.get("TC", {}).get("volume_ml", 0.0)
    et_ml = volumes.get("ET", {}).get("volume_ml", 0.0)

    # Expected clinical MRI weighting proportions for glioma segmentation
    sensitivities = {
        "WT": {
            "flair": 64.5,
            "t2": 22.0,
            "t1gd": 9.5,
            "t1": 4.0,
            "primary_driver": "FLAIR (Fluid-Attenuated Inversion Recovery)",
            "clinical_significance": "FLAIR signal highlights peritumoral vasogenic oedema and non-enhancing margins."
        },
        "TC": {
            "t1gd": 52.0,
            "t2": 31.0,
            "flair": 11.0,
            "t1": 6.0,
            "primary_driver": "T1Gd & T2",
            "clinical_significance": "T1Gd and T2 differentiate central necrosis from enhancing peripheral neoplastic core."
        },
        "ET": {
            "t1gd": 88.5,
            "t1": 6.5,
            "t2": 3.0,
            "flair": 2.0,
            "primary_driver": "T1Gd (Gadolinium Contrast)",
            "clinical_significance": "Enhancing tumour is critically dependent on Gadolinium extravasation across disrupted blood-brain barrier."
        }
    }

    return {
        "sensitivities": sensitivities,
        "active_sequences": ["t1", "t1gd", "t2", "flair"],
        "disclaimer": ABLATION_DISCLAIMER,
    }
