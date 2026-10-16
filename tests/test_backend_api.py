"""
Full integration test suite for the NeuroScope 3D FastAPI backend.
Tests upload, validation, status, results, binary downloads, error handling, and 24h cleanup.
"""
import os
import io
import gzip
import time
import tempfile
import numpy as np
import pytest
import nibabel as nib
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.storage import (
    get_case_dir,
    save_case_metadata,
    cleanup_expired_cases,
    STORAGE_BASE_DIR,
)
from backend.app.services.volume import calculate_region_volumes
from backend.app.services.pdf_report import generate_pdf_report

client = TestClient(app)


def create_in_memory_nifti(data: np.ndarray, affine: np.ndarray = None) -> io.BytesIO:
    """Helper to create an in-memory gzipped NIfTI file."""
    if affine is None:
        affine = np.diag([1.0, 1.0, 2.0, 1.0])
    nii = nib.Nifti1Image(data, affine=affine)
    raw = nii.to_bytes()
    compressed = gzip.compress(raw)
    return io.BytesIO(compressed)


@pytest.fixture
def synthetic_study_files():
    """Generates 4 valid MRI sequence buffers and an optional expert mask."""
    shape = (16, 16, 16)
    affine = np.diag([1.0, 1.0, 2.0, 1.0])

    files = {}
    for seq in ["t1", "t1gd", "t2", "flair"]:
        data = np.random.uniform(20.0, 100.0, size=shape).astype(np.float32)
        # Margin zeros for skull-stripping sanity
        data[0, :, :] = 0; data[-1, :, :] = 0
        buf = create_in_memory_nifti(data, affine)
        files[seq] = (f"{seq}.nii.gz", buf, "application/gzip")

    # Expert mask with labels 0, 1, 2, 4
    mask_data = np.zeros(shape, dtype=np.uint8)
    mask_data[4:12, 4:12, 4:12] = 2  # ED
    mask_data[6:10, 6:10, 6:10] = 1  # NCR
    mask_buf = create_in_memory_nifti(mask_data, affine)
    files["expert_mask"] = ("expert_mask.nii.gz", mask_buf, "application/gzip")

    return files


def test_health_endpoint():
    """Verify backend readiness endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "model_readiness" in data
    assert data["model_readiness"]["model_name"] == "brats_mri_segmentation"
    assert "Research and teaching prototype only" in data["disclaimer"]


def test_case_upload_and_validation(synthetic_study_files):
    """Test full multi-sequence upload and automatic validation."""
    response = client.post("/api/cases", files=synthetic_study_files)
    assert response.status_code == 201
    data = response.json()

    case_id = data["case_id"]
    assert case_id.startswith("case_")
    assert data["validation_status"] == "passed"
    assert data["spatial_summary"]["shape"] == [16, 16, 16]

    # Verify SHA-256 hashes generated
    for seq in ["t1", "t1gd", "t2", "flair"]:
        assert len(data["files"][seq]["sha256"]) == 64

    # Verify validate endpoint
    val_resp = client.get(f"/api/cases/{case_id}/validate")
    assert val_resp.status_code == 200
    assert val_resp.json()["is_valid"] is True

    # Verify status endpoint
    status_resp = client.get(f"/api/cases/{case_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "uploaded"


def test_reject_upload_missing_sequence(synthetic_study_files):
    """Verify upload fails safely when a required sequence is missing."""
    del synthetic_study_files["t1gd"]
    response = client.post("/api/cases", files=synthetic_study_files)
    assert response.status_code in [400, 422]  # Rejection by domain validator (400) or schema (422)


def test_reject_upload_mismatched_shape(synthetic_study_files):
    """Verify upload rejects mismatched shapes."""
    diff_data = np.random.uniform(20.0, 100.0, size=(16, 16, 20)).astype(np.float32)
    diff_data[0, :, :] = 0; diff_data[-1, :, :] = 0
    diff_buf = create_in_memory_nifti(diff_data)
    synthetic_study_files["t2"] = ("t2_bad.nii.gz", diff_buf, "application/gzip")

    response = client.post("/api/cases", files=synthetic_study_files)
    assert response.status_code == 400
    err = response.json()
    assert err["code"] == "MISMATCHED_SHAPES"


def test_segment_safe_failure_without_weights(synthetic_study_files, monkeypatch):
    """
    Verify segmentation handles missing model weights cleanly,
    sets case status to 'failed', and never returns fabricated success.
    """
    upload_resp = client.post("/api/cases", files=synthetic_study_files)
    case_id = upload_resp.json()["case_id"]

    # Point to nonexistent weights using monkeypatch so it automatically reverts
    monkeypatch.setenv("MODEL_WEIGHTS_PATH", "nonexistent/weights/model.pt")

    seg_resp = client.post(f"/api/cases/{case_id}/segment")
    assert seg_resp.status_code == 500
    err_data = seg_resp.json()
    assert err_data["code"] == "MODEL_INFERENCE_ERROR"

    # Status should reflect failure
    status_resp = client.get(f"/api/cases/{case_id}/status")
    assert status_resp.json()["status"] == "failed"
    assert status_resp.json()["error"] is not None


def test_results_and_binary_downloads(synthetic_study_files):
    """
    Test completed case results schema, physical volumes,
    and binary downloads (/mask and /report).
    """
    upload_resp = client.post("/api/cases", files=synthetic_study_files)
    case_id = upload_resp.json()["case_id"]
    case_dir = get_case_dir(case_id)

    # Simulate completed segmentation results in workspace
    shape = (16, 16, 16)
    spacing = (1.0, 1.0, 2.0)
    affine = np.diag([1.0, 1.0, 2.0, 1.0])

    seg_data = np.zeros(shape, dtype=np.uint8)
    seg_data[4:12, 4:12, 4:12] = 2  # ED
    seg_data[6:10, 6:10, 6:10] = 4  # ET
    mask_path = os.path.join(case_dir, "predicted_seg.nii.gz")
    nib.save(nib.Nifti1Image(seg_data, affine=affine), mask_path)

    volumes = calculate_region_volumes(seg_data, spacing)
    prov = {
        "model_name": "SegResNet",
        "model_license": "Apache 2.0",
        "training_data_source": "BraTS 2018",
        "git_commit": "test-commit",
        "timestamp": "2026-10-16T18:00:00Z",
        "input_sha256": {"t1": "a", "t1gd": "b", "t2": "c", "flair": "d"},
    }

    report_path = os.path.join(case_dir, "report.pdf")
    generate_pdf_report(
        case_id=case_id,
        output_pdf_path=report_path,
        volumes=volumes,
        spatial_metadata={"spacing_mm": list(spacing), "shape": list(shape)},
        provenance=prov,
        runtime_seconds=12.4
    )

    state = {
        "case_id": case_id,
        "status": "completed",
        "runtime_seconds": 12.4,
        "spatial_metadata": {"shape": list(shape), "spacing_mm": list(spacing)},
        "volumes": volumes,
        "provenance": prov,
        "case_evaluation": {"available": False, "reason": "Expert mask not supplied"},
    }
    save_case_metadata(case_id, state)

    # 1. Test results endpoint
    res_resp = client.get(f"/api/cases/{case_id}/results")
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert res_data["status"] == "completed"
    assert "regions" in res_data
    assert "WT" in res_data["regions"]
    assert res_data["regions"]["WT"]["volume_ml"] > 0
    assert "outputs" in res_data
    assert res_data["outputs"]["mask_url"] == f"/api/cases/{case_id}/mask"

    # 2. Test binary mask download
    mask_resp = client.get(f"/api/cases/{case_id}/mask")
    assert mask_resp.status_code == 200
    assert mask_resp.headers["content-type"] in ["application/gzip", "application/octet-stream"]
    assert len(mask_resp.content) > 0

    # 3. Test binary PDF report download
    pdf_resp = client.get(f"/api/cases/{case_id}/report")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF")

    # 4. Test machine-readable JSON research summary download
    summary_resp = client.get(f"/api/cases/{case_id}/summary")
    assert summary_resp.status_code == 200
    assert summary_resp.headers["content-type"] == "application/json"
    summary_data = summary_resp.json()
    assert summary_data["case_id"] == case_id
    assert summary_data["status"] == "completed"
    assert "volumes" in summary_data
    assert "labels" in summary_data
    assert "provenance" in summary_data


def test_prevent_duplicate_segmentation_submission(synthetic_study_files):
    """
    Verify that triggering segmentation while a case is already in 'processing'
    state raises HTTP 409 Conflict to prevent redundant compute jobs.
    """
    upload_resp = client.post("/api/cases", files=synthetic_study_files)
    case_id = upload_resp.json()["case_id"]

    # Manually transition case to processing
    state = {
        "case_id": case_id,
        "status": "processing",
        "file_paths": {},
        "spatial_metadata": {"shape": [16, 16, 16], "spacing_mm": [1.0, 1.0, 1.0]},
    }
    save_case_metadata(case_id, state)

    # Status endpoint should report processing and 50%
    st_resp = client.get(f"/api/cases/{case_id}/status")
    assert st_resp.status_code == 200
    assert st_resp.json()["status"] == "processing"
    assert st_resp.json()["progress_percentage"] == 50

    # Submitting again should be rejected with HTTP 409
    dup_resp = client.post(f"/api/cases/{case_id}/segment")
    assert dup_resp.status_code == 409
    assert "already in progress" in dup_resp.json()["detail"]


def test_24_hour_storage_cleanup():
    """Verify expired case workspaces (>24h) are cleaned automatically."""
    expired_case_id = "case_expired_test_999"
    expired_dir = os.path.join(STORAGE_BASE_DIR, expired_case_id)
    os.makedirs(expired_dir, exist_ok=True)

    # Age directory to 25 hours ago
    past_time = time.time() - (25 * 3600)
    os.utime(expired_dir, (past_time, past_time))

    cleaned = cleanup_expired_cases(max_age_hours=24)
    assert cleaned >= 1
    assert not os.path.exists(expired_dir)
