# NeuroScope 3D — 5-Minute Demonstration Script & Viva Preparation

> **MANDATORY DISCLAIMER:**  
> **Research and teaching prototype only. Not for clinical diagnosis, patient care, or surgical planning.**  
> NeuroScope 3D does not replace qualified radiologists or clinical decision-making. No patient health information (PHI) or real patient scans may be processed without ethics clearance and de-identification.

---

## 1. 5-Minute Live Demonstration Sequence

| Timestamp | Phase | Key Actions & Narrative | On-Screen Elements |
|---|---|---|---|
| **0:00 – 1:00** | **Introduction & Problem Scope** | • Welcome judges and state core purpose: high-dimensional multimodal MRI is difficult for trainees to mentally reconstruct into 3D subregions.<br>• Highlight the **Mandatory Disclaimer** prominently rendered across the interface.<br>• Introduce the input modalities: **T1, T1Gd, T2, FLAIR** and BraTS 2021 subregions (**WT, TC, ET**). | Disclaimer banner at top, header showing backend status, clean dark-mode dashboard. |
| **1:00 – 2:00** | **Input Ingestion & Robustness Engine** | • Demonstrate drag-and-drop file ingestion.<br>• Highlight the **Validation Service** (Failure Pack): explain how corrupted headers, mismatched affines, 2D slices, or all-zero arrays are rejected immediately before touching the GPU.<br>• Point out that the system checks file size (< 1 GB) before loading to prevent DoS. | `UploadPanel`: sequence status badges, file selection, client-side sequence assignment. |
| **2:00 – 3:15** | **Live Inference & Multi-Planar NiiVue Visualization** | • Trigger live inference via MONAI SegResNet.<br>• Explain the pipeline: channel stacking `[T1Gd, T1, T2, FLAIR]`, non-zero intensity normalization, sliding-window inferer.<br>• Show multi-planar viewer (Axial, Coronal, Sagittal) and 3D volume view.<br>• Click around to show **synchronized crosshair navigation** with world coordinates ($mm$) and voxel indices.<br>• Toggle individual region layers (WT, TC, ET) and adjust opacity. | `NiiVueViewer`: synchronized 4-view layout (Axial, Coronal, Sagittal, 3D), HUD crosshair overlay, layer toggles. |
| **3:15 – 4:15** | **Volumetric Rigor & Physical Spacing** | • Present the **Volumetric Summary Cards**: WT, TC, ET in millilitres ($mL$).<br>• Explain mathematical formulation: $\text{Volume} = N \times s_x \times s_y \times s_z / 1000$ using the *original* voxel grid spacing, not resampled model space.<br>• Mention the organizer cube benchmark ($20 \times 20 \times 20$ voxels of label 2 at $1 \times 1 \times 2\text{ mm} = 16.0\text{ mL}$).<br>• Show the "Jump to Centroid" action centering the crosshair on the lesion bounding box. | `VolumetricCards`: color-coded cards for WT (yellow), TC (red), ET (cyan) with voxel count and physical $mL$. |
| **4:15 – 5:00** | **Evaluation, Auditing & PDF Export** | • Demonstrate quantitative evaluation against an optional expert mask: per-region Dice and Sensitivity.<br>• Contrast per-case metrics against the 10-case held-out benchmark reference.<br>• Download the complete **Provenance PDF Report** and open it: showcase input SHA-256 hashes, model card provenance, git commit ID, and disclaimer.<br>• Highlight data privacy: **zero external AI APIs**, private ephemeral case workspace, and **automatic 24-hour purge**. | `EvaluationPanel`, `DownloadsPanel`, generated PDF with full audit trail. |

---

## 2. Likely Viva & Reviewer Questions (with Authoritative Answers)

### Q1: Why did you choose SegResNet over standard 3D UNet or Swin UNETR?
> **Answer:**  
> The pretrained MONAI SegResNet (`brats_mri_segmentation` v0.5.4) offers an optimal balance between segmentation accuracy (0.852 mean Dice on BraTS) and memory efficiency. Its encoder-decoder architecture with autoencoder regularization acts as an auxiliary task that prevents overfitting on small medical cohorts while running comfortably within sliding-window inference on standard T4 GPU memory constraints.

### Q2: Why can't you just perform `argmax` across the network output channels?
> **Answer:**  
> The BraTS subregions are hierarchical and overlapping, not mutually exclusive:  
> - **Whole Tumour (WT)** includes all tumour tissue (labels 1, 2, 4).  
> - **Tumour Core (TC)** includes necrotic core and active enhancing tumour (labels 1, 4).  
> - **Enhancing Tumour (ET)** is the active rim (label 4).  
> The model outputs 3 sigmoid probability channels (`[TC, WT, ET]`). We apply sigmoid thresholding ($> 0.5$) and strictly enforce nesting: $ET \subseteq TC \subseteq WT$. We then map:  
> - Label 4 (ET) where $ET > 0$  
> - Label 1 (NCR) where $TC > 0$ and $ET = 0$  
> - Label 2 (ED) where $WT > 0$ and $TC = 0$  
> Running `argmax` across channels would destroy the hierarchical nesting and produce invalid topological regions.

### Q3: How do you guarantee anatomical orientation without blindly flipping arrays?
> **Answer:**  
> We preserve the original reference image's spatial affine matrix throughout the entire inference lifecycle. Resampling and grid restoration use the exact spatial affine transformation with nearest-neighbour interpolation for categorical labels. When presenting coordinates in NiiVue, we report world coordinates in millimetres directly from the affine transform. In acceptance tests (Criteria 6 & 7), we verified that lateralized lesions remain lateralized, and mirrored anatomy without affine modification appropriately shifts across the sagittal midline.

### Q4: How does your system handle corrupted or adversarial inputs (Failure Pack)?
> **Answer:**  
> We implemented a dedicated validation service (`backend/app/services/validation.py`) that audits uploads *before* any model execution:  
> 1. Verifies actual file content (not just file extensions).  
> 2. Rejects files $> 1\text{ GB}$ before loading into RAM.  
> 3. Catches corrupt gzip archives and non-NIfTI files.  
> 4. Enforces 3D dimensions (rejecting 2D slices).  
> 5. Rejects volumes with NaNs, Infs, or constant/all-zero intensities.  
> 6. Validates that all four sequences have identical matrix dimensions and compatible affines.  
> All 8 failure-pack cases raise structured HTTP 400/422 errors with clean error codes, never crashing the server or producing phantom predictions.

### Q5: How do you handle patient data privacy and HIPAA/GDPR concerns?
> **Answer:**  
> 1. **No External APIs:** Scans never leave the local deployment environment. We never call external commercial AI or LLM APIs.  
> 2. **No Persistent Database:** We do not maintain a SQL or NoSQL database linking user identities to scans.  
> 3. **Isolated Ephemeral Storage:** Each upload is assigned a cryptographically random UUID (`case_{uuid}`) in a non-public filesystem directory.  
> 4. **Automatic 24-Hour Purge:** Case workspaces older than 24 hours are automatically purged on routine maintenance and health check intervals (`cleanup_expired_cases()`).

### Q6: What are the primary limitations of this prototype?
> **Answer:**  
> As documented in `docs/MODEL_CARD.md`:  
> - The model was trained on high-grade and low-grade gliomas in adults; it is **not** validated for pediatric brain tumours, meningiomas, brain metastases, or non-neoplastic pathologies.  
> - Input scans must be skull-stripped and rigidly co-registered across all four sequences.  
> - Inference runtime on CPU is slow (~3–5 minutes), requiring a dedicated NVIDIA GPU (e.g. T4/A10G) for the sub-two-minute target.  
> - It is strictly a **research and teaching prototype**, never for clinical diagnosis.
