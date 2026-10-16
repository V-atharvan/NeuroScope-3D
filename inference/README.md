# NeuroScope 3D — Inference Pipeline (`inference/`)

**Area Owner:** Feature Branch `feature/ai-pipeline`  
**Base Model:** MONAI Model Zoo `brats_mri_segmentation` SegResNet Bundle  
**Mandatory Disclaimer:** *Research and teaching prototype only. Not for clinical diagnosis.*

---

## 1. Responsibilities

The `inference/` module manages:
1. Loading the pre-trained SegResNet MONAI bundle once into memory.
2. Channel ordering: Verify bundle requirements (expected order: `T1Gd`, `T1`, `T2`, `FLAIR`).
3. Running model forward pass with sliding window inference.
4. Output postprocessing: Enforce logical nesting (`ET ⊆ TC ⊆ WT`).
5. Conversion of model output to standard BraTS 2021 tissue labels:
   - `0`: Background
   - `1`: NCR (Necrotic core)
   - `2`: ED (Peritumoral oedema)
   - `4`: ET (Enhancing tumour)
6. Spatial restoration: Invert spatial transforms and project segmentation back onto the reference image's original grid, shape, and affine matrix.
7. Standalone CLI & callable python interface.

---

## 2. File Organization

- `predict.py`: CLI and python entrypoint accepting four NIfTI sequence paths and writing a valid BraTS 2021 NIfTI mask.
- `preprocessing.py`: Multi-modal volume stacking, resampling, and intensity normalization following bundle specification.
- `postprocessing.py`: Nesting enforcement, label mapping, and inverse spatial transformation back to original grid.

---

## 3. CLI Contract

When implemented on `feature/ai-pipeline`, the standalone script will be invoked as:

```bash
python -m inference.predict \
  --t1 /path/to/t1.nii.gz \
  --t1gd /path/to/t1ce.nii.gz \
  --t2 /path/to/t2.nii.gz \
  --flair /path/to/flair.nii.gz \
  --output /path/to/output_seg_brats2021.nii.gz \
  --device cuda
```
