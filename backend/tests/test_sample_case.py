from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_load_sample_case_endpoint():
    response = client.post("/api/cases/sample")
    assert response.status_code == 201
    data = response.json()
    assert "case_id" in data
    assert data["validation_status"] == "passed"
    assert "files" in data
    assert "t1" in data["files"]
    assert "t1gd" in data["files"]
    assert "t2" in data["files"]
    assert "flair" in data["files"]
    assert "spatial_summary" in data

    # Test downloading an individual sequence
    case_id = data["case_id"]
    seq_resp = client.get(f"/api/cases/{case_id}/sequences/t1")
    assert seq_resp.status_code == 200
    assert len(seq_resp.content) > 0
