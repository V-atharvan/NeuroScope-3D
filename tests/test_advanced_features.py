"""
Tests for NeuroScope 3D Advanced Features:
- 95th-Percentile Hausdorff Distance (HD95) in mm
- Anatomical Sanity & Skull-Stripping OOD Checkers (Refusal & Warning)
- Voxel-Level Expert Agreement Overlay (TP / FP / FN) and REST API endpoint
"""
import os
import io
import gzip
import numpy as np
import pytest
import nibabel as nib
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.validation import (
    validate_study,
    validate_anatomical_sanity,
    check_skull_stripping_heuristic,
    ValidationError,
)
from backend.app.services.evaluation_overlay import (
    generate_agreement_volume,
    get_region_binary_mask,
)
from evaluation.evaluate import compute_hausdorff_distance_95, evaluate_case

client = TestClient(app)


def create_in_memory_nifti(data: np.ndarray, affine: np.ndarray = None) -> io.BytesIO:
    if affine is None:
        affine = np.diag([1.0, 1.0, 2.0, 1.0])
    nii = nib.Nifti1Image(data, affine=affine)
    raw = nii.to_bytes()
    compressed = gzip.compress(raw)
    return io.BytesIO(compressed)


def test_hd95_empty_masks_concordance():
    """Empty ground-truth and empty prediction should have HD95 = 0.0 mm."""
    shape = (20, 20, 20)
    pred_empty = np.zeros(shape, dtype=bool)
    gt_empty = np.zeros(shape, dtype=bool)

    hd95 = compute_hausdorff_distance_95(pred_empty, gt_empty, spacing_mm=(1.0, 1.0, 1.0))
    assert hd95 == 0.0


def test_hd95_one_voxel_displacement():
    """Single-voxel shift in 1mm grid should yield distance within 1.0 - 2.0 mm."""
    shape = (20, 20, 20)
    spacing = (1.0, 1.0, 1.0)
    gt = np.zeros(shape, dtype=np.uint8)
    pred = np.zeros(shape, dtype=np.uint8)

    # 4x4x4 cube at (5,5,5)
    gt[5:9, 5:9, 5:9] = 1
    # 4x4x4 cube shifted by 1 voxel along X: (6,5,5)
    pred[6:10, 5:9, 5:9] = 1

    hd95 = compute_hausdorff_distance_95(pred, gt, spacing_mm=spacing)
    assert 0.8 <= hd95 <= 1.5


def test_agreement_volume_partition_completeness():
    """Verifies that TP + FP + FN + TN equals the total volume voxel count."""
    shape = (16, 16, 16)
    pred_labels = np.zeros(shape, dtype=np.uint8)
    gt_labels = np.zeros(shape, dtype=np.uint8)

    # Label 2 = ED, Label 1 = NCR, Label 4 = ET. WT includes {1, 2, 4}
    pred_labels[4:10, 4:10, 4:10] = 2  # Pred WT = 6x6x6 = 216 voxels
    gt_labels[6:12, 4:10, 4:10] = 2    # GT WT = 6x6x6 = 216 voxels

    # Overlap between [4:10] and [6:12] is [6:10] = 4x6x6 = 144 voxels
    agreement_map, stats = generate_agreement_volume(pred_labels, gt_labels, region="WT")

    tp = np.count_nonzero(agreement_map == 1)
    fp = np.count_nonzero(agreement_map == 2)
    fn = np.count_nonzero(agreement_map == 3)
    tn = np.count_nonzero(agreement_map == 0)

    assert tp == 144
    assert fp == 216 - 144  # 72
    assert fn == 216 - 144  # 72
    assert tp + fp + fn + tn == shape[0] * shape[1] * shape[2]
    assert stats["tp_voxels"] == 144
    assert stats["fp_voxels"] == 72
    assert stats["fn_voxels"] == 72
    assert 0.0 < stats["dice"] < 1.0


def test_anatomical_sanity_refusal_empty_and_solid_phantom():
    """Checks that non-brain inputs (<2% or >95% foreground) trigger refusal."""
    shape = (30, 30, 30)

    # 1. Sparse noise / empty scan (0.1% foreground)
    sparse_data = np.zeros(shape, dtype=np.float32)
    sparse_data[15, 15, 15] = 50.0
    with pytest.raises(ValidationError) as exc_info:
        validate_anatomical_sanity(sparse_data)
    assert exc_info.value.code == "REFUSAL_NOT_A_BRAIN"

    # 2. Solid block / non-brain CT body phantom (100% foreground)
    solid_data = np.ones(shape, dtype=np.float32) * 80.0
    with pytest.raises(ValidationError) as exc_info2:
        validate_anatomical_sanity(solid_data)
    assert exc_info2.value.code == "REFUSAL_NOT_A_BRAIN"


def test_skull_stripping_margin_warning():
    """Non-skull-stripped scan with border intensities should trigger WARNING_NOT_SKULL_STRIPPED."""
    shape = (20, 20, 20)
    data = np.zeros(shape, dtype=np.float32)
    # Center brain
    data[5:15, 5:15, 5:15] = 60.0
    # Add non-stripped scalp signal on outer boundary
    data[0, :, :] = 50.0
    data[-1, :, :] = 50.0
    data[:, 0, :] = 50.0
    data[:, -1, :] = 50.0

    warnings, meta = validate_anatomical_sanity(data)
    assert any("WARNING_NOT_SKULL_STRIPPED" in w for w in warnings)
    assert meta["is_skull_stripped"] is False
    assert meta["border_nonzero_ratio"] > 0.20


def test_agreement_mask_endpoint_integration():
    """Uploads a synthetic case with expert mask, segments it, and downloads agreement mask."""
    shape = (16, 16, 16)
    affine = np.diag([1.0, 1.0, 2.0, 1.0])

    files = {}
    for seq in ["t1", "t1gd", "t2", "flair"]:
        data = np.random.uniform(20.0, 80.0, size=shape).astype(np.float32)
        # Margin zeros for skull-strip cleanliness
        data[0, :, :] = 0; data[-1, :, :] = 0; data[:, 0, :] = 0; data[:, -1, :] = 0
        files[seq] = (f"{seq}.nii.gz", create_in_memory_nifti(data, affine), "application/gzip")

    mask_data = np.zeros(shape, dtype=np.uint8)
    mask_data[4:12, 4:12, 4:12] = 2  # ED
    files["expert_mask"] = ("expert_mask.nii.gz", create_in_memory_nifti(mask_data, affine), "application/gzip")

    # 1. Upload case
    upload_resp = client.post("/api/cases", files=files)
    assert upload_resp.status_code == 201
    case_id = upload_resp.json()["case_id"]

    # 2. Simulate completed segmentation results in workspace
    from backend.app.services.storage import get_case_dir, load_case_metadata, save_case_metadata
    from backend.app.services.volume import calculate_region_volumes
    case_dir = get_case_dir(case_id)

    seg_data = np.zeros(shape, dtype=np.uint8)
    seg_data[4:10, 4:10, 4:10] = 2  # ED
    mask_path = os.path.join(case_dir, "predicted_seg.nii.gz")
    nib.save(nib.Nifti1Image(seg_data, affine=affine), mask_path)

    state = load_case_metadata(case_id)
    state["status"] = "completed"
    state["volumes"] = calculate_region_volumes(seg_data, (1.0, 1.0, 2.0))
    state["provenance"] = {
        "model_name": "SegResNet",
        "model_license": "Apache 2.0",
        "training_data_source": "BraTS 2018",
        "timestamp": "2026-10-16T18:00:00Z",
        "input_sha256": {"t1": "a", "t1gd": "b", "t2": "c", "flair": "d"},
    }
    state["case_evaluation"] = {
        "available": True,
        "metrics": evaluate_case(seg_data, mask_data, spacing_mm=(1.0, 1.0, 2.0))
    }
    save_case_metadata(case_id, state)

    # 3. Verify get_case_results contains agreement_mask_url
    res_resp = client.get(f"/api/cases/{case_id}/results")
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert res_data["outputs"]["agreement_mask_url"] is not None
    assert f"/api/cases/{case_id}/agreement-mask?region=WT" in res_data["outputs"]["agreement_mask_url"]

    # 4. Download Agreement Mask via endpoint
    agr_resp = client.get(f"/api/cases/{case_id}/agreement-mask?region=WT")
    assert agr_resp.status_code == 200
    assert agr_resp.headers["content-type"] == "application/gzip"
    assert len(agr_resp.content) > 0

    # Parse downloaded agreement volume
    decompressed = gzip.decompress(agr_resp.content)
    # Check that decompressed NIfTI can be parsed
    fh = nib.FileHolder(fileobj=io.BytesIO(decompressed))
    agr_nii = nib.Nifti1Image.from_file_map({'header': fh, 'image': fh})
    agr_vol = np.asanyarray(agr_nii.dataobj)
    assert agr_vol.shape == shape
    unique_vals = set(np.unique(agr_vol))
    # Values must be subset of {0, 1, 2, 3}
    assert unique_vals.issubset({0, 1, 2, 3})


def test_mesh_export_world_affine():
    """Verifies that Marching Cubes produces polygonal meshes in physical world mm coordinates."""
    from backend.app.services.mesh_export import generate_region_mesh, export_mesh_bytes
    shape = (20, 20, 20)
    # Affine with 2.0mm voxel spacing and (10, 20, 30) origin offset
    affine = np.diag([2.0, 2.0, 2.0, 1.0])
    affine[:3, 3] = [10.0, 20.0, 30.0]

    vol = np.zeros(shape, dtype=np.uint8)
    vol[5:15, 5:15, 5:15] = 2  # ED (WT)

    mesh = generate_region_mesh(vol, affine, region="WT")
    assert mesh is not None
    assert len(mesh.vertices) > 0
    assert len(mesh.faces) > 0

    # Minimum vertex coordinate should be >= origin offset (10, 20, 30)
    min_coords = np.min(mesh.vertices, axis=0)
    assert min_coords[0] >= 10.0
    assert min_coords[1] >= 20.0
    assert min_coords[2] >= 30.0

    # Test GLB export
    glb_bytes = export_mesh_bytes(mesh, export_format="glb")
    assert glb_bytes.startswith(b"glTF")

    # Test OBJ export
    obj_bytes = export_mesh_bytes(mesh, export_format="obj")
    assert b"v " in obj_bytes
    assert b"f " in obj_bytes


def test_uncertainty_quantification_profile():
    """Verifies Shannon entropy and boundary ambiguity metrics across tumor regions."""
    from inference.uncertainty import compute_deterministic_uncertainty_profile
    shape = (24, 24, 24)
    labels = np.zeros(shape, dtype=np.uint8)
    labels[6:18, 6:18, 6:18] = 2  # ED
    labels[8:16, 8:16, 8:16] = 1  # NCR
    labels[10:14, 10:14, 10:14] = 4  # ET

    profile = compute_deterministic_uncertainty_profile(labels)
    assert "WT" in profile
    assert "TC" in profile
    assert "ET" in profile

    for reg in ["WT", "TC", "ET"]:
        assert 0.0 <= profile[reg]["mean_entropy"] <= 1.0
        assert 0.0 <= profile[reg]["boundary_uncertainty"] <= 1.0
        assert "confidence_rating" in profile[reg]
        assert 0.0 <= profile[reg]["confidence_percentage"] <= 100.0


def test_modality_ablation_profile():
    """Verifies sequence sensitivity metrics and required non-clinical disclaimer."""
    from inference.ablation import compute_modality_ablation_profile
    mock_volumes = {
        "WT": {"voxel_count": 5000, "volume_ml": 5.0},
        "TC": {"voxel_count": 2000, "volume_ml": 2.0},
        "ET": {"voxel_count": 800, "volume_ml": 0.8},
    }

    profile = compute_modality_ablation_profile(mock_volumes)
    assert "sensitivities" in profile
    assert "disclaimer" in profile
    assert "COMPUTATIONAL SENSITIVITY ESTIMATE ONLY" in profile["disclaimer"]
    assert profile["sensitivities"]["ET"]["t1gd"] >= 70.0
    assert profile["sensitivities"]["WT"]["flair"] >= 60.0


def test_longitudinal_rano_criteria():
    """Verifies RANO response trajectory categorization for two-timepoint scans."""
    from backend.app.services.longitudinal import compare_two_timepoint_studies

    baseline_vols = {
        "WT": {"volume_ml": 20.0},
        "TC": {"volume_ml": 10.0},
        "ET": {"volume_ml": 5.0},
    }

    # 1. Progressive Disease (PD): >= +25% ET volume increase
    followup_pd = {
        "WT": {"volume_ml": 25.0},
        "TC": {"volume_ml": 14.0},
        "ET": {"volume_ml": 6.5},  # +30%
    }
    res_pd = compare_two_timepoint_studies(baseline_vols, followup_pd)
    assert res_pd["rano_trajectory"]["rano_category"] == "Progressive Disease (PD)"
    assert res_pd["volumetric_deltas"]["ET"]["percentage_delta"] == 30.0

    # 2. Partial Response (PR): <= -50% ET volume reduction
    followup_pr = {
        "WT": {"volume_ml": 10.0},
        "TC": {"volume_ml": 4.0},
        "ET": {"volume_ml": 2.0},  # -60%
    }
    res_pr = compare_two_timepoint_studies(baseline_vols, followup_pr)
    assert res_pr["rano_trajectory"]["rano_category"] == "Partial Response (PR)"
    assert res_pr["volumetric_deltas"]["ET"]["percentage_delta"] == -60.0

    # 3. Stable Disease (SD): between -50% and +25%
    followup_sd = {
        "WT": {"volume_ml": 20.5},
        "TC": {"volume_ml": 10.2},
        "ET": {"volume_ml": 5.2},  # +4%
    }
    res_sd = compare_two_timepoint_studies(baseline_vols, followup_sd)
    assert res_sd["rano_trajectory"]["rano_category"] == "Stable Disease (SD)"
    assert res_sd["volumetric_deltas"]["ET"]["percentage_delta"] == 4.0


def test_cohort_benchmark_endpoint():
    """Verifies that the held-out cohort benchmark endpoint returns 10 cases with disclosures."""
    resp = client.get("/api/evaluation/cohort")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_cases"] == 10
    assert len(data["individual_cases"]) == 10
    assert "aggregate_metrics" in data
    assert "training_overlap_disclosure" in data
    assert "BraTS 2018" in data["training_overlap_disclosure"]


def test_scorer_cli_execution():
    """Verifies that the judges' scorer CLI runs with --help and exits cleanly."""
    import subprocess
    import sys
    res = subprocess.run([sys.executable, "segment.py", "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "NeuroScope 3D" in res.stdout
    assert "--t1" in res.stdout
    assert "--output" in res.stdout


def test_imputation_mode_synthesis():
    """Verifies that allow_imputation=True synthesizes 1 missing sequence with a high-severity warning."""
    shape = (16, 16, 16)
    affine = np.diag([1.0, 1.0, 1.0, 1.0])

    # Upload only 3 sequences: t1, t2, flair (omitting t1gd)
    files = {}
    for seq in ["t1", "t2", "flair"]:
        data = np.random.uniform(20.0, 80.0, size=shape).astype(np.float32)
        data[0, :, :] = 0; data[-1, :, :] = 0; data[:, 0, :] = 0; data[:, -1, :] = 0
        files[seq] = (f"{seq}.nii.gz", create_in_memory_nifti(data, affine), "application/gzip")

    # Without allow_imputation (default), must reject with 400 MISSING_SEQUENCE
    resp_strict = client.post("/api/cases", files=files)
    assert resp_strict.status_code == 400
    assert resp_strict.json()["code"] == "MISSING_SEQUENCE"

    # With allow_imputation=True, must accept and synthesize with warning
    files_impute = {}
    for seq in ["t1", "t2", "flair"]:
        data = np.random.uniform(20.0, 80.0, size=shape).astype(np.float32)
        data[0, :, :] = 0; data[-1, :, :] = 0; data[:, 0, :] = 0; data[:, -1, :] = 0
        files_impute[seq] = (f"{seq}.nii.gz", create_in_memory_nifti(data, affine), "application/gzip")

    resp_impute = client.post("/api/cases?allow_imputation=true", files=files_impute)
    assert resp_impute.status_code == 201
    impute_data = resp_impute.json()
    assert any("WARNING_SEQUENCE_IMPUTED" in w for w in impute_data.get("warnings", []))
