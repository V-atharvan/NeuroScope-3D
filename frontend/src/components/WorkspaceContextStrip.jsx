import React from 'react';
import { CheckCircle2, Clock } from 'lucide-react';

export default function WorkspaceContextStrip({
  caseId,
  spatialMetadata,
  backendHealth
}) {
  const hasCase = Boolean(caseId);
  const shape = spatialMetadata?.dimensions || spatialMetadata?.shape;
  const spacing = spatialMetadata?.voxel_spacing_mm || spatialMetadata?.spacing_mm;
  const spacingText = Array.isArray(spacing) ? `${spacing[0].toFixed(1)} mm` : null;

  const modelLoaded = backendHealth?.model_readiness?.loaded;

  return (
    <div className="context-strip mobile-scrollable-strip">
      <div className="context-left">
        <span className="context-subject-pill">
          <span
            style={{
              width: 6,
              height: 6,
              backgroundColor: hasCase ? 'var(--primary-accent)' : 'var(--outline)',
              display: 'inline-block'
            }}
          />
          SUBJECT: {hasCase ? caseId : 'Standby (Awaiting Ingestion)'}
        </span>
        <span style={{ fontSize: '12px', color: 'var(--on-surface-variant)' }}>
          Modality:{' '}
          <strong style={{ color: 'var(--on-surface-dark)', fontWeight: 600 }}>
            {hasCase ? 'mpMRI (T1, T1CE, T2, FLAIR)' : '--'}
          </strong>
        </span>
        <span style={{ fontSize: '12px', color: 'var(--on-surface-variant)' }}>
          Voxel Grid:{' '}
          {shape ? (
            <strong className="font-mono" style={{ color: 'var(--on-surface-dark)' }}>
              {shape.join(' × ')} ({spacingText || '1.0 mm'} isotropic)
            </strong>
          ) : (
            <span className="font-mono">--</span>
          )}
        </span>
      </div>

      <div className="context-right">
        <span style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 600, color: 'var(--on-surface-variant)' }}>
          Engine:
        </span>
        <span
          className="font-mono"
          style={{
            fontSize: '11px',
            backgroundColor: 'var(--surface-container)',
            border: '1px solid var(--border-structural)',
            padding: '2px 8px',
            borderRadius: '2px',
            color: 'var(--on-surface-dark)'
          }}
        >
          MONAI SegResNet
        </span>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            padding: '2px 8px',
            backgroundColor: modelLoaded ? 'var(--surface-container-low)' : 'var(--surface-container)',
            color: modelLoaded ? 'var(--primary-accent)' : 'var(--on-surface-variant)',
            border: `1px solid ${modelLoaded ? 'var(--secondary-blue)' : 'var(--border-structural)'}`,
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            fontWeight: 600,
            borderRadius: '2px'
          }}
        >
          {modelLoaded ? <CheckCircle2 size={13} /> : <Clock size={13} />}
          <span>{modelLoaded ? 'Pipeline Active' : 'Pipeline Standby'}</span>
        </span>
      </div>
    </div>
  );
}
