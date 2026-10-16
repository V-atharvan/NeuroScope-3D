# NeuroScope 3D — Base Antigravity Prompts

This file contains the **base repository prompts only** for Antigravity. Run them one at a time. Review the changes and test results after each prompt before continuing.

## Project context

NeuroScope 3D is a research-and-teaching web platform that accepts four brain MRI sequences (T1, T1Gd, T2, FLAIR), runs a pretrained 3D segmentation model, visualizes predicted tumour regions, calculates estimated volumes, evaluates predictions against expert masks when available, and generates a provenance-aware report.

**Mandatory disclaimer:** Research and teaching prototype only. Not for clinical diagnosis.

### Agreed technology choices

- AI: MONAI pretrained `brats_mri_segmentation` SegResNet bundle.
- Backend: Python + FastAPI.
- Frontend: React + Vite.
- Medical image visualization: **NiiVue-led approach (Option A)**. Do not add a separate Three.js viewer by default.
- NIfTI handling: NiBabel.
- Array processing: NumPy.
- Image transforms: the exact transforms specified by the selected MONAI bundle.
- Reporting: ReportLab or an equivalent suitable PDF library.
- Testing: pytest and frontend tests as appropriate.

### Provided resources

- BraTS 2021: https://www.med.upenn.edu/cbica/brats2021/
- TCIA BraTS 2021: https://www.cancerimagingarchive.net/analysis-result/rsna-asnr-miccai-brats-2021/
- Medical Segmentation Decathlon: http://medicaldecathlon.com/
- MONAI model bundle: https://github.com/Project-MONAI/model-zoo/tree/dev/models/brats_mri_segmentation
- NiiVue: https://github.com/niivue/niivue

Use the organizer's starter kit and permitted development subset first. Do not download the entire dataset unless there is a demonstrated need. The Medical Segmentation Decathlon is optional; verify its `dataset.json`, label mapping, and channel order before using it.

---

## Prompt 1 — Establish the base repository

```text
Act as a senior software architect and engineering lead. We are building NeuroScope 3D, a 24-hour hackathon product.

Before writing code, read PRD_BASE.md and ARCHITECTURE.md completely. Treat them as the authoritative project requirements. Inspect the current repository and preserve existing work, especially any organizer starter-kit files.

Create the initial repository scaffold, not the entire application.

1. Establish these top-level areas, adapting to any existing starter-kit structure:
   - frontend/
   - backend/
   - inference/
   - evaluation/
   - reports/
   - docs/
2. Preserve the base PRD and architecture documents and place copies in docs/ if needed.
3. Create a .gitignore for virtual environments, node_modules, .env files, caches, uploaded MRI files, expert masks, hidden judge cases, generated case artefacts, temporary reports, and other large/local outputs.
4. Create .env.example with placeholder variable names only. Never include secrets.
5. Create a root README explaining the product, intended use, setup direction, folder structure, and research-only disclaimer.
6. Create a shared API/data-contract document describing upload inputs, segmentation outputs, errors, region volumes, and report downloads.
7. Add minimal backend and frontend scaffolds only where needed. Do not implement fake AI outputs.
8. Keep the scaffold small, easy to understand, and suitable for four contributors working on feature branches.
9. Do not add a database, authentication, external AI API, or separate Three.js viewer unless a documented requirement justifies it.
10. Do not overwrite or discard starter-kit code.

Verify the final tree, check that secrets and research data are not tracked, and list the setup commands. Report created files and unresolved blockers. Do not claim features work unless tested.
```

**Checkpoint:** Review the file tree and make the initial base commit.

---

## Prompt 2 — Verify the MONAI pretrained model

```text
Read PRD_BASE.md, ARCHITECTURE.md, and the shared API contract. Inspect the organizer starter kit first.

Model resource:
https://github.com/Project-MONAI/model-zoo/tree/dev/models/brats_mri_segmentation

Verify the exact bundle version, configuration, weights, licence, preprocessing, postprocessing, expected channel order, output semantics, dependencies, available hardware, and inference runtime.

The referenced bundle expects T1Gd, T1, T2, FLAIR at 1 mm isotropic resolution and predicts TC, WT, and ET. Verify these assumptions against the exact bundle/configuration available in this repository before relying on them.

Run the provided inference example on one permitted development case. Reuse the official bundle and starter-kit code where practical. Record the command used, measured runtime, and observed output shape and meaning. Create docs/MODEL_CARD.md with verified provenance.

Constraints:
- Do not train or fine-tune in this step.
- Do not access, tune on, or retain hidden judge cases.
- Do not use stored dataset images or labels as an inference lookup.
- Do not invent weights, output values, metrics, or licences.
- Do not silently change the bundle's preprocessing.
- Do not claim successful GPU inference unless it actually ran.

If files, weights, hardware, or dependencies are unavailable, report the precise blocker and what is still verifiable. Do not build the frontend around unverified output assumptions.
```

**Checkpoint:** Confirm an actual prediction was generated from a permitted development case.

---

## Prompt 3 — Build the standalone inference pipeline

```text
Read PRD_BASE.md, ARCHITECTURE.md, docs/MODEL_CARD.md, and the verified MONAI bundle configuration.

Implement a standalone Python command that accepts four MRI NIfTI files and writes a predicted BraTS 2021 label-map NIfTI. Reuse the organizer starter kit and official bundle rather than rewriting the model unnecessarily.

Suggested interface (adapt to the existing repository as needed):

python inference/predict.py --t1 case_T1.nii.gz --t1gd case_T1Gd.nii.gz --t2 case_T2.nii.gz --flair case_FLAIR.nii.gz --output predicted_labels.nii.gz

Requirements:
1. Apply the exact preprocessing required by the verified bundle.
2. Run the pretrained model and interpret its actual output channels correctly.
3. Derive WT, TC, and ET masks with consistent nesting: ET ⊆ TC ⊆ WT.
4. Convert the model output into BraTS 2021 tissue labels:
   - 0 = background
   - 1 = NCR
   - 2 = ED
   - 4 = ET
5. Verify the conversion against the model's output semantics and organizer scorer.
6. Map the result back to the original input grid and affine, inverting any required spatial transforms.
7. Use suitable label-preserving interpolation, such as nearest-neighbour, when resampling categorical labels.
8. Validate output shape, affine, orientation, and allowed label values.
9. Provide useful error messages and non-zero exit codes on failure.
10. Keep this pipeline independent of the web application.

Add tests for label conversion, region derivation, and output geometry. Do not blindly flip arrays to fix orientation. Do not fabricate results or use stored-case lookup.

Run the command on a permitted development case and inspect the output. If execution is blocked, report the exact blocker instead of claiming success. Do not proceed to frontend integration until the output format is verified.
```

**Checkpoint:** Run inference twice on the same permitted case and compare the outputs.

---

## Prompt 4 — Implement validation and volume calculation

```text
Read PRD_BASE.md and ARCHITECTURE.md. Implement reusable NIfTI validation and physical-volume calculation services.

Accept .nii and .nii.gz, but validate actual file contents rather than trusting extensions.

Reject with clear errors:
- Non-NIfTI contents or corrupt gzip.
- Missing required MRI sequence.
- 2D rather than 3D images.
- NaN or infinite values.
- Constant volumes, including all-zero data.
- Individual files larger than 1 GB.
- Mismatched image shapes or incompatible spatial affines.
- Invalid optional expert-mask geometry or label values.

Check file size before loading large data. Ensure malformed inputs do not crash the application and never produce a result. For skull-stripping and brain-content sanity checks, use documented conservative heuristics; do not claim simple intensity checks prove anatomical validity.

Calculate derived regions from the final BraTS label map:
- WT = labels {1, 2, 4}
- TC = labels {1, 4}
- ET = label {4}

Use:
volume_mL = voxel_count * spacing_x * spacing_y * spacing_z / 1000

Use the original image's physical voxel spacing, not resampled model-input spacing.

Required test: a 20 x 20 x 20 voxel expert mask containing label 2 with spacing 1 x 1 x 2 mm must report WT = 16.0 mL, TC = 0 mL, ET = 0 mL.

Also test anisotropic spacing, non-cubic volumes, and empty regions. Define empty-mask metric behavior explicitly. Add automated tests and never substitute hardcoded expected values for actual calculations.
```

**Checkpoint:** The cube volume test passes.

---

## Prompt 5 — Build the FastAPI backend

```text
Read PRD_BASE.md, ARCHITECTURE.md, the shared API contract, and the standalone inference pipeline.

Build a FastAPI backend that connects validated uploads to the real inference implementation.

Provide equivalent endpoints for:
- GET /api/health
- POST /api/cases
- GET /api/cases/{case_id}/validate
- POST /api/cases/{case_id}/segment
- GET /api/cases/{case_id}/status
- GET /api/cases/{case_id}/results
- GET /api/cases/{case_id}/mask
- GET /api/cases/{case_id}/report

Route names may be adjusted if the documented functionality and frontend contract remain consistent.

Requirements:
1. Accept four MRI files with explicit sequence assignments and an optional expert mask.
2. Validate before inference.
3. Invoke the actual inference pipeline.
4. Calculate WT, TC, and ET volumes.
5. Return structured JSON metadata and clear errors.
6. Provide binary downloads for the predicted NIfTI and PDF report.
7. Report model readiness and processing status.
8. Use unique temporary case identifiers.
9. Automatically delete uploaded files and generated case artefacts within 24 hours.
10. Never expose uploaded data through a public static directory.
11. Never send scans to external services or language-model APIs.
12. Do not encode full 3D volumes as JSON.
13. Restrict development CORS to the actual frontend origin.
14. Load and reuse model weights when practical.

Use a simple temporary filesystem workflow unless a concrete requirement requires additional infrastructure. Test valid uploads, malformed files, missing sequences, inference failures, downloads, and volume metadata. Update the README with actual launch commands. Never return mock segmentation results as successful inference.
```

**Checkpoint:** The API processes a permitted development case without needing the frontend.

---

## Prompt 6 — Build the React + NiiVue interface

```text
Read PRD_BASE.md, ARCHITECTURE.md, and the shared API contract.

Build the NeuroScope 3D frontend using React + Vite and NiiVue:
https://github.com/niivue/niivue

Use the NiiVue-led visualization decision (Option A). Do not introduce a separate Three.js viewer by default. Verify NiiVue's available volume, overlay, mesh, and interaction capabilities first.

Create a functional, polished research dashboard containing:
1. Four-file MRI uploader for T1, T1Gd, T2, and FLAIR.
2. Optional expert-mask uploader.
3. Validation errors and processing status.
4. Axial, coronal, and sagittal views.
5. Segmentation overlays.
6. 3D brain/region visualization using suitable NiiVue capabilities.
7. WT, TC, and ET visibility controls and opacity controls where supported.
8. Estimated-volume cards.
9. Evaluation and warning panels.
10. NIfTI and PDF download actions.
11. A persistent research-only disclaimer on every screen.

Coordinate requirements:
- Use the NIfTI geometry and affine correctly.
- Maintain a canonical crosshair position.
- Synchronize all slice views and the 3D view.
- Display voxel indices and world coordinates in millimetres.
- Test left/right orientation; never fix it by blindly flipping arrays.

Integration requirements:
- Call the real FastAPI endpoints.
- Show loading states and actual backend errors.
- Do not fabricate segmentation, metrics, or volumes.
- Distinguish unavailable metrics from numeric zero.
- Keep the interface usable and responsive.

Run the frontend and backend together. Upload a permitted development case and verify that the actual model prediction appears. Document any incomplete NiiVue capability honestly instead of simulating it.
```

**Checkpoint:** A real case can be uploaded and its actual prediction viewed.

---

## Prompt 7 — Implement evaluation and PDF reporting

```text
Read PRD_BASE.md, ARCHITECTURE.md, docs/MODEL_CARD.md, and the inference code.

Implement evaluation and report generation from real model outputs and permitted expert annotations.

Evaluation:
1. Calculate Dice and sensitivity separately for WT, TC, and ET.
2. Evaluate at least 10 held-out labelled cases, split by patient/case rather than slice.
3. Record the split and case IDs where allowed by event rules.
4. Disclose known or possible overlap with the pretrained model's training data.
5. Define behavior for empty masks.
6. Clearly distinguish per-case expert-mask comparison from aggregate held-out evaluation.
7. Never invent metrics or imply that general evaluation scores prove an individual prediction is correct.

PDF report:
- Case identifier and timestamp.
- Region voxel counts and estimated volumes.
- Applicable per-case metrics.
- Clearly identified held-out evaluation summary.
- Model name, version, licence, and training-data source.
- Preprocessing details.
- Input SHA-256 hashes.
- Code commit identifier.
- Training/evaluation overlap disclosure.
- Limitations and research-only disclaimer.

Do not claim ten-case evaluation until it has actually been run. Generate a sample report from a real permitted development case, verify the values and confirm that the PDF opens correctly.

Never store hidden judge cases or send scans to external AI services. Ensure temporary files are deleted within 24 hours. Update the model card and README with verified information only.
```

**Checkpoint:** A valid sample PDF is generated and checked.

---

## Prompt 8 — Run the organizer acceptance tests

```text
Read PRD_BASE.md and ARCHITECTURE.md. Audit the integrated application against the acceptance criteria. Do not add optional features until this audit is complete.

Test:
1. Standalone inference creates a valid BraTS 2021 label map.
2. Output preserves the original input grid and affine.
3. WT, TC, and ET are derived correctly.
4. The cube test returns WT 16.0 mL, TC 0 mL, ET 0 mL.
5. The anisotropic slice-removal test meets the organizer's tolerance.
6. Same-anatomy orientation changes preserve the anatomical side.
7. Mirrored anatomy with unchanged affine appears on the opposite side.
8. Linked crosshair positions agree within two voxels.
9. All eight failure-pack cases produce clear errors, no crash, and no result.
10. Repeated inference achieves Dice >= 0.99 for the same case.
11. At least 10 held-out labelled cases have documented metrics.
12. End-to-end runtime meets the two-minute target on the organizer's T4-class GPU.
13. PDF report and model card are correct.
14. The disclaimer is visible throughout the UI and report.
15. Temporary data are deleted within 24 hours.

Run automated tests and the actual inference pipeline. Inspect output headers and labels, test crosshair/orientation behavior, and measure runtime. Fix the highest-impact failures first, then rerun affected tests.

Return a checklist with PASS, FAIL, or BLOCKED and evidence for every item. Never mark an untested requirement as passing. Do not tune on or retain hidden judge cases.
```

**Checkpoint:** Produce a truthful acceptance-test report.

---

## Prompt 9 — Freeze and prepare submission

```text
Read PRD_BASE.md, ARCHITECTURE.md, the current README, and model card.

Prepare NeuroScope 3D for submission without changing the architecture or adding features.

1. Verify that a clean clone can be configured using documented commands.
2. Document frontend and backend startup commands.
3. Document required dependencies and environment variables.
4. Document standalone inference and test commands.
5. Verify model name, version, licence, training data, preprocessing, and limitations in the model card.
6. Cite BraTS 2021 (Baid et al., DOI 10.7937/jc8x-9874) and the Medical Segmentation Decathlon in README if used.
7. Generate and verify one sample report.
8. Ensure no secrets, MRI datasets, hidden cases, or temporary case outputs are committed.
9. Verify temporary-data deletion within 24 hours.
10. Verify the main demonstration uses live inference; any precomputed fallback must be explicitly labelled.
11. Prepare a five-minute demo sequence and likely viva questions.

Do not claim clinical validation or diagnostic capability.

Return the final repository tree, exact commands, test results, known limitations, and a submission-readiness checklist. Only mark requirements ready if they have actually been verified.
```

---

## Prompt 10 — Rules for work on any feature branch

Use this when starting a branch-specific implementation.

```text
Read PRD_BASE.md, ARCHITECTURE.md, the shared API contract, and the PRD assigned to this branch before editing code.

Implement only the responsibilities assigned to this branch, while understanding the complete NeuroScope 3D system.

- Preserve the shared API, region definitions, label conventions, and spatial-coordinate contract.
- Inspect existing code before changing it.
- Do not overwrite another member's work.
- Do not fabricate inference results or evaluation metrics.
- Do not commit MRI data, hidden cases, credentials, or generated case data.
- Add and run tests for your component.
- Commit only related changes.
- Discuss interface changes before implementing them.
- Report changed files, commands run, test results, and unresolved issues.
- Do not merge into main or force-push unless explicitly instructed.

The component must integrate into the shared application, not become a separate prototype.
```

## Execution order

1. Prompt 1 — Base repository.
2. Prompt 2 — Verify the pretrained model.
3. Prompt 3 — Standalone inference.
4. Prompt 4 — Validation and volumes.
5. Prompt 5 — Backend.
6. Prompt 6 — Frontend and NiiVue.
7. Prompt 7 — Evaluation and reporting.
8. Prompt 8 — Acceptance tests.
9. Prompt 9 — Submission freeze.
10. Prompt 10 — Use whenever starting or continuing a feature branch.

**Important:** Once the base repository and API contract exist, frontend and evaluation work can proceed in parallel with inference/backend work. Use clearly marked test fixtures for interface development, but never present fixtures as actual model predictions.
