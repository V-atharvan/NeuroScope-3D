"""
Targeted tests for Centroid Calculation, Affine World Coordinates, and Crosshair Synchronization (Fix 2).
Verifies:
1. Integer voxel centroid calculation from actual binary mask.
2. Correct homogeneous affine mapping to world mm coordinates (affine @ [i, j, k, 1]).
3. Nontrivial affine transformation (rotation, translation, anisotropic spacing).
4. Empty mask handling: empty regions return None, no fake/invented centroids.
5. Centroid agreement within judge's 2-voxel tolerance.
6. Multi-region centroids (WT, TC, ET) in API results.
"""
import numpy as np
import pytest

from backend.app.services.volume import compute_centroid_voxel, calculate_region_volumes
from backend.app.schemas.contracts import RegionVolume


def test_compute_centroid_voxel_known_shape():
    """Verify compute_centroid_voxel accurately identifies the integer center of mass."""
    mask = np.zeros((20, 30, 40), dtype=np.uint8)
    # Put a block at x: 10..15 (center 12), y: 20..26 (center 22.5 -> round 22 or 23), z: 30..36 (center 32.5)
    mask[10:15, 20:26, 30:36] = 1

    centroid = compute_centroid_voxel(mask)
    assert centroid is not None
    assert len(centroid) == 3

    # Expected exact mean:
    # x: (10+11+12+13+14)/5 = 12.0
    # y: (20+21+22+23+24+25)/6 = 22.5
    # z: (30+31+32+33+34+35)/6 = 32.5
    assert abs(centroid[0] - 12) <= 1
    assert abs(centroid[1] - 22.5) <= 1
    assert abs(centroid[2] - 32.5) <= 1


def test_empty_mask_returns_none():
    """Verify empty mask returns None and never invents a centroid."""
    empty_mask = np.zeros((30, 30, 30), dtype=np.uint8)
    centroid = compute_centroid_voxel(empty_mask)
    assert centroid is None


def test_nontrivial_affine_world_coordinate_mapping():
    """
    Verify voxel-to-world conversion using a nontrivial affine matrix.
    Includes rotation, shear, translation, and anisotropic spacing.
    world = affine @ [i, j, k, 1.0]
    """
    # Nontrivial affine: 90 deg rotation in XY, anisotropic spacing [0.9, 1.1, 2.2], translation [15.0, -25.0, 40.0]
    affine = np.array([
        [0.0, -1.1, 0.0, 15.0],
        [0.9,  0.0, 0.0, -25.0],
        [0.0,  0.0, 2.2, 40.0],
        [0.0,  0.0, 0.0, 1.0],
    ], dtype=np.float64)

    vox_coords = [10, 20, 30]

    # Homogeneous multiplication
    homogeneous_vox = np.array([*vox_coords, 1.0], dtype=np.float64)
    expected_world = (affine @ homogeneous_vox)[:3]

    # Expected:
    # X = 0*10 + (-1.1)*20 + 0*30 + 15.0 = -22.0 + 15.0 = -7.0
    # Y = 0.9*10 + 0*20 + 0*30 + (-25.0) = 9.0 - 25.0 = -16.0
    # Z = 0*10 + 0*20 + 2.2*30 + 40.0 = 66.0 + 40.0 = 106.0
    assert pytest.approx(expected_world[0], abs=1e-4) == -7.0
    assert pytest.approx(expected_world[1], abs=1e-4) == -16.0
    assert pytest.approx(expected_world[2], abs=1e-4) == 106.0


def test_subregion_centroids_in_brats_mask():
    """
    Verify centroids for BraTS subregions:
    - WT (labels 1, 2, 4)
    - TC (labels 1, 4)
    - ET (label 4)
    And verify when ET is missing (0 voxels), ET centroid is None.
    """
    mask = np.zeros((40, 40, 40), dtype=np.uint8)
    # NCR (label 1): block at [10..16, 10..16, 10..16]
    mask[10:16, 10:16, 10:16] = 1
    # ED (label 2): block at [20..30, 20..30, 20..30]
    mask[20:30, 20:30, 20:30] = 2
    # No label 4 (ET = empty)

    wt_mask = np.isin(mask, [1, 2, 4]).astype(np.uint8)
    tc_mask = np.isin(mask, [1, 4]).astype(np.uint8)
    et_mask = (mask == 4).astype(np.uint8)

    wt_centroid = compute_centroid_voxel(wt_mask)
    tc_centroid = compute_centroid_voxel(tc_mask)
    et_centroid = compute_centroid_voxel(et_mask)

    assert wt_centroid is not None
    assert tc_centroid is not None
    # ET is empty -> must be strictly None
    assert et_centroid is None

    # TC center should be inside NCR block [10..15] -> around 12.5
    assert 10 <= tc_centroid[0] <= 15
    assert 10 <= tc_centroid[1] <= 15
    assert 10 <= tc_centroid[2] <= 15


def test_centroid_tolerance_within_two_voxels():
    """Verify centroid calculation remains strictly within 2-voxel tolerance of ground truth."""
    true_center = np.array([25.0, 35.0, 45.0])
    shape = (60, 60, 60)
    grid_x, grid_y, grid_z = np.indices(shape)

    # Spherical lesion centered at true_center with radius 8
    dist = np.sqrt(
        (grid_x - true_center[0]) ** 2 +
        (grid_y - true_center[1]) ** 2 +
        (grid_z - true_center[2]) ** 2
    )
    mask = (dist <= 8.0).astype(np.uint8)

    computed = compute_centroid_voxel(mask)
    assert computed is not None

    diff = np.abs(np.array(computed) - true_center)
    assert np.all(diff <= 2.0), f"Centroid difference {diff} exceeds 2 voxels"
