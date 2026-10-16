"""
Tests for Boundary Watch (Quality Flags) and Case Compare (Longitudinal & Spatial Compatibility).
"""
import numpy as np
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.boundary_watch import (
    analyze_boundary_watch,
    analyze_connected_components,
    analyze_slice_continuity,
    analyze_border_contact,
    analyze_nesting_integrity
)
from backend.app.services.longitudinal import (
    calculate_volumetric_delta,
    classify_rano_trajectory,
    check_spatial_compatibility,
    compare_two_timepoint_studies
)

client = TestClient(app)


def test_connected_components_single_vs_multiple():
    # Single contiguous block
    mask = np.zeros((30, 30, 30), dtype=bool)
    mask[10:15, 10:15, 10:15] = True
    res_single = analyze_connected_components(mask, voxel_volume_ml=0.001, region_name="WT")
    assert res_single["component_count"] == 1
    assert res_single["satellite_count"] == 0
    assert not res_single["flagged"]

    # Add 4 separate satellite components
    mask[2, 2, 2] = True
    mask[25, 25, 25] = True
    mask[2, 25, 2] = True
    mask[25, 2, 25] = True
    res_multi = analyze_connected_components(mask, voxel_volume_ml=0.001, region_name="WT")
    assert res_multi["component_count"] == 5
    assert res_multi["satellite_count"] == 4
    assert res_multi["flagged"] is True
    assert len(res_multi["satellite_centroids"]) > 0


def test_slice_continuity_and_stepped_jumps():
    # Smooth cylinder along Z
    mask_smooth = np.zeros((30, 30, 20), dtype=bool)
    mask_smooth[10:20, 10:20, 5:15] = True
    res_smooth = analyze_slice_continuity(mask_smooth, region_name="WT")
    assert not res_smooth["flagged"]
    assert res_smooth["max_jump_ratio"] == 0.0

    # Stepped jump: large area on slice 8 (100 voxels), tiny area on slice 9 (2 voxels)
    mask_stepped = np.zeros((40, 40, 20), dtype=bool)
    mask_stepped[5:25, 5:25, 5:8] = True  # 400 voxels/slice
    mask_stepped[5:6, 5:6, 8] = True       # 1 voxel on slice 8
    res_stepped = analyze_slice_continuity(mask_stepped, region_name="WT")
    assert res_stepped["flagged"] is True
    assert res_stepped["max_jump_ratio"] > 0.7


def test_border_contact():
    # Interior lesion (no border contact)
    mask_interior = np.zeros((20, 20, 20), dtype=bool)
    mask_interior[5:15, 5:15, 5:15] = True
    res_interior = analyze_border_contact(mask_interior, region_name="WT")
    assert res_interior["border_voxels"] == 0
    assert not res_interior["border_touching"]
    assert not res_interior["flagged"]

    # Lesion touching x=0 and z=19 borders
    mask_border = np.zeros((20, 20, 20), dtype=bool)
    mask_border[0:5, 5:15, 5:15] = True
    res_border = analyze_border_contact(mask_border, region_name="WT")
    assert res_border["border_voxels"] > 0
    assert res_border["border_touching"] is True
    assert res_border["flagged"] is True


def test_nesting_integrity_verification():
    # Valid nesting: ET ⊆ TC ⊆ WT
    label_map = np.zeros((20, 20, 20), dtype=np.uint8)
    label_map[5:15, 5:15, 5:15] = 2  # WT base (ED)
    label_map[7:13, 7:13, 7:13] = 1  # TC core (NCR)
    label_map[8:12, 8:12, 8:12] = 4  # ET subregion (ET)
    res_valid = analyze_nesting_integrity(label_map)
    assert res_valid["is_nesting_valid"] is True
    assert res_valid["total_violations"] == 0
    assert not res_valid["flagged"]


def test_boundary_watch_full_analysis():
    label_map = np.zeros((30, 30, 30), dtype=np.uint8)
    label_map[10:20, 10:20, 10:20] = 2
    label_map[12:18, 12:18, 12:18] = 1
    label_map[13:17, 13:17, 13:17] = 4

    bw = analyze_boundary_watch(label_map, voxel_spacing=(1.0, 1.0, 1.0))
    assert "quality_risk_category" in bw
    assert "quality_risk_badge" in bw
    assert "checks" in bw
    assert bw["checks"]["nesting_integrity"]["is_nesting_valid"] is True


def test_longitudinal_rano_criteria():
    # 1. Progressive Disease (PD): ET increases >= 25%
    rano_pd = classify_rano_trajectory(et_delta_pct=30.0, wt_delta_pct=10.0)
    assert "Progressive Disease" in rano_pd["rano_category"]

    # 2. Partial Response (PR): ET decreases <= -50%
    rano_pr = classify_rano_trajectory(et_delta_pct=-60.0, wt_delta_pct=-35.0)
    assert "Partial Response" in rano_pr["rano_category"]

    # 3. Stable Disease (SD): Between -50% and +25%
    rano_sd = classify_rano_trajectory(et_delta_pct=-10.0, wt_delta_pct=-5.0)
    assert "Stable Disease" in rano_sd["rano_category"]


def test_spatial_compatibility_check():
    sp0 = {"shape": [240, 240, 155], "spacing_mm": [1.0, 1.0, 1.0]}
    sp1 = {"shape": [240, 240, 155], "spacing_mm": [1.0, 1.0, 1.0]}
    compat_same = check_spatial_compatibility(sp0, sp1)
    assert compat_same["is_identical_grid"] is True
    assert len(compat_same["advisories"]) == 0

    # Dimension/spacing variance
    sp2 = {"shape": [128, 128, 64], "spacing_mm": [1.5, 1.5, 2.0]}
    compat_diff = check_spatial_compatibility(sp0, sp2)
    assert compat_diff["is_identical_grid"] is False
    assert len(compat_diff["advisories"]) >= 2


def test_api_list_cases_and_sample_pair():
    # Test GET /api/cases
    resp_cases = client.get("/api/cases")
    assert resp_cases.status_code == 200
    data = resp_cases.json()
    assert "cases" in data
    assert isinstance(data["cases"], list)

    # Test POST /api/cases/sample-longitudinal-pair
    resp_pair = client.post("/api/cases/sample-longitudinal-pair")
    assert resp_pair.status_code == 200
    pair_data = resp_pair.json()
    assert "baseline_case_id" in pair_data
    assert "followup_case_id" in pair_data
    assert "comparison" in pair_data
    assert "rano_trajectory" in pair_data["comparison"]

    # Test GET /api/cases/{case_id}/boundary-watch
    b_id = pair_data["baseline_case_id"]
    resp_bw = client.get(f"/api/cases/{b_id}/boundary-watch")
    assert resp_bw.status_code == 200
    bw_data = resp_bw.json()
    assert "quality_risk_category" in bw_data
    assert "checks" in bw_data
