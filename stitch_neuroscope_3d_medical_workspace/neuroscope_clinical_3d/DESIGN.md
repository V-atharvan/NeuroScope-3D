---
name: NeuroScope Clinical 3D
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#424654'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#727786'
  outline-variant: '#c2c6d7'
  surface-tint: '#0058c9'
  primary: '#0056c4'
  on-primary: '#ffffff'
  primary-container: '#196eef'
  on-primary-container: '#fefcff'
  inverse-primary: '#b0c6ff'
  secondary: '#115abf'
  on-secondary: '#ffffff'
  secondary-container: '#6096fe'
  on-secondary-container: '#002e6b'
  tertiary: '#00647c'
  on-tertiary: '#ffffff'
  tertiary-container: '#007f9d'
  on-tertiary-container: '#fafdff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d9e2ff'
  primary-fixed-dim: '#b0c6ff'
  on-primary-fixed: '#001944'
  on-primary-fixed-variant: '#00429a'
  secondary-fixed: '#d8e2ff'
  secondary-fixed-dim: '#aec6ff'
  on-secondary-fixed: '#001a42'
  on-secondary-fixed-variant: '#004396'
  tertiary-fixed: '#b7eaff'
  tertiary-fixed-dim: '#69d4f8'
  on-tertiary-fixed: '#001f28'
  on-tertiary-fixed-variant: '#004e61'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
  body-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: -0.01em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.02em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 0.75rem
  gutter-md: 1rem
  margin: 1rem
  margin-md: 1.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style
The design system serves neuro-oncologists, neuroradiologists, and clinical researchers conducting high-stakes volumetric assessments and AI-driven tumor segmentation. The emotional target is absolute clinical clarity, computational authority, and zero-distraction focus. 

The aesthetic is strictly **Clinical Functionalism / Technical Minimalism**:
- Completely flat visual architecture: zero gradients, zero glow artifacts, zero glassmorphism, and zero decorative lighting.
- High-density information design inspired by surgical equipment monitors and diagnostic workstations, calibrated for high-luminance diagnostic display environments.
- Structural reliance on crisp 1px hairpins, solid tonal fills, and sharp typographic hierarchy to separate primary anatomical viewports, numerical inference metrics, and multi-planar volumetric tools.

## Colors
The color architecture enforces precise visual categorization with strict diagnostic restraint.

### Surface & Neutral Tokens
- **Canvas Base**: `#F8FAFC` (Slate-50) – clinical off-white canvas engineered to minimize eye strain during long diagnostic sessions.
- **Surface Elevation 0 (Cards & Viewport Frames)**: `#FFFFFF` – pure white for analytical modules, viewport toolbars, and metadata panels.
- **Surface Elevation 1 (Muted Containers & Troughs)**: `#F1F5F9` (Slate-100) – utilized for segmented controls, disabled buttons, and tabular column headers.
- **Border Structural**: `#E2E8F0` (Slate-200) – universal 1px geometric delineator.
- **Text Primary**: `#0F172A` (Slate-900) – clinical findings, coordinate readouts, and high-contrast labels.
- **Text Secondary / Muted**: `#475569` (Slate-600) / `#64748B` (Slate-500) – units of measurement, patient metadata captions, and inactive controls.

### Functional & Accent Roles
- **Primary Accent (`#2373F4`)**: Deep solid blue applied to confirmed volumetric actions, active slice selectors, primary CTA triggers, and definitive segmentation boundaries.
- **Secondary Blue (`#578EF5`)**: Medium active blue for secondary actions, interactive hover states, active multi-planar reconstruction (MPR) axes, and secondary tool toggles.
- **Highlight Cyan (`#65D0F4`)**: Crisp sky blue designated for axial/coronal/sagittal reference lines, ROI crosshairs, and non-enhancing tumor (NET) region delineations.
- **Highlight Pale Lime (`#F2F7A0`)**: Solid soft yellow-lime reserved strictly for enhancing tumor (ET) labels, segmentation boundary alerts, confidence score warning flags, and high-visibility status tags.
- **Semantic Critical**: `#DC2626` (Red-600) for destructive model rollbacks, edema markers, and clinical contraindications.

## Typography
Typographic clarity directly impacts patient outcomes. The system couples **Inter** for high-legibility interface navigation and clinical narrative reports with **JetBrains Mono** for all quantitative, spatial, and inference metadata.

### Typography Application Rules
- **Inter**: Governs user hierarchy, patient case histories, tool navigation, and clinical descriptions. Weights are restricted strictly to `400` (Regular) and `600` (Semi-bold) to preserve sharp rendering under anti-aliased subpixels.
- **JetBrains Mono**: Strictly applied to DICOM tag metadata, voxel coordinates `(x, y, z)`, volumetric totals `(cm³ / mm³)`, Dice similarity coefficients, Hounsfield/signal units, and model latency timings. Tabular numbers (`tnum`) must remain enabled globally across all numerical data points to avoid spatial jitter during slider scrubbing.

## Layout & Spacing
The layout implements an asymmetric dense viewport architecture designed to maximize high-resolution MRI workspace efficiency:
- **Canvas Shell**: Rigid tripartite multi-panel split layout: Left DICOM Series Explorer (280px fixed width), Center Multi-Planar Reconstruction (MPR) Viewport Cluster (fluid dynamic flex), Right Quantitative Tumor Analytics & Deep Learning Mask Inspector (360px fixed width).
- **Grid & Gutters**: High-density 12-column sub-grid inside analytic drawers, utilizing tight `0.75rem` (12px) gutters to maintain maximum visual telemetry per square inch.
- **Viewport Canvas Rule**: Primary 3D/2D radiological viewports enforce internal zero-margin docking with contextual micro-padding (`0.25rem` / `0.5rem`) on floating coordinate overlays and HUD scale markers.
- **Responsive Handling**:
  - Below `1440px`: Analytics and series panels transition to pinned, collapsible drawer rails, granting full viewport real estate to MRI slices.
  - Mobile/Tablet (`<1024px`): Interface locks into read-only triage/review mode; editing tools collapse into a linear bottom action sheet.

## Elevation & Depth
In alignment with strict diagnostic standards, depth is produced via **crisp structural geometry and subtle, tight ambient occlusion**—not atmospheric diffusion or blurred layers.

- **Zero-Glow Mandate**: Completely prohibit soft Gaussian blur shadows, colored drop glows, drop-shadow halos on active states, and translucent blur filters (`backdrop-filter: blur()`).
- **Surface Elevation 0 (Base Cards & Viewport Modules)**: Pure white background `#FFFFFF`, bordered with a 1px solid line of `#E2E8F0`, underpinned by a razor-sharp, low-spread ambient shadow: `box-shadow: 0 1px 2px 0 rgba(15, 23, 42, 0.06)`.
- **Surface Elevation 1 (Interactive Overlays, Contextual Toolbars, Menus)**: `#FFFFFF` fill, 1px solid border `#CBD5E1`, with distinct multi-layer sharp elevation: `box-shadow: 0 4px 6px -1px rgba(15, 23, 42, 0.08), 0 2px 4px -2px rgba(15, 23, 42, 0.06)`.
- **Boundary Precision**: All viewport boundaries and analytical divisions rely on hard single-pixel `#E2E8F0` dividing lines to ensure image diagnostic accuracy is never compromised by blurred edge artifacts.

## Shapes
The shape language conveys precision surgical tooling:
- **Roundedness Scale 1 (Soft / Micro-Radii)**: Core interactive components (inputs, secondary buttons, badges, card enclosures) strictly utilize `0.25rem` (4px) corner radii.
- **Large Containers & Viewports**: Module frames utilize `0.375rem` (6px) or maintain hard `0px` joins when flush against canvas borders.
- **Tool Icons & Control Toggles**: Maintain square `4px` corner bevels. Pill shapes (`rounded-full`) are banned except for minimal circular status indicators (5px × 5px dot indicators).

## Components

### Buttons
- **Primary Clinical Action**: Flat solid `#2373F4` fill, text `#FFFFFF` (Inter Semi-Bold), 1px solid border `#2373F4`. Hover: `#1B5EC8` solid. Active: `#154AA0`. No gradients or drop shadows.
- **Secondary Action**: Flat solid `#FFFFFF` fill, text `#0F172A`, 1px solid border `#E2E8F0`. Hover: `#F8FAFC` background with border `#CBD5E1`.
- **Tertiary / Viewport Tool Button**: Transparent fill, 1px solid transparent border. Hover: `#F1F5F9` solid fill, 1px solid `#E2E8F0`. Active state: `#2373F4` solid fill with `#FFFFFF` text/icon.

### Chips & Clinical Badges
- **Enhancing Tumor (ET) Badge**: Flat `#F2F7A0` solid background with `#0F172A` text (JetBrains Mono Semi-Bold, 10px), 1px solid `#E4EB78`.
- **Non-Enhancing / Necrotic Core Badge**: Flat `#65D0F4` solid background with `#0F172A` text, 1px solid `#49B8DE`.
- **Edema / Peritumoral Zone Badge**: Flat `#E2E8F0` solid background with `#334155` text, 1px solid `#CBD5E1`.

### Data Cards & Volumetric Containers
- Background `#FFFFFF`, 1px solid `#E2E8F0` border, `0.25rem` border radius, micro-shadow `0 1px 2px 0 rgba(15, 23, 42, 0.06)`.
- Card Header: Separated by a 1px solid `#E2E8F0` rule, featuring metadata title in `Inter 13px Semi-bold` and slice/coordinate details in `JetBrains Mono 11px`.

### Inputs, Sliders & Numerical Scrubbers
- **Text & Coordinate Fields**: Flat `#FFFFFF` fill, 1px solid `#CBD5E1` border, 4px corner radius. Focused state: 1px solid `#2373F4` (with an additional 1px solid outer ring `#578EF5` with no blur). Font: `JetBrains Mono`.
- **Slice Windowing Sliders (WW/WL)**: Flat continuous 2px bar `#E2E8F0`, active progression track solid `#2373F4`, scrubber thumb is a sharp 12px × 12px square with 2px radius in solid `#2373F4` (no shadow, no glow).

### Checkboxes & Segment Toggles
- **Checkboxes**: 14px × 14px square, 2px radius, 1px solid `#CBD5E1`. Checked state: solid `#2373F4` fill with white geometric checkmark.
- **Segmented ROI Switchers**: Housed in `#F1F5F9` solid trough with 4px padding. Selected segment button adopts `#FFFFFF` solid fill, 1px solid `#CBD5E1`, with primary slate text.

### Domain-Specific Components
- **Crosshair MPR Coordinate HUD**: Micro-panel docked directly into MRI viewports, `#FFFFFF` with 1px solid `#E2E8F0`, displaying axial, coronal, and sagittal slice indices in `JetBrains Mono 11px`.
- **Tumor Volumetric Delta Bar**: Micro-indicator consisting of flat adjacent solid color blocks (`#F2F7A0`, `#65D0F4`, `#578EF5`) representing comparative volumetric changes (cm³) against prior baseline scans without rounded inner dividers.