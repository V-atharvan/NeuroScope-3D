import React, { useState } from 'react';
import { Award, BarChart2, Info, UploadCloud, CheckCircle2, AlertTriangle, Layers, ArrowRight } from 'lucide-react';
import { uploadExpertMask } from '../services/api';

export default function EvaluationPanel({
  caseId,
  evaluation,
  benchmarkReference,
  volumes,
  onExpertMaskUploaded,
  onActivateAgreementLens
}) {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [selectedRegion, setSelectedRegion] = useState('WT');

  const hasCaseEval = Boolean(evaluation && evaluation.available && evaluation.metrics);
  const metrics = evaluation?.metrics || {};

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !caseId) return;

    setIsUploading(true);
    setUploadError(null);
    try {
      const result = await uploadExpertMask(caseId, file);
      if (onExpertMaskUploaded) {
        onExpertMaskUploaded(result);
      }
    } catch (err) {
      setUploadError(err.message || 'Failed to upload expert reference mask.');
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  const meanBenchmark = benchmarkReference?.mean_dice
    ? ((benchmarkReference.mean_dice.WT + benchmarkReference.mean_dice.TC + benchmarkReference.mean_dice.ET) / 3).toFixed(3)
    : null;

  const regions = [
    { key: 'WT', name: 'Whole Tumour (WT)', labels: 'Labels 1, 2, 4', colorClass: 'wt' },
    { key: 'TC', name: 'Tumour Core (TC)', labels: 'Labels 1, 4', colorClass: 'tc' },
    { key: 'ET', name: 'Enhancing Tumour (ET)', labels: 'Label 4', colorClass: 'et' },
  ];

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div className="clinical-section-header">
        <h2 className="section-title-text" style={{ display: 'flex', alignItems: 'center' }}>
          <span className="section-number-badge">3</span>
          Expert Comparison & Agreement
        </h2>
        <span
          className="font-mono"
          style={{
            fontSize: '11px',
            color: hasCaseEval ? '#10B981' : 'var(--on-surface-variant)',
            fontWeight: hasCaseEval ? 700 : 500,
          }}
        >
          {hasCaseEval ? 'REFERENCE ACTIVE' : 'NO EXPERT MASK'}
        </span>
      </div>

      {hasCaseEval ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {/* Quick Agreement Lens Action Banner */}
          {onActivateAgreementLens && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '6px 10px',
                backgroundColor: '#0F172A',
                border: '1px solid #1E293B',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Layers size={13} color="#38BDF8" />
                <span style={{ fontSize: '11px', color: '#E2E8F0', fontWeight: 600 }}>Agreement Lens</span>
              </div>
              <div style={{ display: 'flex', gap: '4px' }}>
                {['WT', 'TC', 'ET'].map((reg) => (
                  <button
                    key={reg}
                    type="button"
                    onClick={() => {
                      setSelectedRegion(reg);
                      onActivateAgreementLens(reg);
                    }}
                    title={`Inspect ${reg} consensus in Agreement Lens`}
                    style={{
                      padding: '2px 7px',
                      fontSize: '10px',
                      fontWeight: selectedRegion === reg ? 700 : 500,
                      backgroundColor: selectedRegion === reg ? 'var(--primary-accent)' : '#1E293B',
                      color: selectedRegion === reg ? '#FFFFFF' : '#94A3B8',
                      border: '1px solid',
                      borderColor: selectedRegion === reg ? 'var(--primary-accent)' : '#334155',
                      borderRadius: '3px',
                      cursor: 'pointer',
                    }}
                  >
                    View {reg}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Region Metric Comparison Cards */}
          {regions.map((reg) => {
            const m = metrics[reg.key] || {};
            const predVol = m.predicted_volume_ml ?? volumes?.[reg.key]?.volume_ml;
            const refVol = m.reference_volume_ml;
            const signedDiff = m.signed_diff_ml;
            const absDiff = m.absolute_diff_ml;
            const relDiff = m.relative_diff_percent;
            const dsc = m.dice;
            const sens = m.sensitivity;
            const hd95 = m.hd95_mm;

            const dscFormatted = dsc !== undefined && dsc !== null ? dsc.toFixed(3) : 'N/A';
            const sensFormatted = sens !== undefined && sens !== null ? sens.toFixed(3) : 'N/A';
            const hd95Formatted = hd95 !== undefined && hd95 !== null ? `${hd95.toFixed(1)} mm` : 'N/A';

            return (
              <div
                key={reg.key}
                className="dice-eval-card"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                  padding: '8px 10px',
                  backgroundColor: 'var(--surface-container-lowest)',
                  border: '1px solid var(--border-structural)',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                {/* Header: Region name + Dice */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontWeight: 600, fontSize: '12px', color: 'var(--on-surface-dark)' }}>
                      {reg.name}
                    </span>
                    <span style={{ fontSize: '9px', color: 'var(--on-surface-variant)', fontFamily: 'monospace' }}>
                      {reg.labels}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className="font-mono" style={{ fontSize: '12px', fontWeight: 700, color: 'var(--on-surface-dark)' }}>
                      Dice: {dscFormatted}
                    </span>
                  </div>
                </div>

                {/* Progress bar for Dice */}
                <div className="progress-trough" style={{ height: '5px' }}>
                  <div
                    className={`progress-fill-${reg.colorClass}`}
                    style={{ width: `${Math.min(100, (dsc || 0) * 100)}%` }}
                  />
                </div>

                {/* Volumetric Comparison Row: Pred vs Ref vs Delta */}
                <div
                  className="font-mono"
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(4, 1fr)',
                    gap: '4px',
                    fontSize: '10px',
                    backgroundColor: 'var(--surface-container-low)',
                    padding: '4px 6px',
                    borderRadius: '3px',
                    marginTop: '2px',
                  }}
                >
                  <div>
                    <div style={{ color: 'var(--on-surface-variant)', fontSize: '9px' }}>PREDICTED</div>
                    <div style={{ fontWeight: 600, color: 'var(--on-surface-dark)' }}>
                      {predVol !== undefined ? `${predVol.toFixed(1)} mL` : '--'}
                    </div>
                  </div>

                  <div>
                    <div style={{ color: 'var(--on-surface-variant)', fontSize: '9px' }}>REFERENCE</div>
                    <div style={{ fontWeight: 600, color: 'var(--on-surface-dark)' }}>
                      {refVol !== undefined ? `${refVol.toFixed(1)} mL` : '--'}
                    </div>
                  </div>

                  <div>
                    <div style={{ color: 'var(--on-surface-variant)', fontSize: '9px' }}>DIFF (ΔV)</div>
                    <div
                      style={{
                        fontWeight: 600,
                        color: signedDiff > 0 ? '#EF4444' : signedDiff < 0 ? '#8B5CF6' : '#10B981',
                      }}
                    >
                      {signedDiff !== undefined && signedDiff !== null
                        ? `${signedDiff > 0 ? '+' : ''}${signedDiff.toFixed(1)} mL`
                        : '--'}
                    </div>
                  </div>

                  <div>
                    <div style={{ color: 'var(--on-surface-variant)', fontSize: '9px' }}>REL DIFF</div>
                    <div style={{ fontWeight: 600, color: 'var(--on-surface-dark)' }}>
                      {relDiff !== undefined && relDiff !== null ? `${relDiff > 0 ? '+' : ''}${relDiff.toFixed(1)}%` : 'N/A'}
                    </div>
                  </div>
                </div>

                {/* Metrics Breakdown: Sensitivity + HD95 + Voxel Counts */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: '10px',
                    color: 'var(--on-surface-variant)',
                    marginTop: '2px',
                    flexWrap: 'wrap',
                    gap: '4px',
                  }}
                >
                  <span>
                    Sens: <b style={{ color: 'var(--on-surface-dark)' }}>{sensFormatted}</b> • HD95:{' '}
                    <b style={{ color: 'var(--on-surface-dark)' }}>{hd95Formatted}</b>
                  </span>

                  {/* Confusion breakdown chips */}
                  <div style={{ display: 'flex', gap: '4px', fontFamily: 'monospace', fontSize: '9px' }}>
                    <span
                      title="True Positive voxels (Concordant agreement)"
                      style={{
                        backgroundColor: '#ECFDF5',
                        color: '#065F46',
                        border: '1px solid #A7F3D0',
                        padding: '1px 4px',
                        borderRadius: '2px',
                      }}
                    >
                      TP: {m.tp_voxels?.toLocaleString() ?? '--'}
                    </span>
                    <span
                      title="False Positive voxels (Prediction only / Over-segmentation)"
                      style={{
                        backgroundColor: '#FEF2F2',
                        color: '#991B1B',
                        border: '1px solid #FECACA',
                        padding: '1px 4px',
                        borderRadius: '2px',
                      }}
                    >
                      FP: {m.fp_voxels?.toLocaleString() ?? '--'}
                    </span>
                    <span
                      title="False Negative voxels (Reference only / Missed)"
                      style={{
                        backgroundColor: '#F5F3FF',
                        color: '#5B21B6',
                        border: '1px solid #DDD6FE',
                        padding: '1px 4px',
                        borderRadius: '2px',
                      }}
                    >
                      FN: {m.fn_voxels?.toLocaleString() ?? '--'}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}

          {/* Research Disclosure Notice */}
          <div
            style={{
              padding: '6px 8px',
              backgroundColor: 'var(--surface-container-low)',
              border: '1px solid var(--border-structural)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '10px',
              color: 'var(--on-surface-variant)',
              lineHeight: 1.35,
            }}
          >
            <b>Notice on Reference Agreement:</b> Concordance metrics reflect geometric contour overlap with the provided expert annotation. Agreement does not guarantee clinical diagnosis or absolute biological truth.
          </div>
        </div>
      ) : (
        <div
          style={{
            backgroundColor: 'var(--surface-container-low)',
            border: '1px solid var(--border-structural)',
            padding: '10px 12px',
            borderRadius: 'var(--radius-sm)',
            fontSize: '11px',
            color: 'var(--on-surface-variant)',
            lineHeight: 1.4,
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, color: 'var(--on-surface-dark)' }}>
            <Info size={14} style={{ color: 'var(--primary-accent)' }} />
            <span>No Expert Reference Mask Supplied</span>
          </div>
          <p style={{ margin: 0 }}>
            Upload an expert segmentation mask (<code className="font-mono">_seg.nii.gz</code>) to compute Dice, sensitivity, volumetric deltas (ΔV), and activate the Agreement Lens.
          </p>

          {caseId && (
            <div style={{ marginTop: '4px' }}>
              <label
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '5px 10px',
                  backgroundColor: 'var(--primary-accent)',
                  color: '#FFFFFF',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: isUploading ? 'not-allowed' : 'pointer',
                  opacity: isUploading ? 0.7 : 1,
                }}
              >
                <UploadCloud size={14} />
                <span>{isUploading ? 'Validating Expert Mask...' : 'Upload Reference Mask (.nii.gz)'}</span>
                <input
                  type="file"
                  accept=".nii,.nii.gz,application/gzip"
                  onChange={handleFileUpload}
                  disabled={isUploading}
                  style={{ display: 'none' }}
                />
              </label>

              {uploadError && (
                <div style={{ marginTop: '6px', color: '#DC2626', fontSize: '10px', fontWeight: 500 }}>
                  {uploadError}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Held-out Aggregate Benchmark Reference */}
      <div className="benchmark-summary-box" style={{ marginTop: '4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, color: '#0F172A' }}>
          <BarChart2 size={14} style={{ color: 'var(--primary-accent)' }} />
          <span>{benchmarkReference?.dataset ? `${benchmarkReference.dataset}:` : 'Model Validation Benchmark:'}</span>
        </div>
        <span style={{ fontWeight: 700, color: 'var(--primary-accent)' }}>
          {meanBenchmark ? `${meanBenchmark} Mean Dice` : '-- Mean Dice'}
        </span>
      </div>
    </section>
  );
}
