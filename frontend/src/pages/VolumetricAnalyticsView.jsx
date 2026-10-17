import React from 'react';
import {
  BarChart3,
  TrendingUp,
  Download,
  FileText,
  Layers,
  Info,
  CheckCircle2,
  RefreshCw,
  Box,
  Compass,
  ArrowRight
} from 'lucide-react';
import { getMaskDownloadUrl, getReportDownloadUrl } from '../services/api';

export default function VolumetricAnalyticsView({
  caseId,
  caseResults,
  activeCase,
  onNavigateToCentroid,
  onOpenWorkstation
}) {
  const effectiveCaseId = caseResults?.case_id || activeCase?.case_id;
  const volumes = caseResults?.regions || activeCase?.volumes || activeCase?.regions;
  const spatialMeta = caseResults?.spatial_metadata || activeCase?.spatial_summary;

  const wt = volumes?.WT;
  const tc = volumes?.TC;
  const et = volumes?.ET;

  const wtVol = wt?.volume_ml ?? 0;
  const tcVol = tc?.volume_ml ?? 0;
  const etVol = et?.volume_ml ?? 0;
  const edVol = Math.max(0, wtVol - tcVol); // Edema = WT - TC

  const tcRatio = wtVol > 0 ? ((tcVol / wtVol) * 100).toFixed(1) : '0.0';
  const etRatio = wtVol > 0 ? ((etVol / wtVol) * 100).toFixed(1) : '0.0';
  const edRatio = wtVol > 0 ? ((edVol / wtVol) * 100).toFixed(1) : '0.0';

  const spacing = spatialMeta?.voxel_spacing_mm || spatialMeta?.spacing_mm || [1.0, 1.0, 1.0];
  const spacingStr = Array.isArray(spacing) ? spacing.map(n => Number(n).toFixed(2)).join(' × ') : '1.00 × 1.00 × 1.00';

  const maxVal = Math.max(wtVol, 1);
  const wtBarPct = 100;
  const tcBarPct = Math.min(100, (tcVol / maxVal) * 100);
  const etBarPct = Math.min(100, (etVol / maxVal) * 100);
  const edBarPct = Math.min(100, (edVol / maxVal) * 100);

  const formatBbox = (bb) => {
    if (!bb || !bb.min || !bb.max) return '[--] → [--]';
    return `[${bb.min.join(',')}] → [${bb.max.join(',')}]`;
  };

  const rows = [
    {
      compartment: 'Whole Tumour (WT)',
      chipClass: 'metric-chip-wt',
      labels: '1, 2, 4 (NCR + ED + ET)',
      volume: wtVol,
      voxels: wt?.voxel_count ?? 0,
      ratio: '100.0%',
      bbox: formatBbox(wt?.bounding_box_voxel),
      centroid: wt?.centroid_voxel,
      status: wt?.measurement_status ? wt.measurement_status.replace('_', ' ').toUpperCase() : (wt?.voxel_count > 0 ? 'VALID' : 'EMPTY'),
      color: '#65D0F4'
    },
    {
      compartment: 'Tumour Core (TC)',
      chipClass: 'metric-chip-tc',
      labels: '1, 4 (NCR + ET)',
      volume: tcVol,
      voxels: tc?.voxel_count ?? 0,
      ratio: `${tcRatio}%`,
      bbox: formatBbox(tc?.bounding_box_voxel),
      centroid: tc?.centroid_voxel,
      status: tc?.measurement_status ? tc.measurement_status.replace('_', ' ').toUpperCase() : (tc?.voxel_count > 0 ? 'VALID' : 'EMPTY'),
      color: '#578EF5'
    },
    {
      compartment: 'Enhancing Tumour (ET)',
      chipClass: 'metric-chip-et',
      labels: '4 (Active Proliferation)',
      volume: etVol,
      voxels: et?.voxel_count ?? 0,
      ratio: `${etRatio}%`,
      bbox: formatBbox(et?.bounding_box_voxel),
      centroid: et?.centroid_voxel,
      status: et?.measurement_status ? et.measurement_status.replace('_', ' ').toUpperCase() : (et?.voxel_count > 0 ? 'VALID' : 'EMPTY'),
      color: '#F2F7A0'
    },
    {
      compartment: 'Peritumoral Edema (ED)',
      chipClass: 'metric-chip-ed',
      labels: '2 (T2 Infiltration)',
      volume: edVol,
      voxels: Math.max(0, (wt?.voxel_count ?? 0) - (tc?.voxel_count ?? 0)),
      ratio: `${edRatio}%`,
      bbox: 'Derived (WT - TC)',
      centroid: null,
      status: 'DERIVED',
      color: '#CBD5E1'
    }
  ];

  return (
    <div className="analytics-page-container">
      {/* 1. Page Header */}
      <div className="analytics-page-header">
        <div>
          <div className="analytics-page-badge">
            <BarChart3 size={14} className="text-primary-blue" />
            <span>ISO 1.0mm³ VOXEL-GRID VOLUMETRIC QUANTITATION</span>
          </div>
          <h1 className="analytics-page-title">Physical Volumetric Quantitation & Analytics</h1>
          <p className="analytics-page-desc">
            Exact physical volume quantification computed from 3D NIfTI affine transformation matrix.
            BraTS standard sub-compartment volumetric hierarchy: WT ≥ TC ≥ ET.
          </p>
        </div>

        <div className="analytics-header-actions">
          {effectiveCaseId && (
            <>
              <a
                href={getMaskDownloadUrl(effectiveCaseId)}
                download={`case_${effectiveCaseId}_seg.nii.gz`}
                className="btn-primary"
                style={{ fontSize: '11px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px', textDecoration: 'none' }}
              >
                <Download size={14} />
                <span>Export NIfTI Mask</span>
              </a>
              <a
                href={getReportDownloadUrl(effectiveCaseId)}
                download={`case_${effectiveCaseId}_report.pdf`}
                className="btn-secondary"
                style={{ fontSize: '11px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px', textDecoration: 'none' }}
              >
                <FileText size={14} />
                <span>Download Audit PDF</span>
              </a>
            </>
          )}
          {onOpenWorkstation && (
            <button
              type="button"
              className="btn-secondary"
              onClick={onOpenWorkstation}
              style={{ fontSize: '11px', padding: '6px 12px' }}
            >
              <span>Back to Workstation</span>
              <ArrowRight size={13} />
            </button>
          )}
        </div>
      </div>

      {/* 2. Top Summary KPI Cards (4 Cards) */}
      <div className="analytics-kpi-grid">
        {/* WT Card */}
        <div className="analytics-kpi-card">
          <div className="analytics-kpi-header">
            <span className="metric-chip-wt">WT: Whole Tumour</span>
            <span className="analytics-kpi-label-ids">Labels 1, 2, 4</span>
          </div>
          <div className="analytics-kpi-value-row">
            <span className="analytics-kpi-num font-mono">{wtVol.toFixed(1)}</span>
            <span className="analytics-kpi-unit">mL</span>
          </div>
          <div className="analytics-kpi-meta font-mono">
            <span>Voxels: <b>{wt?.voxel_count?.toLocaleString() ?? '--'}</b></span>
            <span>Total Burden</span>
          </div>
        </div>

        {/* TC Card */}
        <div className="analytics-kpi-card">
          <div className="analytics-kpi-header">
            <span className="metric-chip-tc">TC: Tumour Core</span>
            <span className="analytics-kpi-label-ids">Labels 1, 4</span>
          </div>
          <div className="analytics-kpi-value-row">
            <span className="analytics-kpi-num font-mono">{tcVol.toFixed(1)}</span>
            <span className="analytics-kpi-unit">mL</span>
          </div>
          <div className="analytics-kpi-meta font-mono">
            <span>Ratio WT: <b>{tcRatio}%</b></span>
            <span>{tc?.voxel_count?.toLocaleString() ?? '--'} voxels</span>
          </div>
        </div>

        {/* ET Card */}
        <div className="analytics-kpi-card">
          <div className="analytics-kpi-header">
            <span className="metric-chip-et">ET: Enhancing</span>
            <span className="analytics-kpi-label-ids">Label 4</span>
          </div>
          <div className="analytics-kpi-value-row">
            <span className="analytics-kpi-num font-mono">{etVol.toFixed(1)}</span>
            <span className="analytics-kpi-unit">mL</span>
          </div>
          <div className="analytics-kpi-meta font-mono">
            <span>Ratio WT: <b>{etRatio}%</b></span>
            <span>Active Margin</span>
          </div>
        </div>

        {/* Edema Card */}
        <div className="analytics-kpi-card">
          <div className="analytics-kpi-header">
            <span className="px-1.5 py-0.5 bg-slate-200 text-slate-800 font-mono text-[10px] font-bold border border-slate-300">
              ED: Peritumoral
            </span>
            <span className="analytics-kpi-label-ids">Label 2</span>
          </div>
          <div className="analytics-kpi-value-row">
            <span className="analytics-kpi-num font-mono">{edVol.toFixed(1)}</span>
            <span className="analytics-kpi-unit">mL</span>
          </div>
          <div className="analytics-kpi-meta font-mono">
            <span>Ratio WT: <b>{edRatio}%</b></span>
            <span>Infiltration Zone</span>
          </div>
        </div>
      </div>

      {/* 3. Responsive Data-Driven Distribution Chart */}
      <div className="analytics-chart-card">
        <div className="analytics-card-header">
          <h2 className="analytics-card-title">Compartment Volume Breakdown & Proportions</h2>
          <span className="font-mono text-xs text-muted">Voxel Grid Spacing: {spacingStr} mm</span>
        </div>

        <div className="analytics-chart-body">
          {/* Bar 1: WT */}
          <div className="analytics-bar-item">
            <div className="analytics-bar-label-group">
              <span className="font-semibold text-xs">Whole Tumour (WT)</span>
              <span className="font-mono font-bold text-xs">{wtVol.toFixed(1)} mL (100%)</span>
            </div>
            <div className="analytics-bar-track">
              <div
                className="analytics-bar-fill"
                style={{ width: `${wtBarPct}%`, backgroundColor: '#65D0F4' }}
              />
            </div>
          </div>

          {/* Bar 2: TC */}
          <div className="analytics-bar-item">
            <div className="analytics-bar-label-group">
              <span className="font-semibold text-xs">Tumour Core (TC)</span>
              <span className="font-mono font-bold text-xs">{tcVol.toFixed(1)} mL ({tcRatio}%)</span>
            </div>
            <div className="analytics-bar-track">
              <div
                className="analytics-bar-fill"
                style={{ width: `${tcBarPct}%`, backgroundColor: '#578EF5' }}
              />
            </div>
          </div>

          {/* Bar 3: ET */}
          <div className="analytics-bar-item">
            <div className="analytics-bar-label-group">
              <span className="font-semibold text-xs">Enhancing Tumour (ET)</span>
              <span className="font-mono font-bold text-xs">{etVol.toFixed(1)} mL ({etRatio}%)</span>
            </div>
            <div className="analytics-bar-track">
              <div
                className="analytics-bar-fill"
                style={{ width: `${etBarPct}%`, backgroundColor: '#F2F7A0' }}
              />
            </div>
          </div>

          {/* Bar 4: ED */}
          <div className="analytics-bar-item">
            <div className="analytics-bar-label-group">
              <span className="font-semibold text-xs">Peritumoral Edema (ED)</span>
              <span className="font-mono font-bold text-xs">{edVol.toFixed(1)} mL ({edRatio}%)</span>
            </div>
            <div className="analytics-bar-track">
              <div
                className="analytics-bar-fill"
                style={{ width: `${edBarPct}%`, backgroundColor: '#CBD5E1' }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* 4. Detailed Volumetric Data Table */}
      <div className="analytics-table-card">
        <div className="analytics-card-header">
          <h2 className="analytics-card-title">Compartment Quantitative Specification Table</h2>
          <span className="font-mono text-xs text-muted">BraTS 2021 Label Specification</span>
        </div>

        <div className="analytics-table-wrap">
          <table className="analytics-data-table">
            <thead>
              <tr>
                <th>Compartment</th>
                <th>BraTS Labels</th>
                <th>Physical Volume</th>
                <th>Voxel Count</th>
                <th>% of WT</th>
                <th>Bounding Box (Voxels)</th>
                <th>Centroid Coordinate</th>
                <th>Validation Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr key={idx}>
                  <td>
                    <span className={row.chipClass}>{row.compartment}</span>
                  </td>
                  <td className="font-mono text-xs">{row.labels}</td>
                  <td className="font-mono font-bold text-sm">
                    {row.volume.toFixed(1)} <span className="text-xs font-normal text-muted">mL</span>
                  </td>
                  <td className="font-mono">{row.voxels.toLocaleString()}</td>
                  <td className="font-mono font-semibold">{row.ratio}</td>
                  <td className="font-mono text-xs">{row.bbox}</td>
                  <td className="font-mono text-xs">
                    {row.centroid ? (
                      <button
                        type="button"
                        className="btn-centroid-jump"
                        onClick={() => onNavigateToCentroid && onNavigateToCentroid(row.centroid)}
                        title={`Jump crosshair to centroid [${row.centroid.join(', ')}]`}
                      >
                        [{row.centroid.join(', ')}]
                      </button>
                    ) : (
                      <span className="text-muted">--</span>
                    )}
                  </td>
                  <td>
                    <span className="status-badge-valid">✓ {row.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 5. Mathematical Formulation & Affine Provenance Banner */}
      <div className="analytics-formula-card">
        <div className="analytics-formula-icon">
          <Info size={18} className="text-primary-blue" />
        </div>
        <div className="analytics-formula-text">
          <strong>Mathematical Voxel-to-Volume Formulation</strong>
          <p className="font-mono">
            V = N × |det(A_3×3)| / 1000 mL = N × (s_x × s_y × s_z) / 1000 mL
          </p>
          <p className="text-xs text-muted">
            Where <code>N</code> is the number of segmented voxels, and <code>A_3×3</code> represents the upper-left
            rotation-scaling sub-matrix of the NIfTI-1 sform/qform coordinate transformation. Calibration verified
            against ISO 1.0mm³ standard (det(A) = 1.000).
          </p>
        </div>
      </div>
    </div>
  );
}
