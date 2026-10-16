# NeuroScope 3D --- Base Product Requirements Document (PRD)

**Document type:** Base / shared project PRD\
**Status:** Initial baseline for the hackathon\
**Project duration:** 24 hours\
**Product category:** Health-tech research and teaching prototype\
**Audience:** All four contributors, AI coding agents, reviewers, and
judges

## 1. Purpose of this document

This is the shared source of truth for the entire NeuroScope 3D project.
Every contributor-specific PRD must refer to this document and preserve
the overall product goals, architecture, interfaces, constraints, and
acceptance criteria.

This base PRD describes: 1. The complete product we are building. 2. The
system-wide requirements and restrictions. 3. What the initial base
commit/repository scaffold must establish. 4. The contracts that
individual feature branches must follow.

It does **not** assign detailed implementation tasks to individual
members. Separate member PRDs will define each branch's scope while
retaining this complete system context.

## 2. Product summary

NeuroScope 3D is a browser-based research and teaching platform that
accepts four co-registered brain MRI sequences---T1, T1Gd, T2, and
FLAIR---runs a pretrained 3D segmentation model, and presents the
model-predicted suspected tumour regions in linked 2D and 3D views.

The platform calculates estimated volumes for Whole Tumour (WT), Tumour
Core (TC), and Enhancing Tumour (ET); optionally compares predictions
with an uploaded expert mask; reports held-out model-evaluation metrics;
and generates a report with provenance and limitations.

**This is not a diagnostic product.** It must never claim to diagnose a
tumour, replace a radiologist, or support treatment or surgical
planning.

## 3. Problem statement

Inspecting numerous MRI slices across multiple sequences can make it
difficult for trainees and researchers to build a mental 3D
understanding of a suspected tumour region. Segmentation, volume
calculation, visualization, and model evaluation may require separate
tools or workflows.

NeuroScope 3D brings these tasks into one workflow: upload and validate
a study, run AI segmentation, inspect the predicted regions in 3D and
linked slices, calculate estimated volumes, review applicable evaluation
metrics, and export results.

The product does not invent a new segmentation model; it integrates a
permitted pretrained model into a robust and transparent workflow.

## 4. Target users and intended use

### Intended users

-   Medical-imaging students and trainees.
-   Researchers working with permitted public, de-identified brain MRI
    datasets.
-   Hackathon judges evaluating the inference pipeline and viewer.

### Intended use

Research, education, visualization, software demonstration, and
quantitative evaluation on permitted research data only.

### Out of scope

-   Diagnosis or clinical decision support.
-   Tumour grading, genetic prediction, prognosis, or treatment
    recommendations.
-   Surgical or radiotherapy planning.
-   Clinical-validation or regulatory claims.
-   Processing real patient scans during the event.
-   Sending MRI data to third-party services or language-model APIs.

## 5. Required user workflow

1.  User uploads four NIfTI files and assigns each to T1, T1Gd, T2, or
    FLAIR.
2.  User may optionally upload an expert segmentation mask using BraTS
    2021 labels.
3.  Backend validates each file and verifies that the four sequences are
    spatially compatible.
4.  Valid inputs are preprocessed according to the selected model
    bundle's documented transforms.
5.  A pretrained 3D model predicts tumour regions.
6.  Predictions are mapped back to the original image grid and affine.
7.  The system produces a BraTS 2021 label map and region masks.
8.  The viewer displays MRI slices and the predicted regions in 3D, with
    linked crosshair coordinates.
9.  The system calculates estimated volumes.
10. If an expert mask is present, the system calculates case-specific
    comparison metrics.
11. The application provides the output NIfTI and a report with
    provenance, limitations, and disclaimer.
12. Temporary uploaded data are automatically deleted within 24 hours.

## 6. Region definitions and label conventions

BraTS 2021 tissue labels:

  Label value   Meaning
  ------------- -------------------------
  0             Background
  1             NCR --- Necrotic core
  2             ED --- Oedema
  4             ET --- Enhancing tumour

Derived regions:

-   **WT (Whole Tumour):** NCR + ED + ET.
-   **TC (Tumour Core):** NCR + ET.
-   **ET (Enhancing Tumour):** ET.

The MONAI bundle may output nested region predictions (TC, WT, ET),
rather than tissue labels. The inference implementation must inspect the
bundle's actual output representation and convert it correctly to BraTS
2021 labels. Do not assume the model output already uses labels 0, 1, 2,
and 4.

For nested region masks, the expected relationship is ET âŠ† TC âŠ† WT.
Postprocessing must enforce a documented, logically consistent
representation before constructing the final label map.

## 7. Functional requirements

### FR-1: MRI upload

-   Accept exactly four required NIfTI sequences: T1, T1Gd, T2, FLAIR.
-   Support `.nii` and `.nii.gz`.
-   Let the user explicitly assign sequence identity; filenames may
    assist but must not be the only mechanism.
-   Accept an optional expert mask in BraTS 2021 label convention.

### FR-2: Input validation and safe failure

Reject invalid cases with clear, user-readable errors. Validate: - File
contents, not just filename extensions. - NIfTI readability and gzip
integrity. - Three-dimensional input volumes. - Finite values; reject
NaN and infinity. - Non-constant image data; reject all-zero and other
constant volumes. - Individual file size no greater than 1 GB. -
Matching shapes and compatible affines across the four sequences. -
Correct sequence assignment. - Optional expert-mask geometry and label
values.

Never display a segmentation result for a case that failed validation or
could not be processed. The application must not crash on the specified
failure pack.

### FR-3: Preprocessing and inference

-   Use a pretrained model publicly available before the event and
    document its licence.
-   Preferred starting point: MONAI Model Zoo `brats_mri_segmentation`
    SegResNet bundle supplied or approved by the organizers.
-   Follow the bundle's actual preprocessing and postprocessing
    configuration.
-   Expected channel order for the referenced bundle: T1Gd, T1, T2,
    FLAIR; verify against the exact bundle version/configuration before
    use.
-   Load the model once where practical and reuse it across cases.
-   Inference must not look up stored dataset images or labels to
    generate an answer.
-   Provide a standalone command or endpoint that accepts four sequences
    and writes a label-map NIfTI.

### FR-4: Output NIfTI

-   Output labels must use BraTS 2021 values 0, 1, 2, and 4.
-   Output must be mapped to the original input grid and affine.
-   Verify output shape, affine, orientation, and label values.
-   The command/endpoint must work independently of the browser
    interface.

### FR-5: 3D and linked-slice visualization

-   Use **NiiVue-led visualization (Option A)** as the primary viewer
    approach.
-   Show axial, coronal, and sagittal views with segmentation overlay.
-   Show L/R, A/P, and S/I anatomical labels as supported by the viewer
    and correctly mapped.
-   Provide a 3D brain/region visualization using NiiVue's available
    volume and mesh capabilities where feasible.
-   Allow rotation, zoom, region visibility toggles, and opacity
    controls where supported by the selected viewer implementation.
-   Keep one synchronized crosshair state across all views and 3D view.
-   Show voxel indices and world coordinates in millimetres.
-   Do not introduce a separate Three.js visualization stack by default;
    only reconsider if NiiVue cannot meet a mandatory requirement.

### FR-6: Volume calculation

For a region with N voxels and voxel spacing sx, sy, sz in millimetres:

`volume_mL = N * sx * sy * sz / 1000`

Use the original image's physical voxel spacing for reported volume, not
the resampled model-input spacing. Show the formula and relevant values
in the UI/report.

Required cube test: a 20 Ã— 20 Ã— 20 mask containing label 2 with spacing
1 Ã— 1 Ã— 2 mm must yield WT = 16.0 mL, TC = 0 mL, ET = 0 mL (within 1%).

### FR-7: Evaluation

-   Report Dice and sensitivity for WT, TC, and ET on at least 10
    held-out labelled cases.
-   Split by patient/case, not by individual slice.
-   Document case IDs/split where allowed by the event rules.
-   Disclose known or possible overlap between evaluation cases and the
    model's training data.
-   Do not present general held-out metrics as if they prove a
    particular upload is correct.
-   If no expert mask is uploaded for a particular case, do not invent
    case-specific Dice/sensitivity.

Metrics: - Dice = 2 Ã— \|Prediction âˆ© GroundTruth\| / (\|Prediction\| +
\|GroundTruth\|) - Sensitivity = \|Prediction âˆ© GroundTruth\| /
\|GroundTruth\|

Define and test behavior for empty masks to avoid division-by-zero
ambiguity.

### FR-8: Report

Generate a report page or PDF with: - Region volumes and voxel counts. -
Applicable case-specific metrics and/or clearly identified held-out
evaluation summary. - Model name, version, and licence. - Training-data
source and overlap disclosure. - Preprocessing details. - Input SHA-256
hashes. - Code commit identifier. - Timestamp. - Limitations and
research-only disclaimer.

### FR-9: Provenance and data lifecycle

-   Keep a record of model/version, preprocessing configuration, input
    hashes, code commit, and processing timestamp.
-   Store uploads only in temporary storage.
-   Automatically delete uploads and generated case artefacts within 24
    hours.
-   Do not commit MRI data, expert masks, hidden judge cases, secrets,
    or temporary outputs to Git.
-   Do not send scans to external APIs or language-model services.

### FR-10: Runtime and reproducibility

-   Complete one case from upload through report within two minutes on
    the organizers' T4-class GPU.
-   Repeated inference on the same case should produce masks with Dice â‰¥
    0.99.
-   Use deterministic settings where practical; document any
    nondeterministic operations.
-   Measure runtime rather than claiming it without testing.

### FR-11: Input sanity

Warn or refuse when a case clearly does not resemble a suitable
skull-stripped brain MRI. Do not claim a simple heuristic is definitive
anatomical verification. The warning/refusal behavior must be tested and
documented.

## 8. Acceptance criteria

The product is considered ready for submission only when the team has
verified:

1.  The standalone inference command/endpoint creates a valid BraTS 2021
    NIfTI label map on the original grid and affine.
2.  A valid four-sequence case completes end-to-end.
3.  The optional expert mask can be displayed and compared when
    supplied.
4.  The 20 Ã— 20 Ã— 20 label-2 cube at 1 Ã— 1 Ã— 2 mm spacing reports WT
    16.0 mL, TC 0 mL, ET 0 mL.
5.  The specified anisotropic test passes the organizer's tolerance.
6.  Both same-anatomy orientation change and mirrored-anatomy tests
    behave correctly.
7.  Linked crosshair positions agree across views within the specified
    tolerance.
8.  All eight failure-pack cases produce clear errors, no crash, and no
    result.
9.  At least ten held-out labelled cases have documented Dice and
    sensitivity for WT, TC, ET.
10. Repeated inference achieves Dice â‰¥ 0.99 on the same case.
11. The complete workflow meets the two-minute runtime target on the
    target GPU.
12. A sample report, model card, and README are ready.
13. The disclaimer appears on every screen.
14. Temporary uploads are automatically deleted within 24 hours.

## 9. Data and model resources

Use the event-provided starter kit and development subset first.

Reference resources: - BraTS 2021:
https://www.med.upenn.edu/cbica/brats2021/ - TCIA BraTS 2021:
https://www.cancerimagingarchive.net/analysis-result/rsna-asnr-miccai-brats-2021/ -
Medical Segmentation Decathlon: http://medicaldecathlon.com/ - MONAI
SegResNet bundle:
https://github.com/Project-MONAI/model-zoo/tree/dev/models/brats_mri_segmentation -
NiiVue: https://github.com/niivue/niivue

Preferred model: MONAI `brats_mri_segmentation`, subject to verifying
the exact bundle version, configuration, licence, expected input
preprocessing, output semantics, and runtime.

The Medical Segmentation Decathlon is optional. Its channel order and
label conventions differ from BraTS 2021; inspect its `dataset.json`
before using it. Do not combine datasets or fine-tune unless allowed by
the event rules and fully documented.

Required data credit: cite BraTS 2021 (Baid et al., DOI
10.7937/jc8x-9874) and the Medical Segmentation Decathlon in the README
if used.

## 10. Base repository scope

The **base commit** establishes the shared project skeleton and
contracts; it does not implement all features.

The base commit must include: - Agreed directory structure. - Shared PRD
and architecture document. - Root README with setup/entry-point
placeholders that are updated as implementation becomes available. -
`.gitignore` for virtual environments, node modules, model weights where
appropriate, MRI uploads, hidden cases, generated outputs, `.env`, and
caches. - Example environment-variable file containing
names/placeholders only, never secrets. - Shared API/data-contract
definitions or schemas. - Basic backend health endpoint or scaffold. -
Frontend scaffold with persistent research-only disclaimer. - A test
directory and test naming conventions. - A single documented local
development approach, with commands updated when implementation is
known. - Branch/merge conventions and definition of done.

The base commit must **not** include: - Real or hidden MRI cases,
labels, or large datasets. - Fabricated inference results presented as
real. - A replacement model or unverified weights. - Unnecessary
database or authentication infrastructure. - A separate Three.js viewer
by default. - Clinical claims.

The initial scaffold should remain small enough to review and should not
block members from developing their feature branches.

## 11. Cross-component contracts

All branches must preserve these contracts:

### Input contract

Four NIfTI volumes identified as T1, T1Gd, T2, and FLAIR; optional
expert label mask.

### Inference contract

A callable pipeline and CLI/API accepting the four sequences and
producing: - A BraTS 2021 label map. - Original-grid/original-affine
output. - Region masks or enough data to derive WT, TC, ET. - Processing
metadata and clear errors.

### Region contract

WT = labels {1,2,4}; TC = labels {1,4}; ET = label {4}.

### Volume contract

Volumes are in mL and use the original input voxel spacing.

### API/UI contract

The frontend receives documented status, error, region-volume,
coordinate, evaluation, provenance, and download information. Do not
encode large voxel arrays as JSON when a binary NIfTI/volume endpoint is
more appropriate.

### Disclaimer contract

Every screen and generated report must state that the product is for
research and teaching only and is not for clinical diagnosis.

## 12. Non-functional requirements

-   **Reliability:** Invalid input must fail safely and clearly.
-   **Reproducibility:** Same input should yield stable output.
-   **Performance:** End-to-end case processing within two minutes on
    target hardware.
-   **Spatial correctness:** Preserve affine, orientation, voxel
    spacing, and crosshair synchronization.
-   **Privacy:** No external scan transmission; temporary data deleted
    within 24 hours.
-   **Maintainability:** Clear module boundaries and documented
    interfaces.
-   **Usability:** A judge should be able to complete the main workflow
    without developer intervention.
-   **Transparency:** Distinguish predicted results, expert comparison,
    and dataset-level evaluation.

## 13. Definition of done for the base commit

The base commit is done when: - The repository structure is present. -
This PRD and the architecture document are committed. - Shared
interfaces and naming conventions are agreed. - `.gitignore` prevents
accidental data/secrets commits. - The project can be cloned without
requiring private files. - The README explains the project, setup
direction, branch conventions, and disclaimer. - No feature branch needs
to invent a conflicting system contract.

## 14. Shared working rules

-   Keep `main` stable and runnable.
-   Use feature branches for independent development.
-   Commit small, meaningful changes.
-   Merge via pull request or a brief review.
-   Integrate early; do not wait until the last hours.
-   Do not force-push shared branches.
-   Do not commit datasets, hidden judge inputs, generated reports,
    credentials, or model files without explicit approval.
-   If a requirement cannot be completed, document the limitation
    honestly rather than simulating success.