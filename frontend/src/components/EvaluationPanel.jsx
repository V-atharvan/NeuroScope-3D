import React from 'react';
import { Award, ShieldAlert, Info } from 'lucide-react';

export default function EvaluationPanel({ evaluation, benchmarkReference, provenance }) {
  const hasCaseEval = evaluation && evaluation.available && evaluation.metrics;
  const metrics = evaluation?.metrics || {};

  return (
    <div className="glass-panel">
      <div className="panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Award size={18} style={{ color: 'var(--accent-purple)' }} />
          <h2 className="panel-title">3. Model Evaluation & Audit Provenance</h2>
        </div>
        <span className="mono-val" style={{ fontSize: '0.75rem' }}>BraTS 2021 Metrics</span>
      </div>

      <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Case-specific Evaluation against Expert Mask */}
        <div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '8px', color: 'var(--text-primary)' }}>
            Case-Specific Comparison (Against Uploaded Expert Mask)
          </div>

          {hasCaseEval ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
              {['WT', 'TC', 'ET'].map((reg) => (
                <div
                  key={reg}
                  style={{
                    padding: '10px',
                    background: 'rgba(0, 0, 0, 0.25)',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                    Region: {reg}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px', fontSize: '0.8rem' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Dice (DSC):</span>
                    <span className="mono-val">{metrics[reg]?.dice !== undefined ? metrics[reg].dice.toFixed(4) : '--'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Sensitivity:</span>
                    <span className="mono-val">{metrics[reg]?.sensitivity !== undefined ? metrics[reg].sensitivity.toFixed(4) : '--'}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div
              style={{
                padding: '12px',
                background: 'rgba(255, 255, 255, 0.03)',
                borderRadius: 'var(--radius-sm)',
                border: '1px dashed var(--border-subtle)',
                fontSize: '0.8rem',
                color: 'var(--text-secondary)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <Info size={16} style={{ color: 'var(--accent-amber)', flexShrink: 0 }} />
              <span>
                <strong>Case metrics unavailable:</strong> {evaluation?.reason || 'Expert mask was not provided with this study upload.'} No per-case Dice or sensitivity was fabricated.
              </span>
            </div>
          )}
        </div>

        {/* Population Held-Out Benchmark Reference */}
        <div
          style={{
            padding: '12px',
            background: 'rgba(0, 0, 0, 0.2)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
            fontSize: '0.75rem',
          }}
        >
          <div style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
            Reference Held-Out Validation Benchmark (MONAI SegResNet)
          </div>
          <div style={{ display: 'flex', gap: '16px', color: 'var(--text-primary)', margin: '4px 0' }}>
            <span>Whole Tumour (WT): <strong>0.9026</strong></span>
            <span>Tumour Core (TC): <strong>0.8559</strong></span>
            <span>Enhancing Tumour (ET): <strong>0.7905</strong></span>
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
            {benchmarkReference?.disclaimer || 'Held-out benchmark metrics are aggregate population references and do not validate individual patient cases.'}
          </div>
        </div>

        {/* Provenance Metadata Table */}
        {provenance && (
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            <div>Model: <span className="mono-val">{provenance.model_name}</span> ({provenance.model_license})</div>
            <div>Training Source: {provenance.training_data_source}</div>
            <div>Execution Commit: <span className="mono-val">{provenance.git_commit}</span></div>
          </div>
        )}
      </div>
    </div>
  );
}
