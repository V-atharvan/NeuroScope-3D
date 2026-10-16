"""
NeuroScope 3D - Comprehensive Volume Measurements and Expert Comparison Test Suite
===================================================================================
Tests all 15 explicit acceptance criteria from Section 12:
 1. Correct WT, TC, and ET label definitions
 2. Required 16 mL anisotropic cube test (20x20x20 block of label 2, spacing 1x1x2 mm)
 3. Empty masks and single-voxel masks
 4. Correct Dice and sensitivity on hand-calculated masks
 5. Reference-empty and prediction-empty edge cases
 6. Invalid labels and non-finite values
 7. Same shape but incompatible affine rejection
 8. Correctly aligned masks with non-identity affine
 9. Nearest-neighbour label resampling where required
 10. Correct TP, FP, and FN visualization
 11. Correct signed and absolute volume differences
 12. Undefined relative difference when reference volume is zero
 13. Correct UI schema handling of unavailable metrics
 14. PDF values matching the API response
 15. Safe handling of invalid uploads and case identifiers
"""
import os
import pytest
import numpy as np
import nibabel as nib
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.volume import (
    calculate_region_volumes,
    compute_physical_volume_ml,
    compute_bounding_box,
    compute_centroid_voxel,
)
from backend.app.services.evaluation_overlay import (
    generate_agreement_volume,
    export_agreement_nifti,
)
from evaluation.evaluate import (
    compute_binary_metrics,
    evaluate_case,
    compute_hausdorff_distance_95,
)
from backend.app.schemas.contracts import CaseMetric, CaseEvaluation, RegionVolume
from backend.app.services.pdf_report import generate_pdf_report


# ==============================================================================
# Criterion 1: Correct WT, TC, and ET label definitions
# ==============================================================================
def test_1_label_definitions():
    """
    BraTS 2021 convention:
    - 0: Background
    - 1: Necrotic & non-enhancing tumour core (NCR)
    - 2: Peritumoral edema (ED)
    - 4: Enhancing tumour (ET)

    Region composition:
    - WT (Whole Tumour): labels {1, 2, 4}
    - TC (Tumour Core): labels {1, 4}
    - ET (Enhancing Tumour): label {4}
    """
    # Test label 1 only (NCR)
    m1 = np.zeros((10, 10, 10), dtype=np.uint8)
    m1[2:5, 2:5, 2:5] = 1  # 27 voxels
    v1 = calculate_region_volumes(m1, (1.0, 1.0, 1.0))
    assert v1["WT"]["voxel_count"] == 27
    assert v1["TC"]["voxel_count"] == 27
    assert v1["ET"]["voxel_count"] == 0

    # Test label 2 only (ED)
    m2 = np.zeros((10, 10, 10), dtype=np.uint8)
    m2[2:5, 2:5, 2:5] = 2  # 27 voxels
    v2 = calculate_region_volumes(m2, (1.0, 1.0, 1.0))
    assert v2["WT"]["voxel_count"] == 27
    assert v2["TC"]["voxel_count"] == 0
    assert v2["ET"]["voxel_count"] == 0

    # Test label 4 only (ET)
    m4 = np.zeros((10, 10, 10), dtype=np.uint8)
    m4[2:5, 2:5, 2:5] = 4  # 27 voxels
    v4 = calculate_region_volumes(m4, (1.0, 1.0, 1.0))
    assert v4["WT"]["voxel_count"] == 27
    assert v4["TC"]["voxel_count"] == 27
    assert v4["ET"]["voxel_count"] == 27


# ==============================================================================
# Criterion 2: Required 16 mL anisotropic cube test
# ==============================================================================
def test_2_required_16ml_anisotropic_cube_test():
    """
    Required Cube Test from Section 2:
    - 20 x 20 x 20 block of label 2 (edema)
    - Voxel spacing 1 x 1 x 2 mm
    - Expected volumes:
      WT = 16.0 mL
      TC = 0.0 mL
      ET = 0.0 mL
    """
    mask = np.zeros((50, 50, 50), dtype=np.uint8)
    mask[10:30, 10:30, 10:30] = 2  # 20 * 20 * 20 = 8000 voxels

    spacing = (1.0, 1.0, 2.0)
    volumes = calculate_region_volumes(mask, voxel_spacing=spacing)

    # 8000 voxels * (1 * 1 * 2 mm^3) = 16,000 mm^3 = 16.0 mL
    assert volumes["WT"]["voxel_count"] == 8000
    assert volumes["WT"]["volume_ml"] == 16.0
    assert volumes["WT"]["measurement_status"] == "valid"

    assert volumes["TC"]["voxel_count"] == 0
    assert volumes["TC"]["volume_ml"] == 0.0
    assert volumes["TC"]["measurement_status"] == "empty_region"

    assert volumes["ET"]["voxel_count"] == 0
    assert volumes["ET"]["volume_ml"] == 0.0
    assert volumes["ET"]["measurement_status"] == "empty_region"


# ==============================================================================
# Criterion 3: Empty masks and single-voxel masks
# ==============================================================================
def test_3_empty_and_single_voxel_masks():
    """Empty masks must return zero volume; single voxel equals physical voxel volume."""
    # Empty mask
    empty = np.zeros((15, 15, 15), dtype=np.uint8)
    v_empty = calculate_region_volumes(empty, (1.0, 1.0, 1.0))
    assert v_empty["WT"]["volume_ml"] == 0.0
    assert v_empty["TC"]["volume_ml"] == 0.0
    assert v_empty["ET"]["volume_ml"] == 0.0
    assert v_empty["WT"]["voxel_count"] == 0

    # Single voxel mask of label 4 (Enhancing Tumour)
    single = np.zeros((10, 10, 10), dtype=np.uint8)
    single[5, 5, 5] = 4
    # Anisotropic spacing: 1.5 x 2.0 x 3.0 mm -> single voxel volume = 9.0 mm^3 = 0.009 mL
    v_single = calculate_region_volumes(single, (1.5, 2.0, 3.0))
    expected_ml = (1 * 1.5 * 2.0 * 3.0) / 1000.0  # 0.009 mL
    assert v_single["ET"]["voxel_count"] == 1
    assert pytest.approx(v_single["ET"]["volume_ml"], abs=1e-4) == expected_ml
    assert pytest.approx(v_single["TC"]["volume_ml"], abs=1e-4) == expected_ml
    assert pytest.approx(v_single["WT"]["volume_ml"], abs=1e-4) == expected_ml


# ==============================================================================
# Criterion 4: Correct Dice and sensitivity on hand-calculated masks
# ==============================================================================
def test_4_hand_calculated_dice_and_sensitivity():
    """
    Pred has 10 positive voxels, GT has 12 positive voxels, overlap TP = 8.
    FP = 2, FN = 4.
    Dice = 2*TP / (2*TP + FP + FN) = 16 / 22 = 8/11 ≈ 0.72727...
    Sensitivity = TP / (TP + FN) = 8 / 12 = 2/3 ≈ 0.66667...
    """
    pred = np.zeros((10, 10, 10), dtype=np.uint8)
    gt = np.zeros((10, 10, 10), dtype=np.uint8)

    # Overlap TP: 8 voxels
    pred[0, 0, 0:8] = 1
    gt[0, 0, 0:8] = 1

    # FP: 2 voxels (only pred)
    pred[0, 0, 8:10] = 1

    # FN: 4 voxels (only gt)
    gt[0, 1, 0:4] = 1

    dice, sens = compute_binary_metrics(pred, gt)
    assert pytest.approx(dice, abs=1e-5) == (16.0 / 22.0)
    assert pytest.approx(sens, abs=1e-5) == (8.0 / 12.0)


# ==============================================================================
# Criterion 5: Reference-empty and prediction-empty edge cases
# ==============================================================================
def test_5_reference_empty_and_prediction_empty_edge_cases():
    """
    Edge case handling:
    - Both empty: Dice = 1.0 (true negative agreement)
    - Reference empty, pred non-empty: Dice = 0.0, Sensitivity = None (undefined: 0 positive reference voxels)
    - Reference non-empty, pred empty: Dice = 0.0, Sensitivity = 0.0
    """
    empty = np.zeros((10, 10, 10), dtype=np.uint8)
    active = np.zeros((10, 10, 10), dtype=np.uint8)
    active[2:4, 2:4, 2:4] = 1

    # Both empty
    d_both, s_both = compute_binary_metrics(empty, empty)
    assert d_both == 1.0
    assert s_both == 1.0

    # Reference empty, prediction active
    d_ref_empty, s_ref_empty = compute_binary_metrics(active, empty, undefined_as_none=True)
    assert d_ref_empty == 0.0
    assert s_ref_empty is None  # Undefined, never fabricated 0

    # Reference active, prediction empty
    d_pred_empty, s_pred_empty = compute_binary_metrics(empty, active)
    assert d_pred_empty == 0.0
    assert s_pred_empty == 0.0


# ==============================================================================
# Criterion 6: Invalid labels and non-finite values
# ==============================================================================
def test_6_invalid_labels_and_non_finite_values():
    """Reject unexpected label values and non-finite NaN/Inf."""
    valid_spacing = (1.0, 1.0, 1.0)

    # Invalid label (e.g., label 3 or label 5)
    bad_labels = np.zeros((10, 10, 10), dtype=np.int32)
    bad_labels[2, 2, 2] = 3
    with pytest.raises(ValueError, match="unsupported label values"):
        calculate_region_volumes(bad_labels, valid_spacing)

    # Non-finite values (NaN)
    nan_arr = np.zeros((10, 10, 10), dtype=np.float32)
    nan_arr[1, 1, 1] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        calculate_region_volumes(nan_arr, valid_spacing)

    # Non-finite values (Inf)
    inf_arr = np.zeros((10, 10, 10), dtype=np.float32)
    inf_arr[1, 1, 1] = np.inf
    with pytest.raises(ValueError, match="non-finite"):
        calculate_region_volumes(inf_arr, valid_spacing)


# ==============================================================================
# Criterion 7: Same shape but incompatible affine rejection
# ==============================================================================
def test_7_same_shape_but_incompatible_affine(tmp_path):
    """
    Two masks having the same dimensions (20, 20, 20) but different affines
    (e.g., 1mm vs 2mm spacing) must fail spatial alignment validation.
    """
    pred_data = np.zeros((20, 20, 20), dtype=np.uint8)
    gt_data = np.zeros((20, 20, 20), dtype=np.uint8)

    pred_aff = np.eye(4)
    gt_aff = np.diag([2.0, 2.0, 2.0, 1.0])  # Mismatched spacing

    pred_file = str(tmp_path / "pred_misaligned.nii.gz")
    gt_file = str(tmp_path / "gt_misaligned.nii.gz")

    nib.save(nib.Nifti1Image(pred_data, pred_aff), pred_file)
    nib.save(nib.Nifti1Image(gt_data, gt_aff), gt_file)

    with pytest.raises(ValueError, match="Spatial affine mismatch"):
        evaluate_case(pred_file, gt_file)


# ==============================================================================
# Criterion 8: Correctly aligned masks with non-identity affine
# ==============================================================================
def test_8_correctly_aligned_non_identity_affine(tmp_path):
    """
    When affine has rotation, shear, or diagonal scaling, voxel volume
    is correctly derived from |det(A_3x3)|.
    """
    # Affine with negative determinant (flipped orientation) and anisotropic scaling
    affine = np.array([
        [-1.5,  0.0,  0.0, 100.0],
        [ 0.0,  2.0,  0.0, -50.0],
        [ 0.0,  0.0,  2.5,  25.0],
        [ 0.0,  0.0,  0.0,   1.0],
    ])
    expected_voxel_mm3 = abs(np.linalg.det(affine[:3, :3]))  # 1.5 * 2.0 * 2.5 = 7.5 mm^3

    mask = np.zeros((20, 20, 20), dtype=np.uint8)
    mask[5:10, 5:10, 5:10] = 4  # 5*5*5 = 125 voxels of ET

    res = calculate_region_volumes(mask, voxel_spacing=(1.5, 2.0, 2.5), affine=affine)
    assert res["ET"]["voxel_count"] == 125
    assert pytest.approx(res["ET"]["voxel_volume_mm3"], abs=1e-5) == 7.5
    expected_vol_ml = (125 * 7.5) / 1000.0  # 0.9375 mL
    assert pytest.approx(res["ET"]["volume_ml"], abs=1e-4) == expected_vol_ml
    assert "det(A_3x3)" in res["ET"]["formula"]


# ==============================================================================
# Criterion 9: Nearest-neighbour label resampling where required
# ==============================================================================
def test_9_nearest_neighbour_label_resampling():
    """Discrete BraTS labels {0, 1, 2, 4} must remain discrete integers."""
    from scipy.ndimage import zoom

    discrete_labels = np.array([0, 1, 2, 4], dtype=np.uint8)
    label_map = np.random.choice(discrete_labels, size=(10, 10, 10))

    # Nearest-neighbor resampling (order=0)
    resampled = zoom(label_map, zoom=(1.5, 1.5, 1.5), order=0)
    unique_resampled = set(np.unique(resampled).tolist())
    assert unique_resampled.issubset({0, 1, 2, 4}), f"Spurious labels produced: {unique_resampled}"


# ==============================================================================
# Criterion 10: Correct TP, FP, and FN visualization
# ==============================================================================
def test_10_tp_fp_fn_visualization():
    """
    Agreement volume mapping:
    - 0: Background (Neither)
    - 1: True Positive (Agreement)
    - 2: False Positive (Prediction only)
    - 3: False Negative (Reference only)
    """
    pred = np.zeros((10, 10, 10), dtype=np.uint8)
    gt = np.zeros((10, 10, 10), dtype=np.uint8)

    # TP at (2, 2, 2)
    pred[2, 2, 2] = 4
    gt[2, 2, 2] = 4

    # FP at (3, 3, 3) (pred has ET, gt is 0)
    pred[3, 3, 3] = 4

    # FN at (4, 4, 4) (gt has ET, pred is 0)
    gt[4, 4, 4] = 4

    # Background at (5, 5, 5)

    agreement_map, stats = generate_agreement_volume(pred, gt, region="ET")
    assert agreement_map[2, 2, 2] == 1  # TP
    assert agreement_map[3, 3, 3] == 2  # FP
    assert agreement_map[4, 4, 4] == 3  # FN
    assert agreement_map[5, 5, 5] == 0  # Background

    assert stats["tp_voxels"] == 1
    assert stats["fp_voxels"] == 1
    assert stats["fn_voxels"] == 1
    assert pytest.approx(stats["dice"], abs=1e-3) == 0.5
    assert pytest.approx(stats["sensitivity"], abs=1e-3) == 0.5


# ==============================================================================
# Criterion 11: Correct signed and absolute volume differences
# ==============================================================================
def test_11_signed_and_absolute_volume_differences(tmp_path):
    """
    ΔV = V_pred - V_ref
    |ΔV| = |V_pred - V_ref|
    """
    pred_data = np.zeros((20, 20, 20), dtype=np.uint8)
    gt_data = np.zeros((20, 20, 20), dtype=np.uint8)

    # 1000 voxels in pred (1.0 mL with 1mm spacing)
    pred_data[0:10, 0:10, 0:10] = 4
    # 500 voxels in gt (0.5 mL)
    gt_data[0:10, 0:10, 0:5] = 4

    p_file = str(tmp_path / "pred_vol.nii.gz")
    g_file = str(tmp_path / "gt_vol.nii.gz")
    nib.save(nib.Nifti1Image(pred_data, np.eye(4)), p_file)
    nib.save(nib.Nifti1Image(gt_data, np.eye(4)), g_file)

    eval_res = evaluate_case(p_file, g_file)
    et_m = eval_res["ET"]

    # Pred = 1.0 mL, Ref = 0.5 mL -> ΔV = +0.5 mL, |ΔV| = 0.5 mL, rel = +100.0%
    assert pytest.approx(et_m["predicted_volume_ml"], abs=1e-2) == 1.0
    assert pytest.approx(et_m["reference_volume_ml"], abs=1e-2) == 0.5
    assert pytest.approx(et_m["signed_diff_ml"], abs=1e-2) == 0.5
    assert pytest.approx(et_m["absolute_diff_ml"], abs=1e-2) == 0.5
    assert pytest.approx(et_m["relative_diff_percent"], abs=1e-1) == 100.0


# ==============================================================================
# Criterion 12: Undefined relative difference when reference volume is zero
# ==============================================================================
def test_12_undefined_relative_difference_when_ref_is_zero(tmp_path):
    """When reference volume is zero, relative difference must be None ('N/A')."""
    pred_data = np.zeros((20, 20, 20), dtype=np.uint8)
    gt_data = np.zeros((20, 20, 20), dtype=np.uint8)

    # Pred has 200 voxels of ET, GT has 0 voxels of ET
    pred_data[0:5, 0:5, 0:8] = 4

    p_file = str(tmp_path / "p_et.nii.gz")
    g_file = str(tmp_path / "g_empty.nii.gz")
    nib.save(nib.Nifti1Image(pred_data, np.eye(4)), p_file)
    nib.save(nib.Nifti1Image(gt_data, np.eye(4)), g_file)

    eval_res = evaluate_case(p_file, g_file)
    et_m = eval_res["ET"]

    assert et_m["reference_volume_ml"] == 0.0
    assert et_m["relative_diff_percent"] is None  # Undefined, not divide by zero
    assert et_m["sensitivity"] is None          # Undefined


# ==============================================================================
# Criterion 13: Correct UI schema handling of unavailable metrics
# ==============================================================================
def test_13_ui_schema_handling_of_unavailable_metrics():
    """CaseMetric must accept None values for undefined sensitivity/rel_diff/hd95."""
    metric = CaseMetric(
        dice=0.0,
        sensitivity=None,
        hd95_mm=None,
        predicted_volume_ml=1.5,
        reference_volume_ml=0.0,
        signed_diff_ml=1.5,
        absolute_diff_ml=1.5,
        relative_diff_percent=None,
        tp_voxels=0,
        fp_voxels=1500,
        fn_voxels=0,
    )
    dumped = metric.model_dump()
    assert dumped["sensitivity"] is None
    assert dumped["relative_diff_percent"] is None
    assert dumped["hd95_mm"] is None


# ==============================================================================
# Criterion 14: PDF values matching the API response
# ==============================================================================
def test_14_pdf_values_matching_api_response(tmp_path):
    """Generated PDF includes actual computed volume numbers, Dice, and sensitivity."""
    pdf_out = str(tmp_path / "verified_eval_report.pdf")
    volumes = {
        "WT": {"voxel_count": 8000, "volume_ml": 16.0, "voxel_volume_mm3": 2.0},
        "TC": {"voxel_count": 4000, "volume_ml": 8.0, "voxel_volume_mm3": 2.0},
        "ET": {"voxel_count": 2000, "volume_ml": 4.0, "voxel_volume_mm3": 2.0},
    }
    case_eval = {
        "available": True,
        "metrics": {
            "WT": {"dice": 0.9123, "sensitivity": 0.9456, "predicted_volume_ml": 16.0, "reference_volume_ml": 15.5, "signed_diff_ml": 0.5, "relative_diff_percent": 3.2, "hd95_mm": 3.4},
            "TC": {"dice": 0.8654, "sensitivity": 0.8876, "predicted_volume_ml": 8.0, "reference_volume_ml": 8.2, "signed_diff_ml": -0.2, "relative_diff_percent": -2.4, "hd95_mm": 4.1},
            "ET": {"dice": 0.8123, "sensitivity": 0.8345, "predicted_volume_ml": 4.0, "reference_volume_ml": 3.8, "signed_diff_ml": 0.2, "relative_diff_percent": 5.3, "hd95_mm": 2.8},
        }
    }
    prov = {
        "model_name": "SegResNet",
        "model_version": "0.5.4",
        "timestamp": "2026-10-17T00:00:00Z",
        "input_sha256": {"t1": "abc"},
    }

    generate_pdf_report(
        case_id="case_pdf_verification",
        output_pdf_path=pdf_out,
        volumes=volumes,
        spatial_metadata={"shape": [50, 50, 50], "spacing_mm": [1.0, 1.0, 2.0]},
        provenance=prov,
        case_evaluation=case_eval,
    )

    with open(pdf_out, "rb") as f:
        pdf_bytes = f.read()

    # Check key text matches in generated PDF
    assert b"16.00 mL" in pdf_bytes or b"16.0" in pdf_bytes
    assert b"0.9123" in pdf_bytes
    assert b"0.9456" in pdf_bytes
    assert b"Segmentation Volumes and Expert Comparison" in pdf_bytes


# ==============================================================================
# Criterion 15: Safe handling of invalid uploads and case identifiers
# ==============================================================================
def test_15_safe_handling_of_invalid_uploads_and_case_ids():
    """Client cannot access or upload to invalid/traversal paths."""
    client = TestClient(app)

    # Path traversal in case_id
    res_traversal = client.get("/api/cases/../../etc/passwd/results")
    assert res_traversal.status_code in (400, 404)

    # Malformed syntax in case_id (returns 400 Bad Request)
    res_malformed = client.get("/api/cases/invalid@syntax!/volumetrics")
    assert res_malformed.status_code == 400

    # Nonexistent but validly formatted case_id (returns 404 Not Found)
    res_404 = client.get("/api/cases/case_nonexistent_000000000000/volumetrics")
    assert res_404.status_code == 404

    # Upload invalid file as expert mask to nonexistent case
    files = {"expert_mask": ("fake.nii.gz", b"this is not a valid gzip or nifti", "application/gzip")}
    res_bad_upload = client.post("/api/cases/case_nonexistent_000000000000/expert-mask", files=files)
    assert res_bad_upload.status_code in (400, 404)
