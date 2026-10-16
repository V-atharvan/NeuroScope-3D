"""
NeuroScope 3D - Pydantic Contracts and Schemas
Adheres strictly to docs/API_CONTRACT.md and PRD_BASE.md.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

MANDATORY_DISCLAIMER = "Research and teaching prototype only. Not for clinical diagnosis."


class ModelReadiness(BaseModel):
    loaded: bool = False
    model_name: str = "brats_mri_segmentation"
    device: str = "cpu"


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "0.1.0"
    commit_id: Optional[str] = None
    timestamp: str
    model_readiness: ModelReadiness = Field(default_factory=ModelReadiness)
    disclaimer: str = MANDATORY_DISCLAIMER


class FileMetadata(BaseModel):
    filename: str
    size_bytes: int
    sha256: str


class ExpertMaskMetadata(BaseModel):
    present: bool = False
    filename: Optional[str] = None
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None


class SpatialSummary(BaseModel):
    shape: List[int]
    spacing_mm: List[float]


class CaseUploadResponse(BaseModel):
    case_id: str
    created_at: str
    files: Dict[str, Any]
    validation_status: str
    spatial_summary: Optional[SpatialSummary] = None
    disclaimer: str = MANDATORY_DISCLAIMER


class CaseValidationResponse(BaseModel):
    case_id: str
    is_valid: bool
    checks: Dict[str, str]
    reference_affine: Optional[List[List[float]]] = None
    error: Optional[str] = None
    disclaimer: str = MANDATORY_DISCLAIMER


class SegmentationTriggerResponse(BaseModel):
    case_id: str
    status: str
    message: str


class CaseStatusResponse(BaseModel):
    case_id: str
    status: str  # queued | processing | completed | failed
    progress_percentage: int = 0
    runtime_seconds: Optional[float] = None
    error: Optional[str] = None
    disclaimer: str = MANDATORY_DISCLAIMER


class BoundingBox(BaseModel):
    min: List[int]
    max: List[int]


class RegionVolume(BaseModel):
    voxel_count: int
    volume_ml: float
    bounding_box_voxel: Optional[BoundingBox] = None


class CaseMetric(BaseModel):
    dice: float
    sensitivity: float


class CaseEvaluation(BaseModel):
    available: bool
    reason: Optional[str] = None
    metrics: Optional[Dict[str, CaseMetric]] = None


class Provenance(BaseModel):
    model_name: str
    model_license: str
    training_data_source: str
    git_commit: Optional[str] = None
    timestamp: str
    input_sha256: Dict[str, str]


class CaseOutputs(BaseModel):
    mask_url: str
    report_url: str


class SpatialMetadata(BaseModel):
    dimensions: List[int]
    voxel_spacing_mm: List[float]
    suggested_crosshair_voxel: Optional[List[int]] = None
    suggested_crosshair_world_mm: Optional[List[float]] = None


class CaseResultsResponse(BaseModel):
    case_id: str
    status: str
    runtime_seconds: Optional[float] = None
    spatial_metadata: SpatialMetadata
    regions: Dict[str, RegionVolume]  # WT, TC, ET
    case_evaluation: Optional[CaseEvaluation] = None
    held_out_benchmark_reference: Optional[Dict[str, Any]] = None
    provenance: Provenance
    outputs: CaseOutputs
    disclaimer: str = MANDATORY_DISCLAIMER


class StandardErrorResponse(BaseModel):
    status: str = "error"
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    disclaimer: str = MANDATORY_DISCLAIMER
