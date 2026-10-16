# NeuroScope 3D --- Base System Architecture

**Document type:** Shared architecture baseline\
**Status:** Initial architecture for a 24-hour hackathon prototype\
**Visualization decision:** NiiVue-led (Option A)\
**Primary model candidate:** MONAI `brats_mri_segmentation` SegResNet
bundle

## 1. Architecture goals

The architecture must support a complete, reproducible path from four
MRI files to: - Validated inputs. - Predicted BraTS 2021 segmentation. -
Original-grid NIfTI output. - Interactive 3D and linked slice
visualization. - Estimated WT, TC, and ET volumes. - Evaluation against
expert masks where available. - A provenance-aware PDF report.

The architecture prioritizes correct medical-image geometry, safe
failure, and judge-test compatibility over unnecessary infrastructure.

## 2. System context

``` text
Research/teaching user
        |
        v
React + Vite web application
        |
        | HTTP API / binary downloads
        v
FastAPI backend
        |
        +--> Upload validation and temporary storage
        |
        +--> Medical image geometry / preprocessing
        |             |
        |             v
        |       MONAI + PyTorch inference
        |             |
        |             v
        |       Region postprocessing
        |             |
        |             v
        |       BraTS label conversion
        |             |
        |             v
        |       Restore original grid/affine
        |
        +--> Volume calculation
        |
        +--> Expert-mask comparison / evaluation
        |
        +--> Report generation
        |
        v
JSON metadata + NIfTI output + PDF report
        |
        v
NiiVue-led browser visualization
```

NiiVue is the primary medical-imaging viewer. Use its volume and
mesh/overlay capabilities where feasible. Do not add a separate Three.js
visualization stack by default; only revisit that choice if a mandatory
3D interaction cannot be satisfied with NiiVue.

## 3. Recommended technology choices

  -----------------------------------------------------------------------
  Concern                 Technology              Notes
  ----------------------- ----------------------- -----------------------
  Web application         React + Vite            Main user interface

  Medical-image viewer    NiiVue                  MRI volume, slice
                                                  planes, overlays, and
                                                  available mesh
                                                  capabilities

  Backend API             FastAPI                 Uploads, orchestration,
                                                  results, downloads

  Inference               PyTorch + MONAI         Pretrained SegResNet
                                                  bundle

  NIfTI handling          NiBabel                 Image data, header,
                                                  affine, output

  Array processing        NumPy                   Masks, counts, metrics

  Image transforms        MONAI transforms;       Follow bundle
                          compatible              configuration
                          medical-image tooling   
                          if needed               

  Surface extraction      scikit-image or         Only if required for 3D
                          compatible method       surface generation

  PDF report              ReportLab               Report output

  Testing                 pytest                  Unit and integration
                                                  tests

  Version control         Git + GitHub            Feature branches and
                                                  reviewed merges
  -----------------------------------------------------------------------

Do not add a database, authentication service, external storage, or
external AI API unless a concrete requirement demands it. For this
short-lived prototype, temporary filesystem storage is sufficient if
implemented safely.

## 4. Repository layout

``` text
neuroscope-3d/
â”œâ”€â”€ frontend/
â”‚   â”œâ”€â”€ src/
â”‚   â”‚   â”œâ”€â”€ components/
â”‚   â”‚   â”œâ”€â”€ pages/
â”‚   â”‚   â”œâ”€â”€ services/
â”‚   â”‚   â””â”€â”€ App.jsx
â”‚   â””â”€â”€ package.json
â”œâ”€â”€ backend/
â”‚   â”œâ”€â”€ app/
â”‚   â”‚   â”œâ”€â”€ main.py
â”‚   â”‚   â”œâ”€â”€ api/
â”‚   â”‚   â”œâ”€â”€ schemas/
â”‚   â”‚   â””â”€â”€ services/
â”‚   â”œâ”€â”€ tests/
â”‚   â””â”€â”€ requirements.txt
â”œâ”€â”€ inference/
â”‚   â”œâ”€â”€ predict.py
â”‚   â”œâ”€â”€ preprocessing.py
â”‚   â”œâ”€â”€ postprocessing.py
â”‚   â””â”€â”€ README.md
â”œâ”€â”€ evaluation/
â”‚   â”œâ”€â”€ evaluate.py
â”‚   â””â”€â”€ README.md
â”œâ”€â”€ reports/
â”‚   â””â”€â”€ README.md
â”œâ”€â”€ docs/
â”‚   â”œâ”€â”€ PRD_BASE.md
â”‚   â”œâ”€â”€ ARCHITECTURE.md
â”‚   â””â”€â”€ MODEL_CARD.md
â”œâ”€â”€ .env.example
â”œâ”€â”€ .gitignore
â”œâ”€â”€ README.md
â””â”€â”€ pyproject.toml or requirements files
```

This is a target layout. If the organizer starter kit already has an
inference layout, preserve and integrate it instead of copying or
rewriting the model bundle unnecessarily.

## 5. Core data flow

### 5.1 Upload and validation

1.  Receive four files and explicit sequence assignments.
2.  Enforce the per-file size limit before loading.
3.  Validate actual NIfTI contents and gzip integrity.
4.  Load headers and arrays safely.
5.  Check 3D shape, finite values, and non-constant intensities.
6.  Compare all four shapes and spatial affines.
7.  Check optional mask shape, affine, and allowed label values.
8.  Return a clear error and stop if validation fails.

Do not treat filename extensions as proof of file format. Do not show
results after a failed validation.

### 5.2 Preprocessing

1.  Load the four sequences with their spatial metadata.
2.  Apply the exact preprocessing expected by the selected MONAI bundle.
3.  Verify the expected channel order (for the referenced bundle, T1Gd,
    T1, T2, FLAIR; confirm in the exact version/configuration).
4.  Resample/reorient only as required by the bundle.
5.  Retain the transformations needed to map predictions back to the
    original grid.

### 5.3 Inference

1.  Load the model once where practical.
2.  Run inference with appropriate inference mode and device.
3.  Apply the bundle's documented postprocessing.
4.  Determine whether outputs represent nested regions or class labels.
5.  Convert the output to WT, TC, ET masks.
6.  Enforce/document region nesting as appropriate.
7.  Convert regions to BraTS 2021 tissue labels.

For nested region masks: - WT = whole tumour. - TC = tumour core. - ET =
enhancing tumour. - Expected nesting: ET âŠ† TC âŠ† WT.

One valid conversion after consistent postprocessing is: - ET voxels â†’
label 4. - TC but not ET â†’ label 1. - WT but not TC â†’ label 2. - Outside
WT â†’ label 0.

Verify this against the actual model's output semantics and starter-kit
scorer.

### 5.4 Restore the original grid and write output

1.  Invert preprocessing spatial transforms.
2.  Resample categorical labels using an appropriate label-preserving
    method such as nearest-neighbour interpolation.
3.  Write NIfTI using the original reference image's shape and affine.
4.  Validate output shape, affine, orientation, and label set.
5.  Expose output through a CLI and API independently of the frontend.

Do not assume that equal array dimensions imply correct spatial
alignment.

### 5.5 Measurements

For each derived region, count voxels on the final/original grid.

`volume_mL = voxel_count Ã— spacing_x Ã— spacing_y Ã— spacing_z / 1000`

Use the original image's physical voxel spacing for reported volume.
Show the formula and numbers in the UI/report.

Required test: 8,000 label-2 voxels at spacing 1 Ã— 1 Ã— 2 mm produce WT
16 mL, TC 0 mL, ET 0 mL.

### 5.6 Evaluation

-   Calculate Dice and sensitivity separately for WT, TC, ET.
-   Use at least ten held-out labelled cases.
-   Split by patient/case.
-   Record the split and case identifiers as permitted.
-   Disclose known or possible training/evaluation overlap.
-   Clearly distinguish case-specific expert-mask comparison from
    aggregate held-out evaluation.
-   Define empty-ground-truth and empty-prediction behavior explicitly.

### 5.7 Visualization

-   NiiVue is the primary viewer.
-   Display original MRI volumes and segmentation overlays in axial,
    coronal, and sagittal views.
-   Keep a canonical crosshair position and update it across views.
-   Display voxel indices and world coordinates.
-   Display the predicted 3D regions using NiiVue-supported volume/mesh
    functionality where feasible.
-   Ensure all transforms use the image affine and a consistent
    coordinate convention.
-   Region visibility and opacity controls should operate on the
    corresponding mask/mesh.
-   The persistent disclaimer must remain visible.

### 5.8 Report

Generate a PDF containing: - Region volumes and voxel counts. -
Applicable per-case comparison metrics. - Clearly labelled held-out
evaluation summary. - Model/version/licence/training data. -
Preprocessing. - Input SHA-256 hashes. - Code commit and timestamp. -
Limitations and research-only disclaimer.

## 6. API contract baseline

Exact route naming may be adjusted during implementation, but the
frontend and backend must agree on the contract before parallel
development.

  ----------------------------------------------------------------------------------
  Endpoint                          Method                  Purpose
  --------------------------------- ----------------------- ------------------------
  `/api/health`                     GET                     Backend and model
                                                            readiness

  `/api/cases`                      POST                    Upload four sequences
                                                            and optional expert mask

  `/api/cases/{case_id}/validate`   GET                     Validation result

  `/api/cases/{case_id}/segment`    POST                    Run inference

  `/api/cases/{case_id}/status`     GET                     Processing status

  `/api/cases/{case_id}/results`    GET                     Volumes, metadata,
                                                            metrics,
                                                            coordinates/provenance

  `/api/cases/{case_id}/mask`       GET                     Download predicted NIfTI

  `/api/cases/{case_id}/report`     GET                     Download PDF report
  ----------------------------------------------------------------------------------

A synchronous inference endpoint may be adequate for local development,
but the API should expose status cleanly if inference runs
asynchronously. Do not build a complex job queue unless the actual
runtime requires it.

### Result schema example

``` json
{
  "case_id": "temporary-id",
  "status": "completed",
  "regions": {
    "WT": {"voxel_count": 0, "volume_ml": 0.0},
    "TC": {"voxel_count": 0, "volume_ml": 0.0},
    "ET": {"voxel_count": 0, "volume_ml": 0.0}
  },
  "evaluation": {
    "available": false,
    "reason": "Expert mask not supplied"
  },
  "outputs": {
    "label_map_available": true,
    "report_available": true
  },
  "disclaimer": "Research and teaching prototype only. Not for clinical diagnosis."
}
```

This is a schema example, not a prediction. Actual values must be
computed from the case.

## 7. Spatial correctness rules

Spatial correctness is a system-wide invariant.

-   The four inputs must be spatially compatible.
-   Any reorientation/resampling must be recorded and reversible.
-   The final segmentation must be on the original input grid and
    affine.
-   The displayed overlays must align with the original MRI.
-   Crosshair position must represent the same physical location in all
    views.
-   The same-anatomy left-right storage-flip test must preserve
    anatomical side.
-   The unchanged-affine mirrored-anatomy test must show the anatomy on
    the opposite side.
-   Volume must use original-grid voxel spacing.

Do not fix orientation bugs by blindly flipping arrays. Use NIfTI affine
and orientation transforms.

## 8. Error handling and temporary storage

Use a clear error schema, for example:

``` json
{
  "status": "error",
  "code": "MISMATCHED_AFFINES",
  "message": "The four MRI sequences do not share compatible spatial geometry. No result was generated."
}
```

Expected error classes include: - Invalid NIfTI content. - Corrupt
gzip. - Missing sequence. - Mismatched shapes. - Mismatched affines. -
2D input. - Constant volume. - NaN or infinite values. - File too
large. - Unsupported or clearly unsuitable input. - Model
loading/inference failure.

Temporary case files and generated artefacts must be deleted within 24
hours. Never store uploads in a public static directory. Never send
scans to third-party APIs. Do not commit inputs, hidden cases, model
outputs, or secrets.

## 9. Model and data provenance

Record at minimum: - Model bundle name/version. - Licence. -
Training-data source. - Preprocessing configuration/version. - Input
SHA-256 hashes. - Code commit identifier. - Timestamp. - Evaluation
dataset split. - Known or possible training/evaluation overlap.

The referenced MONAI bundle is documented as trained on BraTS 2018.
Verify the exact bundle metadata and licence used in the actual build.

## 10. Performance and resource assumptions

-   Target end-to-end time: â‰¤ 2 minutes per case on the organizers'
    T4-class GPU.
-   Development hardware may differ; benchmark early.
-   Keep model weights out of Git unless there is a specific approved
    reason.
-   Load model weights once when possible.
-   Avoid sending full 3D arrays as JSON.
-   Transfer NIfTI/volume data using binary responses or supported
    viewer loading paths.
-   Use the supplied starter kit before creating custom inference code.
-   A precomputed example may only be a clearly labelled backup; primary
    demonstration must run live inference.

## 11. Testing strategy

### Unit tests

-   Input validation.
-   BraTS label conversion.
-   Region derivation.
-   Volume formula.
-   Metric calculations.
-   Output label set and affine preservation.
-   Report metadata generation.

### Integration tests

-   Valid case upload â†’ inference â†’ output NIfTI.
-   Valid case upload â†’ volume metadata.
-   Optional expert mask â†’ comparison metrics.
-   Results â†’ viewer loading.
-   Results â†’ report download.
-   Temporary-data cleanup.

### Organizer test pack

-   Non-NIfTI file named `.nii.gz`.
-   Corrupt gzip.
-   Only three sequences.
-   Mismatched shapes.
-   2D image.
-   All-zero volume.
-   NaN values.
-   File larger than 1 GB.
-   Cube volume test.
-   Anisotropic slice-removal test.
-   Same-anatomy orientation test.
-   Mirrored-anatomy test.
-   Linked crosshair test.
-   Reproducibility test.
-   Skull-stripping/input-sanity test.

## 12. Development and Git conventions

Recommended branches: - `main` --- stable integration branch. -
`feature/ai-pipeline` - `feature/backend` - `feature/frontend` -
`feature/evaluation`

The initial base commit should establish the folders, shared contracts,
`.gitignore`, documentation, and minimal health/scaffold functionality.
Feature branches should implement their assigned components without
changing shared contracts unilaterally.

Rules: - Small meaningful commits. - Push branches regularly. - Merge
via pull request or brief review. - Integrate early. - Update feature
branches from `main` regularly. - Resolve contract changes with the team
before merging. - Do not force-push shared branches.

## 13. Definition of done

The integrated product is ready when: - Standalone inference outputs
valid BraTS 2021 labels on the original grid/affine. - Upload validation
and all failure cases behave correctly. - Volume and orientation tests
pass. - Linked slice views and crosshair are spatially consistent. -
Held-out metrics are actually computed and documented. - Reproducibility
and runtime targets are tested. - PDF report, model card, and README are
complete. - Disclaimer is visible throughout the UI and in the report. -
Temporary files are deleted within 24 hours. - A clean clone can be set
up using the README.