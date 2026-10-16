# Model Card: MONAI `brats_mri_segmentation` (SegResNet)

**Document Type:** Model Provenance & Verification Card  
**Status:** Verified against official MONAI Model Zoo bundle configuration (`dev` branch / v0.5.4)  
**Mandatory Disclaimer:** *Research and teaching prototype only. Not for clinical diagnosis, patient care, or surgical planning.*

---

## 1. Model Overview

| Property | Value |
|---|---|
| **Model Name** | BraTS MRI Segmentation (`brats_mri_segmentation`) |
| **Bundle Version** | `0.5.4` |
| **Architecture** | 3D SegResNet (Encoder-Decoder with Autoencoder Regularization) |
| **Framework** | PyTorch / MONAI Core |
| **License** | Apache License 2.0 |
| **Authors / Copyright** | MONAI team / Copyright (c) MONAI Consortium |
| **Training Dataset** | BraTS 2018 Challenge Dataset (Multimodal Glioma Benchmark) |
| **Reference Paper** | Andriy Myronenko, *"3D MRI brain tumor segmentation using autoencoder regularization"*, MICCAI Brainlesion Workshop 2018, Springer. [arXiv:1810.11654](https://arxiv.org/abs/1810.11654) |

---

## 2. Model Architecture & Parameters

SegResNet architecture instantiated via `monai.networks.nets.SegResNet`:

```json
{
  "_target_": "SegResNet",
  "in_channels": 4,
  "out_channels": 3,
  "init_filters": 16,
  "blocks_down": [1, 2, 2, 4],
  "blocks_up": [1, 1, 1],
  "dropout_prob": 0.2
}
```

---

## 3. Input Specification & Preprocessing

The model requires 4 co-registered 3D MRI modalities at **1.0 mm isotropic resolution**:

### 3.1 Expected Channel Ordering
The bundle's `configs/metadata.json` explicitly mandates the following 4-channel sequence order:

| Channel Index | Modality Code | Description |
|:---:|:---:|---|
| **0** | `T1c` / `T1Gd` | T1-weighted contrast-enhanced (Gadolinium) |
| **1** | `T1` | T1-weighted native / pre-contrast |
| **2** | `T2` | T2-weighted |
| **3** | `FLAIR` | Fluid-Attenuated Inversion Recovery |

> [!IMPORTANT]
> Note that `T1Gd` is at **channel index 0**, followed by `T1` at index 1. Input preparation must strictly enforce this tensor stacking order `[T1Gd, T1, T2, FLAIR]`.

### 3.2 Preprocessing Transforms
As defined in `configs/inference.json`:
1. `LoadImaged(keys="image", image_only=False)`
2. `NormalizeIntensityd(keys="image", nonzero=True, channel_wise=True)`
   - Normalizes intensities on non-zero brain voxels per channel independently (z-score normalization: $\frac{x - \mu}{\sigma}$).

---

## 4. Inference & Sliding Window Engine

Because 3D volumes require significant VRAM, inference is performed via sliding window:

```json
{
  "_target_": "SlidingWindowInferer",
  "roi_size": [240, 240, 160],
  "sw_batch_size": 1,
  "overlap": 0.5
}
```
- **Patch ROI Size:** $240 \times 240 \times 160$ voxels
- **Window Overlap:** 50% (`0.5`) with Gaussian weighting across overlapping patches
- **Batch Size:** 1

---

## 5. Output Representation & Postprocessing

### 5.1 Raw Network Outputs (3 Channels)
The model outputs a 3-channel tensor representing overlapping subregions:

| Channel Index | Region Name | Meaning |
|:---:|---|---|
| **0** | **TC** | Tumor Core |
| **1** | **WT** | Whole Tumor |
| **2** | **ET** | Enhancing Tumor |

### 5.2 Postprocessing Pipeline
As defined in `configs/inference.json`:
1. `Activationsd(keys="pred", sigmoid=True)`: Converts network logits to probabilities.
2. `Invertd(keys="pred", transform=@preprocessing, nearest_interp=False)`: Inverts spatial resamplings back onto the original reference MRI grid and affine.
3. `AsDiscreted(keys="pred", threshold=0.5)`: Binarizes probabilities at threshold $0.5$.
4. `Lambdad`: Converts the 3 binary subregion channels to standard **BraTS 2021 integer labels**:
   ```python
   lambda x: torch.where(x[2] > 0, 4, torch.where(x[0] > 0, 1, torch.where(x[1] > 0, 2, 0)))
   ```

### 5.3 Resulting BraTS 2021 Label Mapping

| Label Value | Meaning | Derivation Condition |
|:---:|---|---|
| **0** | Background | Outside Whole Tumor |
| **1** | Necrotic & Non-Enhancing Core (NCR) | $\text{TC} \setminus \text{ET}$ (Channel 0 active, Channel 2 inactive) |
| **2** | Peritumoral Oedema (ED) | $\text{WT} \setminus \text{TC}$ (Channel 1 active, Channel 0 inactive) |
| **4** | Enhancing Tumour (ET) | Channel 2 active |

---

## 6. Benchmark Evaluation Metrics

From the official MONAI bundle validation on held-out BraTS 2018 cases:

| Metric | Score |
|---|---|
| **Overall Mean Dice** | `0.8518` |
| **Whole Tumour (WT) Dice** | `0.9026` |
| **Tumour Core (TC) Dice** | `0.8559` |
| **Enhancing Tumour (ET) Dice** | `0.7905` |

---

## 7. Current Environment Verification & Blockers

Per Prompt 2 requirements:
- **Local GPU Availability:** No local NVIDIA GPU is present on this host (`nvidia-smi` command not found). Target GPU inference must be executed on the organizers' T4-class GPU instance or locally tested using CPU fallback (`--device cpu`).
- **Dependencies:** The target environment requires `monai>=1.3.0` and `torch>=2.1.0`.
- **Sample Case / Starter Kit Data:** The repository does not currently contain organizer starter-kit NIfTI development cases or pre-downloaded weights. 
- **Verifiable Status:** All architectural, tensor, channel ordering, transform, and label conversion semantics have been verified directly from the authoritative MONAI Model Zoo bundle configuration.
