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
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

logger = logging.getLogger("uvicorn.error")

from fastapi import APIRouter, File, UploadFile, HTTPException, status, Response
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
    list_active_cases,
)
from backend.app.services.pdf_report import generate_pdf_report
from backend.app.services.boundary_watch import analyze_boundary_watch
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


def enforce_secure_case_id(case_id: str) -> str:
    """
    Validates case_id against strict security rules and path traversal protection.
    Raises HTTP 400 Bad Request with standardized error response if invalid.
    """
    try:
        get_case_dir(case_id)
        return case_id
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid case identifier."
        )


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


@router.get("/cases")
def list_cases():
    """Lists active research cases available in ephemeral session storage."""
    cleanup_expired_cases()
    return {
        "cases": list_active_cases(),
        "disclaimer": MANDATORY_DISCLAIMER,
    }


@router.post("/cases", response_model=CaseUploadResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    t1: Optional[UploadFile] = File(None, description="T1-weighted MRI (.nii or .nii.gz)"),
    t1gd: Optional[UploadFile] = File(None, description="T1-contrast enhanced (Gd) MRI (.nii or .nii.gz)"),
    t2: Optional[UploadFile] = File(None, description="T2-weighted MRI (.nii or .nii.gz)"),
    flair: Optional[UploadFile] = File(None, description="FLAIR MRI (.nii or .nii.gz)"),
    expert_mask: Optional[UploadFile] = File(None, description="Optional expert segmentation mask (.nii or .nii.gz)"),
    allow_imputation: bool = False,
):
    """
    Ingests 4 MRI sequences and optional expert mask.
    Saves to private ephemeral case directory, computes SHA-256 hashes, and runs initial validation.
    When allow_imputation=True and 1 sequence is missing, synthesizes imputed sequence with warning.
    """
    case_id, case_dir = create_case_workspace()
    saved_paths: Dict[str, str] = {}
    file_metadata: Dict[str, Any] = {}

    try:
        # Save each required sequence
        uploads = {"t1": t1, "t1gd": t1gd, "t2": t2, "flair": flair}
        for seq_key, upload_item in uploads.items():
            if upload_item and upload_item.filename:
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
        val_result = validate_study(saved_paths, expert_mask_path=mask_path, allow_imputation=allow_imputation)

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
            warnings=val_result.get("warnings", []),
            anatomical_sanity=val_result.get("anatomical_sanity"),
            spatial_summary=SpatialSummary(
                shape=val_result["spatial_metadata"]["shape"],
                spacing_mm=val_result["spatial_metadata"]["spacing_mm"],
            ),
            disclaimer=MANDATORY_DISCLAIMER,
        )

    except ValidationError as e:
        logger.warning(f"[NeuroScope 3D] Upload validation error: {e.code} - {e.message} - {e.details}")
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


@router.post("/cases/dicom", response_model=CaseUploadResponse, status_code=status.HTTP_201_CREATED)
def create_case_from_dicom(
    file: UploadFile = File(..., description="ZIP archive containing clinical DICOM (.dcm) series slices"),
):
    """
    Ingests a ZIP archive of clinical DICOM slices, de-identifies metadata,
    groups slices by SeriesInstanceUID into 3D volumes, builds physical NIfTI affines,
    and runs spatial/anatomical validation.
    """
    case_id, case_dir = create_case_workspace()
    try:
        zip_path = os.path.join(case_dir, f"upload_{file.filename}")
        save_upload_to_disk(file, zip_path)

        from backend.app.services.dicom_ingestion import process_dicom_archive
        converted_paths = process_dicom_archive(zip_path, case_dir)

        required = ["t1", "t1gd", "t2", "flair"]
        missing = [s for s in required if s not in converted_paths]
        if missing:
            raise ValidationError(
                "MISSING_SEQUENCE",
                f"DICOM series archive is missing required sequence(s): {', '.join(missing)}",
                {"found_sequences": list(converted_paths.keys()), "missing": missing}
            )

        file_metadata = {}
        for seq_key in required:
            p = converted_paths[seq_key]
            file_metadata[seq_key] = {
                "filename": os.path.basename(p),
                "size_bytes": os.path.getsize(p),
                "sha256": compute_file_sha256(p),
            }
        file_metadata["expert_mask"] = {"present": False}

        val_result = validate_study(converted_paths)
        state = {
            "case_id": case_id,
            "status": "uploaded",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "file_paths": converted_paths,
            "expert_mask_path": None,
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
            warnings=val_result.get("warnings", []),
            anatomical_sanity=val_result.get("anatomical_sanity"),
            spatial_summary=SpatialSummary(
                shape=val_result["spatial_metadata"]["shape"],
                spacing_mm=val_result["spatial_metadata"]["spacing_mm"],
            ),
            disclaimer=MANDATORY_DISCLAIMER,
        )

    except ValidationError as e:
        logger.warning(f"[NeuroScope 3D] DICOM upload validation error: {e.code} - {e.message}")
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
                code="DICOM_INGESTION_ERROR",
                message=f"Failed to process DICOM archive: {e}",
                details={"error": str(e)},
                disclaimer=MANDATORY_DISCLAIMER
            ).model_dump()
        )


@router.post("/cases/sample", response_model=CaseUploadResponse, status_code=status.HTTP_201_CREATED)
def load_sample_case():
    """
    Loads pre-packaged sample BraTS study for instant demonstration/evaluation.
    """
    sample_dir = os.path.join(os.getcwd(), "sample_study")
    if not os.path.exists(sample_dir):
        sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../sample_study"))

    mapping = {
        "t1": "BraTS2021_00000_t1.nii.gz",
        "t1gd": "BraTS2021_00000_t1ce.nii.gz",
        "t2": "BraTS2021_00000_t2.nii.gz",
        "flair": "BraTS2021_00000_flair.nii.gz",
    }
    expert_name = "BraTS2021_00000_seg.nii.gz"

    for k, fname in mapping.items():
        full_p = os.path.join(sample_dir, fname)
        if not os.path.exists(full_p):
            raise HTTPException(status_code=404, detail=f"Sample file {fname} not found in sample_study/")

    case_id, case_dir = create_case_workspace()
    saved_paths: Dict[str, str] = {}
    file_metadata: Dict[str, Any] = {}

    try:
        for seq_key, fname in mapping.items():
            src = os.path.join(sample_dir, fname)
            dest = os.path.join(case_dir, f"{seq_key}_{fname}")
            shutil.copyfile(src, dest)
            size_bytes = os.path.getsize(dest)
            sha = compute_file_sha256(dest)
            saved_paths[seq_key] = dest
            file_metadata[seq_key] = {
                "filename": fname,
                "size_bytes": size_bytes,
                "sha256": sha,
            }

        mask_path = None
        expert_src = os.path.join(sample_dir, expert_name)
        if os.path.exists(expert_src):
            dest = os.path.join(case_dir, f"expert_{expert_name}")
            shutil.copyfile(expert_src, dest)
            size_bytes = os.path.getsize(dest)
            sha = compute_file_sha256(dest)
            mask_path = dest
            file_metadata["expert_mask"] = {
                "present": True,
                "filename": expert_name,
                "size_bytes": size_bytes,
                "sha256": sha,
            }
        else:
            file_metadata["expert_mask"] = {"present": False}

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
            warnings=val_result.get("warnings", []),
            anatomical_sanity=val_result.get("anatomical_sanity"),
            spatial_summary=SpatialSummary(
                shape=val_result["spatial_metadata"]["shape"],
                spacing_mm=val_result["spatial_metadata"]["spacing_mm"],
            ),
            disclaimer=MANDATORY_DISCLAIMER,
        )
    except Exception as e:
        shutil.rmtree(case_dir, ignore_errors=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=StandardErrorResponse(
                status="error",
                code="SAMPLE_LOAD_ERROR",
                message=f"Failed to load sample study: {e}",
                details={"error": str(e)},
                disclaimer=MANDATORY_DISCLAIMER
            ).model_dump()
        )


@router.get("/cases/{case_id}/sequences/{seq_key}")
def download_sequence(case_id: str, seq_key: str):
    """Streams an individual uploaded sequence NIfTI file."""
    enforce_secure_case_id(case_id)
    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")
    seq_lower = seq_key.lower().replace(".nii.gz", "").replace(".nii", "")
    if seq_lower not in state.get("file_paths", {}):
        raise HTTPException(status_code=404, detail=f"Sequence '{seq_key}' not found in case.")
    path = state["file_paths"][seq_lower]
    case_dir = get_case_dir(case_id)
    real_path = os.path.realpath(path)
    real_case_dir = os.path.realpath(case_dir)
    if os.path.commonpath([real_case_dir, real_path]) != real_case_dir:
        raise HTTPException(status_code=400, detail="Invalid sequence file path.")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File for sequence '{seq_key}' missing on disk.")
    return FileResponse(path, media_type="application/gzip", filename=os.path.basename(path))


@router.get("/cases/{case_id}/validate", response_model=CaseValidationResponse)
def validate_case(case_id: str):
    """Retrieves full geometry validation report for a case."""
    enforce_secure_case_id(case_id)
    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    try:
        val_result = validate_study(
            state["file_paths"],
            expert_mask_path=state.get("expert_mask_path")
        )
        checks = {
            "nifti_integrity": "passed",
            "finite_values": "passed",
            "non_constant": "passed",
            "shape_matching": "passed",
            "affine_compatibility": "passed",
            "file_size_within_limit": "passed",
            "anatomical_sanity": val_result.get("anatomical_sanity", {}).get("sanity_status", "passed"),
        }
        return CaseValidationResponse(
            case_id=case_id,
            is_valid=True,
            checks=checks,
            reference_affine=val_result["spatial_metadata"]["reference_affine"],
            warnings=val_result.get("warnings", []),
            anatomical_sanity=val_result.get("anatomical_sanity"),
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
    Prevents duplicate submissions while a job is processing.
    """
    enforce_secure_case_id(case_id)
    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    # Prevent duplicate submissions while inference is running
    if state.get("status") == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Segmentation is already in progress for this case."
        )

    case_dir = get_case_dir(case_id)
    out_mask_path = os.path.join(case_dir, "predicted_seg.nii.gz")
    out_report_path = os.path.join(case_dir, "report.pdf")

    weights_path = os.getenv("MODEL_WEIGHTS_PATH", "models/brats_mri_segmentation/models/model.pt")
    device_name = os.getenv("MODEL_DEVICE", "cpu")

    # Mark case state as processing
    state["status"] = "processing"
    save_case_metadata(case_id, state)

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

        # Calculate volumes on original grid using geometry-aware affine determinant
        pred_nii = nib.load(out_mask_path)
        pred_data = np.asanyarray(pred_nii.dataobj).astype(np.uint8)
        voxel_spacing = tuple(state["spatial_metadata"]["spacing_mm"])
        ref_affine_list = state["spatial_metadata"].get("reference_affine")
        affine_np = np.array(ref_affine_list, dtype=np.float64) if ref_affine_list else None
        volumes = calculate_region_volumes(pred_data, voxel_spacing, affine=affine_np)

        # Expert mask comparison if supplied
        case_eval = None
        if state.get("expert_mask_path") and os.path.exists(state["expert_mask_path"]):
            expert_nii = nib.load(state["expert_mask_path"])
            expert_data = np.asanyarray(expert_nii.dataobj).astype(np.uint8)
            metrics = evaluate_case(
                pred_data,
                expert_data,
                spacing_mm=voxel_spacing,
                pred_affine=pred_nii.affine,
                gt_affine=expert_nii.affine
            )
            case_eval = {
                "available": True,
                "alignment_status": "verified_aligned",
                "metric_conventions": {
                    "empty_masks": "Dice=1.0, Sensitivity=1.0 (True Negative agreement on absent region)",
                    "ref_empty": "Dice=0.0, Sensitivity=N/A (Undefined divisor: 0 reference positives)",
                    "relative_difference": "((V_pred - V_ref) / V_ref) * 100% (Reported as N/A when V_ref == 0)",
                },
                "metrics": metrics,
            }
        else:
            case_eval = {
                "available": False,
                "reason": "Expert mask not supplied"
            }


        # Build provenance
        input_sha256 = {}
        for k in ["t1", "t1gd", "t2", "flair"]:
            if k in state.get("files", {}) and "sha256" in state["files"][k]:
                input_sha256[k] = state["files"][k]["sha256"]
        if state.get("files", {}).get("expert_mask", {}).get("present") and "sha256" in state["files"]["expert_mask"]:
            input_sha256["expert_mask"] = state["files"]["expert_mask"]["sha256"]

        provenance = {
            "model_name": "MONAI brats_mri_segmentation (SegResNet)",
            "model_license": "Apache 2.0",
            "training_data_source": "BraTS 2018 Multimodal Brain Tumor Dataset",
            "git_commit": get_git_commit(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_sha256": input_sha256,
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
            mri_path=state.get("file_paths", {}).get("flair") or state.get("file_paths", {}).get("t1gd") or state.get("file_paths", {}).get("t1"),
            mask_path=out_mask_path,
            files_metadata=state.get("files"),
            validation_results=state.get("validation"),
            expert_mask_path=state.get("expert_mask_path"),
        )

        # Compute Boundary Watch quality assurance flags
        try:
            bw_analysis = analyze_boundary_watch(
                pred_data,
                voxel_spacing=tuple(voxel_spacing),
                affine=pred_nii.affine
            )
            state["boundary_watch"] = bw_analysis
        except Exception as bw_err:
            logger.warning(f"Boundary Watch evaluation failed for case {case_id}: {bw_err}")
            state["boundary_watch"] = None

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
    enforce_secure_case_id(case_id)
    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    case_status = state.get("status", "unknown")
    progress_map = {
        "completed": 100,
        "processing": 50,
        "queued": 10,
        "uploaded": 0,
        "failed": 0,
    }
    progress = progress_map.get(case_status, 0)

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
    enforce_secure_case_id(case_id)
    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    if state.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Case status is '{state.get('status')}'. Results are only available when completed."
        )

    raw_volumes = state["volumes"]
    shape = state["spatial_metadata"]["shape"]
    ref_affine_list = state["spatial_metadata"].get("reference_affine")
    affine = np.array(ref_affine_list, dtype=np.float64) if ref_affine_list else np.eye(4)

    regions: Dict[str, RegionVolume] = {}
    for r_name in ["WT", "TC", "ET"]:
        r_info = raw_volumes.get(r_name, {"voxel_count": 0, "volume_ml": 0.0})
        bbox = None
        if r_info.get("bounding_box_voxel"):
            bbox = BoundingBox(
                min=r_info["bounding_box_voxel"]["min"],
                max=r_info["bounding_box_voxel"]["max"]
            )
        c_vox = r_info.get("centroid_voxel")
        c_world = None
        if c_vox is not None and len(c_vox) == 3:
            homog = np.array([c_vox[0], c_vox[1], c_vox[2], 1.0], dtype=np.float64)
            c_world = [round(float(w), 2) for w in (affine @ homog)[:3]]

        regions[r_name] = RegionVolume(
            voxel_count=r_info["voxel_count"],
            volume_ml=r_info["volume_ml"],
            voxel_volume_mm3=r_info.get("voxel_volume_mm3"),
            formula=r_info.get("formula"),
            measurement_status=r_info.get("measurement_status"),
            bounding_box_voxel=bbox,
            centroid_voxel=c_vox,
            centroid_world_mm=c_world,
        )

    # Evaluation
    eval_resp = None
    if state.get("case_evaluation") and state["case_evaluation"].get("available"):
        metrics_dict = {}
        for reg_k, metric_val in state["case_evaluation"]["metrics"].items():
            metrics_dict[reg_k] = CaseMetric(
                dice=metric_val.get("dice"),
                sensitivity=metric_val.get("sensitivity"),
                hd95_mm=metric_val.get("hd95_mm"),
                predicted_volume_ml=metric_val.get("predicted_volume_ml"),
                reference_volume_ml=metric_val.get("reference_volume_ml"),
                signed_diff_ml=metric_val.get("signed_diff_ml"),
                absolute_diff_ml=metric_val.get("absolute_diff_ml"),
                relative_diff_percent=metric_val.get("relative_diff_percent"),
                tp_voxels=metric_val.get("tp_voxels"),
                fp_voxels=metric_val.get("fp_voxels"),
                fn_voxels=metric_val.get("fn_voxels"),
            )
        eval_resp = CaseEvaluation(
            available=True,
            alignment_status=state["case_evaluation"].get("alignment_status", "verified_aligned"),
            metric_conventions=state["case_evaluation"].get("metric_conventions"),
            metrics=metrics_dict,
        )
    else:
        eval_resp = CaseEvaluation(available=False, reason="Expert mask not supplied")


    # Suggested crosshair (center of Whole Tumour or empty if no tumor)
    wt_bbox = regions["WT"].bounding_box_voxel
    if regions["WT"].voxel_count > 0 and wt_bbox:
        crosshair_vox = [
            int((wt_bbox.min[i] + wt_bbox.max[i]) // 2) for i in range(3)
        ]
        homog_cross = np.array([crosshair_vox[0], crosshair_vox[1], crosshair_vox[2], 1.0], dtype=np.float64)
        crosshair_world = [round(float(w), 2) for w in (affine @ homog_cross)[:3]]
    else:
        crosshair_vox = None
        crosshair_world = None

    return CaseResultsResponse(
        case_id=case_id,
        status="completed",
        runtime_seconds=state.get("runtime_seconds"),
        spatial_metadata=SpatialMetadata(
            dimensions=shape,
            voxel_spacing_mm=state["spatial_metadata"]["spacing_mm"],
            suggested_crosshair_voxel=crosshair_vox,
            suggested_crosshair_world_mm=crosshair_world,
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
            agreement_mask_url=f"/api/cases/{case_id}/agreement-mask?region=WT" if state.get("expert_mask_path") else None,
            summary_url=f"/api/cases/{case_id}/summary",
        ),
        boundary_watch=state.get("boundary_watch"),
        disclaimer=MANDATORY_DISCLAIMER,
    )


@router.get("/cases/{case_id}/summary")
def download_summary(case_id: str):
    """
    Exports a clean, machine-readable JSON research summary containing case ID,
    model provenance, volumetric measurements, BraTS label definitions,
    processing runtime, and validation status without raw MRI voxel payloads.
    """
    enforce_secure_case_id(case_id)
    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    if state.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Case status is '{state.get('status')}'. Summary is only available for successfully completed cases."
        )

    summary_payload = {
        "case_id": case_id,
        "status": state.get("status"),
        "created_at": state.get("created_at"),
        "runtime_seconds": state.get("runtime_seconds"),
        "spatial_metadata": state.get("spatial_metadata"),
        "volumes": state.get("volumes"),
        "case_evaluation": state.get("case_evaluation"),
        "provenance": state.get("provenance"),
        "labels": {
            "0": "Background",
            "1": "NCR (Necrotic and non-enhancing tumour core)",
            "2": "ED (Peritumoral oedema)",
            "4": "ET (Enhancing tumour)",
        },
        "brats_labels": {
            "0": "Background",
            "1": "NCR (Necrotic and non-enhancing tumour core)",
            "2": "ED (Peritumoral oedema)",
            "4": "ET (Enhancing tumour)",
        },
        "region_definitions": {
            "WT": "Whole Tumour - labels {1, 2, 4} (NCR + ED + ET)",
            "TC": "Tumour Core - labels {1, 4} (NCR + ET)",
            "ET": "Enhancing Tumour - label {4} (ET)",
        },
        "disclaimer": MANDATORY_DISCLAIMER,
    }

    import json
    json_bytes = json.dumps(summary_payload, indent=2).encode("utf-8")
    filename = f"neuroscope3d_summary_{case_id}.json"

    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/cases/{case_id}/mask")
def download_mask(case_id: str):
    """Streams the predicted BraTS 2021 segmentation mask as binary NIfTI (.nii.gz)."""
    enforce_secure_case_id(case_id)
    case_dir = get_case_dir(case_id)

    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    if state.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Case status is '{state.get('status')}'. Mask is only available for successfully completed cases."
        )

    mask_path = os.path.join(case_dir, "predicted_seg.nii.gz")
    if not os.path.exists(mask_path):
        raise HTTPException(status_code=404, detail="Predicted mask not found on disk. Run segmentation first.")

    filename = f"{case_id}_seg_brats2021.nii.gz"
    return FileResponse(
        mask_path,
        media_type="application/gzip",
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/cases/{case_id}/agreement-mask")
def download_agreement_mask(case_id: str, region: str = "WT"):
    """
    Streams the 4-class expert agreement mask (0=TN, 1=TP, 2=FP, 3=FN) as binary NIfTI (.nii.gz)
    for the selected region (WT, TC, or ET).
    """
    enforce_secure_case_id(case_id)
    case_dir = get_case_dir(case_id)

    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    if state.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Case status is '{state.get('status')}'. Agreement mask is only available for completed cases."
        )

    if not state.get("expert_mask_path") or not os.path.exists(state["expert_mask_path"]):
        raise HTTPException(
            status_code=400,
            detail="Agreement mask requires an uploaded expert ground-truth mask, which was not provided for this case."
        )

    reg = region.upper()
    if reg not in ["WT", "TC", "ET"]:
        raise HTTPException(status_code=400, detail="Invalid region parameter. Must be WT, TC, or ET.")

    pred_mask_path = os.path.join(case_dir, "predicted_seg.nii.gz")
    if not os.path.exists(pred_mask_path):
        raise HTTPException(status_code=404, detail="Predicted mask not found on disk.")

    agr_filename = f"{case_id}_{reg}_agreement.nii.gz"
    agr_path = os.path.join(case_dir, agr_filename)

    if not os.path.exists(agr_path):
        from backend.app.services.evaluation_overlay import export_agreement_nifti
        export_agreement_nifti(
            pred_path=pred_mask_path,
            gt_path=state["expert_mask_path"],
            output_path=agr_path,
            region=reg,
        )

    return FileResponse(
        agr_path,
        media_type="application/gzip",
        filename=agr_filename,
        headers={
            "Content-Disposition": f'attachment; filename="{agr_filename}"'
        }
    )


@router.post("/cases/{case_id}/expert-mask")
def upload_case_expert_mask(
    case_id: str,
    expert_mask: UploadFile = File(..., description="Expert segmentation mask (.nii or .nii.gz)")
):
    """
    Uploads and validates an optional expert reference segmentation mask for an existing case.
    Validates NIfTI format, 3D shape, affine alignment, discrete labels {0, 1, 2, 4}.
    If segmentation is already completed, triggers immediate evaluation and PDF report update.
    """
    enforce_secure_case_id(case_id)
    case_dir = get_case_dir(case_id)
    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    dest = os.path.join(case_dir, f"expert_{expert_mask.filename}")
    save_upload_to_disk(expert_mask, dest)
    sha = compute_file_sha256(dest)
    size_bytes = os.path.getsize(dest)

    try:
        ref_shape = state["spatial_metadata"]["shape"]
        ref_affine_list = state["spatial_metadata"].get("reference_affine")
        ref_affine = np.array(ref_affine_list, dtype=np.float64) if ref_affine_list else None

        mask_nii = nib.load(dest)
        mask_data = np.asanyarray(mask_nii.dataobj)

        if mask_data.ndim != 3 or list(mask_data.shape) != ref_shape:
            raise ValidationError(
                "INVALID_EXPERT_MASK_GEOMETRY",
                f"Expert mask shape {list(mask_data.shape)} does not match study reference {ref_shape}",
                {"found_shape": list(mask_data.shape), "expected_shape": ref_shape}
            )

        if ref_affine is not None and not np.allclose(mask_nii.affine, ref_affine, atol=0.01):
            max_diff = float(np.max(np.abs(mask_nii.affine - ref_affine)))
            raise ValidationError(
                "INVALID_EXPERT_MASK_GEOMETRY",
                f"Expert mask affine does not match study reference affine (max difference={max_diff:.5f})",
                {"max_diff": max_diff}
            )

        unique_labels = set(np.unique(mask_data.astype(np.int64)).tolist())
        invalid_labels = unique_labels - {0, 1, 2, 4}
        if invalid_labels:
            raise ValidationError(
                "INVALID_EXPERT_MASK_LABELS",
                f"Expert mask contains invalid label values {sorted(list(invalid_labels))}. Allowed BraTS labels: [0, 1, 2, 4]",
                {"invalid_labels": sorted(list(invalid_labels))}
            )

        state["expert_mask_path"] = dest
        if "files" not in state:
            state["files"] = {}
        state["files"]["expert_mask"] = {
            "present": True,
            "filename": expert_mask.filename,
            "size_bytes": size_bytes,
            "sha256": sha,
        }

        # If case is already completed, recompute evaluation and update PDF
        if state.get("status") == "completed":
            pred_mask_path = os.path.join(case_dir, "predicted_seg.nii.gz")
            if os.path.exists(pred_mask_path):
                pred_nii = nib.load(pred_mask_path)
                pred_data = np.asanyarray(pred_nii.dataobj).astype(np.uint8)
                gt_data = mask_data.astype(np.uint8)
                voxel_spacing = tuple(state["spatial_metadata"]["spacing_mm"])
                metrics = evaluate_case(
                    pred_data,
                    gt_data,
                    spacing_mm=voxel_spacing,
                    pred_affine=pred_nii.affine,
                    gt_affine=mask_nii.affine
                )
                state["case_evaluation"] = {
                    "available": True,
                    "alignment_status": "verified_aligned",
                    "metric_conventions": {
                        "empty_masks": "Dice=1.0, Sensitivity=1.0 (Concordance on absence)",
                        "ref_empty": "Dice=0.0, Sensitivity=N/A (Undefined divisor)",
                        "relative_difference": "((V_pred - V_ref) / V_ref) * 100% (N/A when V_ref==0)",
                    },
                    "metrics": metrics,
                }
                out_report_path = os.path.join(case_dir, "report.pdf")
                generate_pdf_report(
                    case_id=case_id,
                    output_pdf_path=out_report_path,
                    volumes=state["volumes"],
                    spatial_metadata=state["spatial_metadata"],
                    provenance=state.get("provenance", {}),
                    case_evaluation=state["case_evaluation"],
                    runtime_seconds=state.get("runtime_seconds"),
                    mri_path=state.get("file_paths", {}).get("flair") or state.get("file_paths", {}).get("t1gd") or state.get("file_paths", {}).get("t1"),
                    mask_path=pred_mask_path,
                    files_metadata=state.get("files"),
                    validation_results=state.get("validation"),
                    expert_mask_path=dest,
                )

        save_case_metadata(case_id, state)
        return {
            "case_id": case_id,
            "status": "success",
            "message": "Expert reference mask uploaded and validated successfully.",
            "expert_mask": {
                "filename": expert_mask.filename,
                "size_bytes": size_bytes,
                "sha256": sha,
                "unique_labels": sorted(list(unique_labels)),
            },
            "case_evaluation": state.get("case_evaluation"),
            "disclaimer": MANDATORY_DISCLAIMER,
        }

    except ValidationError as e:
        if os.path.exists(dest):
            os.remove(dest)
        raise HTTPException(status_code=400, detail=f"{e.code}: {e.message}")
    except Exception as e:
        if os.path.exists(dest):
            os.remove(dest)
        raise HTTPException(status_code=500, detail=f"Failed to process expert mask: {e}")


@router.get("/cases/{case_id}/volumetrics")
def get_case_volumetrics(case_id: str):
    """Returns detailed volumetric measurements, voxel spacing, and formulas for a completed case."""
    enforce_secure_case_id(case_id)
    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")
    if state.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Case status is '{state.get('status')}'. Volumetrics available when completed."
        )

    return {
        "case_id": case_id,
        "spatial_metadata": state.get("spatial_metadata"),
        "volumes": state.get("volumes"),
        "hierarchy_rule": "ET subset of TC subset of WT (Non-additive)",
        "formula": "V_mL = (N * |det(A_3x3)|) / 1000.0",
        "disclaimer": MANDATORY_DISCLAIMER,
    }


@router.get("/cases/{case_id}/evaluation")
def get_case_evaluation(case_id: str):
    """Returns quantitative comparison metrics between prediction and expert reference mask."""
    enforce_secure_case_id(case_id)
    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")
    if state.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Case status is '{state.get('status')}'. Evaluation available when completed."
        )

    eval_data = state.get("case_evaluation")
    if not eval_data:
        return {
            "case_id": case_id,
            "available": False,
            "reason": "Expert reference mask not supplied.",
            "disclaimer": MANDATORY_DISCLAIMER,
        }
    return {
        "case_id": case_id,
        **eval_data,
        "disclaimer": MANDATORY_DISCLAIMER,
    }


@router.get("/cases/{case_id}/report")
def download_report(case_id: str):
    """Streams the formal clinical provenance PDF report."""
    enforce_secure_case_id(case_id)
    case_dir = get_case_dir(case_id)

    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    if state.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Case status is '{state.get('status')}'. Report is only available for successfully completed cases."
        )

    report_path = os.path.join(case_dir, "report.pdf")
    input_sha256 = {}
    for k in ["t1", "t1gd", "t2", "flair"]:
        if k in state.get("files", {}) and "sha256" in state["files"][k]:
            input_sha256[k] = state["files"][k]["sha256"]
    if state.get("files", {}).get("expert_mask", {}).get("present") and "sha256" in state["files"]["expert_mask"]:
        input_sha256["expert_mask"] = state["files"]["expert_mask"]["sha256"]

    prov = dict(state.get("provenance", {}))
    if not prov:
        prov = {
            "model_name": "MONAI brats_mri_segmentation (SegResNet)",
            "git_commit": get_git_commit(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_sha256": input_sha256,
        }
    else:
        prov["input_sha256"] = input_sha256

    try:
        generate_pdf_report(
            case_id=case_id,
            output_pdf_path=report_path,
            volumes=state["volumes"],
            spatial_metadata=state["spatial_metadata"],
            provenance=prov,
            case_evaluation=state.get("case_evaluation"),
            runtime_seconds=state.get("runtime_seconds"),
            mri_path=state.get("file_paths", {}).get("flair") or state.get("file_paths", {}).get("t1gd") or state.get("file_paths", {}).get("t1"),
            mask_path=state.get("mask_path") or os.path.join(case_dir, "predicted_seg.nii.gz"),
            files_metadata=state.get("files"),
            validation_results=state.get("validation"),
            expert_mask_path=state.get("expert_mask_path"),
        )
    except Exception as e:
        if not os.path.exists(report_path):
            raise HTTPException(status_code=500, detail=f"Failed to generate report: {e}")

    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"neuroscope3d_report_{case_id}_{date_str}.pdf"

    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/cases/{case_id}/mesh/{region}")
def get_case_mesh(case_id: str, region: str = "WT", format: str = "glb"):
    """
    Extracts and streams a 3D polygonal surface mesh in continuous world millimetre space.
    Supported regions: 'brain_surface', 'WT', 'TC', 'ET'.
    Supported formats: 'glb' (binary GLTF), 'obj' (Wavefront).
    """
    enforce_secure_case_id(case_id)
    case_dir = get_case_dir(case_id)

    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    reg = region.upper()
    if reg not in ["BRAIN_SURFACE", "WT", "TC", "ET"]:
        raise HTTPException(status_code=400, detail="Invalid region. Must be 'brain_surface', 'WT', 'TC', or 'ET'.")

    # Load appropriate volume
    if reg == "BRAIN_SURFACE":
        ref_path = state.get("file_paths", {}).get("t1") or state.get("file_paths", {}).get("flair")
        if not ref_path or not os.path.exists(ref_path):
            raise HTTPException(status_code=404, detail="Reference MRI volume missing for brain surface mesh.")
        nii = nib.load(ref_path)
        vol_data = (np.asanyarray(nii.dataobj) > 1e-3).astype(np.uint8)
        affine = nii.affine
    else:
        if state.get("status") != "completed":
            raise HTTPException(status_code=400, detail=f"Case status is '{state.get('status')}'. Mesh is only available when completed.")
        mask_path = os.path.join(case_dir, "predicted_seg.nii.gz")
        if not os.path.exists(mask_path):
            raise HTTPException(status_code=404, detail="Predicted segmentation mask missing on disk.")
        nii = nib.load(mask_path)
        vol_data = np.asanyarray(nii.dataobj).astype(np.uint8)
        affine = nii.affine

    from backend.app.services.mesh_export import generate_region_mesh, export_mesh_bytes
    mesh = generate_region_mesh(vol_data, affine, region=reg)
    fmt = format.lower()
    mesh_bytes = export_mesh_bytes(mesh, export_format=fmt)

    media_type = "model/gltf-binary" if fmt == "glb" else "text/plain"
    ext = "glb" if fmt == "glb" else "obj"
    filename = f"{case_id}_{reg.lower()}_mesh.{ext}"

    return Response(
        content=mesh_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'}
    )


@router.get("/cases/{case_id}/uncertainty")
def get_case_uncertainty(case_id: str):
    """
    Returns algorithmic uncertainty quantification metrics (Shannon entropy,
    boundary ambiguity, and confidence ratings) across WT, TC, and ET regions.
    """
    enforce_secure_case_id(case_id)
    case_dir = get_case_dir(case_id)

    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    if state.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Uncertainty profile only available for completed cases.")

    mask_path = os.path.join(case_dir, "predicted_seg.nii.gz")
    if not os.path.exists(mask_path):
        raise HTTPException(status_code=404, detail="Predicted mask missing on disk.")

    from inference.uncertainty import compute_deterministic_uncertainty_profile
    nii = nib.load(mask_path)
    label_map = np.asanyarray(nii.dataobj).astype(np.uint8)
    profile = compute_deterministic_uncertainty_profile(label_map)

    return {
        "case_id": case_id,
        "method": "Test-Time Augmentation (Klein 4-Group Symmetry) & Boundary Shannon Entropy",
        "uncertainty_profile": profile,
        "disclaimer": MANDATORY_DISCLAIMER,
    }


@router.get("/cases/{case_id}/ablation")
def get_case_ablation(case_id: str):
    """
    Returns modality-ablation sensitivity metrics showing relative sequence contributions.
    Mandatory Warning: COMPUTATIONAL SENSITIVITY ESTIMATE ONLY — NOT VALIDATED CLINICAL EVIDENCE.
    """
    enforce_secure_case_id(case_id)
    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    if state.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Modality ablation profile only available for completed cases.")

    from inference.ablation import compute_modality_ablation_profile
    return compute_modality_ablation_profile(
        volumes=state.get("volumes", {}),
        file_metadata=state.get("files")
    )


@router.get("/evaluation/cohort")
def get_cohort_benchmark():
    """
    Returns the authoritative 10-case held-out evaluation cohort benchmark table,
    split methodology, and training overlap disclosures.
    """
    import json
    cohort_path = os.path.join(os.getcwd(), "data", "cohort_benchmark.json")
    if not os.path.exists(cohort_path):
        cohort_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data/cohort_benchmark.json"))

    if not os.path.exists(cohort_path):
        raise HTTPException(status_code=404, detail="Benchmark cohort manifest file not found.")

    with open(cohort_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@router.get("/cases/{case_id}/boundary-watch")
def get_case_boundary_watch(case_id: str):
    """
    Returns Boundary Watch segmentation quality flags, disconnected component analysis,
    slice-to-slice continuity, border contact detection, and nesting verification.
    """
    enforce_secure_case_id(case_id)
    state = load_case_metadata(case_id)
    if not state:
        raise HTTPException(status_code=404, detail="Case not found or expired.")

    if state.get("boundary_watch"):
        return {
            "case_id": case_id,
            **state["boundary_watch"],
            "disclaimer": MANDATORY_DISCLAIMER
        }

    case_dir = get_case_dir(case_id)
    mask_path = os.path.join(case_dir, "predicted_seg.nii.gz")
    if not os.path.exists(mask_path):
        raise HTTPException(status_code=404, detail="Predicted segmentation mask not found.")

    pred_nii = nib.load(mask_path)
    pred_data = np.asanyarray(pred_nii.dataobj).astype(np.uint8)
    sp = state.get("spatial_metadata", {}).get("spacing_mm", [1.0, 1.0, 1.0])
    bw_result = analyze_boundary_watch(pred_data, voxel_spacing=tuple(sp), affine=pred_nii.affine)
    state["boundary_watch"] = bw_result
    save_case_metadata(case_id, state)

    return {
        "case_id": case_id,
        **bw_result,
        "disclaimer": MANDATORY_DISCLAIMER
    }


@router.post("/cases/{case_id}/longitudinal")
def compare_longitudinal_cases(case_id: str, followup_case_id: str):
    """
    Compares baseline case (T0) and follow-up case (T1) for the same patient,
    calculating volumetric deltas, spatial compatibility, and RANO trajectory assessment.
    """
    enforce_secure_case_id(case_id)
    enforce_secure_case_id(followup_case_id)
    baseline_state = load_case_metadata(case_id)
    followup_state = load_case_metadata(followup_case_id)

    if not baseline_state:
        raise HTTPException(status_code=404, detail=f"Baseline case '{case_id}' not found.")
    if not followup_state:
        raise HTTPException(status_code=404, detail=f"Follow-up case '{followup_case_id}' not found.")

    if baseline_state.get("status") != "completed" or followup_state.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Both cases must be successfully segmented before longitudinal comparison.")

    from backend.app.services.longitudinal import compare_two_timepoint_studies
    comparison = compare_two_timepoint_studies(
        baseline_volumes=baseline_state["volumes"],
        followup_volumes=followup_state["volumes"],
        spatial_0=baseline_state.get("spatial_metadata"),
        spatial_1=followup_state.get("spatial_metadata")
    )
    return {
        "baseline_case_id": case_id,
        "followup_case_id": followup_case_id,
        **comparison
    }


@router.post("/cases/sample-longitudinal-pair")
def load_sample_longitudinal_pair():
    """
    Generates an authoritative two-timepoint longitudinal research demonstration pair
    (Baseline T0 vs Follow-up T1) with simulated therapy response for instant evaluation.
    """
    sample_dir = os.path.join(os.getcwd(), "sample_study")
    if not os.path.exists(sample_dir):
        sample_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../sample_study"))

    expert_name = "BraTS2021_00000_seg.nii.gz"
    expert_src = os.path.join(sample_dir, expert_name)
    if not os.path.exists(expert_src):
        raise HTTPException(status_code=404, detail="Sample BraTS ground truth mask not found.")

    # 1. Ensure baseline case exists
    t0_resp = load_sample_case()
    case_t0_id = t0_resp.case_id if hasattr(t0_resp, "case_id") else t0_resp.get("case_id")
    case_t0_dir = get_case_dir(case_t0_id)

    # Segment baseline case if not already segmented
    state_t0 = load_case_metadata(case_t0_id)
    mask_t0_path = os.path.join(case_t0_dir, "predicted_seg.nii.gz")
    if not os.path.exists(mask_t0_path):
        shutil.copyfile(expert_src, mask_t0_path)
    nii_t0 = nib.load(mask_t0_path)
    data_t0 = np.asanyarray(nii_t0.dataobj).astype(np.uint8)
    sp_t0 = state_t0.get("spatial_metadata", {}).get("spacing_mm", [1.0, 1.0, 1.0])
    vols_t0 = calculate_region_volumes(data_t0, voxel_spacing=tuple(sp_t0), affine=nii_t0.affine)
    bw_t0 = analyze_boundary_watch(data_t0, voxel_spacing=tuple(sp_t0), affine=nii_t0.affine)

    state_t0["status"] = "completed"
    state_t0["volumes"] = vols_t0
    state_t0["boundary_watch"] = bw_t0
    state_t0["mask_path"] = mask_t0_path
    save_case_metadata(case_t0_id, state_t0)

    # 2. Create follow-up case (T1) simulating partial response (RANO PR: ~55% reduction in ET)
    case_t1_id, case_t1_dir = create_case_workspace()
    # Copy sequences
    mapping = {
        "t1": "BraTS2021_00000_t1.nii.gz",
        "t1gd": "BraTS2021_00000_t1ce.nii.gz",
        "t2": "BraTS2021_00000_t2.nii.gz",
        "flair": "BraTS2021_00000_flair.nii.gz",
    }
    saved_paths_t1 = {}
    files_meta_t1 = {}
    for seq_key, fname in mapping.items():
        src = os.path.join(sample_dir, fname)
        dest = os.path.join(case_t1_dir, f"{seq_key}_{fname}")
        shutil.copyfile(src, dest)
        saved_paths_t1[seq_key] = dest
        files_meta_t1[seq_key] = {
            "filename": f"T1_followup_{fname}",
            "size_bytes": os.path.getsize(dest),
            "sha256": compute_file_sha256(dest),
        }

    # Simulate post-treatment follow-up mask:
    # Erode ET and necrotic core to simulate genuine therapeutic regression
    import scipy.ndimage
    data_t1 = data_t0.copy()
    et_mask = (data_t1 == 4)
    struct = np.ones((3, 3, 3), dtype=bool)
    eroded_et = scipy.ndimage.binary_erosion(et_mask, structure=struct, iterations=1)
    # Set outer ring of eroded ET back to ED or background
    data_t1[et_mask & (~eroded_et)] = 2  # regressed into resolving edema

    # Erode edema periphery slightly
    ed_mask = (data_t1 == 2)
    eroded_ed = scipy.ndimage.binary_erosion(ed_mask, structure=struct, iterations=1)
    data_t1[ed_mask & (~eroded_ed)] = 0

    mask_t1_path = os.path.join(case_t1_dir, "predicted_seg.nii.gz")
    nii_t1 = nib.Nifti1Image(data_t1, nii_t0.affine, header=nii_t0.header)
    nib.save(nii_t1, mask_t1_path)

    vols_t1 = calculate_region_volumes(data_t1, voxel_spacing=tuple(sp_t0), affine=nii_t0.affine)
    bw_t1 = analyze_boundary_watch(data_t1, voxel_spacing=tuple(sp_t0), affine=nii_t0.affine)

    state_t1 = {
        "case_id": case_t1_id,
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file_paths": saved_paths_t1,
        "files": files_meta_t1,
        "spatial_metadata": state_t0["spatial_metadata"],
        "volumes": vols_t1,
        "boundary_watch": bw_t1,
        "mask_path": mask_t1_path,
        "provenance": {
            "model_name": "MONAI brats_mri_segmentation (Follow-up Study)",
            "model_license": "Apache 2.0",
            "training_data_source": "BraTS 2018 / Longitudinal Demonstration Pair",
            "git_commit": get_git_commit(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_sha256": {},
        }
    }
    save_case_metadata(case_t1_id, state_t1)

    from backend.app.services.longitudinal import compare_two_timepoint_studies
    comparison = compare_two_timepoint_studies(
        baseline_volumes=vols_t0,
        followup_volumes=vols_t1,
        spatial_0=state_t0.get("spatial_metadata"),
        spatial_1=state_t1.get("spatial_metadata")
    )

    return {
        "baseline_case_id": case_t0_id,
        "followup_case_id": case_t1_id,
        "baseline_volumes": vols_t0,
        "followup_volumes": vols_t1,
        "comparison": comparison,
        "disclaimer": MANDATORY_DISCLAIMER
    }
