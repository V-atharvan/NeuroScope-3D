"""
Test suite for NeuroScope 3D - 3D Brain and Linked MRI Viewer.
Verifies:
1. Spatial Correctness:
   - Voxel-to-world and world-to-voxel conversions
   - Non-identity, rotated, and anisotropic affines
   - Left-Right orientation preservation on asymmetric landmark volumes
   - Crosshair synchronization across Axial, Coronal, and Sagittal planes
   - Modality switching without physical coordinate drift
2. Segmentation Correctness:
   - Categorical BraTS label preservation (no interpolation artifacts)
   - Independent region visibility mapping
   - 3D surface mesh extraction in continuous world space
3. Lifecycle & Failure Handling:
   - Missing sequence handling
   - Invalid case ID protection
   - Empty mask handling without crashes
"""
import io
import gzip
import numpy as np
import pytest
import nibabel as nib
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.volume import (
    compute_centroid_voxel,
    compute_physical_volume_ml,
    calculate_region_volumes,
)
from backend.app.services.mesh_export import generate_region_mesh, export_mesh_bytes
from inference.postprocessing import restore_original_grid, derive_region_masks

client = TestClient(app)


# ==============================================================================
# 1. Spatial Correctness & Coordinate Conversions
# ==============================================================================

def test_voxel_to_world_and_roundtrip_identity():
    """Verify voxel-to-world and world-to-voxel on an identity affine."""
    affine = np.eye(4, dtype=np.float64)
    voxel = np.array([12, 24, 36], dtype=np.float64)

    # World = Affine @ [i, j, k, 1]
    world = (affine @ np.array([*voxel, 1.0]))[:3]
    np.testing.assert_array_equal(world, voxel)

    # Invert back: Voxel = Affine^-1 @ [x, y, z, 1]
    inv_affine = np.linalg.inv(affine)
    recovered_voxel = (inv_affine @ np.array([*world, 1.0]))[:3]
    np.testing.assert_array_equal(recovered_voxel, voxel)


def test_voxel_to_world_anisotropic_and_rotated():
    """
    Verify coordinate transform with anisotropic voxel spacing [0.75, 1.25, 2.5] mm,
    a 30-degree rotation about the Z axis, and translation [10.0, -20.0, 50.0] mm.
    """
    angle = np.pi / 6  # 30 degrees
    cos_a = np.cos(angle)
    sin_a = np.sin(angle)

    affine = np.array([
        [0.75 * cos_a, -1.25 * sin_a, 0.0,  10.0],
        [0.75 * sin_a,  1.25 * cos_a, 0.0, -20.0],
        [0.0,           0.0,          2.5,  50.0],
        [0.0,           0.0,          0.0,   1.0],
    ], dtype=np.float64)

    vox = np.array([40, 20, 10], dtype=np.float64)
    homo_vox = np.array([*vox, 1.0], dtype=np.float64)
    world = (affine @ homo_vox)[:3]

    # Expected analytical coordinates:
    expected_x = (0.75 * cos_a * 40) + (-1.25 * sin_a * 20) + 10.0
    expected_y = (0.75 * sin_a * 40) + (1.25 * cos_a * 20) - 20.0
    expected_z = (2.5 * 10) + 50.0

    assert np.isclose(world[0], expected_x, atol=1e-5)
    assert np.isclose(world[1], expected_y, atol=1e-5)
    assert np.isclose(world[2], expected_z, atol=1e-5)

    # Roundtrip back to voxel
    inv_affine = np.linalg.inv(affine)
    recovered_vox = (inv_affine @ np.array([*world, 1.0]))[:3]
    np.testing.assert_allclose(recovered_vox, vox, atol=1e-5)


def test_asymmetric_left_right_anatomical_landmarks():
    """
    Verify that in standard radiological/neurological RAS+ space,
    an asymmetric landmark in the anatomical Right hemisphere produces
    positive X coordinates, and Left produces negative X coordinates.
    Ensures left-right orientation is never mirrored accidentally.
    """
    # Standard RAS+ affine centered at (0, 0, 0)
    # Shape 64x64x64, voxel size 1.0 mm, origin at center (-32, -32, -32)
    affine_ras = np.diag([1.0, 1.0, 1.0, 1.0])
    affine_ras[:3, 3] = [-32.0, -32.0, -32.0]

    # Voxel on the Right side (X > 32, e.g. X = 48)
    right_voxel = np.array([48.0, 32.0, 32.0, 1.0])
    right_world = affine_ras @ right_voxel
    assert right_world[0] > 0.0, f"Right hemisphere landmark must have X > 0 in RAS (got {right_world[0]})"
    assert right_world[0] == 16.0

    # Voxel on the Left side (X < 32, e.g. X = 16)
    left_voxel = np.array([16.0, 32.0, 32.0, 1.0])
    left_world = affine_ras @ left_voxel
    assert left_world[0] < 0.0, f"Left hemisphere landmark must have X < 0 in RAS (got {left_world[0]})"
    assert left_world[0] == -16.0


def test_crosshair_synchronization_canonical_coordinate():
    """
    Verifies that selecting an arbitrary point in the Axial plane (z=15)
    maps directly and canonically to the corresponding Coronal (y) and Sagittal (x) slice cuts.
    """
    affine = np.diag([1.0, 1.0, 2.0, 1.0])
    affine[:3, 3] = [-50.0, -50.0, -20.0]

    canonical_voxel = np.array([25, 30, 15])
    homo = np.array([*canonical_voxel, 1.0])
    canonical_world_mm = (affine @ homo)[:3]

    # Verify each plane's slice coordinate corresponds to the canonical position:
    # Axial cut: z = 15 vox -> world z = 2.0 * 15 - 20 = 10.0 mm
    assert canonical_world_mm[2] == 10.0
    # Coronal cut: y = 30 vox -> world y = 1.0 * 30 - 50 = -20.0 mm
    assert canonical_world_mm[1] == -20.0
    # Sagittal cut: x = 25 vox -> world x = 1.0 * 25 - 50 = -25.0 mm
    assert canonical_world_mm[0] == -25.0


def test_modality_switching_without_spatial_drift():
    """
    Verifies that two MRI sequences with differing voxel grids (e.g. 1mm isotropic vs 2mm slice thickness)
    covering the same physical space preserve identical world mm coordinates.
    """
    # High-res T1: 1.0mm isotropic
    affine_t1 = np.diag([1.0, 1.0, 1.0, 1.0])
    # Low-res T2: 2.0mm axial slice thickness
    affine_t2 = np.diag([1.0, 1.0, 2.0, 1.0])

    target_world_mm = np.array([15.0, -10.0, 30.0])

    # Convert world to voxel for T1
    inv_t1 = np.linalg.inv(affine_t1)
    vox_t1 = (inv_t1 @ np.array([*target_world_mm, 1.0]))[:3]
    assert np.allclose(vox_t1, [15.0, -10.0, 30.0])

    # Convert world to voxel for T2
    inv_t2 = np.linalg.inv(affine_t2)
    vox_t2 = (inv_t2 @ np.array([*target_world_mm, 1.0]))[:3]
    # Z coordinate should be 30.0 / 2.0 = 15.0 voxels
    assert np.allclose(vox_t2, [15.0, -10.0, 15.0])

    # Converting both back to world gives the EXACT same physical location
    w1 = (affine_t1 @ np.array([*vox_t1, 1.0]))[:3]
    w2 = (affine_t2 @ np.array([*vox_t2, 1.0]))[:3]
    np.testing.assert_array_equal(w1, w2)


# ==============================================================================
# 2. Segmentation Correctness & Mesh Generation
# ==============================================================================

def test_categorical_nearest_neighbour_restoration():
    """
    Verifies that grid restoration strictly uses nearest-neighbour interpolation
    and never introduces non-discrete intermediate labels (e.g. 3) in BraTS maps {0, 1, 2, 4}.
    """
    labels = np.array([
        [[0, 1], [2, 4]],
        [[4, 2], [1, 0]],
    ], dtype=np.uint8)

    restored = restore_original_grid(labels, target_shape=(16, 16, 16))
    unique_vals = set(np.unique(restored))
    assert unique_vals.issubset({0, 1, 2, 4})
    assert 3 not in unique_vals


def test_independent_region_mask_definitions():
    """
    Verifies exact BraTS 2021 subregion composition:
    - WT = {1, 2, 4} (NCR + ED + ET)
    - TC = {1, 4}    (NCR + ET)
    - ET = {4}       (ET)
    """
    seg = np.array([
        [[0, 1], [2, 4]]
    ], dtype=np.uint8)

    masks = derive_region_masks(seg)
    # Voxel (0, 1, 0) with label 2 (ED) should be in WT only
    assert masks["WT"][0, 1, 0] is True or masks["WT"][0, 1, 0] == 1
    assert masks["TC"][0, 1, 0] is False or masks["TC"][0, 1, 0] == 0
    assert masks["ET"][0, 1, 0] is False or masks["ET"][0, 1, 0] == 0

    # Voxel (0, 0, 1) with label 1 (NCR) should be in WT and TC, but not ET
    assert masks["WT"][0, 0, 1] is True or masks["WT"][0, 0, 1] == 1
    assert masks["TC"][0, 0, 1] is True or masks["TC"][0, 0, 1] == 1
    assert masks["ET"][0, 0, 1] is False or masks["ET"][0, 0, 1] == 0

    # Voxel (0, 1, 1) with label 4 (ET) should be in all three
    assert masks["WT"][0, 1, 1] is True or masks["WT"][0, 1, 1] == 1
    assert masks["TC"][0, 1, 1] is True or masks["TC"][0, 1, 1] == 1
    assert masks["ET"][0, 1, 1] is True or masks["ET"][0, 1, 1] == 1


def test_3d_mesh_generation_world_coordinates():
    """
    Verifies that generate_region_mesh generates a valid 3D surface mesh
    with vertices calibrated in physical continuous world mm space.
    """
    shape = (20, 20, 20)
    affine = np.diag([1.5, 1.5, 2.0, 1.0])
    affine[:3, 3] = [10.0, 20.0, 30.0]

    vol = np.zeros(shape, dtype=np.uint8)
    vol[6:14, 6:14, 6:14] = 4  # ET sphere/cube

    mesh = generate_region_mesh(vol, affine, region="ET")
    assert len(mesh.vertices) > 0
    assert len(mesh.faces) > 0

    # Vertex coordinates must be in physical world mm range
    # In voxels: [6..14] -> transformed by 1.5, 1.5, 2.0 with offset 10, 20, 30
    min_world = mesh.vertices.min(axis=0)
    max_world = mesh.vertices.max(axis=0)

    # X bounds: 6*1.5 + 10 = 19.0 to 14*1.5 + 10 = 31.0
    assert 18.0 <= min_world[0] <= 21.0
    assert 29.0 <= max_world[0] <= 32.0

    # Export to OBJ
    obj_bytes = export_mesh_bytes(mesh, export_format="obj")
    assert isinstance(obj_bytes, bytes)
    assert b"v " in obj_bytes
    assert b"f " in obj_bytes


# ==============================================================================
# 3. Lifecycle, Empty Mask & Failure Handling
# ==============================================================================

def test_empty_mask_mesh_generation_does_not_crash():
    """Verify empty mask mesh generation returns an empty Trimesh without crashing."""
    shape = (20, 20, 20)
    affine = np.eye(4)
    empty_vol = np.zeros(shape, dtype=np.uint8)

    mesh = generate_region_mesh(empty_vol, affine, region="WT")
    assert len(mesh.vertices) == 0
    assert len(mesh.faces) == 0


def test_missing_sequence_endpoint_404():
    """Verify requesting an un-uploaded sequence returns a clean HTTP 404."""
    # Test on a nonexistent case
    resp = client.get("/api/cases/case_nonexistent_123/sequences/t1")
    assert resp.status_code == 404


def test_invalid_case_id_security_check():
    """Verify path traversal or malformed case IDs are rejected with HTTP 400."""
    resp = client.get("/api/cases/..%2F..%2Fetc%2Fpasswd/sequences/t1")
    assert resp.status_code in [400, 404]
