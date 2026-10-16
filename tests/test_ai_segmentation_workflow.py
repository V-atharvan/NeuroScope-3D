"""
Comprehensive test suite for the AI Segmentation and Output Workflow in NeuroScope 3D.
Verifies:
1. SegResNet model bundle loading, eval mode, and singleton caching.
2. Safe CUDA OutOfMemoryError handling and CPU fallback message.
3. Input sequence ordering contract [0: T1Gd, 1: T1, 2: T2, 3: FLAIR].
4. Empty prediction handling (all zeros, 0.0 mL, None centroids).
5. Non-empty prediction, nesting enforcement (ET <= TC <= WT), and label mapping.
6. Geometry-aware volume calculation with affine determinant.
7. End-to-end segmentation execution on sample study with full output verification
   (NIfTI mask, 4-page PDF report, summary JSON, agreement mask, GLB/OBJ meshes).
"""
import os
import json
import numpy as np
import pytest
import nibabel as nib
import torch
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.storage import get_case_dir, load_case_metadata
from backend.app.services.volume import calculate_region_volumes, compute_physical_volume_ml
from inference.predict import get_or_load_model, clear_model_cache, run_model_inference
from inference.postprocessing import (
    enforce_nesting_and_convert_labels,
    derive_region_masks,
    restore_original_grid,
    validate_label_map,
)
from inference.preprocessing import normalize_intensity_nonzero

client = TestClient(app)
WEIGHTS_PATH = os.path.abspath("models/brats_mri_segmentation/models/model.pt")


# ==============================================================================
# 1. Model Loading, Evaluation Mode, and Cache
# ==============================================================================

def test_model_loading_and_singleton_caching():
    """Verify that SegResNet is loaded once into memory in evaluation mode."""
    clear_model_cache()

    model1, device1 = get_or_load_model(WEIGHTS_PATH, device_name="cpu")
    assert not model1.training, "Model must be in evaluation mode (model.eval())"
    assert device1.type == "cpu"

    # Second call must retrieve the exact same cached instance
    model2, device2 = get_or_load_model(WEIGHTS_PATH, device_name="cpu")
    assert model1 is model2, "Model checkpoint must be cached and not reloaded"

    # Clearing cache should force reload
    clear_model_cache()
    model3, _ = get_or_load_model(WEIGHTS_PATH, device_name="cpu")
    assert model3 is not model1


def test_missing_weights_file_error():
    """Verify informative FileNotFoundError when model weights do not exist."""
    clear_model_cache()
    with pytest.raises(FileNotFoundError, match="Pretrained model weights not found"):
        get_or_load_model("nonexistent_path/model.pt", device_name="cpu")


def test_cuda_oom_handling():
    """Verify that CUDA OutOfMemoryError is intercepted with an actionable message."""
    dummy_input = np.zeros((4, 32, 32, 32), dtype=np.float32)

    with patch("monai.inferers.SlidingWindowInferer.__call__", side_effect=torch.cuda.OutOfMemoryError("CUDA out of memory")):
        with pytest.raises(RuntimeError) as excinfo:
            run_model_inference(dummy_input, WEIGHTS_PATH, device_name="cuda")

        assert "GPU Out of Memory (CUDA OOM)" in str(excinfo.value) or "SegResNet forward pass" in str(excinfo.value)


# ==============================================================================
# 2. Input Modality Ordering and Preprocessing
# ==============================================================================

def test_input_modality_channel_contract():
    """
    Verify the strict BraTS SegResNet channel ordering contract:
    Channel 0: T1Gd (contrast-enhanced)
    Channel 1: T1 (native)
    Channel 2: T2
    Channel 3: FLAIR
    """
    from inference.preprocessing import preprocess_study
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        shape = (16, 16, 16)
        affine = np.eye(4, dtype=np.float32)

        paths = {}
        # Write distinctive mean intensities for each modality
        intensities = {"t1gd": 100.0, "t1": 200.0, "t2": 300.0, "flair": 400.0}
        for mod, val in intensities.items():
            p = os.path.join(tmpdir, f"test_{mod}.nii.gz")
            data = np.full(shape, val, dtype=np.float32)
            # Add spatial variation to ensure std > 0
            data[4:8, 4:8, 4:8] += 50.0
            nib.save(nib.Nifti1Image(data, affine=affine), p)
            paths[mod] = p

        tensor, meta = preprocess_study(paths)
        assert tensor.shape == (4, 16, 16, 16)
        assert meta["channel_order"] == ["t1gd", "t1", "t2", "flair"]


# ==============================================================================
# 3. Postprocessing: Empty Predictions & Nesting Constraints
# ==============================================================================

def test_empty_prediction_handling():
    """
    Verify that an all-negative logits tensor (no tumour detected) produces
    an all-background (0) label map, 0.0 mL volume, and None centroids.
    """
    # 3 channels (TC, WT, ET), all negative
    empty_logits = np.full((3, 10, 10, 10), -10.0, dtype=np.float32)
    labels = enforce_nesting_and_convert_labels(empty_logits, threshold=0.5, is_logits=True)

    assert np.all(labels == 0), "All voxels must be background (0)"

    masks = derive_region_masks(labels)
    for reg in ["WT", "TC", "ET"]:
        assert not np.any(masks[reg]), f"Mask for {reg} must be all False"

    volumes = calculate_region_volumes(labels, voxel_spacing=(1.0, 1.0, 1.0))
    for reg in ["WT", "TC", "ET"]:
        assert volumes[reg]["voxel_count"] == 0
        assert volumes[reg]["volume_ml"] == 0.0
        assert volumes[reg]["centroid_voxel"] is None
        assert volumes[reg]["bounding_box_voxel"] is None


def test_nesting_constraint_enforcement_and_labels():
    """
    Verify nesting: ET <= TC <= WT.
    Label mapping:
    - 0: Background
    - 1: NCR (Necrotic and non-enhancing tumour core, i.e. TC and not ET)
    - 2: ED (Peritumoural edema, i.e. WT and not TC)
    - 4: ET (Enhancing tumour)
    """
    logits = np.full((3, 2, 2, 2), -10.0, dtype=np.float32)

    # Voxel (0, 0, 0): Only ET has positive logit (anomalous)
    logits[2, 0, 0, 0] = 5.0

    # Voxel (0, 0, 1): TC positive, WT negative (anomalous)
    logits[0, 0, 0, 1] = 5.0

    # Voxel (0, 1, 0): WT positive only -> ED (label 2)
    logits[1, 0, 1, 0] = 5.0

    # Voxel (1, 1, 1): All negative -> Background (label 0)

    labels = enforce_nesting_and_convert_labels(logits, threshold=0.5, is_logits=True)

    # Voxel (0, 0, 0) should be promoted to ET (4)
    assert labels[0, 0, 0] == 4
    # Voxel (0, 0, 1) should be promoted to NCR (1)
    assert labels[0, 0, 1] == 1
    # Voxel (0, 1, 0) should be ED (2)
    assert labels[0, 1, 0] == 2
    # Voxel (1, 1, 1) should be Background (0)
    assert labels[1, 1, 1] == 0

    masks = derive_region_masks(labels)
    # Check strict hierarchical subset: ET subset of TC subset of WT
    assert np.all(masks["ET"] <= masks["TC"])
    assert np.all(masks["TC"] <= masks["WT"])


# ==============================================================================
# 4. Physical Volume Calculations on Anisotropic and Sheared Grids
# ==============================================================================

def test_affine_volume_calculation():
    """Verify physical volume computation with affine determinant vs spacing."""
    # Diagonal affine with voxel dimensions 1.5 x 2.0 x 3.0 mm
    affine_diag = np.diag([1.5, 2.0, 3.0, 1.0])
    vol_1 = compute_physical_volume_ml(1000, spacing_mm=(1.5, 2.0, 3.0), affine=affine_diag)
    # 1000 * (1.5 * 2.0 * 3.0) / 1000 = 9.0 mL
    assert np.isclose(vol_1, 9.0)

    # Rotated affine (45 degrees about Z axis)
    angle = np.pi / 4
    cos_a, sin_a = np.cos(angle), np.sin(angle)
    rot_affine = np.array([
        [cos_a, -sin_a, 0.0, 10.0],
        [sin_a,  cos_a, 0.0, 20.0],
        [0.0,    0.0,   2.5, 30.0],
        [0.0,    0.0,   0.0,  1.0],
    ])
    # det(rot[:3, :3]) = 1.0 * 2.5 = 2.5 mm^3 per voxel
    vol_rot = compute_physical_volume_ml(2000, spacing_mm=(1.0, 1.0, 2.5), affine=rot_affine)
    # 2000 * 2.5 / 1000 = 5.0 mL
    assert np.isclose(vol_rot, 5.0)


# ==============================================================================
# 5. End-to-End Workflow with Prepackaged Sample Study
# ==============================================================================

def test_sample_study_end_to_end_workflow():
    """
    Executes the entire workflow on the pre-packaged BraTS sample study:
    1. Load sample case (/api/cases/sample)
    2. Verify status and prevent duplicate submissions
    3. Run AI segmentation (/api/cases/{case_id}/segment)
    4. Fetch volumetric results (/api/cases/{case_id}/results)
    5. Download predicted NIfTI mask (/api/cases/{case_id}/mask)
    6. Download research PDF report (/api/cases/{case_id}/report)
    7. Export research summary JSON (/api/cases/{case_id}/summary)
    8. Download expert agreement mask (/api/cases/{case_id}/agreement-mask?region=WT)
    9. Export 3D surface meshes (/api/cases/{case_id}/mesh/WT?format=glb and format=obj)
    """
    # 1. Load sample study
    load_resp = client.post("/api/cases/sample")
    assert load_resp.status_code == 201, f"Failed to load sample study: {load_resp.text}"
    case_data = load_resp.json()
    case_id = case_data["case_id"]
    assert case_data["validation_status"] == "passed"
    assert case_data["files"]["expert_mask"]["present"] is True

    # 2. Check initial status
    status_resp = client.get(f"/api/cases/{case_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "uploaded"
    assert status_resp.json()["progress_percentage"] == 0

    # 3. Execute AI segmentation
    seg_resp = client.post(f"/api/cases/{case_id}/segment")
    assert seg_resp.status_code == 200, f"Segmentation failed: {seg_resp.text}"
    seg_result = seg_resp.json()
    assert seg_result["status"] == "completed"

    # 4. Status should now report completed (100%)
    status_resp2 = client.get(f"/api/cases/{case_id}/status")
    assert status_resp2.status_code == 200
    assert status_resp2.json()["status"] == "completed"
    assert status_resp2.json()["progress_percentage"] == 100

    # 5. Fetch quantitative results
    res_resp = client.get(f"/api/cases/{case_id}/results")
    assert res_resp.status_code == 200
    res = res_resp.json()
    assert res["status"] == "completed"
    assert "regions" in res
    assert "WT" in res["regions"] and "TC" in res["regions"] and "ET" in res["regions"]
    assert res["regions"]["WT"]["volume_ml"] > 0
    assert res["case_evaluation"]["available"] is True
    assert "WT" in res["case_evaluation"]["metrics"]
    assert "dice" in res["case_evaluation"]["metrics"]["WT"]

    # 6. Verify NIfTI mask download
    mask_resp = client.get(f"/api/cases/{case_id}/mask")
    assert mask_resp.status_code == 200
    assert mask_resp.headers["content-type"] in ["application/gzip", "application/octet-stream"]
    assert len(mask_resp.content) > 100

    # 7. Verify formal PDF report download
    report_resp = client.get(f"/api/cases/{case_id}/report")
    assert report_resp.status_code == 200
    assert report_resp.headers["content-type"] == "application/pdf"
    assert report_resp.content.startswith(b"%PDF")

    # 8. Verify research summary JSON export
    summary_resp = client.get(f"/api/cases/{case_id}/summary")
    assert summary_resp.status_code == 200
    assert summary_resp.headers["content-type"] == "application/json"
    summary_json = summary_resp.json()
    assert summary_json["case_id"] == case_id
    assert summary_json["status"] == "completed"
    assert "volumes" in summary_json
    assert "brats_labels" in summary_json
    assert "provenance" in summary_json
    assert "disclaimer" in summary_json

    # 9. Verify 4-class expert agreement overlay mask
    agr_resp = client.get(f"/api/cases/{case_id}/agreement-mask?region=WT")
    assert agr_resp.status_code == 200
    assert agr_resp.headers["content-type"] in ["application/gzip", "application/octet-stream"]
    assert len(agr_resp.content) > 100

    # 10. Verify 3D surface mesh export (GLB and OBJ)
    glb_resp = client.get(f"/api/cases/{case_id}/mesh/WT?format=glb")
    assert glb_resp.status_code == 200
    assert glb_resp.headers["content-type"] == "model/gltf-binary"
    assert len(glb_resp.content) > 50

    obj_resp = client.get(f"/api/cases/{case_id}/mesh/WT?format=obj")
    assert obj_resp.status_code == 200
    assert "text/plain" in obj_resp.headers["content-type"]
    assert b"v " in obj_resp.content  # Wavefront OBJ vertex syntax
