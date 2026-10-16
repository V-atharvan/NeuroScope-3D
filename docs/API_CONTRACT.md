# NeuroScope 3D — Shared API and Data Contract Specification

**Document Type:** Shared API & System Data Contract  
**Status:** Baseline Specification for Feature Branches  
**Target Audience:** Frontend, Backend, Inference, and Evaluation Engineers  
**Mandatory Disclaimer:** *Research and teaching prototype only. Not for clinical diagnosis.*

---

## 1. Overview & Core Invariants

NeuroScope 3D exposes a RESTful HTTP API paired with binary stream endpoints to support the complete workflow:
1. Multi-sequence MRI upload and validation.
2. Pretrained 3D model segmentation (MONAI SegResNet bundle).
3. Derived region metrics and volume calculations.
4. Quantitative evaluation against optional expert masks.
5. Interactive slice and 3D visualization via NiiVue.
6. Provenance-aware PDF report generation.

### 1.1 Non-Negotiable System Invariants
- **No Diagnostic Claims:** Every payload and view must carry the research-only disclaimer.
- **Original-Grid Preservation:** The output segmentation mask must strictly preserve the spatial geometry (dimensions, voxel spacing, and affine matrix) of the input reference MRI (T1).
- **Binary Transport for Medical Volumes:** Large 3D voxel arrays must **never** be serialized as JSON. NIfTI volumes (`.nii.gz`) must be served as binary streams.
- **24-Hour Lifecycle:** Temporary case directories and generated artefacts must be purged within 24 hours.

---

## 2. Anatomical Labels and Region Definitions

### 2.1 BraTS 2021 Label Mapping
The output segmentation mask NIfTI must contain integer labels adhering strictly to BraTS 2021 convention:

| Label Value | Short Code | Meaning |
|---|---|---|
| `0` | BG | Background / non-tumour tissue |
| `1` | NCR | Necrotic and non-enhancing tumour core |
| `2` | ED | Peritumoral oedema |
| `4` | ET | GD-enhancing tumour |

*(Note: Label 3 is not used in BraTS 2021 convention).*

### 2.2 Derived Clinical Target Regions
Evaluations and volume calculations operate on three composite regions:
- **WT (Whole Tumour):** NCR + ED + ET (Labels `{1, 2, 4}`)
- **TC (Tumour Core):** NCR + ET (Labels `{1, 4}`)
- **ET (Enhancing Tumour):** ET (Label `{4}`)

**Nesting Constraint:** Postprocessing must guarantee `ET ⊆ TC ⊆ WT`.

### 2.3 Physical Volume Calculation
Volume in millilitres ($mL$ or $cm^3$) must be calculated on the **original reference image grid** using its physical voxel spacing:

$$\text{Volume (mL)} = \frac{N \times s_x \times s_y \times s_z}{1000}$$

where:
- $N$ = total count of positive voxels in the region.
- $s_x, s_y, s_z$ = voxel spacing in millimetres along $X, Y, Z$ axes (from NIfTI header `pixdim[1:4]`).

**Verification Cube Criterion:**
A synthetic test volume with $20 \times 20 \times 20$ voxels of Label 2 (ED) at spacing $1.0 \times 1.0 \times 2.0\text{ mm}$ ($8,000\text{ voxels} \times 2\text{ mm}^3 = 16,000\text{ mm}^3$) must produce:
- **WT:** $16.0\text{ mL}$ (within 1%)
- **TC:** $0.0\text{ mL}$
- **ET:** $0.0\text{ mL}$

---

## 3. Endpoints Specification

### 3.1 Health & Readiness Check
- **Route:** `GET /api/health`
- **Description:** Verifies backend operational status, runtime device (CUDA/CPU), model readiness, and Git commit.
- **Success Response (`200 OK`):**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "commit_id": "c1a2b3d",
  "timestamp": "2026-10-16T18:45:00Z",
  "model_readiness": {
    "loaded": false,
    "model_name": "brats_mri_segmentation",
    "device": "cpu"
  },
  "disclaimer": "Research and teaching prototype only. Not for clinical diagnosis."
}
```

---

### 3.2 Case Creation & Multi-Sequence Upload
- **Route:** `POST /api/cases`
- **Content-Type:** `multipart/form-data`
- **Request Fields:**
  - `t1` (file, required): T1-weighted NIfTI (`.nii` or `.nii.gz`).
  - `t1gd` (file, required): T1-contrast enhanced (Gd) NIfTI (`.nii` or `.nii.gz`).
  - `t2` (file, required): T2-weighted NIfTI (`.nii` or `.nii.gz`).
  - `flair` (file, required): FLAIR NIfTI (`.nii` or `.nii.gz`).
  - `expert_mask` (file, optional): Expert segmentation NIfTI (`.nii` or `.nii.gz`) with BraTS 2021 labels `{0, 1, 2, 4}`.
- **Size Limit:** Maximum 1.0 GB per individual file.
- **Success Response (`201 Created`):**
```json
{
  "case_id": "case_9f8b4c2a-7e1d-4033-b411-92b8d96e51c8",
  "created_at": "2026-10-16T18:45:10Z",
  "files": {
    "t1": {"filename": "BraTS2021_00001_t1.nii.gz", "size_bytes": 1420500, "sha256": "e3b0c442..."},
    "t1gd": {"filename": "BraTS2021_00001_t1ce.nii.gz", "size_bytes": 1450200, "sha256": "f5a1c321..."},
    "t2": {"filename": "BraTS2021_00001_t2.nii.gz", "size_bytes": 1390100, "sha256": "a4d2e110..."},
    "flair": {"filename": "BraTS2021_00001_flair.nii.gz", "size_bytes": 1410300, "sha256": "b7c9e884..."},
    "expert_mask": {"present": false}
  },
  "validation_status": "passed",
  "spatial_summary": {
    "shape": [240, 240, 155],
    "spacing_mm": [1.0, 1.0, 1.0]
  },
  "disclaimer": "Research and teaching prototype only. Not for clinical diagnosis."
}
```

---

### 3.3 Validate Case Geometries
- **Route:** `GET /api/cases/{case_id}/validate`
- **Description:** Returns the strict spatial, affine, and data-integrity verification status for the four sequences.
- **Success Response (`200 OK`):**
```json
{
  "case_id": "case_9f8b4c2a-7e1d-4033-b411-92b8d96e51c8",
  "is_valid": true,
  "checks": {
    "nifti_integrity": "passed",
    "finite_values": "passed",
    "non_constant": "passed",
    "shape_matching": "passed",
    "affine_compatibility": "passed",
    "file_size_within_limit": "passed"
  },
  "reference_affine": [
    [-1.0, 0.0, 0.0, 0.0],
    [0.0, -1.0, 0.0, 239.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0, 1.0]
  ],
  "disclaimer": "Research and teaching prototype only. Not for clinical diagnosis."
}
```

---

### 3.4 Execute Segmentation
- **Route:** `POST /api/cases/{case_id}/segment`
- **Description:** Triggers preprocessing, SegResNet model inference, region postprocessing, and original grid restoration.
- **Success Response (`202 Accepted` or `200 OK`):**
```json
{
  "case_id": "case_9f8b4c2a-7e1d-4033-b411-92b8d96e51c8",
  "status": "processing",
  "message": "Segmentation started."
}
```

---

### 3.5 Case Processing Status
- **Route:** `GET /api/cases/{case_id}/status`
- **Success Response (`200 OK`):**
```json
{
  "case_id": "case_9f8b4c2a-7e1d-4033-b411-92b8d96e51c8",
  "status": "completed",
  "progress_percentage": 100,
  "runtime_seconds": 18.4,
  "disclaimer": "Research and teaching prototype only. Not for clinical diagnosis."
}
```

---

### 3.6 Case Results & Quantitation
- **Route:** `GET /api/cases/{case_id}/results`
- **Description:** Provides region volumes, bounding boxes, coordinate anchors, model provenance, and comparison metrics.
- **Success Response (`200 OK`):**
```json
{
  "case_id": "case_9f8b4c2a-7e1d-4033-b411-92b8d96e51c8",
  "status": "completed",
  "runtime_seconds": 18.4,
  "spatial_metadata": {
    "dimensions": [240, 240, 155],
    "voxel_spacing_mm": [1.0, 1.0, 1.0],
    "suggested_crosshair_voxel": [118, 134, 76],
    "suggested_crosshair_world_mm": [-118.0, 105.0, 76.0]
  },
  "regions": {
    "WT": {
      "voxel_count": 48210,
      "volume_ml": 48.21,
      "bounding_box_voxel": {"min": [92, 104, 52], "max": [146, 168, 98]}
    },
    "TC": {
      "voxel_count": 21450,
      "volume_ml": 21.45,
      "bounding_box_voxel": {"min": [98, 112, 60], "max": [138, 154, 90]}
    },
    "ET": {
      "voxel_count": 12300,
      "volume_ml": 12.30,
      "bounding_box_voxel": {"min": [102, 116, 64], "max": [134, 150, 88]}
    }
  },
  "case_evaluation": {
    "available": true,
    "metrics": {
      "WT": {"dice": 0.912, "sensitivity": 0.925},
      "TC": {"dice": 0.884, "sensitivity": 0.891},
      "ET": {"dice": 0.841, "sensitivity": 0.852}
    }
  },
  "held_out_benchmark_reference": {
    "dataset": "BraTS 2021 validation split (10 held-out cases)",
    "mean_dice": {"WT": 0.908, "TC": 0.871, "ET": 0.835},
    "disclaimer": "Held-out benchmark metrics are aggregate population references and do not validate individual patient cases."
  },
  "provenance": {
    "model_name": "MONAI brats_mri_segmentation (SegResNet)",
    "model_license": "Apache 2.0",
    "training_data_source": "BraTS 2018 / 2021 pre-trained bundle",
    "git_commit": "c1a2b3d",
    "timestamp": "2026-10-16T18:45:28Z",
    "input_sha256": {
      "t1": "e3b0c442...",
      "t1gd": "f5a1c321...",
      "t2": "a4d2e110...",
      "flair": "b7c9e884..."
    }
  },
  "outputs": {
    "mask_url": "/api/cases/case_9f8b4c2a-7e1d-4033-b411-92b8d96e51c8/mask",
    "report_url": "/api/cases/case_9f8b4c2a-7e1d-4033-b411-92b8d96e51c8/report"
  },
  "disclaimer": "Research and teaching prototype only. Not for clinical diagnosis."
}
```

---

### 3.7 Binary Segmentation Mask Download
- **Route:** `GET /api/cases/{case_id}/mask`
- **Response Headers:**
  - `Content-Type: application/gzip` (or `application/octet-stream`)
  - `Content-Disposition: attachment; filename="case_{case_id}_seg_brats2021.nii.gz"`
- **Response Body:** Gzipped NIfTI binary byte stream.

---

### 3.8 PDF Report Download
- **Route:** `GET /api/cases/{case_id}/report`
- **Response Headers:**
  - `Content-Type: application/pdf`
  - `Content-Disposition: attachment; filename="case_{case_id}_neuroscope_report.pdf"`
- **Response Body:** Binary PDF document with volumes, provenance, SHA-256 hashes, metrics, and disclaimers.

---

## 4. Standard Error Protocol

When any validation or inference step fails, the API must return a structured JSON error response matching this standard schema:

```json
{
  "status": "error",
  "code": "MISMATCHED_AFFINES",
  "message": "The four MRI sequences do not share compatible spatial geometry. No result was generated.",
  "details": {
    "reference_sequence": "t1",
    "conflicting_sequence": "flair",
    "difference_norm": 0.045,
    "tolerance": 0.001
  },
  "disclaimer": "Research and teaching prototype only. Not for clinical diagnosis."
}
```

### Standard Error Codes:
- `MISSING_SEQUENCE`: One or more required sequences (`t1`, `t1gd`, `t2`, `flair`) were not supplied.
- `INVALID_NIFTI`: File cannot be parsed by NiBabel or has corrupt gzip streams.
- `DIMENSION_MISMATCH_NOT_3D`: Volume is not 3-dimensional (e.g., 2D slice or 4D time series).
- `MISMATCHED_SHAPES`: Input sequences have differing array dimensions.
- `MISMATCHED_AFFINES`: Affine spatial orientation matrices differ beyond tolerance.
- `NON_FINITE_VALUES`: Volume contains `NaN`, `+Inf`, or `-Inf` values.
- `CONSTANT_VOLUME`: Volume is all-zeros or has zero variance (uninformative constant data).
- `FILE_TOO_LARGE`: Individual file exceeded the 1.0 GB limit.
- `SKULL_STRIP_WARNING`: Volume fails sanity checks for skull-stripped brain imaging.
- `MODEL_INFERENCE_ERROR`: Internal exception during PyTorch/MONAI forward pass.
- `CASE_NOT_FOUND`: Case ID does not exist or expired after the 24-hour retention window.
