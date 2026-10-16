# NeuroScope 3D

> **MANDATORY DISCLAIMER:**  
> **Research and teaching prototype only. Not for clinical diagnosis, patient care, or surgical planning.**  
> NeuroScope 3D does not replace qualified radiologists or clinical decision-making. No patient health information (PHI) or real patient scans may be processed without ethics clearance and de-identification.

---

## 1. Product Summary & Problem Statement

Inspecting high-dimensional MRI scans across multiple imaging sequences can make it difficult for medical trainees and imaging researchers to form an accurate mental 3D model of suspected tumour volumes. Calculating tissue sub-region volumes, running AI segmentation, and validating models often require disparate tools and disconnected workflows.

**NeuroScope 3D** provides a unified, web-based platform that:
1. Accepts four co-registered brain MRI sequences (**T1**, **T1Gd / T1CE**, **T2**, and **FLAIR**) plus an optional expert mask.
2. Executes a pretrained 3D segmentation model ([MONAI Model Zoo SegResNet](https://github.com/Project-MONAI/model-zoo/tree/dev/models/brats_mri_segmentation)).
3. Maps predicted tumour regions back to the original physical voxel grid and affine space.
4. Visualizes multi-planar slices (Axial, Coronal, Sagittal) and 3D regions using **NiiVue (Option A)** with synchronized crosshair navigation.
5. Computes physical tissue volumes for **Whole Tumour (WT)**, **Tumour Core (TC)**, and **Enhancing Tumour (ET)** in millilitres ($mL$).
6. Evaluates segmentations against an optional uploaded expert mask (Dice Similarity Coefficient & Sensitivity).
7. Exports a verifiable provenance and PDF report (including input SHA-256 hashes, model details, code commit, and disclaimers).
8. Protects privacy via local processing, zero external AI APIs, and an automatic 24-hour ephemeral file purge.

---

## 2. Intended Use and Scope

### Intended Users
- Medical-imaging students and trainees.
- Researchers analyzing public, de-identified brain MRI datasets (e.g., BraTS 2021, TCIA).
- Hackathon reviewers evaluating inference pipeline efficiency and visualization fidelity.

### Out of Scope
- Clinical diagnosis or therapeutic recommendations.
- Tumour grading, genetic marker prediction, or prognosis.
- Surgical or radiotherapy planning.
- Processing unvetted patient scans or protected health information (PHI).
- Transmitting scan data to external commercial AI APIs or third-party cloud servers.

---

## 3. Repository Layout

```text
NeuroScope-3D/
├── docs/                               # Architecture, models, reports & checklists
│   ├── PRD_BASE.md                     # Base shared product requirements
│   ├── ARCHITECTURE.md                 # Base system architecture
│   ├── API_CONTRACT.md                 # Shared REST API and data contracts
│   ├── MODEL_CARD.md                   # Pretrained MONAI SegResNet verification card
│   ├── ACCEPTANCE_TEST_REPORT.md       # Audit report across all 15 organizer criteria
│   └── DEMO_SCRIPT.md                  # 5-minute presentation script & viva answers
├── backend/                            # FastAPI backend services
│   ├── app/
│   │   ├── main.py                     # FastAPI application entrypoint & CORS
│   │   ├── api/                        # HTTP routes & endpoint definitions
│   │   ├── schemas/                    # Pydantic data models & contracts
│   │   └── services/                   # Validation, storage, volume & PDF services
│   └── requirements.txt                # Python backend dependencies
├── frontend/                           # React + Vite web client
│   ├── src/
│   │   ├── components/                 # NiiVue viewer, HUD, cards, uploaders
│   │   ├── pages/                      # Dashboard workspace
│   │   ├── services/                   # Backend API client
│   │   ├── App.jsx                     # Top-level application layout
│   │   ├── main.jsx                    # React entrypoint
│   │   └── index.css                   # Medical imaging dark-mode design system
│   ├── index.html                      # HTML shell
│   ├── vite.config.js                  # Vite configuration & API proxy
│   └── package.json                    # Frontend dependencies (NiiVue, Lucide)
├── inference/                          # AI inference pipeline
│   ├── README.md                       # Inference architecture & bundle notes
│   ├── predict.py                      # Standalone CLI and callable pipeline
│   ├── preprocessing.py                # Sequence loading, reorientation, and stacking
│   └── postprocessing.py               # Nesting enforcement and original grid restoration
├── evaluation/                         # Quantitative evaluation & benchmarking
│   ├── README.md                       # Evaluation metrics & edge-case definitions
│   └── evaluate.py                     # Dice & Sensitivity computation
├── reports/                            # Provenance & PDF report generation
│   └── README.md                       # Report layout & retention contract
├── tests/                              # Automated test suite
│   ├── test_acceptance.py              # Full 15-criterion organizer acceptance tests
│   ├── test_backend_api.py             # FastAPI endpoint integration tests
│   ├── test_validation_and_volume.py   # Failure-pack and volume calculation tests
│   ├── test_inference_pipeline.py      # Pre/postprocessing and nesting tests
│   └── test_evaluation_and_reports.py  # Cohort evaluation and PDF generation tests
├── .env.example                        # Template environment variables (no secrets)
├── .gitignore                          # Excludes venvs, MRI scans, weights, and caches
└── README.md                           # This document
```

---

## 4. Setup and Local Development

### Prerequisites
- **Python:** 3.10+ (tested on Python 3.10 - 3.14)
- **Node.js:** v18+ (tested on v20+)
- **Git**
- Optional: NVIDIA GPU with CUDA drivers for accelerated PyTorch/MONAI inference.

### 4.0 One-Command Platform Launcher (Judges & Evaluators)
You can launch both the FastAPI backend (`http://localhost:8000`) and React web workstation (`http://localhost:5173`) concurrently with a single command:
```bash
# Cross-platform Python launcher:
python run_platform.py

# Or on Windows:
run_platform.bat
```

### 4.1 Backend Setup (Manual)
```bash
# 1. Create and activate a Python virtual environment
python -m venv .venv

# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate

# 2. Install backend dependencies
pip install -r backend/requirements.txt

# 3. Copy environment configuration
cp .env.example .env

# 4. Run the FastAPI development server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
The backend API documentation is accessible at `http://localhost:8000/docs`.  
The backend health check is at `http://localhost:8000/api/health`.

### 4.2 Frontend Setup (Manual)
```bash
# In a separate terminal:
cd frontend

# 1. Install dependencies
npm install

# 2. Launch Vite development server
npm run dev
```
The web application is accessible at `http://localhost:5173`.

### 4.3 Standalone Judges' Scorer CLI (`segment.py`)
The platform includes the official standalone runner required by the judges' scoring harness:
```bash
python segment.py \
  --t1 path/to/case_T1.nii.gz \
  --t1gd path/to/case_T1Gd.nii.gz \
  --t2 path/to/case_T2.nii.gz \
  --flair path/to/case_FLAIR.nii.gz \
  --output path/to/predicted_seg.nii.gz
```
Accepts four co-registered sequences, runs the 3D model, and writes predicted integer labels (1 NCR, 2 ED, 4 ET) matching the input grid and affine. If running on GPU, add `--device cuda`.

### 4.4 Running Automated Acceptance & Security Tests
```bash
# Run the complete test suite (all 10 test suites, 100+ tests):
python -m pytest tests/ -v

# Run the storage security & path traversal test suite (Fix 3):
python -m pytest tests/test_storage_security.py -v

# Run the centroid calculation & crosshair synchronization test suite (Fix 2):
python -m pytest tests/test_centroid_crosshair.py -v

# Run the NiiVue segmentation overlay loading test suite (Fix 1):
python -m pytest tests/test_overlay_loading.py -v

# Run the dedicated PDF Report System test suite (all 18 criteria):
python -m pytest tests/test_pdf_report_system.py -v
```

### 4.5 Professional PDF Report Generation & Download
NeuroScope 3D produces a publication-grade, 4-page medical imaging research report for every successfully processed case:

1. **Web UI Flow:**
   - Ingest a multi-sequence study (or click **Load Sample BraTS Study**).
   - Click **Run Segmentation Pipeline**.
   - Upon completion, the **Export & Provenance** panel expands with a live **4-Page Research Report Summary** preview.
   - Click **Export PDF Report** to download the dated document (`neuroscope3d_report_{case_id}_{date}.pdf`).
   - Click **Export BraTS Label NIfTI (.nii.gz)** to download the predicted 3D segmentation mask.

2. **REST API Direct Access:**
   ```bash
   # Download PDF Report (returns application/pdf with Content-Disposition)
   curl -O http://localhost:8000/api/cases/{case_id}/report

   # Download Predicted Label Map (.nii.gz)
   curl -O http://localhost:8000/api/cases/{case_id}/mask
   ```

3. **Report Specifications & Architecture:**
   - **Page 1 — Case Summary & Orthogonal Overlays:** Study header, mandatory disclaimer, multi-planar slice visualizations (Axial, Coronal, Sagittal) extracted at the tumor centroid with translucent subregion overlays, compact volume summary table, and processing duration.
   - **Page 2 — Segmentation & Volumetrics:** BraTS 2021 tissue definitions, strict nesting constraint enforcement ($ET \subseteq TC \subseteq WT$, non-additive rule), physical space volume quantitation table ($mm^3$ and $mL$), 3D spatial bounding boxes, and case-specific expert comparison metrics (DSC & Sensitivity) when ground truth is uploaded.
   - **Page 3 — Model Evaluation & Quality Audit:** Pretrained MONAI SegResNet held-out cohort benchmark metrics (Mean DSC: WT 0.9026, TC 0.8559, ET 0.7905), training overlap disclosure, comprehensive clinical limitations, and 6-point NIfTI geometry validation audit results.
   - **Page 4 — Provenance & Reproducibility:** Cryptographic SHA-256 checksums computed on raw input streams, verified MONAI bundle metadata (v0.5.4, Apache 2.0 License), preprocessing/inference parameters, code commit hash, ISO 8601 UTC timestamp, and ephemeral 24-hour retention notice.
   - **Running Header & Footer:** Every page includes the regulatory header and running footer:  
     `"NeuroScope 3D | Research and Teaching Use Only | Not for Clinical Diagnosis | Page X of 4"`


---

## 5. Environment Configuration

All configuration is driven by standard environment variables (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `0.0.0.0` | Backend API bind host |
| `PORT` | `8000` | Backend API bind port |
| `CORS_ORIGIN` | `http://localhost:5173` | Restricted CORS origin for frontend |
| `STORAGE_DIR` | `./storage/cases` | Local ephemeral workspace root |
| `TEMP_RETENTION_HOURS` | `24` | Automated case purge age threshold |
| `MODEL_WEIGHTS_PATH` | `models/brats_mri_segmentation/models/model.pt` | Path to downloaded MONAI SegResNet weights |
| `DEVICE` | `cuda` | PyTorch compute device (`cuda` or `cpu`) |

---

## 6. Citations & Attribution

1. **BraTS 2021 Benchmark:**  
   Baid, U., et al. *The RSNA-ASNR-MICCAI BraTS 2021 Benchmark on Brain Tumor Segmentation and Radiogenomic Classification.* arXiv:2107.02314 (2021). DOI: [10.7937/jc8x-9874](https://doi.org/10.7937/jc8x-9874).
2. **Medical Segmentation Decathlon (MSD):**  
   Simpson, A.L., et al. *A large annotated medical image dataset for the development and evaluation of segmentation algorithms.* Nature Communications 10, 2636 (2019). DOI: [10.1038/s41467-019-11011-3](https://doi.org/10.1038/s41467-019-11011-3).
3. **SegResNet Architecture:**  
   Myronenko, A. *3D MRI brain tumor segmentation using autoencoder regularization.* Brainlesion: Glioma, Multiple Sclerosis, Stroke and Traumatic Brain Injuries. Springer, Cham, 2018. arXiv: [1810.11654](https://arxiv.org/abs/1810.11654).
4. **MONAI Model Zoo:**  
   Project MONAI: SegResNet Pre-trained Brain Tumor Segmentation Bundle. [GitHub Repository](https://github.com/Project-MONAI/model-zoo/tree/dev/models/brats_mri_segmentation).
5. **NiiVue:**  
   Rorden, C., et al. *NiiVue: WebGL 2.0 medical image viewer.* [GitHub Repository](https://github.com/niivue/niivue).
