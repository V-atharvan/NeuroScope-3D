"""
Targeted security and regression tests for storage path traversal hardening (Fix 3).
Verifies strict case ID format validation, canonical base containment,
protection across all case endpoints, symlink escape prevention, and safe cleanup.
"""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.storage import (
    validate_case_id,
    get_case_dir,
    cleanup_expired_cases,
    STORAGE_BASE_DIR,
)

client = TestClient(app)


def test_validate_case_id_pattern():
    """Verify regex and length validation for case IDs."""
    # Valid IDs
    assert validate_case_id("case_12345") is True
    assert validate_case_id("case_a1b2c3d4-e5f6-7890-abcd-ef1234567890") is True
    assert validate_case_id("case_test_study-01") is True

    # Invalid IDs
    assert validate_case_id("") is False
    assert validate_case_id("case_") is False  # length 5 < minimum 6
    assert validate_case_id("case" + "x" * 80) is False  # exceeds max length
    assert validate_case_id("case_../traversal") is False
    assert validate_case_id("case_..\\traversal") is False
    assert validate_case_id("../case_123") is False
    assert validate_case_id("/etc/passwd") is False
    assert validate_case_id("C:\\Windows\\System32") is False
    assert validate_case_id("case_123$evil") is False
    assert validate_case_id("case_123;rm") is False
    assert validate_case_id("case_123%2e%2e") is False
    assert validate_case_id("case_123\x00") is False
    assert validate_case_id("case_123:stream") is False


def test_get_case_dir_containment_and_rejection():
    """Verify get_case_dir raises ValueError on malicious inputs."""
    # Malicious inputs must raise ValueError
    malicious_inputs = [
        "../",
        "../../etc/passwd",
        "..\\..\\Windows",
        "case_123/../../secret",
        "case_123\\..\\..\\secret",
        "/absolute/path",
        "C:\\Windows",
        "case_bad$chars",
        "case_has%20space",
        "case_\x00_null",
    ]
    for bad_id in malicious_inputs:
        with pytest.raises(ValueError):
            get_case_dir(bad_id)


def test_get_case_dir_canonical_containment():
    """Verify that a valid case directory resolves strictly within STORAGE_BASE_DIR."""
    canonical_base = os.path.realpath(os.path.abspath(STORAGE_BASE_DIR))
    resolved = get_case_dir("case_valid_test_id_123")
    assert resolved.startswith(canonical_base)
    assert os.path.commonpath([canonical_base, resolved]) == canonical_base


def test_endpoints_reject_path_traversal():
    """Verify all case-accessing endpoints return HTTP 400 Bad Request on traversal."""
    malicious_ids = [
        "..%2f..%2fetc%2fpasswd",
        "../../etc/passwd",
        "..\\..\\windows",
        "case_123%2f..%2f..",
        "case_invalid$symbol",
        "case_space in id",
    ]

    endpoints = [
        "/api/cases/{id}/status",
        "/api/cases/{id}/validate",
        "/api/cases/{id}/results",
        "/api/cases/{id}/mask",
        "/api/cases/{id}/report",
        "/api/cases/{id}/sequences/t1",
        "/api/cases/{id}/agreement-mask",
        "/api/cases/{id}/uncertainty",
        "/api/cases/{id}/ablation",
    ]

    for bad_id in malicious_ids:
        for ep_template in endpoints:
            url = ep_template.format(id=bad_id)
            resp = client.get(url)
            # Must return 400 or 404 (if URL path parsing absorbs dots), NEVER 200 or 500
            assert resp.status_code in (400, 404), f"Endpoint {url} returned {resp.status_code}"
            # Ensure no absolute filesystem paths are disclosed in error messages
            err_text = resp.text.lower()
            assert "c:\\" not in err_text
            assert "/home/" not in err_text
            assert "/users/" not in err_text


def test_valid_but_nonexistent_case_returns_404():
    """Verify validly formatted but nonexistent case ID returns 404 Not Found."""
    nonexistent_id = "case_00000000-0000-0000-0000-000000000000"
    resp = client.get(f"/api/cases/{nonexistent_id}/status")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_symlink_escape_protection(tmp_path):
    """Verify symlinks pointing outside storage root are detected and blocked."""
    outside_dir = tmp_path / "outside_secret_data"
    outside_dir.mkdir()
    secret_file = outside_dir / "confidential.txt"
    secret_file.write_text("classified data")

    # Create a symlink inside STORAGE_BASE_DIR pointing to outside_dir if symlinks supported
    symlink_name = "case_symlink_attack_test"
    symlink_path = os.path.join(STORAGE_BASE_DIR, symlink_name)

    try:
        os.symlink(str(outside_dir), symlink_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not supported in current environment/permissions")

    try:
        # get_case_dir must detect and reject symlink escape
        with pytest.raises(ValueError, match="Symbolic link"):
            get_case_dir(symlink_name)
    finally:
        if os.path.islink(symlink_path):
            os.unlink(symlink_path)


def test_cleanup_expired_cases_safe_with_symlink(tmp_path):
    """Verify cleanup_expired_cases safely unlinks symlinks without recursing outside."""
    outside_dir = tmp_path / "outside_protected_dir"
    outside_dir.mkdir()
    protected_file = outside_dir / "keep_me_safe.txt"
    protected_file.write_text("must not be deleted")

    symlink_name = "case_symlink_cleanup_test"
    symlink_path = os.path.join(STORAGE_BASE_DIR, symlink_name)

    try:
        os.symlink(str(outside_dir), symlink_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not supported in current environment/permissions")

    try:
        # Run cleanup with 0 max_age_hours to trigger removal
        removed = cleanup_expired_cases(max_age_hours=0)
        # Symlink itself should be unlinked
        assert not os.path.lexists(symlink_path)
        # External target directory and protected file must remain intact
        assert outside_dir.exists()
        assert protected_file.exists()
        assert protected_file.read_text() == "must not be deleted"
    finally:
        if os.path.lexists(symlink_path):
            os.unlink(symlink_path)
