import os
import subprocess
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from backend.app.schemas.contracts import (
    HealthResponse,
    ModelReadiness,
    MANDATORY_DISCLAIMER,
)

router = APIRouter(prefix="/api", tags=["NeuroScope 3D API"])


def get_git_commit() -> str:
    """Safely retrieve current Git commit hash or fallback to env/unknown."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        return commit
    except Exception:
        return os.getenv("GIT_COMMIT_HASH", "scaffold-baseline")


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """
    Backend and model readiness check.
    Returns operational status, model readiness, device, and mandatory disclaimer.
    """
    model_device = os.getenv("MODEL_DEVICE", "cpu")
    model_bundle = os.getenv("MODEL_BUNDLE_PATH", "./models/brats_mri_segmentation")
    model_loaded = os.path.exists(model_bundle)

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        commit_id=get_git_commit(),
        timestamp=datetime.now(timezone.utc).isoformat(),
        model_readiness=ModelReadiness(
            loaded=model_loaded,
            model_name="brats_mri_segmentation",
            device=model_device,
        ),
        disclaimer=MANDATORY_DISCLAIMER,
    )


@router.post("/cases", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def create_case():
    """
    Endpoint scaffold for multi-sequence MRI upload and validation.
    Implementation reserved for feature/backend and feature/ai-pipeline branches.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Upload pipeline is scaffolded. Implement in feature/backend branch."
    )


@router.get("/cases/{case_id}/validate", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def validate_case(case_id: str):
    """
    Endpoint scaffold for case geometry validation.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Validation service is scaffolded. Implement in feature/backend branch."
    )


@router.post("/cases/{case_id}/segment", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def run_segmentation(case_id: str):
    """
    Endpoint scaffold to trigger model inference.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Inference orchestrator is scaffolded. Implement in feature/ai-pipeline branch."
    )


@router.get("/cases/{case_id}/status", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_case_status(case_id: str):
    """
    Endpoint scaffold for processing status.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Status tracking is scaffolded. Implement in feature/backend branch."
    )


@router.get("/cases/{case_id}/results", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_case_results(case_id: str):
    """
    Endpoint scaffold for quantitative results.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Results aggregator is scaffolded. Implement in feature/backend branch."
    )
