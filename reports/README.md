# NeuroScope 3D — Provenance & PDF Reporting (`reports/`)

**Area Owner:** Feature Branch `feature/backend` / Reporting  
**Engine:** Python ReportLab  
**Mandatory Disclaimer:** *Research and teaching prototype only. Not for clinical diagnosis.*

---

## 1. Overview & Contents

The `reports/` module generates the formal case documentation PDF and exports verifiable metadata:

### Mandatory Report Contents:
1. **Header & Disclaimer:** Prominently displays the research and teaching prototype disclaimer and confirms this is not for diagnostic, surgical, or treatment use.
2. **Patient / Case Anonymization:** De-identified Case ID and timestamp.
3. **Region Quantitation:**
   - Whole Tumour (WT) volume in $mL$ and voxel count.
   - Tumour Core (TC) volume in $mL$ and voxel count.
   - Enhancing Tumour (ET) volume in $mL$ and voxel count.
   - Reference physical voxel dimensions ($s_x, s_y, s_z$).
4. **Provenance & Audit Trail:**
   - Pre-trained model name, version, and license (e.g. Apache 2.0).
   - Training dataset provenance and overlap disclosure.
   - SHA-256 hashes of the four input MRI files (T1, T1Gd, T2, FLAIR).
   - Git commit hash of the executing code.
5. **Evaluation Summary:**
   - Case-specific Dice and sensitivity if an expert mask was provided.
   - Benchmark held-out summary reference (clearly labelled as aggregate reference, not patient validation).
6. **Key Slice Snapshots:** (Axial, Sagittal, Coronal views showing segmentation overlay).

---

## 2. Retention Policy
Generated PDF reports in temporary storage are subject to the same strict 24-hour automatic purge policy as MRI uploads.
