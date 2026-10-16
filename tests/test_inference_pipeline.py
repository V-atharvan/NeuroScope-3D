"""
Unit and integration tests for the standalone inference pipeline.
Tests label conversion, nesting enforcement, grid restoration, and preprocessing validation.
"""
import os
import tempfile
import numpy as np
import pytest
import nibabel as nib

from inference.preprocessing import (
    load_and_validate_nifti,
    normalize_intensity_nonzero,
    preprocess_study,
    PreprocessingError,
)
from inference.postprocessing import (
    enforce_nesting_and_convert_labels,
    restore_original_grid,
    validate_label_map,
    derive_region_masks,
    PostprocessingError,
)


def test_nonzero_intensity_normalization():
    """Verify z-score normalization on nonzero voxels only."""
    data = np.zeros((10, 10, 10), dtype=np.float32)
    data[2:8, 2:8, 2:8] = np.random.uniform(50.0, 150.0, size=(6, 6, 6)).astype(np.float32)

    normalized = normalize_intensity_nonzero(data)

    # Background remains strictly 0
    assert np.all(normalized[data == 0] == 0.0)

    # Nonzero voxels have mean ~ 0 and std ~ 1
    nonzero_vals = normalized[data > 0]
    assert np.isclose(np.mean(nonzero_vals), 0.0, atol=1e-5)
    assert np.isclose(np.std(nonzero_vals), 1.0, atol=1e-5)


def test_enforce_nesting_and_label_conversion_standard():
    """
    Test standard mapping from 3 subregions (TC, WT, ET) to BraTS 2021 labels.
    Channel 0: TC, Channel 1: WT, Channel 2: ET
    """
    # Create 3-channel logits array with 4 voxels:
    # Voxel 0: Background (all negative)
    # Voxel 1: ED only (WT positive, TC/ET negative) -> Label 2
    # Voxel 2: NCR (WT & TC positive, ET negative) -> Label 1
    # Voxel 3: ET (WT, TC, ET all positive) -> Label 4
    logits = np.full((3, 1, 1, 4), -10.0, dtype=np.float32)

    # Voxel 1: ED (WT active)
    logits[1, 0, 0, 1] = 10.0

    # Voxel 2: NCR (WT and TC active)
    logits[0, 0, 0, 2] = 10.0
    logits[1, 0, 0, 2] = 10.0

    # Voxel 3: ET (All three active)
    logits[0, 0, 0, 3] = 10.0
    logits[1, 0, 0, 3] = 10.0
    logits[2, 0, 0, 3] = 10.0

    labels = enforce_nesting_and_convert_labels(logits, threshold=0.5, is_logits=True)

    expected = np.array([[[0, 2, 1, 4]]], dtype=np.uint8)
    np.testing.assert_array_equal(labels, expected)


def test_enforce_nesting_anomalous_correction():
    """
    Test that an anomalous prediction where ET is positive but TC/WT were below threshold
    is properly nested (ET ⊆ TC ⊆ WT) and mapped to Label 4.
    """
    logits = np.full((3, 1, 1, 1), -10.0, dtype=np.float32)
    logits[2, 0, 0, 0] = 10.0  # Only ET is high

    labels = enforce_nesting_and_convert_labels(logits, threshold=0.5, is_logits=True)
    assert labels[0, 0, 0] == 4  # Should be ET

    # Check derived masks guarantee ET ⊆ TC ⊆ WT
    masks = derive_region_masks(labels)
    assert masks["ET"][0, 0, 0] == True
    assert masks["TC"][0, 0, 0] == True
    assert masks["WT"][0, 0, 0] == True


def test_derive_region_masks_definitions():
    """
    Verify BraTS 2021 region definitions:
    WT = {1, 2, 4}, TC = {1, 4}, ET = {4}
    """
    labels = np.array([[[0, 1, 2, 4]]], dtype=np.uint8)
    masks = derive_region_masks(labels)

    # WT includes 1, 2, 4
    np.testing.assert_array_equal(masks["WT"], np.array([[[False, True, True, True]]]))

    # TC includes 1, 4
    np.testing.assert_array_equal(masks["TC"], np.array([[[False, True, False, True]]]))

    # ET includes 4 only
    np.testing.assert_array_equal(masks["ET"], np.array([[[False, False, False, True]]]))


def test_restore_original_grid_nearest_neighbour():
    """
    Verify that restoring a resampled grid preserves categorical labels {0, 1, 2, 4}
    without creating non-categorical interpolation artifacts (e.g. 3).
    """
    small_labels = np.array([
        [[0, 1], [2, 4]],
        [[4, 2], [1, 0]]
    ], dtype=np.uint8)  # shape (2, 2, 2)

    target_shape = (10, 12, 14)
    upsampled = restore_original_grid(small_labels, target_shape=target_shape)

    assert upsampled.shape == target_shape
    assert set(np.unique(upsampled)).issubset({0, 1, 2, 4})
    # Label 3 should NEVER exist
    assert 3 not in upsampled


def test_validate_label_map_rejections():
    """Verify validation rejects invalid shapes or label values."""
    valid_map = np.zeros((20, 20, 20), dtype=np.uint8)
    valid_map[5:10, 5:10, 5:10] = 2
    validate_label_map(valid_map, expected_shape=(20, 20, 20))  # Should pass

    # Reject shape mismatch
    with pytest.raises(PostprocessingError, match="does not match reference shape"):
        validate_label_map(valid_map, expected_shape=(20, 20, 25))

    # Reject invalid label 3
    invalid_map = valid_map.copy()
    invalid_map[0, 0, 0] = 3
    with pytest.raises(PostprocessingError, match="invalid label values"):
        validate_label_map(invalid_map, expected_shape=(20, 20, 20))


def test_preprocess_study_end_to_end_synthetic():
    """
    Creates temporary synthetic NIfTI sequences and verifies channel stacking
    and affine checks.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        shape = (16, 16, 16)
        affine = np.eye(4, dtype=np.float32)

        paths = {}
        for seq in ["t1", "t1gd", "t2", "flair"]:
            data = np.random.uniform(10.0, 100.0, size=shape).astype(np.float32)
            nii = nib.Nifti1Image(data, affine=affine)
            p = os.path.join(tmpdir, f"case_{seq}.nii.gz")
            nib.save(nii, p)
            paths[seq] = p

        # Test valid preprocessing
        tensor, meta = preprocess_study(paths)
        assert tensor.shape == (4, 16, 16, 16)
        assert meta["original_shape"] == [16, 16, 16]

        # Test rejection of incompatible affine
        bad_affine = affine.copy()
        bad_affine[0, 3] = 15.0  # translate X by 15mm
        bad_nii = nib.Nifti1Image(np.ones(shape, dtype=np.float32), affine=bad_affine)
        bad_path = os.path.join(tmpdir, "case_flair_bad.nii.gz")
        nib.save(bad_nii, bad_path)

        paths_bad = paths.copy()
        paths_bad["flair"] = bad_path
        with pytest.raises(PreprocessingError, match="Incompatible spatial affine"):
            preprocess_study(paths_bad)
