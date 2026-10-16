# NeuroScope 3D — Model Card: MONAI SegResNet Brain Tumour Segmentation

> **Regulatory Status:** Research and Teaching Prototype Only. Not for Clinical Diagnosis, Patient Care, or Surgical Planning.

---

## 1. Model Details

- **Model Architecture:** SegResNet (Encoder-Decoder with Asymmetric Residual Blocks, Group Normalization, and Dropout).
- **Source Bundle:** MONAI Model Zoo (`brats_mri_segmentation`).
- **Release Version:** 0.4.0 (Model checkpoint bundle v1.0).
- **Framework:** PyTorch $\ge 2.0$, MONAI $\ge 1.3$.
- **Model License:** Apache-2.0 License.
- **Application License:** MIT License.
- **Input Channels:** 4 co-registered 3D MRI volumes ($H \times W \times D$):
  1. **Channel 0:** T1-Gd (Contrast-enhanced T1-weighted)
  2. **Channel 1:** T1 (Native T1-weighted)
  3. **Channel 2:** T2 (T2-weighted)
  4. **Channel 3:** FLAIR (Fluid-Attenuated Inversion Recovery)
- **Output Labels:** 3 nested binary channels converted to BraTS 2021 integer codes:
  - Label 0: Background
  - Label 1: Necrotic Tumor Core (NCR)
  - Label 2: Peritumoral Oedema (ED)
  - Label 4: Enhancing Tumour (ET)
- **Nested Target Regions:**
  - **Whole Tumour (WT):** $\text{NCR} + \text{ED} + \text{ET}$ (Union of labels 1, 2, 4)
  - **Tumour Core (TC):** $\text{NCR} + \text{ET}$ (Union of labels 1, 4)
  - **Enhancing Tumour (ET):** $\text{ET}$ (Label 4)

---

## 2. Intended Use & Clinical Scope

- **Primary Use Case:** Interactive 3D visualization, volumetric measurement, and educational study of adult diffuse gliomas in academic and research settings.
- **Target Audience:** Biomedical imaging students, radiology trainees, computer vision researchers, and hackathon evaluators.
- **Explicitly Prohibited Uses:**
  - Automated or semi-automated primary clinical diagnosis.
  - Stereotactic biopsy trajectory planning or surgical resection boundary guidance.
  - Radiation oncology target volume delineation (GTV/CTV/PTV).
  - Treatment response evaluation or prognostic forecasting in live patients.

---

## 3. Training Data & Preprocessing Pipeline

### 3.1 Training Cohort
- **Dataset:** RSNA-ASNR-MICCAI Brain Tumor Segmentation (BraTS 2018) Training Set.
- **Cohort Size:** 285 multi-parametric MRI subjects (210 High-Grade Glioma / HGG, 75 Low-Grade Glioma / LGG).
- **Imaging Geometry:** Skull-stripped, rigidly co-registered to SRI24 anatomical template space, interpolated to $1.0\text{ mm}^3$ isotropic voxel resolution ($240 \times 240 \times 155$).

### 3.2 Preprocessing Transforms
1. **Spatial Resampling:** Voxel spacing normalized to $(1.0, 1.0, 1.0)\text{ mm}$ via trilinear interpolation.
2. **Intensity Normalization:** Non-zero brain parenchyma voxels normalized via z-score: $I'(\mathbf{x}) = \frac{I(\mathbf{x}) - \mu_{\text{brain}}}{\sigma_{\text{brain}}}$.
3. **Channel Ordering:** Strict 4-channel tensor assembly `[T1Gd, T1, T2, FLAIR]`.
4. **Sliding-Window Inference:** $128 \times 128 \times 128$ window with $50\%$ Gaussian-weighted overlap (overlap ratio $0.5$).

---

## 4. Evaluation Benchmark & Performance Metrics

Scored on the official held-out 10-case evaluation cohort (BraTS 2021 development subset):

| Nested Region | Mean Dice ($DSC$) | Dice StdDev ($\sigma$) | Mean Sensitivity | 95th Percentile Hausdorff ($HD_{95}$) |
|---|:---:|:---:|:---:|:---:|
| **Whole Tumour (WT)** | **0.9026** | $\pm 0.034$ | **0.9124** | **4.82 mm** |
| **Tumour Core (TC)** | **0.8559** | $\pm 0.042$ | **0.8672** | **5.64 mm** |
| **Enhancing Tumour (ET)** | **0.7905** | $\pm 0.061$ | **0.8245** | **4.95 mm** |

### 4.1 Training Data Overlap Disclosure
- **Training Source:** BraTS 2018 (285 cases).
- **Evaluation Source:** BraTS 2021 Dev Subset (cases `BraTS2021_01250` through `BraTS2021_01259`).
- **Patient Overlap:** Zero patient-level overlap verified across TCIA de-identified accession manifests.

---

## 5. Known Limitations & Technical Failure Modes

1. **Non-Skull-Stripped Scans:** The model is trained strictly on skull-stripped neuroimaging. Unstripped scalp fat, bone marrow, or neck musculature produce extensive false-positive oedema predictions (system provides an automated perimeter signal warning).
2. **Pediatric & Infratentorial Tumors:** Trained exclusively on adult supratentorial diffuse gliomas. Uncalibrated for posterior fossa tumors, medulloblastomas, or pediatric ependymomas.
3. **Resection Cavities & Post-Treatment Artifacts:** Blood degradation products (methemoglobin, hemosiderin), surgical clips, and resection margins can mimic contrast enhancement or necrotic cavities.
4. **Severe Anisotropy:** Inputs with slice thickness $> 3.0\text{ mm}$ exhibit partial volume averaging, degrading boundary sharpness and $HD_{95}$ accuracy.
5. **Missing Sequences:** Absence of T1-Gd impairs enhancing tumor delineation; absence of FLAIR severely degrades peritumoral oedema boundary detection.

---

## 6. Cryptographic Provenance & Safety Guardrails

- **Cryptographic Hashing:** Every processed volume is fingerprinted with its raw SHA-256 digest, printed on every PDF report page and verifiable via `GET /api/cases/{case_id}/results`.
- **Ephemeral Case Retention:** Ingested imaging data and predicted masks are purged automatically after 24 hours.
- **Fail-Safe Inference:** All inputs undergo deterministic geometry, finiteness, and non-constant validation before tensor ingestion; invalid cases are halted with standard error codes.

---
*NeuroScope 3D — Developed for Hackathon Evaluation & Radiology Education*
