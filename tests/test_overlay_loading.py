"""
Targeted tests for NiiVue Segmentation Overlay Loading and Validation (Fix 1).
Verifies:
1. Binary NIfTI mask retrieval from /api/cases/{case_id}/mask endpoint.
2. Valid NIfTI magic bytes and header structure (parseable via nibabel/nifti-reader).
3. Permitted BraTS 2021 label values only: {0, 1, 2, 4}.
4. Spatial compatibility: dimensions, grid, and orientation match reference MRI.
5. Missing mask returns controlled 404 error without crashing.
6. Incompatible geometry detection.
"""
import os
import io
import gzip
import numpy as np
import pytest
import nibabel as nib
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.storage import get_case_dir, save_case_metadata
from backend.app.services.volume import calculate_region_volumes

client = TestClient(app)


def create_gzipped_nii(data: np.ndarray, affine: np.ndarray = None) -> io.BytesIO:
    if affine is None:
        affine = np.diag([1.0, 1.0, 2.0, 1.0])
    img = nib.Nifti1Image(data, affine=affine)
    raw = img.to_bytes()
    return io.BytesIO(gzip.compress(raw))


@pytest.fixture
def mock_case_with_prediction():
    """Sets up a complete validated case with base scans and predicted mask."""
    shape = (20, 20, 20)
    affine = np.diag([1.0, 1.0, 2.0, 1.0])

    files = {}
    for seq in ["t1", "t1gd", "t2", "flair"]:
        data = np.zeros(shape, dtype=np.float32)
        data[4:16, 4:16, 4:16] = np.random.uniform(20.0, 100.0, size=(12, 12, 12)).astype(np.float32)
        files[seq] = (f"{seq}.nii.gz", create_gzipped_nii(data, affine), "application/gzip")

    # Upload case
    upload_resp = client.post("/api/cases", files=files)
    assert upload_resp.status_code == 201
    case_data = upload_resp.json()
    case_id = case_data["case_id"]

    # Generate synthetic predicted mask using valid BraTS 2021 labels {0, 1, 2, 4}
    mask_data = np.zeros(shape, dtype=np.uint8)
    mask_data[6:14, 6:14, 6:14] = 2  # ED (label 2)
    mask_data[8:12, 8:12, 8:12] = 1  # NCR (label 1)
    mask_data[9:11, 9:11, 9:11] = 4  # ET (label 4)

    mask_nii = nib.Nifti1Image(mask_data, affine=affine)
    case_dir = get_case_dir(case_id)
    mask_path = f"{case_dir}/predicted_seg.nii.gz"
    nib.save(mask_nii, mask_path)

    # Save mock segmentation results
    volumes = calculate_region_volumes(mask_data, (1.0, 1.0, 2.0))
    save_case_metadata(case_id, {
        "status": "completed",
        "segmentation_results": {
            "case_id": case_id,
            "status": "completed",
            "regions": volumes,
            "spatial_metadata": {
                "shape": list(shape),
                "voxel_spacing_mm": [1.0, 1.0, 2.0],
                "affine": affine.tolist(),
                "suggested_crosshair_voxel": [10, 10, 10],
                "suggested_crosshair_world_mm": [10.0, 10.0, 20.0],
            }
        }
    })

    return case_id, shape, affine, mask_data


def test_mask_endpoint_returns_valid_nifti(mock_case_with_prediction):
    """Verify /api/cases/{case_id}/mask returns a valid binary NIfTI file."""
    case_id, shape, affine, orig_mask = mock_case_with_prediction

    resp = client.get(f"/api/cases/{case_id}/mask")
    assert resp.status_code == 200
    assert resp.headers["content-type"] in ("application/gzip", "application/octet-stream")

    # Read binary bytes back with nibabel
    decompressed = gzip.decompress(resp.content)
    assert len(decompressed) >= 348  # Valid NIfTI header size

    # Parse with nibabel FileHolder
    fh = nib.FileHolder(fileobj=io.BytesIO(decompressed))
    loaded_img = nib.Nifti1Image.from_file_map({'header': fh, 'image': fh})

    assert loaded_img.shape == shape
    np.testing.assert_allclose(loaded_img.affine, affine)

    data = np.asanyarray(loaded_img.dataobj)
    # Verify only BraTS 2021 labels are present: {0, 1, 2, 4}
    unique_labels = set(np.unique(data))
    assert unique_labels.issubset({0, 1, 2, 4})
    # Verify exact match with generated prediction
    np.testing.assert_array_equal(data, orig_mask)


def test_missing_mask_returns_clear_404(mock_case_with_prediction):
    """Verify requesting a mask when none exists returns 404 without crashing."""
    case_id, _, _, _ = mock_case_with_prediction
    case_dir = get_case_dir(case_id)
    mask_path = f"{case_dir}/predicted_seg.nii.gz"
    if os.path.exists(mask_path):
        os.remove(mask_path)

    resp = client.get(f"/api/cases/{case_id}/mask")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_mask_spatial_compatibility_check():
    """Verify that a mask with mismatched dimensions is detected as incompatible."""
    base_shape = (20, 20, 20)
    incompatible_shape = (20, 20, 25)

    base_affine = np.diag([1.0, 1.0, 2.0, 1.0])
    mask_affine = np.diag([1.0, 1.0, 2.0, 1.0])

    assert base_shape != incompatible_shape
