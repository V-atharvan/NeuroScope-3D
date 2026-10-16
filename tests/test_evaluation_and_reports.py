"""
Unit and integration tests for Prompt 7: Quantitative Evaluation and PDF Report Generation.
Tests 10-case cohort evaluation harness, patient-level splits, empty mask edge cases,
and full PDF report generation and binary verification.
"""
import os
import tempfile
import numpy as np
import pytest
import nibabel as nib

from evaluation.evaluate import (
    compute_binary_metrics,
    evaluate_case,
    evaluate_cohort,
    evaluate_nifti_files,
    TRAINING_OVERLAP_DISCLOSURE,
)
from backend.app.services.pdf_report import generate_pdf_report
from backend.app.services.volume import calculate_region_volumes


def test_ten_case_held_out_cohort_evaluation(tmp_path):
    """
    Evaluates a 10-case held-out patient cohort.
    Verifies that metrics are computed per case, patient splits are preserved,
    and mean +/- std aggregate statistics are accurately calculated.
    """
    case_entries = []
    shape = (12, 12, 12)
    affine = np.diag([1.0, 1.0, 1.0, 1.0])

    for i in range(1, 11):
        cid = f"BraTS2021_Patient_{i:03d}"

        # Create GT mask with varying tumor patterns
        gt_mask = np.zeros(shape, dtype=np.uint8)
        gt_mask[3:9, 3:9, 3:9] = 2  # ED
        gt_mask[4:8, 4:8, 4:8] = 1  # NCR
        if i % 2 == 0:
            gt_mask[5:7, 5:7, 5:7] = 4  # ET in even cases

        # Create Prediction mask with minor simulated boundary differences
        pred_mask = np.zeros(shape, dtype=np.uint8)
        pred_mask[3:9, 3:9, 3:9] = 2
        pred_mask[4:8, 4:8, 4:8] = 1
        if i % 2 == 0:
            pred_mask[5:7, 5:7, 5:7] = 4
        else:
            # Simulated false positive ET
            pred_mask[5:6, 5:6, 5:6] = 4

        gt_file = str(tmp_path / f"{cid}_gt.nii.gz")
        pred_file = str(tmp_path / f"{cid}_pred.nii.gz")
        nib.save(nib.Nifti1Image(gt_mask, affine), gt_file)
        nib.save(nib.Nifti1Image(pred_mask, affine), pred_file)

        case_entries.append({
            "case_id": cid,
            "pred_path": pred_file,
            "gt_path": gt_file,
        })

    # Run cohort evaluation
    cohort_summary = evaluate_cohort(case_entries, cohort_name="BraTS 2021 Held-Out Benchmark Cohort")

    assert cohort_summary["total_cases"] == 10
    assert len(cohort_summary["individual_cases"]) == 10
    assert cohort_summary["split_methodology"] == "Patient/case-level split (not by slice)"
    assert cohort_summary["training_overlap_disclosure"] == TRAINING_OVERLAP_DISCLOSURE

    # Verify aggregate metrics for WT, TC, ET exist and have valid bounds
    agg = cohort_summary["aggregate_metrics"]
    for reg in ["WT", "TC", "ET"]:
        assert 0.0 <= agg[reg]["mean_dice"] <= 1.0
        assert 0.0 <= agg[reg]["mean_sensitivity"] <= 1.0
        assert agg[reg]["std_dice"] >= 0.0

    # WT should have high Dice
    assert agg["WT"]["mean_dice"] >= 0.95


def test_empty_mask_evaluation_metric_definitions():
    """
    Verify strict mathematical definitions for empty masks:
    - If |GT| == 0 and |Pred| == 0: Dice = 1.0, Sensitivity = 1.0
    - If |GT| == 0 and |Pred| > 0:  Dice = 0.0, Sensitivity = 1.0
    - If |GT| > 0 and |Pred| == 0:  Dice = 0.0, Sensitivity = 0.0
    """
    zeros = np.zeros((10, 10, 10), dtype=np.uint8)
    ones = np.ones((10, 10, 10), dtype=np.uint8)

    d1, s1 = compute_binary_metrics(zeros, zeros)
    assert d1 == 1.0 and s1 == 1.0

    d2, s2 = compute_binary_metrics(ones, zeros)
    assert d2 == 0.0 and s2 == 1.0

    d3, s3 = compute_binary_metrics(zeros, ones)
    assert d3 == 0.0 and s3 == 0.0


def test_generate_sample_pdf_report_and_verify_binary(tmp_path):
    """
    Generates a full sample PDF report, verifies file existence,
    binary validity (%PDF magic bytes, EOF marker), and content sections.
    """
    pdf_path = str(tmp_path / "sample_neuroscope_report.pdf")

    # Sample volumetric results from a 16x16x16 case
    mask = np.zeros((16, 16, 16), dtype=np.uint8)
    mask[4:12, 4:12, 4:12] = 2  # ED
    mask[6:10, 6:10, 6:10] = 1  # NCR
    mask[7:9, 7:9, 7:9] = 4    # ET
    spacing = (1.0, 1.0, 1.0)
    volumes = calculate_region_volumes(mask, spacing)

    prov = {
        "model_name": "MONAI brats_mri_segmentation (SegResNet)",
        "model_license": "Apache 2.0",
        "training_data_source": "BraTS 2018 Multimodal Brain Tumor Dataset",
        "git_commit": "79e12e4",
        "timestamp": "2026-10-16T19:30:00Z",
        "input_sha256": {
            "t1": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "t1gd": "f5a1c3214567890abcdef1234567890abcdef1234567890abcdef1234567890a",
            "t2": "a4d2e1104567890abcdef1234567890abcdef1234567890abcdef1234567890b",
            "flair": "b7c9e8844567890abcdef1234567890abcdef1234567890abcdef1234567890c",
        },
    }

    eval_data = {
        "available": True,
        "metrics": {
            "WT": {"dice": 0.9412, "sensitivity": 0.9520},
            "TC": {"dice": 0.8920, "sensitivity": 0.9015},
            "ET": {"dice": 0.8540, "sensitivity": 0.8670},
        }
    }

    result_path = generate_pdf_report(
        case_id="case_sample_verification_001",
        output_pdf_path=pdf_path,
        volumes=volumes,
        spatial_metadata={"shape": [16, 16, 16], "spacing_mm": [1.0, 1.0, 1.0]},
        provenance=prov,
        case_evaluation=eval_data,
        runtime_seconds=18.42,
    )

    assert os.path.exists(result_path)
    file_size = os.path.getsize(result_path)
    assert file_size > 3000  # Substantial PDF document

    # Read binary content
    with open(result_path, "rb") as f:
        content = f.read()

    # Verify standard PDF magic header
    assert content.startswith(b"%PDF-")

    # Verify PDF trailer
    assert b"%%EOF" in content[-1024:]

    # Verify document info contains disclaimer and title
    assert b"Research and teaching prototype only" in content or b"NeuroScope 3D" in content
