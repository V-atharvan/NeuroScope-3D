from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["product"] == "NeuroScope 3D"
    assert "disclaimer" in data
    assert "Research and teaching prototype only" in data["disclaimer"]


def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "model_readiness" in data
    assert data["model_readiness"]["model_name"] == "brats_mri_segmentation"
    assert "Research and teaching prototype only" in data["disclaimer"]
