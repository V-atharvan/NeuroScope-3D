# NeuroScope 3D

> **MANDATORY DISCLAIMER:**  
> **Research and teaching prototype only. Not for clinical diagnosis, patient care, or surgical planning.**  
> NeuroScope 3D does not replace qualified radiologists or clinical decision-making. No patient health information (PHI) or real patient scans may be processed without ethics clearance and de-identification.

---

## 1. Product Summary & Problem Statement

Inspecting high-dimensional MRI scans across multiple imaging sequences can make it difficult for medical trainees and imaging researchers to form an accurate mental 3D model of suspected tumour volumes. Calculating tissue sub-region volumes, running AI segmentation, and validating models often require disparate tools and disconnected workflows.

**NeuroScope 3D** provides a unified, web-based platform that:
1. Accepts four co-registered brain MRI sequences (**T1**, **T1Gd / T1CE**, **T2**, and **FLAIR**).
2. Executes a pretrained 3D segmentation model ([MONAI Model Zoo SegResNet](https://github.com/Project-MONAI/model-zoo/tree/dev/models/brats_mri_segmentation)).
3. Maps predicted tumour regions back to the original physical voxel grid and affine space.
4. Visualizes multi-planar slices (Axial, Coronal, Sagittal) and 3D regions using **NiiVue (Option A)** with synchronized crosshair navigation.
5. Computes physical tissue volumes for **Whole Tumour (WT)**, **Tumour Core (TC)**, and **Enhancing Tumour (ET)** in millilitres ($mL$).
6. Evaluates segmentations against an optional uploaded expert mask (Dice Similarity Coefficient & Sensitivity).
7. Exports a verifiable provenance and PDF report (including input SHA-256 hashes, model details, code commit, and disclaimers).

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
- Processing unvetted patient scans.
- Transmitting scan data to external commercial AI APIs or third-party cloud servers.

---

## 3. Repository Layout

```text
NeuroScope-3D/
├── docs/                               # Project requirements and interface specifications
│   ├── PRD_BASE.md                     # Base shared product requirements
│   ├── ARCHITECTURE.md                 # Base system architecture
│   └── API_CONTRACT.md                 # Shared REST API and data contracts
├── backend/                            # FastAPI backend services
│   ├── app/
│   │   ├── main.py                     # FastAPI application entrypoint & CORS
│   │   ├── api/                        # HTTP routes & endpoint definitions
│   │   ├── schemas/                    # Pydantic data models & contracts
│   │   └── services/                   # Validation & orchestration services
│   ├── tests/                          # Backend unit & integration tests
│   └── requirements.txt                # Python dependencies
├── frontend/                           # React + Vite web client
│   ├── src/
│   │   ├── components/                 # Disclaimer banner, header, controls
│   │   ├── pages/                      # Dashboard & study workspace
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
├── .env.example                        # Template environment variables (no secrets)
├── .gitignore                          # Excludes venvs, MRI scans, weights, and caches
├── PRD_BASE.md                         # Root base PRD copy
├── Architecture.md                     # Root architecture document copy
└── README.md                           # This document
```

---

## 4. Setup and Local Development

### Prerequisites
- **Python:** 3.10+ (tested on Python 3.10 - 3.14)
- **Node.js:** v18+ (tested on v26)
- **Git**
- Optional: NVIDIA GPU with CUDA drivers for accelerated PyTorch/MONAI inference.

### 4.1 Backend Setup
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

### 4.2 Frontend Setup
```bash
# In a separate terminal:
cd frontend

# 1. Install dependencies
npm install

# 2. Launch Vite development server
npm run dev
```
The web application is accessible at `http://localhost:5173`.

### 4.3 Running Tests
```bash
# Run backend tests
pytest backend/tests/
```

---

## 5. Contributor Workflow & Branching Conventions

The team is split across four core feature branches working in parallel:

| Branch Name | Primary Scope | Primary Directories |
|---|---|---|
| `feature/ai-pipeline` | Pretrained MONAI bundle integration, channel ordering, inference CLI, BraTS label mapping, affine restoration | `inference/`, `docs/MODEL_CARD.md` |
| `feature/backend` | Multi-sequence upload endpoint, validation service, volume computation ($V = N \times s_x \times s_y \times s_z / 1000$), PDF generation | `backend/`, `reports/` |
| `feature/frontend` | NiiVue viewer integration (Option A), multi-planar slice controls, crosshair sync, 3D mesh rendering, upload UI | `frontend/` |
| `feature/evaluation` | Held-out 10-case evaluation, Dice and sensitivity calculations, slice-removal & orientation invariance tests | `evaluation/` |

### Rules of Engagement
- `main` remains stable, clean, and buildable at all times.
- Never commit raw MRI data (`.nii`, `.nii.gz`), model weights (`.pt`, `.pth`), secrets, or generated reports to Git.
- Keep the research disclaimer visible on all views and reports.
- Resolve any shared contract adjustments in `docs/API_CONTRACT.md` before committing.

---

## 6. Citations & Attribution

1. **BraTS 2021 Dataset:**  
   Baid, U., et al. *The RSNA-ASNR-MICCAI BraTS 2021 Benchmark on Brain Tumor Segmentation and Radiogenomic Classification.* arXiv:2107.02314 (2021). DOI: [10.7937/jc8x-9874](https://doi.org/10.7937/jc8x-9874).
2. **MONAI Model Zoo:**  
   Project MONAI: SegResNet Pre-trained Brain Tumor Segmentation Bundle. [GitHub Repository](https://github.com/Project-MONAI/model-zoo/tree/dev/models/brats_mri_segmentation).
3. **NiiVue:**  
   Rorden, C., et al. NiiVue: WebGL 2.0 medical image viewer. [GitHub Repository](https://github.com/niivue/niivue).
