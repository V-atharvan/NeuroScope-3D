import React, { useState } from 'react';
import { Eye, EyeOff, Play, Loader2, RefreshCw, FlaskConical, AlertCircle, CheckCircle2 } from 'lucide-react';

export default function VolumetricCards({
  volumes,
  spatialMetadata,
  onSelectCentroid,
  layerVisibility,
  onToggleLayer,
  onRunSegmentation,
  onLoadSample,
  isSegmenting = false,
  caseId = null,
}) {
  const [localCalculating, setLocalCalculating] = useState(false);
  const [localError, setLocalError] = useState(null);

  const hasVolumes = Boolean(volumes && (volumes.WT || volumes.TC || volumes.ET));
  const isBusy = Boolean(isSegmenting || localCalculating);

  const wt = volumes?.WT;
  const tc = volumes?.TC;
  const et = volumes?.ET;

  const spacing = spatialMetadata?.voxel_spacing_mm || spatialMetadata?.spacing_mm || [1.0, 1.0, 1.0];
  const spacingStr = Array.isArray(spacing) ? spacing.map((s) => Number(s).toFixed(1)).join(' × ') : '1.0 × 1.0 × 1.0';

  const formatBbox = (bb) => {
    if (!bb || !bb.min || !bb.max) return '[--] → [--]';
    return `[${bb.min.join(',')}] → [${bb.max.join(',')}]`;
  };

  const tcRatio = (wt?.volume_ml && tc?.volume_ml) ? ((tc.volume_ml / wt.volume_ml) * 100).toFixed(1) : '--';

  const voxelVolMm3 = wt?.voxel_volume_mm3 || tc?.voxel_volume_mm3 || et?.voxel_volume_mm3 || (Array.isArray(spacing) ? (spacing[0] * spacing[1] * spacing[2]) : 1.0);
  const activeFormula = wt?.formula || `V = N × |det(A_3×3)| / 1000 mL (${spacingStr} mm³)`;

  const handleTriggerCalculation = async () => {
    setLocalError(null);
    if (onRunSegmentation) {
      setLocalCalculating(true);
      try {
        await onRunSegmentation();
      } catch (err) {
        setLocalError(err.message || 'Failed to compute tumor volumes.');
      } finally {
        setLocalCalculating(false);
      }
    }
  };

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div className="clinical-section-header">
        <h2 className="section-title-text" style={{ display: 'flex', alignItems: 'center' }}>
          <span className="section-number-badge">2</span>
          Volumetric Quantitation (mL)
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {hasVolumes && onRunSegmentation && (
            <button
              type="button"
              onClick={handleTriggerCalculation}
              disabled={isBusy}
              title="Recalculate tumor volumes"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '2px 6px',
                fontSize: '10px',
                borderRadius: '3px',
                border: '1px solid #CBD5E1',
                background: '#FFFFFF',
                color: '#475569',
                cursor: isBusy ? 'not-allowed' : 'pointer',
              }}
            >
              <RefreshCw size={10} className={isBusy ? 'spin' : ''} />
              <span>{isBusy ? 'Calculating...' : 'Recalculate'}</span>
            </button>
          )}
          <span
            className="font-mono"
            style={{
              fontSize: '11px',
              fontWeight: 700,
              padding: '2px 6px',
              borderRadius: '3px',
              backgroundColor: hasVolumes ? '#ECFDF5' : isBusy ? '#EFF6FF' : '#F8FAFC',
              color: hasVolumes ? '#059669' : isBusy ? '#2563EB' : 'var(--on-surface-variant)',
              border: `1px solid ${hasVolumes ? '#A7F3D0' : isBusy ? '#BFDBFE' : '#E2E8F0'}`,
            }}
          >
            {isBusy ? 'CALCULATING...' : hasVolumes ? '✓ INFERENCE ACTIVE' : 'STANDBY'}
          </span>
        </div>
      </div>

      {!hasVolumes && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          padding: '10px 12px',
          backgroundColor: isBusy ? '#EFF6FF' : '#F8FAFC',
          border: `1px solid ${isBusy ? '#93C5FD' : '#CBD5E1'}`,
          borderRadius: 'var(--radius-sm)',
          fontSize: '11px',
          color: '#334155',
          lineHeight: 1.4
        }}>
          {isBusy ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#1D4ED8', fontWeight: 600 }}>
              <Loader2 size={16} className="spin" />
              <span>Computing physical tumor volumes (WT, TC, ET) via SegResNet pipeline...</span>
            </div>
          ) : (
            <>
              <div>
                Multi-compartment physical quantitation measures exact tissue volumes in millilitres (mL) from the 3D voxel grid: <strong>WT</strong> (Whole Tumour), <strong>TC</strong> (Tumour Core), and <strong>ET</strong> (Enhancing Tumour).
              </div>

              {localError && (
                <div style={{
                  padding: '6px 8px',
                  backgroundColor: '#FEF2F2',
                  border: '1px solid #FECACA',
                  borderRadius: '3px',
                  color: '#DC2626',
                  fontSize: '11px',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '6px'
                }}>
                  <AlertCircle size={14} style={{ flexShrink: 0, marginTop: '1px' }} />
                  <span>{localError}</span>
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '2px' }}>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={handleTriggerCalculation}
                  disabled={isBusy || !caseId}
                  title={!caseId ? 'Upload and validate MRI sequences in Step 1 first' : 'Calculate tumor volumes for uploaded case'}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    fontSize: '12px',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    cursor: (isBusy || !caseId) ? 'not-allowed' : 'pointer'
                  }}
                >
                  <Play size={14} fill="currentColor" />
                  <span>{caseId ? 'Calculate Tumor Volumes (mL)' : 'Upload Study in Step 1 First'}</span>
                </button>

                {onLoadSample && (
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={onLoadSample}
                    disabled={isBusy}
                    style={{
                      width: '100%',
                      padding: '6px 10px',
                      fontSize: '11px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                      cursor: isBusy ? 'not-allowed' : 'pointer'
                    }}
                  >
                    <FlaskConical size={13} />
                    <span>Load Sample BraTS Study &amp; Calculate Volumes</span>
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* 3 Solid Metric Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {/* Whole Tumour (WT) */}
        <div className="metric-card-solid">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span className="metric-chip-wt">WT: Whole Tumour</span>
              {hasVolumes && onToggleLayer && (
                <button
                  type="button"
                  onClick={() => onToggleLayer('WT')}
                  title={layerVisibility?.WT ? 'Hide Whole Tumour in viewers' : 'Show Whole Tumour in viewers'}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: layerVisibility?.WT ? '#EFF6FF' : '#F1F5F9',
                    border: '1px solid',
                    borderColor: layerVisibility?.WT ? '#93C5FD' : '#CBD5E1',
                    borderRadius: '3px',
                    padding: '2px 4px',
                    cursor: 'pointer',
                    color: layerVisibility?.WT ? '#1D4ED8' : '#94A3B8',
                  }}
                >
                  {layerVisibility?.WT ? <Eye size={12} /> : <EyeOff size={12} />}
                </button>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              {hasVolumes && (
                <span
                  style={{
                    padding: '1px 5px',
                    borderRadius: '2px',
                    fontSize: '9px',
                    fontWeight: 700,
                    letterSpacing: '0.04em',
                    backgroundColor: wt?.voxel_count > 0 ? '#ECFDF5' : '#F8FAFC',
                    color: wt?.voxel_count > 0 ? '#065F46' : '#64748B',
                    border: '1px solid',
                    borderColor: wt?.voxel_count > 0 ? '#A7F3D0' : '#E2E8F0',
                  }}
                >
                  {wt?.measurement_status ? wt.measurement_status.replace('_', ' ').toUpperCase() : (wt?.voxel_count > 0 ? 'VALID' : 'EMPTY')}
                </span>
              )}
              <span className="metric-val-num">
                {hasVolumes && wt?.volume_ml !== undefined ? wt.volume_ml.toFixed(1) : '--'}{' '}
                <span className="metric-val-unit">mL</span>
              </span>
            </div>
          </div>
          <div
            className="font-mono"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '11px',
              color: 'var(--on-surface-variant)',
              marginTop: '2px'
            }}
          >
            <span>Voxels: <b>{hasVolumes && wt?.voxel_count !== undefined ? wt.voxel_count.toLocaleString() : '--'}</b> ({hasVolumes ? `${(wt?.voxel_volume_mm3 ?? voxelVolMm3).toFixed(2)} mm³` : '--'})</span>
            <span>BBox: {hasVolumes ? formatBbox(wt?.bounding_box_voxel) : '[--] → [--]'}</span>
          </div>
          {hasVolumes && (
            <div
              className="font-mono"
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: '10px',
                color: 'var(--on-surface-variant)',
                marginTop: '4px',
                paddingTop: '3px',
                borderTop: '1px dashed #E2E8F0'
              }}
            >
              <span>Centroid:</span>
              {wt?.centroid_voxel ? (
                <button
                  type="button"
                  onClick={() => onSelectCentroid && onSelectCentroid(wt.centroid_voxel)}
                  title={`Jump crosshair to WT centroid [${wt.centroid_voxel.join(', ')}]`}
                  style={{
                    border: '1px solid #BFDBFE',
                    background: '#EFF6FF',
                    color: '#1D4ED8',
                    padding: '1px 6px',
                    borderRadius: '3px',
                    cursor: 'pointer',
                    fontWeight: 600,
                    fontSize: '10px'
                  }}
                >
                  [{wt.centroid_voxel.join(', ')}]
                </button>
              ) : (
                <span style={{ color: '#94A3B8' }}>None (0 voxels)</span>
              )}
            </div>
          )}
        </div>

        {/* Tumour Core (TC) */}
        <div className="metric-card-solid">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span className="metric-chip-tc">TC: Tumour Core</span>
              {hasVolumes && onToggleLayer && (
                <button
                  type="button"
                  onClick={() => onToggleLayer('TC')}
                  title={layerVisibility?.TC ? 'Hide Tumour Core in viewers' : 'Show Tumour Core in viewers'}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: layerVisibility?.TC ? '#FEF2F2' : '#F1F5F9',
                    border: '1px solid',
                    borderColor: layerVisibility?.TC ? '#FECACA' : '#CBD5E1',
                    borderRadius: '3px',
                    padding: '2px 4px',
                    cursor: 'pointer',
                    color: layerVisibility?.TC ? '#DC2626' : '#94A3B8',
                  }}
                >
                  {layerVisibility?.TC ? <Eye size={12} /> : <EyeOff size={12} />}
                </button>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              {hasVolumes && (
                <span
                  style={{
                    padding: '1px 5px',
                    borderRadius: '2px',
                    fontSize: '9px',
                    fontWeight: 700,
                    letterSpacing: '0.04em',
                    backgroundColor: tc?.voxel_count > 0 ? '#ECFDF5' : '#F8FAFC',
                    color: tc?.voxel_count > 0 ? '#065F46' : '#64748B',
                    border: '1px solid',
                    borderColor: tc?.voxel_count > 0 ? '#A7F3D0' : '#E2E8F0',
                  }}
                >
                  {tc?.measurement_status ? tc.measurement_status.replace('_', ' ').toUpperCase() : (tc?.voxel_count > 0 ? 'VALID' : 'EMPTY')}
                </span>
              )}
              <span className="metric-val-num">
                {hasVolumes && tc?.volume_ml !== undefined ? tc.volume_ml.toFixed(1) : '--'}{' '}
                <span className="metric-val-unit">mL</span>
              </span>
            </div>
          </div>
          <div
            className="font-mono"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '11px',
              color: 'var(--on-surface-variant)',
              marginTop: '2px'
            }}
          >
            <span>Voxels: <b>{hasVolumes && tc?.voxel_count !== undefined ? tc.voxel_count.toLocaleString() : '--'}</b> ({hasVolumes ? `${(tc?.voxel_volume_mm3 ?? voxelVolMm3).toFixed(2)} mm³` : '--'})</span>
            <span>Ratio WT: <b>{hasVolumes ? `${tcRatio}%` : '--'}</b></span>
          </div>
          {hasVolumes && (
            <div
              className="font-mono"
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: '10px',
                color: 'var(--on-surface-variant)',
                marginTop: '4px',
                paddingTop: '3px',
                borderTop: '1px dashed #E2E8F0'
              }}
            >
              <span>Centroid:</span>
              {tc?.centroid_voxel ? (
                <button
                  type="button"
                  onClick={() => onSelectCentroid && onSelectCentroid(tc.centroid_voxel)}
                  title={`Jump crosshair to TC centroid [${tc.centroid_voxel.join(', ')}]`}
                  style={{
                    border: '1px solid #FECACA',
                    background: '#FEF2F2',
                    color: '#DC2626',
                    padding: '1px 6px',
                    borderRadius: '3px',
                    cursor: 'pointer',
                    fontWeight: 600,
                    fontSize: '10px'
                  }}
                >
                  [{tc.centroid_voxel.join(', ')}]
                </button>
              ) : (
                <span style={{ color: '#94A3B8' }}>None (0 voxels)</span>
              )}
            </div>
          )}
        </div>

        {/* Enhancing Tumour (ET) */}
        <div className="metric-card-solid">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span className="metric-chip-et">ET: Enhancing Tumour</span>
              {hasVolumes && onToggleLayer && (
                <button
                  type="button"
                  onClick={() => onToggleLayer('ET')}
                  title={layerVisibility?.ET ? 'Hide Enhancing Tumour in viewers' : 'Show Enhancing Tumour in viewers'}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: layerVisibility?.ET ? '#FEFCE8' : '#F1F5F9',
                    border: '1px solid',
                    borderColor: layerVisibility?.ET ? '#FEF08A' : '#CBD5E1',
                    borderRadius: '3px',
                    padding: '2px 4px',
                    cursor: 'pointer',
                    color: layerVisibility?.ET ? '#CA8A04' : '#94A3B8',
                  }}
                >
                  {layerVisibility?.ET ? <Eye size={12} /> : <EyeOff size={12} />}
                </button>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              {hasVolumes && (
                <span
                  style={{
                    padding: '1px 5px',
                    borderRadius: '2px',
                    fontSize: '9px',
                    fontWeight: 700,
                    letterSpacing: '0.04em',
                    backgroundColor: et?.voxel_count > 0 ? '#ECFDF5' : '#F8FAFC',
                    color: et?.voxel_count > 0 ? '#065F46' : '#64748B',
                    border: '1px solid',
                    borderColor: et?.voxel_count > 0 ? '#A7F3D0' : '#E2E8F0',
                  }}
                >
                  {et?.measurement_status ? et.measurement_status.replace('_', ' ').toUpperCase() : (et?.voxel_count > 0 ? 'VALID' : 'EMPTY')}
                </span>
              )}
              <span className="metric-val-num">
                {hasVolumes && et?.volume_ml !== undefined ? et.volume_ml.toFixed(1) : '--'}{' '}
                <span className="metric-val-unit">mL</span>
              </span>
            </div>
          </div>
          <div
            className="font-mono"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '11px',
              color: 'var(--on-surface-variant)',
              marginTop: '2px'
            }}
          >
            <span>Voxels: <b>{hasVolumes && et?.voxel_count !== undefined ? et.voxel_count.toLocaleString() : '--'}</b> ({hasVolumes ? `${(et?.voxel_volume_mm3 ?? voxelVolMm3).toFixed(2)} mm³` : '--'})</span>
            <span>Active Margin</span>
          </div>
          {hasVolumes && (
            <div
              className="font-mono"
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: '10px',
                color: 'var(--on-surface-variant)',
                marginTop: '4px',
                paddingTop: '3px',
                borderTop: '1px dashed #E2E8F0'
              }}
            >
              <span>Centroid:</span>
              {et?.centroid_voxel ? (
                <button
                  type="button"
                  onClick={() => onSelectCentroid && onSelectCentroid(et.centroid_voxel)}
                  title={`Jump crosshair to ET centroid [${et.centroid_voxel.join(', ')}]`}
                  style={{
                    border: '1px solid #FEF08A',
                    background: '#FEFCE8',
                    color: '#CA8A04',
                    padding: '1px 6px',
                    borderRadius: '3px',
                    cursor: 'pointer',
                    fontWeight: 600,
                    fontSize: '10px'
                  }}
                >
                  [{et.centroid_voxel.join(', ')}]
                </button>
              ) : (
                <span style={{ color: '#94A3B8' }}>None (0 voxels)</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Formula Display Card */}
      <div className="formula-strip" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <span style={{ fontWeight: 700, color: 'var(--on-surface-variant)', fontSize: '10px' }}>FORMULA:</span>
          <span className="font-mono" style={{ fontSize: '10px' }}>{activeFormula}</span>
        </div>
        <span className="font-mono" style={{ fontSize: '9px', color: 'var(--on-surface-variant)' }}>
          WT ≥ TC ≥ ET
        </span>
      </div>
    </section>
  );
}
