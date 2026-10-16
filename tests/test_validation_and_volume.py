"""
Comprehensive test suite for NIfTI validation and physical volume calculation services.
Includes the mandatory cube volume test, anisotropic tests, empty masks, and all failure pack cases.
"""
import os
import gzip
import tempfile
import numpy as np
import pytest
import nibabel as nib

from backend.app.services.volume import (
    calculate_region_volumes,
    compute_physical_volume_ml,
    compute_bounding_box,
)
from backend.app.services.validation import (
    validate_study,
    load_and_verify_single_volume,
    check_file_size,
    ValidationError,
)
from evaluation.evaluate import compute_binary_metrics, evaluate_case


# ==============================================================================
# 1. Physical Volume Tests (FR-6)
# ==============================================================================

def test_mandatory_cube_volume():
    """
    REQUIRED CUBE TEST:
    A 20 x 20 x 20 mask containing label 2 with spacing 1 x 1 x 2 mm
    must yield WT = 16.0 mL, TC = 0.0 mL, ET = 0.0 mL.
    Calculation: 8,000 voxels * (1 * 1 * 2 mm³) = 16,000 mm³ = 16.0 mL.
    Label 2 (ED) is in WT (NCR + ED + ET), but NOT in TC (NCR + ET) or ET (ET).
    """
    mask = np.zeros((20, 20, 20), dtype=np.uint8)
    mask[:, :, :] = 2  # all label 2 (ED)
    spacing = (1.0, 1.0, 2.0)

    volumes = calculate_region_volumes(mask, spacing)

    assert pytest.approx(volumes["WT"]["volume_ml"], rel=1e-3) == 16.0
    assert volumes["WT"]["voxel_count"] == 8000

    assert pytest.approx(volumes["TC"]["volume_ml"], abs=1e-5) == 0.0
    assert volumes["TC"]["voxel_count"] == 0

    assert pytest.approx(volumes["ET"]["volume_ml"], abs=1e-5) == 0.0
    assert volumes["ET"]["voxel_count"] == 0


def test_anisotropic_and_non_cubic_volumes():
    """
    Test anisotropic spacing and non-cubic array dimensions.
    Array shape: (15, 25, 40) = 15,000 voxels.
    Spacing: (0.8, 1.2, 2.5) mm -> 0.8 * 1.2 * 2.5 = 2.4 mm³ per voxel.
    - 5,000 voxels of Label 4 (ET)
    - 3,000 voxels of Label 1 (NCR)
    - 2,000 voxels of Label 2 (ED)
    Expected:
    - ET = 5,000 * 2.4 / 1000 = 12.0 mL
    - TC = (5,000 + 3,000) * 2.4 / 1000 = 19.2 mL
    - WT = (5,000 + 3,000 + 2,000) * 2.4 / 1000 = 24.0 mL
    """
    mask = np.zeros((15, 25, 40), dtype=np.uint8)
    mask[:5, :, :] = 4   # 5 * 25 * 40 = 5,000 voxels of ET
    mask[5:8, :, :] = 1  # 3 * 25 * 40 = 3,000 voxels of NCR
    mask[8:10, :, :] = 2 # 2 * 25 * 40 = 2,000 voxels of ED

    spacing = (0.8, 1.2, 2.5)
    volumes = calculate_region_volumes(mask, spacing)

    assert pytest.approx(volumes["ET"]["volume_ml"], rel=1e-3) == 12.0
    assert volumes["ET"]["voxel_count"] == 5000

    assert pytest.approx(volumes["TC"]["volume_ml"], rel=1e-3) == 19.2
    assert volumes["TC"]["voxel_count"] == 8000

    assert pytest.approx(volumes["WT"]["volume_ml"], rel=1e-3) == 24.0
    assert volumes["WT"]["voxel_count"] == 10000


def test_single_labelled_voxel_volume():
    """
    Verify volume and centroid calculation for a single labelled voxel
    under both isotropic and anisotropic voxel spacing.
    Formula: 1 voxel * (sx * sy * sz) / 1000 mL.
    """
    shape = (20, 20, 20)
    spacing = (1.5, 2.0, 3.0)  # voxel mm³ = 1.5 * 2.0 * 3.0 = 9.0 mm³ -> 0.009 mL

    # Single ET voxel (label 4)
    mask_et = np.zeros(shape, dtype=np.uint8)
    mask_et[10, 10, 10] = 4
    vols_et = calculate_region_volumes(mask_et, spacing)
    assert vols_et["ET"]["voxel_count"] == 1
    assert vols_et["TC"]["voxel_count"] == 1
    assert vols_et["WT"]["voxel_count"] == 1
    assert pytest.approx(vols_et["ET"]["volume_ml"], abs=1e-5) == 0.009
    assert vols_et["ET"]["centroid_voxel"] == [10, 10, 10]

    # Single NCR voxel (label 1) -> in WT and TC, not ET
    mask_ncr = np.zeros(shape, dtype=np.uint8)
    mask_ncr[5, 8, 12] = 1
    vols_ncr = calculate_region_volumes(mask_ncr, spacing)
    assert vols_ncr["ET"]["voxel_count"] == 0
    assert vols_ncr["TC"]["voxel_count"] == 1
    assert vols_ncr["WT"]["voxel_count"] == 1
    assert pytest.approx(vols_ncr["TC"]["volume_ml"], abs=1e-5) == 0.009
    assert vols_ncr["ET"]["volume_ml"] == 0.0


def test_affine_determinant_volume_calculation():
    """
    Verify that affine matrix determinant is used for volume computation when provided,
    supporting rotated and sheared physical voxel grids.
    """
    mask = np.zeros((10, 10, 10), dtype=np.uint8)
    mask[2:6, 2:6, 2:6] = 4  # 4 * 4 * 4 = 64 voxels of ET
    spacing = (1.0, 1.0, 1.0)

    # 45-degree rotated affine around Z axis with scaling 2.0 on Z
    # det([cos -sin 0; sin cos 0; 0 0 2]) = (cos² + sin²) * 2 = 2.0 mm³
    theta = np.pi / 4.0
    affine = np.array([
        [np.cos(theta), -np.sin(theta), 0.0, 10.0],
        [np.sin(theta),  np.cos(theta), 0.0, 20.0],
        [0.0,            0.0,           2.0, 30.0],
        [0.0,            0.0,           0.0,  1.0],
    ], dtype=np.float64)

    vols = calculate_region_volumes(mask, spacing, affine=affine)
    # Expected: 64 voxels * 2.0 mm³ / 1000 = 0.128 mL
    assert vols["ET"]["voxel_count"] == 64
    assert pytest.approx(vols["ET"]["volume_ml"], rel=1e-3) == 0.128


def test_empty_volume_regions():
    """Verify empty mask produces 0.0 mL, 0 voxels, and None bounding box."""
    mask = np.zeros((30, 30, 30), dtype=np.uint8)
    spacing = (1.0, 1.0, 1.0)
    volumes = calculate_region_volumes(mask, spacing)

    for reg in ["WT", "TC", "ET"]:
        assert volumes[reg]["voxel_count"] == 0
        assert volumes[reg]["volume_ml"] == 0.0
        assert volumes[reg]["bounding_box_voxel"] is None



def test_bounding_box_calculation():
    """Verify bounding box coordinates for a localized region."""
    mask = np.zeros((50, 50, 50), dtype=np.uint8)
    mask[10:20, 15:35, 5:45] = 4  # Label 4 (ET)

    volumes = calculate_region_volumes(mask, (1.0, 1.0, 1.0))
    bbox = volumes["ET"]["bounding_box_voxel"]
    assert bbox is not None
    assert bbox["min"] == [10, 15, 5]
    assert bbox["max"] == [19, 34, 44]


# ==============================================================================
# 2. Empty-Mask Evaluation Metrics Tests (FR-7)
# ==============================================================================

def test_empty_mask_metric_edge_cases():
    """
    Verify defined edge-case behaviors for empty masks:
    1. Both GT and Pred empty: Dice = 1.0, Sensitivity = 1.0 (True Negative agreement)
    2. GT empty, Pred positive: Dice = 0.0, Sensitivity = 1.0 (False Positive)
    3. GT positive, Pred empty: Dice = 0.0, Sensitivity = 0.0 (False Negative)
    """
    empty = np.zeros((10, 10, 10), dtype=np.uint8)
    positive = np.zeros((10, 10, 10), dtype=np.uint8)
    positive[2:5, 2:5, 2:5] = 1

    # Case 1: Both empty
    d1, s1 = compute_binary_metrics(empty, empty)
    assert d1 == 1.0
    assert s1 == 1.0

    # Case 2: GT empty, Pred has false positives (Sensitivity undefined: 0 positive reference voxels)
    d2, s2 = compute_binary_metrics(positive, empty)
    assert d2 == 0.0
    assert s2 is None or s2 == 1.0


    # Case 3: GT positive, Pred is empty (missed detection)
    d3, s3 = compute_binary_metrics(empty, positive)
    assert d3 == 0.0
    assert s3 == 0.0


# ==============================================================================
# 3. Input Validation Failure Pack Tests (FR-2)
# ==============================================================================

@pytest.fixture
def valid_study_fixture(tmp_path):
    """Generates a valid set of 4 sequences and an expert mask."""
    shape = (20, 20, 20)
    affine = np.diag([1.0, 1.0, 2.0, 1.0])

    paths = {}
    for seq in ["t1", "t1gd", "t2", "flair"]:
        data = np.random.uniform(20.0, 120.0, size=shape).astype(np.float32)
        # Create zero border for skull-stripping sanity
        data[0, :, :] = 0; data[-1, :, :] = 0
        data[:, 0, :] = 0; data[:, -1, :] = 0
        data[:, :, 0] = 0; data[:, :, -1] = 0

        p = str(tmp_path / f"study_{seq}.nii.gz")
        nib.save(nib.Nifti1Image(data, affine=affine), p)
        paths[seq] = p

    # Valid expert mask with labels 0, 1, 2, 4
    mask = np.zeros(shape, dtype=np.uint8)
    mask[5:15, 5:15, 5:15] = 2
    mask[8:12, 8:12, 8:12] = 1
    mask_path = str(tmp_path / "study_expert.nii.gz")
    nib.save(nib.Nifti1Image(mask, affine=affine), mask_path)

    return paths, mask_path


def test_valid_study_passes(valid_study_fixture):
    paths, mask_path = valid_study_fixture
    result = validate_study(paths, expert_mask_path=mask_path)
    assert result["status"] == "passed"
    assert result["has_expert_mask"] == True
    assert result["spatial_metadata"]["shape"] == [20, 20, 20]


def test_reject_corrupt_gzip(valid_study_fixture, tmp_path):
    paths, _ = valid_study_fixture
    corrupt_file = str(tmp_path / "corrupt.nii.gz")
    with open(corrupt_file, "wb") as f:
        f.write(b"\x1f\x8b\x08not_a_valid_gzip_stream_corrupt_tail")

    paths["flair"] = corrupt_file
    with pytest.raises(ValidationError) as exc:
        validate_study(paths)
    assert exc.value.code in ["CORRUPT_GZIP", "INVALID_NIFTI"]


def test_reject_non_nifti_with_nii_name(valid_study_fixture, tmp_path):
    paths, _ = valid_study_fixture
    fake_nii = str(tmp_path / "plain_text.nii")
    with open(fake_nii, "w") as f:
        f.write("This is a plain text file, not a valid medical NIfTI file.")

    paths["t2"] = fake_nii
    with pytest.raises(ValidationError) as exc:
        validate_study(paths)
    assert exc.value.code == "INVALID_NIFTI"


def test_reject_missing_sequence(valid_study_fixture):
    paths, _ = valid_study_fixture
    del paths["t1gd"]
    with pytest.raises(ValidationError) as exc:
        validate_study(paths)
    assert exc.value.code == "MISSING_SEQUENCE"


def test_reject_2d_image(valid_study_fixture, tmp_path):
    paths, _ = valid_study_fixture
    # Create 2D image
    data_2d = np.ones((50, 50), dtype=np.float32) * 50.0
    p = str(tmp_path / "slice_2d.nii.gz")
    nib.save(nib.Nifti1Image(data_2d, np.eye(4)), p)

    paths["t1"] = p
    with pytest.raises(ValidationError) as exc:
        validate_study(paths)
    assert exc.value.code == "DIMENSION_MISMATCH_NOT_3D"


def test_reject_nan_values(valid_study_fixture, tmp_path):
    paths, _ = valid_study_fixture
    data = np.ones((20, 20, 20), dtype=np.float32) * 50.0
    data[5, 5, 5] = np.nan
    p = str(tmp_path / "nan_case.nii.gz")
    nib.save(nib.Nifti1Image(data, np.eye(4)), p)

    paths["t1"] = p
    with pytest.raises(ValidationError) as exc:
        validate_study(paths)
    assert exc.value.code == "NON_FINITE_VALUES"


def test_reject_all_zero_constant_volume(valid_study_fixture, tmp_path):
    paths, _ = valid_study_fixture
    zeros = np.zeros((20, 20, 20), dtype=np.float32)
    p = str(tmp_path / "zeros.nii.gz")
    nib.save(nib.Nifti1Image(zeros, np.eye(4)), p)

    paths["flair"] = p
    with pytest.raises(ValidationError) as exc:
        validate_study(paths)
    assert exc.value.code == "CONSTANT_VOLUME"


def test_reject_mismatched_shapes(valid_study_fixture, tmp_path):
    paths, _ = valid_study_fixture
    diff_shape = np.random.uniform(10.0, 50.0, size=(20, 20, 25)).astype(np.float32)
    p = str(tmp_path / "diff_shape.nii.gz")
    nib.save(nib.Nifti1Image(diff_shape, np.diag([1.0, 1.0, 2.0, 1.0])), p)

    paths["t2"] = p
    with pytest.raises(ValidationError) as exc:
        validate_study(paths)
    assert exc.value.code == "MISMATCHED_SHAPES"


def test_reject_mismatched_affines(valid_study_fixture, tmp_path):
    paths, _ = valid_study_fixture
    data = np.random.uniform(10.0, 50.0, size=(20, 20, 20)).astype(np.float32)
    diff_affine = np.diag([1.5, 1.0, 2.0, 1.0])  # altered X spacing
    p = str(tmp_path / "diff_affine.nii.gz")
    nib.save(nib.Nifti1Image(data, diff_affine), p)

    paths["flair"] = p
    with pytest.raises(ValidationError) as exc:
        validate_study(paths)
    assert exc.value.code == "MISMATCHED_AFFINES"


def test_reject_invalid_expert_mask_labels(valid_study_fixture, tmp_path):
    paths, _ = valid_study_fixture
    affine = np.diag([1.0, 1.0, 2.0, 1.0])
    bad_mask = np.zeros((20, 20, 20), dtype=np.uint8)
    bad_mask[5:10, 5:10, 5:10] = 3  # Label 3 is forbidden in BraTS 2021
    p = str(tmp_path / "bad_labels_mask.nii.gz")
    nib.save(nib.Nifti1Image(bad_mask, affine=affine), p)

    with pytest.raises(ValidationError) as exc:
        validate_study(paths, expert_mask_path=p)
    assert exc.value.code == "INVALID_EXPERT_MASK_LABELS"


def test_reject_file_larger_than_1gb(tmp_path):
    dummy_file = str(tmp_path / "large_file.nii")
    with open(dummy_file, "wb") as f:
        f.seek(100)
        f.write(b"\0")

    # Pass max_bytes=50 to simulate file size exceeding limit
    with pytest.raises(ValidationError) as exc:
        check_file_size(dummy_file, max_bytes=50)
    assert exc.value.code == "FILE_TOO_LARGE"
