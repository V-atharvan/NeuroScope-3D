"""
NeuroScope 3D - MRI Upload and Validation Test Suite
=====================================================
Covers all mandatory failure-pack cases, valid scenarios, geometry checks,
expert mask validation, imputation, and integration with the inference pipeline.

Run with:
    cd <repo-root>
    python -m pytest tests/test_mri_upload_validation.py -v
"""
import os
import gzip
import struct
import tempfile
import io

import numpy as np
import nibabel as nib
import pytest

from backend.app.services.validation import (
    validate_study,
    load_and_verify_single_volume,
    check_file_size,
    verify_gzip_integrity,
    validate_anatomical_sanity,
    check_skull_stripping_heuristic,
    ValidationError,
    ALLOWED_BRATS_LABELS,
    REQUIRED_SEQUENCES,
    MAX_FILE_SIZE_BYTES,
)
from backend.app.services.storage import (
    create_case_workspace,
    get_case_dir,
    validate_case_id,
)


# ==============================================================================
# Helpers / Fixtures
# ==============================================================================

def make_brain_volume(shape=(20, 20, 20), affine=None, seed=42, intensity_range=(20.0, 120.0)):
    """Creates a synthetic brain-like volume with zeroed borders (skull-stripped)."""
    rng = np.random.default_rng(seed)
    data = rng.uniform(*intensity_range, size=shape).astype(np.float32)
    # Zero the border voxels (skull-stripped)
    data[0, :, :] = 0; data[-1, :, :] = 0
    data[:, 0, :] = 0; data[:, -1, :] = 0
    data[:, :, 0] = 0; data[:, :, -1] = 0
    if affine is None:
        affine = np.diag([1.0, 1.0, 2.0, 1.0])
    return data, affine


def save_nii(data, affine, path, compressed=True):
    """Saves a NIfTI image to disk."""
    img = nib.Nifti1Image(data, affine=affine)
    nib.save(img, path)
    return path


def make_study_paths(tmp_path, shape=(20, 20, 20), affine=None):
    """Creates a valid 4-sequence study and returns paths dict."""
    if affine is None:
        affine = np.diag([1.0, 1.0, 2.0, 1.0])
    paths = {}
    for i, seq in enumerate(REQUIRED_SEQUENCES):
        data, _ = make_brain_volume(shape=shape, affine=affine, seed=i * 7)
        p = str(tmp_path / f"study_{seq}.nii.gz")
        save_nii(data, affine, p)
        paths[seq] = p
    return paths


def make_expert_mask(shape, affine, tmp_path):
    """Creates a valid BraTS 2021 expert mask."""
    mask = np.zeros(shape, dtype=np.uint8)
    mask[5:15, 5:15, 5:15] = 2
    mask[8:12, 8:12, 8:12] = 1
    mask[9:11, 9:11, 9:11] = 4
    p = str(tmp_path / "expert.nii.gz")
    save_nii(mask.astype(np.float32), affine, p)
    return p


# ==============================================================================
# 1. File size checks
# ==============================================================================

class TestFileSizeChecks:
    def test_normal_file_passes(self, tmp_path):
        f = str(tmp_path / "ok.nii")
        with open(f, "wb") as fh:
            fh.write(b"\x00" * 100)
        size = check_file_size(f, max_bytes=1000)
        assert size == 100

    def test_file_too_large_raises(self, tmp_path):
        f = str(tmp_path / "big.nii")
        with open(f, "wb") as fh:
            fh.seek(200)
            fh.write(b"\x00")
        with pytest.raises(ValidationError) as exc:
            check_file_size(f, max_bytes=50)
        assert exc.value.code == "FILE_TOO_LARGE"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ValidationError) as exc:
            check_file_size(str(tmp_path / "nonexistent.nii"))
        assert exc.value.code == "FILE_NOT_FOUND"

    def test_1gb_limit_enforcement(self, tmp_path):
        """Verify the 1 GB constant is 1073741824 bytes."""
        assert MAX_FILE_SIZE_BYTES == 1024 * 1024 * 1024


# ==============================================================================
# 2. Gzip integrity checks
# ==============================================================================

class TestGzipIntegrity:
    def test_valid_gz_passes(self, tmp_path):
        p = str(tmp_path / "ok.nii.gz")
        with gzip.open(p, "wb") as gz:
            gz.write(b"valid content data here")
        verify_gzip_integrity(p)  # should not raise

    def test_corrupt_gz_raises(self, tmp_path):
        p = str(tmp_path / "corrupt.nii.gz")
        with open(p, "wb") as fh:
            fh.write(b"\x1f\x8b\x08not_a_valid_gzip_stream_corrupt")
        with pytest.raises(ValidationError) as exc:
            verify_gzip_integrity(p)
        assert exc.value.code == "CORRUPT_GZIP"

    def test_non_gz_file_skipped(self, tmp_path):
        p = str(tmp_path / "plain.nii")
        with open(p, "w") as fh:
            fh.write("hello")
        verify_gzip_integrity(p)  # should not raise (not a .gz file)


# ==============================================================================
# 3. Single-volume loading and validation
# ==============================================================================

class TestSingleVolumeLoading:
    def test_valid_nii_gz_passes(self, tmp_path):
        data, affine = make_brain_volume()
        p = str(tmp_path / "t1.nii.gz")
        save_nii(data, affine, p)
        out_data, out_affine, out_header = load_and_verify_single_volume(p, "t1")
        assert out_data.shape == data.shape
        assert np.allclose(out_affine, affine)

    def test_valid_nii_uncompressed_passes(self, tmp_path):
        data, affine = make_brain_volume()
        p = str(tmp_path / "t1.nii")
        save_nii(data, affine, p, compressed=False)
        out_data, _, _ = load_and_verify_single_volume(p, "t1")
        assert out_data.shape == (20, 20, 20)

    def test_reject_non_nifti_plain_text(self, tmp_path):
        p = str(tmp_path / "fake.nii")
        with open(p, "w") as fh:
            fh.write("This is not a NIfTI file.")
        with pytest.raises(ValidationError) as exc:
            load_and_verify_single_volume(p, "t1")
        assert exc.value.code == "INVALID_NIFTI"

    def test_reject_2d_volume(self, tmp_path):
        data_2d = np.ones((50, 50), dtype=np.float32) * 50.0
        p = str(tmp_path / "slice2d.nii.gz")
        save_nii(data_2d, np.eye(4), p)
        with pytest.raises(ValidationError) as exc:
            load_and_verify_single_volume(p, "t2")
        assert exc.value.code == "DIMENSION_MISMATCH_NOT_3D"

    def test_reject_4d_volume(self, tmp_path):
        data_4d = np.ones((10, 10, 10, 5), dtype=np.float32) * 50.0
        p = str(tmp_path / "timeseries.nii.gz")
        img = nib.Nifti1Image(data_4d, np.eye(4))
        nib.save(img, p)
        with pytest.raises(ValidationError) as exc:
            load_and_verify_single_volume(p, "t1")
        assert exc.value.code == "DIMENSION_MISMATCH_NOT_3D"

    def test_reject_nan_values(self, tmp_path):
        data = np.ones((20, 20, 20), dtype=np.float32) * 50.0
        data[5, 5, 5] = np.nan
        p = str(tmp_path / "nan.nii.gz")
        save_nii(data, np.eye(4), p)
        with pytest.raises(ValidationError) as exc:
            load_and_verify_single_volume(p, "t1")
        assert exc.value.code == "NON_FINITE_VALUES"

    def test_reject_inf_values(self, tmp_path):
        data = np.ones((20, 20, 20), dtype=np.float32) * 50.0
        data[3, 3, 3] = np.inf
        p = str(tmp_path / "inf.nii.gz")
        save_nii(data, np.eye(4), p)
        with pytest.raises(ValidationError) as exc:
            load_and_verify_single_volume(p, "t1")
        assert exc.value.code == "NON_FINITE_VALUES"

    def test_reject_all_zero_constant(self, tmp_path):
        data = np.zeros((20, 20, 20), dtype=np.float32)
        p = str(tmp_path / "zeros.nii.gz")
        save_nii(data, np.eye(4), p)
        with pytest.raises(ValidationError) as exc:
            load_and_verify_single_volume(p, "flair")
        assert exc.value.code == "CONSTANT_VOLUME"

    def test_reject_constant_nonzero_volume(self, tmp_path):
        data = np.full((20, 20, 20), 42.0, dtype=np.float32)
        p = str(tmp_path / "constant.nii.gz")
        save_nii(data, np.eye(4), p)
        with pytest.raises(ValidationError) as exc:
            load_and_verify_single_volume(p, "t2")
        assert exc.value.code == "CONSTANT_VOLUME"

    def test_reject_corrupt_gzip_as_single_volume(self, tmp_path):
        p = str(tmp_path / "bad.nii.gz")
        with open(p, "wb") as fh:
            fh.write(b"\x1f\x8b\x08corrupted_gzip_content_here")
        with pytest.raises(ValidationError) as exc:
            load_and_verify_single_volume(p, "t1")
        assert exc.value.code in ("CORRUPT_GZIP", "INVALID_NIFTI")

    def test_nibabel_corrects_negative_pixdim(self, tmp_path):
        """
        NiBabel automatically corrects negative pixdim to abs value when loading,
        so negative pixdim alone does not raise a ValidationError.
        This test documents the known NiBabel behaviour.
        """
        data, _ = make_brain_volume()
        img = nib.Nifti1Image(data, np.eye(4))
        img.header['pixdim'][1] = -1.0
        p = str(tmp_path / "neg_spacing.nii.gz")
        nib.save(img, p)
        # NiBabel auto-corrects -> abs(−1.0) = 1.0 -> spacing is valid -> no error
        out_data, _, out_header = load_and_verify_single_volume(p, "t1")
        spacing = [float(z) for z in out_header.get_zooms()[:3]]
        assert all(s > 0 for s in spacing), "NiBabel should have corrected spacing to positive"

    def test_nibabel_corrects_zero_pixdim(self, tmp_path):
        """
        NiBabel automatically corrects zero pixdim to 1 when loading.
        This test documents the known NiBabel behaviour: zero pixdim does not
        propagate as an invalid spacing value into our validator.
        """
        data, _ = make_brain_volume()
        img = nib.Nifti1Image(data, np.eye(4))
        img.header['pixdim'][1] = 0.0
        p = str(tmp_path / "zero_spacing.nii.gz")
        nib.save(img, p)
        # NiBabel auto-corrects 0 -> 1, so spacing is valid; no error expected
        out_data, _, out_header = load_and_verify_single_volume(p, "t1")
        spacing = [float(z) for z in out_header.get_zooms()[:3]]
        assert all(s > 0 for s in spacing), "NiBabel should have corrected zero spacing"


# ==============================================================================
# 4. Anatomical sanity checks
# ==============================================================================

class TestAnatomicalSanity:
    def test_valid_brain_passes(self):
        data, _ = make_brain_volume(shape=(30, 30, 30))
        warnings, meta = validate_anatomical_sanity(data)
        assert meta["sanity_status"] in ("verified_brain", "warning_present")

    def test_sparse_volume_rejected(self):
        data = np.zeros((30, 30, 30), dtype=np.float32)
        data[14, 14, 14] = 100.0  # nearly empty (<2% fg)
        with pytest.raises(ValidationError) as exc:
            validate_anatomical_sanity(data)
        assert exc.value.code == "REFUSAL_NOT_A_BRAIN"

    def test_dense_volume_rejected(self):
        data = np.full((30, 30, 30), 100.0, dtype=np.float32)  # >95% fg
        with pytest.raises(ValidationError) as exc:
            validate_anatomical_sanity(data)
        assert exc.value.code == "REFUSAL_NOT_A_BRAIN"

    def test_skull_stripped_passes(self):
        data, _ = make_brain_volume(shape=(30, 30, 30))
        is_stripped, ratio = check_skull_stripping_heuristic(data)
        assert is_stripped  # borders are zeroed

    def test_non_skull_stripped_emits_warning(self):
        data = np.random.uniform(50.0, 150.0, size=(30, 30, 30)).astype(np.float32)
        is_stripped, ratio = check_skull_stripping_heuristic(data)
        assert not is_stripped
        assert ratio >= 0.20


# ==============================================================================
# 5. Full study validation — valid cases
# ==============================================================================

class TestValidStudy:
    def test_valid_four_sequences_passes(self, tmp_path):
        paths = make_study_paths(tmp_path)
        result = validate_study(paths)
        assert result["status"] == "passed"
        assert set(result["files"].keys()) >= {"t1", "t1gd", "t2", "flair"}

    def test_valid_study_with_expert_mask(self, tmp_path):
        shape = (20, 20, 20)
        affine = np.diag([1.0, 1.0, 2.0, 1.0])
        paths = make_study_paths(tmp_path, shape=shape, affine=affine)
        mask_p = make_expert_mask(shape, affine, tmp_path)
        result = validate_study(paths, expert_mask_path=mask_p)
        assert result["status"] == "passed"
        assert result["has_expert_mask"] is True

    def test_spatial_metadata_returned(self, tmp_path):
        paths = make_study_paths(tmp_path, shape=(20, 20, 20))
        result = validate_study(paths)
        sm = result["spatial_metadata"]
        assert sm["shape"] == [20, 20, 20]
        assert len(sm["spacing_mm"]) == 3
        assert all(s > 0 for s in sm["spacing_mm"])
        assert len(sm["reference_affine"]) == 4

    def test_anisotropic_spacing_passes(self, tmp_path):
        affine = np.diag([0.9375, 0.9375, 1.0, 1.0])
        paths = make_study_paths(tmp_path, shape=(20, 20, 20), affine=affine)
        result = validate_study(paths)
        assert result["status"] == "passed"
        assert result["spatial_metadata"]["spacing_mm"] == pytest.approx([0.9375, 0.9375, 1.0], rel=1e-3)

    def test_non_identity_affine_passes(self, tmp_path):
        affine = np.array([
            [0.9375, 0.0, 0.0, -120.0],
            [0.0, 0.9375, 0.0, -126.0],
            [0.0, 0.0, 1.0, -72.0],
            [0.0, 0.0, 0.0, 1.0],
        ], dtype=np.float64)
        paths = make_study_paths(tmp_path, shape=(20, 20, 20), affine=affine)
        result = validate_study(paths)
        assert result["status"] == "passed"

    def test_both_nii_and_niigz_in_same_study(self, tmp_path):
        affine = np.diag([1.0, 1.0, 2.0, 1.0])
        paths = {}
        for i, seq in enumerate(REQUIRED_SEQUENCES):
            data, _ = make_brain_volume(seed=i)
            ext = ".nii" if i % 2 == 0 else ".nii.gz"
            p = str(tmp_path / f"study_{seq}{ext}")
            save_nii(data, affine, p)
            paths[seq] = p
        result = validate_study(paths)
        assert result["status"] == "passed"


# ==============================================================================
# 6. Missing sequence failures
# ==============================================================================

class TestMissingSequences:
    def test_reject_three_sequences(self, tmp_path):
        paths = make_study_paths(tmp_path)
        del paths["t1gd"]
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "MISSING_SEQUENCE"
        assert exc.value.details["missing_sequence"] == "t1gd"

    def test_reject_two_sequences(self, tmp_path):
        paths = make_study_paths(tmp_path)
        del paths["t1gd"]
        del paths["flair"]
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "MISSING_SEQUENCE"

    def test_reject_empty_dict(self):
        with pytest.raises(ValidationError) as exc:
            validate_study({})
        assert exc.value.code == "MISSING_SEQUENCE"

    def test_missing_sequence_message_names_it(self, tmp_path):
        paths = make_study_paths(tmp_path)
        del paths["flair"]
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert "flair" in exc.value.message.lower()


# ==============================================================================
# 7. Geometry mismatch failures
# ==============================================================================

class TestGeometryMismatches:
    def test_reject_mismatched_shapes(self, tmp_path):
        paths = make_study_paths(tmp_path, shape=(20, 20, 20))
        # Replace T2 with a different shape
        data = make_brain_volume(shape=(20, 20, 25))[0]
        p = str(tmp_path / "diff_shape.nii.gz")
        save_nii(data, np.diag([1.0, 1.0, 2.0, 1.0]), p)
        paths["t2"] = p
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "MISMATCHED_SHAPES"

    def test_reject_mismatched_affines(self, tmp_path):
        paths = make_study_paths(tmp_path, shape=(20, 20, 20))
        data, _ = make_brain_volume(shape=(20, 20, 20))
        diff_affine = np.diag([1.5, 1.0, 2.0, 1.0])  # altered X spacing
        p = str(tmp_path / "diff_affine.nii.gz")
        save_nii(data, diff_affine, p)
        paths["flair"] = p
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "MISMATCHED_AFFINES"
        assert "flair" in exc.value.message.lower()

    def test_reject_non_nifti_renamed(self, tmp_path):
        paths = make_study_paths(tmp_path)
        fake = str(tmp_path / "fake.nii")
        with open(fake, "w") as fh:
            fh.write("I am not a NIfTI file.")
        paths["t1"] = fake
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "INVALID_NIFTI"

    def test_reject_corrupt_gzip_in_study(self, tmp_path):
        paths = make_study_paths(tmp_path)
        corrupt = str(tmp_path / "corrupt.nii.gz")
        with open(corrupt, "wb") as fh:
            fh.write(b"\x1f\x8b\x08not_valid_gzip")
        paths["t2"] = corrupt
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code in ("CORRUPT_GZIP", "INVALID_NIFTI")


# ==============================================================================
# 8. Numerical validity failures
# ==============================================================================

class TestNumericalValidity:
    def test_reject_all_zeros(self, tmp_path):
        paths = make_study_paths(tmp_path)
        data = np.zeros((20, 20, 20), dtype=np.float32)
        p = str(tmp_path / "zeros.nii.gz")
        save_nii(data, np.diag([1.0, 1.0, 2.0, 1.0]), p)
        paths["flair"] = p
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "CONSTANT_VOLUME"

    def test_reject_nan(self, tmp_path):
        paths = make_study_paths(tmp_path)
        data, affine = make_brain_volume()
        data[5, 5, 5] = np.nan
        p = str(tmp_path / "nan.nii.gz")
        save_nii(data, affine, p)
        paths["t1"] = p
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "NON_FINITE_VALUES"

    def test_reject_inf(self, tmp_path):
        paths = make_study_paths(tmp_path)
        data, affine = make_brain_volume()
        data[3, 3, 3] = -np.inf
        p = str(tmp_path / "inf.nii.gz")
        save_nii(data, affine, p)
        paths["t2"] = p
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "NON_FINITE_VALUES"

    def test_reject_constant_nonzero(self, tmp_path):
        paths = make_study_paths(tmp_path)
        data = np.full((20, 20, 20), 99.9, dtype=np.float32)
        p = str(tmp_path / "const.nii.gz")
        save_nii(data, np.diag([1.0, 1.0, 2.0, 1.0]), p)
        paths["t1gd"] = p
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "CONSTANT_VOLUME"


# ==============================================================================
# 9. Expert mask validation
# ==============================================================================

class TestExpertMaskValidation:
    def test_valid_expert_mask_passes(self, tmp_path):
        shape = (20, 20, 20)
        affine = np.diag([1.0, 1.0, 2.0, 1.0])
        paths = make_study_paths(tmp_path, shape=shape, affine=affine)
        mask_p = make_expert_mask(shape, affine, tmp_path)
        result = validate_study(paths, expert_mask_path=mask_p)
        assert result["has_expert_mask"] is True
        assert "expert_mask" in result["files"]

    def test_missing_expert_mask_is_optional(self, tmp_path):
        paths = make_study_paths(tmp_path)
        result = validate_study(paths, expert_mask_path=None)
        assert result["has_expert_mask"] is False
        assert result["status"] == "passed"

    def test_reject_invalid_labels(self, tmp_path):
        shape = (20, 20, 20)
        affine = np.diag([1.0, 1.0, 2.0, 1.0])
        paths = make_study_paths(tmp_path, shape=shape, affine=affine)

        bad_mask = np.zeros(shape, dtype=np.uint8)
        bad_mask[5:10, 5:10, 5:10] = 3  # Label 3 is forbidden in BraTS 2021
        p = str(tmp_path / "bad_labels.nii.gz")
        save_nii(bad_mask.astype(np.float32), affine, p)

        with pytest.raises(ValidationError) as exc:
            validate_study(paths, expert_mask_path=p)
        assert exc.value.code == "INVALID_EXPERT_MASK_LABELS"
        assert 3 in exc.value.details["invalid_labels"]

    def test_reject_mask_with_shape_mismatch(self, tmp_path):
        shape = (20, 20, 20)
        affine = np.diag([1.0, 1.0, 2.0, 1.0])
        paths = make_study_paths(tmp_path, shape=shape, affine=affine)

        wrong_mask = np.zeros((25, 25, 25), dtype=np.float32)
        p = str(tmp_path / "wrong_shape_mask.nii.gz")
        save_nii(wrong_mask, affine, p)

        with pytest.raises(ValidationError) as exc:
            validate_study(paths, expert_mask_path=p)
        assert exc.value.code == "INVALID_EXPERT_MASK_GEOMETRY"

    def test_reject_mask_with_affine_mismatch(self, tmp_path):
        shape = (20, 20, 20)
        affine = np.diag([1.0, 1.0, 2.0, 1.0])
        wrong_affine = np.diag([2.0, 1.0, 2.0, 1.0])
        paths = make_study_paths(tmp_path, shape=shape, affine=affine)

        mask = np.zeros(shape, dtype=np.float32)
        p = str(tmp_path / "bad_affine_mask.nii.gz")
        save_nii(mask, wrong_affine, p)

        with pytest.raises(ValidationError) as exc:
            validate_study(paths, expert_mask_path=p)
        assert exc.value.code == "INVALID_EXPERT_MASK_GEOMETRY"

    def test_valid_brats_labels_accepted(self, tmp_path):
        """All four BraTS 2021 labels {0, 1, 2, 4} should be accepted."""
        shape = (20, 20, 20)
        affine = np.diag([1.0, 1.0, 2.0, 1.0])
        paths = make_study_paths(tmp_path, shape=shape, affine=affine)

        mask = np.zeros(shape, dtype=np.uint8)
        mask[2:5, 2:5, 2:5] = 4
        mask[5:8, 5:8, 5:8] = 1
        mask[8:11, 8:11, 8:11] = 2
        p = str(tmp_path / "full_labels.nii.gz")
        save_nii(mask.astype(np.float32), affine, p)

        result = validate_study(paths, expert_mask_path=p)
        assert result["has_expert_mask"] is True
        labels = set(result["files"]["expert_mask"]["unique_labels"])
        assert labels.issubset(ALLOWED_BRATS_LABELS)

    def test_reject_corrupt_expert_mask(self, tmp_path):
        shape = (20, 20, 20)
        affine = np.diag([1.0, 1.0, 2.0, 1.0])
        paths = make_study_paths(tmp_path, shape=shape, affine=affine)

        bad_p = str(tmp_path / "corrupt_mask.nii.gz")
        with open(bad_p, "wb") as fh:
            fh.write(b"\x1f\x8b\x08corrupt")

        with pytest.raises(ValidationError) as exc:
            validate_study(paths, expert_mask_path=bad_p)
        assert exc.value.code in ("CORRUPT_GZIP", "INVALID_NIFTI", "INVALID_EXPERT_MASK")


# ==============================================================================
# 10. Case storage security
# ==============================================================================

class TestCaseStorageSecurity:
    def test_create_case_workspace_returns_valid_id(self):
        case_id, case_dir = create_case_workspace()
        assert case_id.startswith("case_")
        assert os.path.isdir(case_dir)
        # Cleanup
        import shutil
        shutil.rmtree(case_dir, ignore_errors=True)

    def test_invalid_case_id_traversal_rejected(self):
        with pytest.raises(ValueError):
            get_case_dir("../escape")

    def test_case_id_with_null_bytes_rejected(self):
        with pytest.raises(ValueError):
            get_case_dir("case_\x00injected")

    def test_case_id_with_absolute_path_rejected(self):
        with pytest.raises(ValueError):
            get_case_dir("/etc/passwd")

    def test_valid_case_id_format_accepted(self):
        case_id, case_dir = create_case_workspace()
        assert validate_case_id(case_id)
        import shutil
        shutil.rmtree(case_dir, ignore_errors=True)

    def test_malformed_case_id_rejected(self):
        assert not validate_case_id("not-a-valid-case")

    def test_too_short_case_id_rejected(self):
        with pytest.raises(ValueError):
            get_case_dir("abc")


# ==============================================================================
# 11. Imputation (allow_imputation=True)
# ==============================================================================

class TestImputation:
    def test_imputation_with_one_missing_sequence(self, tmp_path):
        paths = make_study_paths(tmp_path)
        del paths["flair"]
        result = validate_study(paths, allow_imputation=True)
        assert result["status"] == "passed"
        warning_text = " ".join(result["warnings"])
        assert "WARNING_SEQUENCE_IMPUTED" in warning_text
        assert "flair" in warning_text.lower()

    def test_imputation_fails_with_two_missing(self, tmp_path):
        paths = make_study_paths(tmp_path)
        del paths["flair"]
        del paths["t2"]
        with pytest.raises(ValidationError) as exc:
            validate_study(paths, allow_imputation=True)
        assert exc.value.code == "MISSING_SEQUENCE"

    def test_no_imputation_raises_missing(self, tmp_path):
        paths = make_study_paths(tmp_path)
        del paths["t1gd"]
        with pytest.raises(ValidationError) as exc:
            validate_study(paths, allow_imputation=False)
        assert exc.value.code == "MISSING_SEQUENCE"


# ==============================================================================
# 12. Integration: validation result structure
# ==============================================================================

class TestValidationResultStructure:
    def test_result_has_required_keys(self, tmp_path):
        paths = make_study_paths(tmp_path)
        result = validate_study(paths)
        required_keys = {"status", "spatial_metadata", "has_expert_mask", "files", "warnings", "anatomical_sanity"}
        assert required_keys.issubset(result.keys())

    def test_spatial_metadata_has_required_keys(self, tmp_path):
        paths = make_study_paths(tmp_path)
        result = validate_study(paths)
        sm = result["spatial_metadata"]
        assert "shape" in sm
        assert "spacing_mm" in sm
        assert "reference_affine" in sm

    def test_all_sequences_in_files(self, tmp_path):
        paths = make_study_paths(tmp_path)
        result = validate_study(paths)
        for seq in REQUIRED_SEQUENCES:
            assert seq in result["files"]

    def test_validation_never_returns_passed_on_failure(self, tmp_path):
        """
        A ValidationError must always be raised on failure — never a dict with status='passed'.
        """
        paths = make_study_paths(tmp_path)
        del paths["t1"]
        with pytest.raises(ValidationError):
            validate_study(paths)

    def test_valid_study_passes_anatomical_sanity(self, tmp_path):
        paths = make_study_paths(tmp_path)
        result = validate_study(paths)
        assert result["anatomical_sanity"]["sanity_status"] in ("verified_brain", "warning_present")


# ==============================================================================
# 13. MANDATORY FAILURE PACK (8 cases from the PRD)
# ==============================================================================

class TestMandatoryFailurePack:
    """Tests the 8 mandatory failure cases from the acceptance criteria."""

    def test_fp1_non_nifti_renamed_to_nii_gz(self, tmp_path):
        """FP-1: A non-NIfTI file renamed to .nii.gz must be rejected."""
        paths = make_study_paths(tmp_path)
        fake = str(tmp_path / "renamed.nii.gz")
        with gzip.open(fake, "wb") as gz:
            gz.write(b"Hello, I am not a NIfTI file!")
        paths["t1"] = fake
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "INVALID_NIFTI"

    def test_fp2_corrupt_gzip(self, tmp_path):
        """FP-2: A corrupt gzip file must be rejected."""
        paths = make_study_paths(tmp_path)
        corrupt = str(tmp_path / "corrupt.nii.gz")
        with open(corrupt, "wb") as fh:
            fh.write(b"\x1f\x8b\x08CORRUPTED_DATA_HERE!!!")
        paths["flair"] = corrupt
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code in ("CORRUPT_GZIP", "INVALID_NIFTI")

    def test_fp3_only_three_sequences(self, tmp_path):
        """FP-3: Only three required MRI sequences must be rejected."""
        paths = make_study_paths(tmp_path)
        del paths["t2"]
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "MISSING_SEQUENCE"

    def test_fp4_mismatched_dimensions(self, tmp_path):
        """FP-4: Mismatched image dimensions must be rejected."""
        paths = make_study_paths(tmp_path, shape=(20, 20, 20))
        data, _ = make_brain_volume(shape=(20, 20, 25))
        p = str(tmp_path / "diff_dim.nii.gz")
        save_nii(data, np.diag([1.0, 1.0, 2.0, 1.0]), p)
        paths["t1gd"] = p
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "MISMATCHED_SHAPES"

    def test_fp5_mismatched_affines(self, tmp_path):
        """FP-5: Mismatched spatial affines must be rejected."""
        paths = make_study_paths(tmp_path, shape=(20, 20, 20))
        data, _ = make_brain_volume(shape=(20, 20, 20))
        diff_affine = np.diag([2.0, 1.0, 2.0, 1.0])
        p = str(tmp_path / "diff_affine.nii.gz")
        save_nii(data, diff_affine, p)
        paths["t2"] = p
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "MISMATCHED_AFFINES"

    def test_fp6_2d_image(self, tmp_path):
        """FP-6: A 2D image must be rejected."""
        paths = make_study_paths(tmp_path)
        data_2d = np.ones((50, 50), dtype=np.float32) * 50.0
        p = str(tmp_path / "slice_2d.nii.gz")
        save_nii(data_2d, np.eye(4), p)
        paths["t1"] = p
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "DIMENSION_MISMATCH_NOT_3D"

    def test_fp7_all_zero_image(self, tmp_path):
        """FP-7: An all-zero image must be rejected."""
        paths = make_study_paths(tmp_path)
        zeros = np.zeros((20, 20, 20), dtype=np.float32)
        p = str(tmp_path / "zeros.nii.gz")
        save_nii(zeros, np.diag([1.0, 1.0, 2.0, 1.0]), p)
        paths["t1gd"] = p
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "CONSTANT_VOLUME"

    def test_fp8_nan_or_infinity(self, tmp_path):
        """FP-8: An image containing NaN or infinity must be rejected."""
        paths = make_study_paths(tmp_path)
        data, affine = make_brain_volume()
        data[10, 10, 10] = np.inf
        p = str(tmp_path / "inf.nii.gz")
        save_nii(data, affine, p)
        paths["flair"] = p
        with pytest.raises(ValidationError) as exc:
            validate_study(paths)
        assert exc.value.code == "NON_FINITE_VALUES"
