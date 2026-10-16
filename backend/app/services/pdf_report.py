"""
NeuroScope 3D - PDF Report Generation Service
Generates formal provenance and quantitative volumetric reports using ReportLab.
Adheres strictly to PRD_BASE.md (FR-8) and docs/API_CONTRACT.md.
"""
from typing import Dict, Any, Optional
import os
from datetime import datetime, timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from backend.app.schemas.contracts import MANDATORY_DISCLAIMER


def generate_pdf_report(
    case_id: str,
    output_pdf_path: str,
    volumes: Dict[str, Any],
    spatial_metadata: Dict[str, Any],
    provenance: Dict[str, Any],
    case_evaluation: Optional[Dict[str, Any]] = None,
    runtime_seconds: Optional[float] = None
) -> str:
    """
    Builds a professional clinical research PDF report.
    """
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
        title=f"NeuroScope 3D Report ({case_id})",
        author="NeuroScope 3D Platform",
        subject=f"{MANDATORY_DISCLAIMER}",
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0F172A'),
        fontName='Helvetica-Bold'
    )

    disclaimer_style = ParagraphStyle(
        'DisclaimerBanner',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#991B1B'),
        backColor=colors.HexColor('#FEF2F2'),
        borderColor=colors.HexColor('#F87171'),
        borderWidth=1,
        borderPadding=8,
        spaceAfter=14,
        fontName='Helvetica-Bold'
    )

    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#1E293B'),
        fontName='Helvetica-Bold',
        spaceBefore=10,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#334155')
    )

    mono_style = ParagraphStyle(
        'MonoText',
        parent=styles['Normal'],
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor('#0F172A'),
        fontName='Courier'
    )

    elements = []

    # 1. Header & Title
    elements.append(Paragraph("NeuroScope 3D", title_style))
    elements.append(Paragraph("Automated Multimodal Brain MRI Segmentation & Volumetric Report", styles['Normal']))
    elements.append(Spacer(1, 10))

    # 2. Mandatory Disclaimer Banner
    elements.append(Paragraph(
        f"<b>MANDATORY NOTICE:</b> {MANDATORY_DISCLAIMER} "
        "This software does not diagnose tumours, replace a radiologist, or support treatment or surgical planning.",
        disclaimer_style
    ))

    # 3. Study Metadata Table
    timestamp = provenance.get("timestamp", datetime.now(timezone.utc).isoformat())
    commit_id = provenance.get("git_commit", "scaffold-baseline")
    runtime_str = f"{runtime_seconds:.2f} seconds" if runtime_seconds else "N/A"

    meta_data = [
        [Paragraph("<b>Case Identifier:</b>", body_style), Paragraph(case_id, mono_style)],
        [Paragraph("<b>Processing Date (UTC):</b>", body_style), Paragraph(timestamp, body_style)],
        [Paragraph("<b>Software Commit:</b>", body_style), Paragraph(commit_id, mono_style)],
        [Paragraph("<b>Inference Runtime:</b>", body_style), Paragraph(runtime_str, body_style)],
        [Paragraph("<b>Input Voxel Spacing:</b>", body_style), Paragraph(f"{spatial_metadata.get('spacing_mm', [1,1,1])} mm", body_style)],
    ]

    meta_table = Table(meta_data, colWidths=[2.0 * inch, 5.0 * inch])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 14))

    # 4. Volumetric Quantitation Table (FR-6)
    elements.append(Paragraph("Volumetric Quantitation (Physical Space)", heading_style))
    elements.append(Paragraph("<i>Calculated on reference grid: Volume (mL) = Voxel Count × s<sub>x</sub> × s<sub>y</sub> × s<sub>z</sub> / 1000</i>", body_style))
    elements.append(Spacer(1, 6))

    vol_headers = [
        Paragraph("<b>Target Region</b>", body_style),
        Paragraph("<b>BraTS Tissue Labels Included</b>", body_style),
        Paragraph("<b>Voxel Count</b>", body_style),
        Paragraph("<b>Physical Volume (mL)</b>", body_style),
    ]

    wt_data = volumes.get("WT", {"voxel_count": 0, "volume_ml": 0.0})
    tc_data = volumes.get("TC", {"voxel_count": 0, "volume_ml": 0.0})
    et_data = volumes.get("ET", {"voxel_count": 0, "volume_ml": 0.0})

    vol_rows = [
        vol_headers,
        [
            Paragraph("<b>Whole Tumour (WT)</b>", body_style),
            Paragraph("NCR + ED + ET (Labels 1, 2, 4)", body_style),
            Paragraph(str(wt_data.get("voxel_count", 0)), body_style),
            Paragraph(f"{wt_data.get('volume_ml', 0.0):.2f} mL", body_style),
        ],
        [
            Paragraph("<b>Tumour Core (TC)</b>", body_style),
            Paragraph("NCR + ET (Labels 1, 4)", body_style),
            Paragraph(str(tc_data.get("voxel_count", 0)), body_style),
            Paragraph(f"{tc_data.get('volume_ml', 0.0):.2f} mL", body_style),
        ],
        [
            Paragraph("<b>Enhancing Tumour (ET)</b>", body_style),
            Paragraph("ET (Label 4)", body_style),
            Paragraph(str(et_data.get("voxel_count", 0)), body_style),
            Paragraph(f"{et_data.get('volume_ml', 0.0):.2f} mL", body_style),
        ],
    ]

    vol_table = Table(vol_rows, colWidths=[1.8 * inch, 2.7 * inch, 1.2 * inch, 1.3 * inch])
    vol_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(vol_table)
    elements.append(Spacer(1, 14))

    # 5. Case Evaluation (if expert mask was supplied)
    if case_evaluation and case_evaluation.get("available"):
        elements.append(Paragraph("Expert Mask Comparison Metrics", heading_style))
        eval_headers = [
            Paragraph("<b>Region</b>", body_style),
            Paragraph("<b>Dice Similarity (DSC)</b>", body_style),
            Paragraph("<b>Sensitivity (TPR)</b>", body_style),
        ]
        metrics = case_evaluation.get("metrics", {})
        eval_rows = [eval_headers]
        for reg in ["WT", "TC", "ET"]:
            m = metrics.get(reg, {"dice": 0.0, "sensitivity": 0.0})
            eval_rows.append([
                Paragraph(f"<b>{reg}</b>", body_style),
                Paragraph(f"{m.get('dice', 0.0):.4f}", body_style),
                Paragraph(f"{m.get('sensitivity', 0.0):.4f}", body_style),
            ])

        eval_table = Table(eval_rows, colWidths=[2.0 * inch, 2.5 * inch, 2.5 * inch])
        eval_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(eval_table)
        elements.append(Spacer(1, 14))
    else:
        elements.append(Paragraph("Case Comparison Metrics", heading_style))
        elements.append(Paragraph(
            "<i>Expert ground-truth mask was not supplied with this study upload. "
            "Case-specific Dice and sensitivity metrics are omitted (never fabricated).</i>",
            body_style
        ))
        elements.append(Spacer(1, 10))

    # 6. Model Provenance & Input Hashes
    elements.append(Paragraph("Model Provenance & Preprocessing Details", heading_style))
    prov_data = [
        [Paragraph("<b>Model Architecture:</b>", body_style), Paragraph(provenance.get("model_name", "SegResNet"), body_style)],
        [Paragraph("<b>Model License:</b>", body_style), Paragraph(provenance.get("model_license", "Apache 2.0"), body_style)],
        [Paragraph("<b>Training Dataset:</b>", body_style), Paragraph(provenance.get("training_data_source", "BraTS 2018 Challenge Dataset"), body_style)],
        [Paragraph("<b>Preprocessing Details:</b>", body_style), Paragraph("Nonzero z-score normalization; channel order [0: T1Gd, 1: T1, 2: T2, 3: FLAIR]; 1mm isotropic reference.", body_style)],
        [Paragraph("<b>Training/Eval Overlap:</b>", body_style), Paragraph("Pretrained on BraTS 2018. Historical BraTS cases may overlap with re-indexed datasets; patient-level splitting is required.", body_style)],
    ]

    input_hashes = provenance.get("input_sha256", {})
    for seq_key in ["t1", "t1gd", "t2", "flair"]:
        h = input_hashes.get(seq_key, "N/A")
        prov_data.append([
            Paragraph(f"<b>SHA-256 ({seq_key.upper()}):</b>", body_style),
            Paragraph(h, mono_style)
        ])

    prov_table = Table(prov_data, colWidths=[2.2 * inch, 4.8 * inch])
    prov_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(prov_table)
    elements.append(Spacer(1, 14))

    # 7. Held-Out Evaluation Reference Note
    elements.append(Paragraph(
        "<b>Held-Out Benchmark Reference:</b> Pretrained SegResNet achieved mean Dice on held-out BraTS 2018 validation split: "
        "WT = 0.9026, TC = 0.8559, ET = 0.7905. "
        "<i>Population benchmark metrics are aggregate references and do not validate individual patient cases.</i>",
        body_style
    ))
    elements.append(Spacer(1, 10))

    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#94A3B8'), spaceAfter=8))
    elements.append(Paragraph(
        f"NeuroScope 3D Prototype | Generated on {timestamp} | {MANDATORY_DISCLAIMER}",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7.5, textColor=colors.HexColor('#64748B'), alignment=1)
    ))

    doc.build(elements)
    return output_pdf_path
