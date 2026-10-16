"""
NeuroScope 3D - FastAPI REST API Router
Implements the shared API contract specified in docs/API_CONTRACT.md.
Connects uploaded multi-sequence cases to validation, inference, volume calculation,
and binary mask/PDF report generation.
"""
import os
import shutil
import time
import subprocess
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, File, UploadFile, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse

from backend.app.schemas.contracts import (
    HealthResponse,
    ModelReadiness,
    CaseUploadResponse,
    CaseValidationResponse,
    SegmentationTriggerResponse,
    CaseStatusResponse,
    CaseResultsResponse,
    StandardErrorResponse,
    SpatialMetadata,
    SpatialSummary,
    RegionVolume,
    BoundingBox,
    CaseEvaluation,
    CaseMetric,
    Provenance,
    CaseOutputs,
    MANDATORY_DISCLAIMER,
)
from backend.app.services.validation import (
    validate_study,
    ValidationError,
    MAX_FILE_SIZE_BYTES,
)
from backend.app.services.volume import calculate_region_volumes
from backend.app.services.storage import (
    create_case_workspace,
    get_case_dir,
    save_case_metadata,
    load_case_metadata,
    cleanup_expired_cases,
    compute_file_sha256,
)
from backend.app.services.pdf_report import generate_pdf_report
from inference.predict import run_pipeline, PreprocessingError, PostprocessingError
from evaluation.evaluate import evaluate_case
import nibabel as nib
import numpy as np

router = APIRouter(prefix="/api", tags=["NeuroScope 3D API"])


def get_git_commit() -> str:
    """Safely retrieves current Git commit hash or fallback."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True
        ).strip()
        return commit
    except Exception:
        return os.getenv("GIT_COMMIT_HASH", "scaffold-baseline")


def save_upload_to_disk(upload_file: UploadFile, dest_path: str, max_bytes: int = MAX_FILE_SIZE_BYTES) -> int:
    """Saves streamed UploadFile to destination path, enforcing size limit."""
    total_written = 0
    with open(dest_path, "wb") as f:
        while chunk := upload_file.file.read(1024 * 1024):  # 1MB chunks
            total_written += len(chunk)
            if total_written > max_bytes:
                raise ValidationError(
                    "FILE_TOO_LARGE",
                    f"File '{upload_file.filename}' exceeded 1 GB maximum limit ({total_written} bytes)",
                    {"file": upload_file.filename, "size_bytes": total_written}
                )
            f.write(chunk)
    return total_written


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Backend operational status and model readiness."""
    cleanup_expired_cases()  # Purge any cases > 24 hours
    model_device = os.getenv("MODEL_DEVICE", "cpu")
    weights_path = os.getenv("MODEL_WEIGHTS_PATH", "models/brats_mri_segmentation/models/model.pt")
    model_loaded = os.path.exists(weights_path)

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


@router.post("/cases", response_model=CaseUploadResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    t1: UploadFile = File(..., description="T1-weighted MRI (.nii or .nii.gz)"),
    t1gd: UploadFile = File(..., description="T1-contrast enhanced (Gd) MRI (.nii or .nii.gz)"),
    t2: UploadFile = File(..., description="T2-weighted MRI (.nii or .nii.gz)"),
    flair: UploadFile = File(..., description="FLAIR MRI (.nii or .nii.gz)"),
    expert_mask: Optional[UploadFile] = File(None, description="Optional expert segmentation mask (.nii or .nii.gz)"),
):
    """
    Ingests 4 MRI sequences and optional expert mask.
    Saves to private ephemeral case directory, computes SHA-256 hashes, and runs initial validation.
    """
    case_id, case_dir = create_case_workspace()
    saved_paths: Dict[str, str] = {}
    file_metadata: Dict[str, Any] = {}

    try:
        # Save each required sequence
        uploads = {"t1": t1, "t1gd": t1gd, "t2": t2, "flair": flair}
        for seq_key, upload_item in uploads.items():
            dest = os.path.join(case_dir, f"{seq_key}_{upload_item.filename}")
            size_bytes = save_upload_to_disk(upload_item, dest)
            sha = compute_file_sha256(dest)
            saved_paths[seq_key] = dest
            file_metadata[seq_key] = {
                "filename": upload_item.filename,
                "size_bytes": size_bytes,
                "sha256": sha,
            }

        # Save optional expert mask
        mask_path = None
        if expert_mask and expert_mask.filename:
            dest = os.path.join(case_dir, f"expert_{expert_mask.filename}")
            size_bytes = save_upload_to_disk(expert_mask, dest)
            sha = compute_file_sha256(dest)
            mask_path = dest
            file_metadata["expert_mask"] = {
                "present": True,
                "filename": expert_mask.filename,
                "size_bytes": size_bytes,
                "sha256": sha,
            }
        else:
            file_metadata["expert_mask"] = {"present": False}

        # Run validation
        val_result = validate_study(saved_paths, expert_mask_path=mask_path)

        state = {
            "case_id": case_id,
            "status": "uploaded",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "file_paths": saved_paths,
            "expert_mask_path": mask_path,
            "files": file_metadata,
            "spatial_metadata": val_result["spatial_metadata"],
            "validation": val_result,
            "runtime_seconds": None,
            "volumes": None,
            "case_evaluation": None,
        }
        save_case_metadata(case_id, state)

        return CaseUploadResponse(
            case_id=case_id,
            created_at=state["created_at"],
            files=file_metadata,
            validation_status="passed",
            spatial_summary=SpatialSummary(
                shape=val_result["spatial_metadata"]["shape"],
                spacing_mm=val_result["spatial_metadata"]["spacing_mm"],
            ),
            disclaimer=MANDATORY_DISCLAIMER,
        )

    except ValidationError as e:
        shutil.rmtree(case_dir, ignore_errors=True)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=StandardErrorResponse(
                status="error",
                code=e.code,
                message=e.message,
                details=e.details,
                disclaimer=MANDATORY_DISCLAIMER
            ).model_dump()
        )
    except Exception as e:
        shutil.rmtree(case_dir, ignore_errors=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=StandardErrorResponse(
                status="error",
                code="UPLOAD_ERROR",
                message=f"Failed to process case upload: {e}",
                details={"error": str(e)},
                disclaimer=MANDATORY_DISCLAIMER
            ).model_dump()
        )


@router.get("/cases/{case_id}/validate", response_model=CaseValidationResponse)
def validate_case(case_id: str):
    """Retrieves full geometry validation report for a case."""
    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    try:
        val_result = validate_study(
            state["file_paths"],
            expert_mask_path=state.get("expert_mask_path")
        )
        return CaseValidationResponse(
            case_id=case_id,
            is_valid=True,
            checks={
                "nifti_integrity": "passed",
                "finite_values": "passed",
                "non_constant": "passed",
                "shape_matching": "passed",
                "affine_compatibility": "passed",
                "file_size_within_limit": "passed",
            },
            reference_affine=val_result["spatial_metadata"]["reference_affine"],
            disclaimer=MANDATORY_DISCLAIMER,
        )
    except ValidationError as e:
        return CaseValidationResponse(
            case_id=case_id,
            is_valid=False,
            checks={"validation": "failed"},
            error=f"{e.code}: {e.message}",
            disclaimer=MANDATORY_DISCLAIMER,
        )


@router.post("/cases/{case_id}/segment", response_model=SegmentationTriggerResponse)
def trigger_segmentation(case_id: str):
    """
    Executes SegResNet model inference, region postprocessing, volume calculations,
    expert comparison (if mask present), and generates the PDF report.
    """
    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    case_dir = get_case_dir(case_id)
    out_mask_path = os.path.join(case_dir, "predicted_seg.nii.gz")
    out_report_path = os.path.join(case_dir, "report.pdf")

    weights_path = os.getenv("MODEL_WEIGHTS_PATH", "models/brats_mri_segmentation/models/model.pt")
    device_name = os.getenv("MODEL_DEVICE", "cpu")

    start_time = time.time()
    try:
        # Run inference pipeline
        run_pipeline(
            t1=state["file_paths"]["t1"],
            t1gd=state["file_paths"]["t1gd"],
            t2=state["file_paths"]["t2"],
            flair=state["file_paths"]["flair"],
            output=out_mask_path,
            weights=weights_path,
            device=device_name,
        )

        elapsed = time.time() - start_time

        # Calculate volumes on original grid
        pred_nii = nib.load(out_mask_path)
        pred_data = pred_nii.get_fdata(dtype=np.uint8)
        voxel_spacing = tuple(state["spatial_metadata"]["spacing_mm"])
        volumes = calculate_region_volumes(pred_data, voxel_spacing)

        # Expert mask comparison if supplied
        case_eval = None
        if state.get("expert_mask_path") and os.path.exists(state["expert_mask_path"]):
            expert_nii = nib.load(state["expert_mask_path"])
            expert_data = expert_nii.get_fdata(dtype=np.uint8)
            metrics = evaluate_case(pred_data, expert_data)
            case_eval = {
                "available": True,
                "metrics": metrics,
            }
        else:
            case_eval = {
                "available": False,
                "reason": "Expert mask not supplied"
            }

        # Build provenance
        provenance = {
            "model_name": "MONAI brats_mri_segmentation (SegResNet)",
            "model_license": "Apache 2.0",
            "training_data_source": "BraTS 2018 Multimodal Brain Tumor Dataset",
            "git_commit": get_git_commit(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_sha256": {k: state["files"][k]["sha256"] for k in ["t1", "t1gd", "t2", "flair"]},
        }

        # Generate PDF report
        generate_pdf_report(
            case_id=case_id,
            output_pdf_path=out_report_path,
            volumes=volumes,
            spatial_metadata=state["spatial_metadata"],
            provenance=provenance,
            case_evaluation=case_eval,
            runtime_seconds=elapsed,
        )

        # Update case state
        state["status"] = "completed"
        state["runtime_seconds"] = round(elapsed, 2)
        state["volumes"] = volumes
        state["case_evaluation"] = case_eval
        state["provenance"] = provenance
        state["mask_path"] = out_mask_path
        state["report_path"] = out_report_path
        save_case_metadata(case_id, state)

        return SegmentationTriggerResponse(
            case_id=case_id,
            status="completed",
            message=f"Segmentation completed in {elapsed:.2f} seconds."
        )

    except (PreprocessingError, PostprocessingError, FileNotFoundError, RuntimeError) as e:
        state["status"] = "failed"
        state["error"] = str(e)
        save_case_metadata(case_id, state)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=StandardErrorResponse(
                status="error",
                code="MODEL_INFERENCE_ERROR",
                message=str(e),
                details={"case_id": case_id},
                disclaimer=MANDATORY_DISCLAIMER
            ).model_dump()
        )


@router.get("/cases/{case_id}/status", response_model=CaseStatusResponse)
def get_case_status(case_id: str):
    """Processing and execution status for a case."""
    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    case_status = state.get("status", "unknown")
    progress = 100 if case_status == "completed" else (0 if case_status in ["uploaded", "failed"] else 50)

    return CaseStatusResponse(
        case_id=case_id,
        status=case_status,
        progress_percentage=progress,
        runtime_seconds=state.get("runtime_seconds"),
        error=state.get("error"),
        disclaimer=MANDATORY_DISCLAIMER,
    )


@router.get("/cases/{case_id}/results", response_model=CaseResultsResponse)
def get_case_results(case_id: str):
    """Quantitative volumetric results, provenance, and output links."""
    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    if state.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Case status is '{state.get('status')}'. Results are only available when completed."
        )

    raw_volumes = state["volumes"]
    regions: Dict[str, RegionVolume] = {}
    for r_name in ["WT", "TC", "ET"]:
        r_info = raw_volumes.get(r_name, {"voxel_count": 0, "volume_ml": 0.0})
        bbox = None
        if r_info.get("bounding_box_voxel"):
            bbox = BoundingBox(
                min=r_info["bounding_box_voxel"]["min"],
                max=r_info["bounding_box_voxel"]["max"]
            )
        regions[r_name] = RegionVolume(
            voxel_count=r_info["voxel_count"],
            volume_ml=r_info["volume_ml"],
            bounding_box_voxel=bbox,
        )

    # Evaluation
    eval_resp = None
    if state.get("case_evaluation") and state["case_evaluation"].get("available"):
        metrics_dict = {}
        for reg_k, metric_val in state["case_evaluation"]["metrics"].items():
            metrics_dict[reg_k] = CaseMetric(
                dice=metric_val["dice"],
                sensitivity=metric_val["sensitivity"]
            )
        eval_resp = CaseEvaluation(available=True, metrics=metrics_dict)
    else:
        eval_resp = CaseEvaluation(available=False, reason="Expert mask not supplied")

    # Suggested crosshair (center of Whole Tumour or image center)
    wt_bbox = regions["WT"].bounding_box_voxel
    shape = state["spatial_metadata"]["shape"]
    if wt_bbox:
        crosshair_vox = [
            (wt_bbox.min[i] + wt_bbox.max[i]) // 2 for i in range(3)
        ]
    else:
        crosshair_vox = [s // 2 for s in shape]

    return CaseResultsResponse(
        case_id=case_id,
        status="completed",
        runtime_seconds=state.get("runtime_seconds"),
        spatial_metadata=SpatialMetadata(
            dimensions=shape,
            voxel_spacing_mm=state["spatial_metadata"]["spacing_mm"],
            suggested_crosshair_voxel=crosshair_vox,
        ),
        regions=regions,
        case_evaluation=eval_resp,
        held_out_benchmark_reference={
            "dataset": "BraTS 2018 Validation Split",
            "mean_dice": {"WT": 0.9026, "TC": 0.8559, "ET": 0.7905},
            "disclaimer": "Held-out benchmark metrics are aggregate population references and do not validate individual patient cases."
        },
        provenance=Provenance(**state["provenance"]),
        outputs=CaseOutputs(
            mask_url=f"/api/cases/{case_id}/mask",
            report_url=f"/api/cases/{case_id}/report",
        ),
        disclaimer=MANDATORY_DISCLAIMER,
    )


@router.get("/cases/{case_id}/mask")
def download_mask(case_id: str):
    """Streams the predicted BraTS 2021 segmentation mask as binary NIfTI (.nii.gz)."""
    case_dir = get_case_dir(case_id)
    mask_path = os.path.join(case_dir, "predicted_seg.nii.gz")
    if not os.path.exists(mask_path):
        raise HTTPException(status_code=404, detail="Predicted mask not found. Run segmentation first.")

    return FileResponse(
        mask_path,
        media_type="application/gzip",
        filename=f"{case_id}_seg_brats2021.nii.gz"
    )


@router.get("/cases/{case_id}/report")
def download_report(case_id: str):
    """Streams the formal clinical provenance PDF report."""
    case_dir = get_case_dir(case_id)
    report_path = os.path.join(case_dir, "report.pdf")
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="PDF report not found. Run segmentation first.")

    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename=f"{case_id}_neuroscope_report.pdf"
    )
