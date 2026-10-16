import React, { useState } from 'react';

export default function Dashboard({ backendHealth }) {
  const [selectedSequences, setSelectedSequences] = useState({
    t1: null,
    t1gd: null,
    t2: null,
    flair: null,
    expert_mask: null,
  });

  const handleFileChange = (seq, file) => {
    setSelectedSequences((prev) => ({
      ...prev,
      [seq]: file,
    }));
  };

  return (
    <main className="dashboard-grid">
      {/* Left Column: Study Ingestion & Controls */}
      <section className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="panel-header">
          <h2 className="panel-title">1. Study Input (4 Sequences)</h2>
          <span className="mono-val" style={{ fontSize: '0.75rem' }}>BraTS 2021 Format</span>
        </div>
        <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary)' }}>
            Upload co-registered NIfTI sequences (.nii or .nii.gz, max 1GB per file).
          </p>

          {[
            { id: 't1', label: 'T1-Weighted Sequence', req: true },
            { id: 't1gd', label: 'T1-Contrast (Gd / T1CE)', req: true },
            { id: 't2', label: 'T2-Weighted Sequence', req: true },
            { id: 'flair', label: 'FLAIR Sequence', req: true },
            { id: 'expert_mask', label: 'Expert Mask (Optional Ground Truth)', req: false },
          ].map((item) => (
            <div key={item.id} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-primary)' }}>
                {item.label} {item.req ? <span style={{ color: 'var(--accent-red)' }}>*</span> : <span style={{ color: 'var(--text-muted)' }}>(Optional)</span>}
              </label>
              <input
                type="file"
                accept=".nii,.nii.gz"
                onChange={(e) => handleFileChange(item.id, e.target.files?.[0] || null)}
                style={{
                  fontSize: '0.75rem',
                  padding: '6px 8px',
                  background: 'rgba(0, 0, 0, 0.3)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  color: 'var(--text-secondary)',
                }}
              />
            </div>
          ))}

          <button
            className="btn btn-primary"
            style={{ marginTop: '8px', width: '100%' }}
            disabled={!selectedSequences.t1 || !selectedSequences.t1gd || !selectedSequences.t2 || !selectedSequences.flair}
            onClick={() => alert('Backend upload pipeline scaffolded. Feature implementation on feature/backend branch.')}
          >
            Validate & Segment Study
          </button>
        </div>
      </section>

      {/* Right Column: Visualization & Quantitative Metrics Placeholder */}
      <section style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* NiiVue Viewer Canvas Mount Panel */}
        <div className="glass-panel" style={{ minHeight: '380px', display: 'flex', flexDirection: 'column' }}>
          <div className="panel-header">
            <h2 className="panel-title">2. NiiVue 3D & Linked Multi-Planar Viewer</h2>
            <div style={{ display: 'flex', gap: '8px' }}>
              <span className="status-badge" style={{ padding: '2px 8px', fontSize: '0.75rem' }}>Axial</span>
              <span className="status-badge" style={{ padding: '2px 8px', fontSize: '0.75rem' }}>Coronal</span>
              <span className="status-badge" style={{ padding: '2px 8px', fontSize: '0.75rem' }}>Sagittal</span>
              <span className="status-badge" style={{ padding: '2px 8px', fontSize: '0.75rem' }}>3D Mesh</span>
            </div>
          </div>
          <div className="panel-body" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '12px', background: 'rgba(0,0,0,0.4)', borderRadius: '0 0 var(--radius-md) var(--radius-md)' }}>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              NiiVue WebGL Canvas Target (Ready for mount in feature/frontend)
            </p>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center', maxWidth: '480px' }}>
              Displays multi-slice views with synchronized crosshairs, anatomical labels (L/R, A/P, S/I), and predicted BraTS region overlays.
            </div>
          </div>
        </div>

        {/* Quantitation & Verification Formula Card */}
        <div className="glass-panel">
          <div className="panel-header">
            <h2 className="panel-title">3. Volumetric Quantitation (Contract FR-6)</h2>
            <span className="mono-val" style={{ fontSize: '0.75rem' }}>Formula: V = N × sx × sy × sz / 1000</span>
          </div>
          <div className="panel-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div style={{ padding: '12px', background: 'rgba(0,0,0,0.25)', borderRadius: 'var(--radius-sm)', borderLeft: '3px solid var(--accent-red)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Whole Tumour (WT)</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, margin: '4px 0' }}>-- mL</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Labels 1, 2, 4 (NCR + ED + ET)</div>
            </div>
            <div style={{ padding: '12px', background: 'rgba(0,0,0,0.25)', borderRadius: 'var(--radius-sm)', borderLeft: '3px solid var(--accent-blue)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Tumour Core (TC)</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, margin: '4px 0' }}>-- mL</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Labels 1, 4 (NCR + ET)</div>
            </div>
            <div style={{ padding: '12px', background: 'rgba(0,0,0,0.25)', borderRadius: 'var(--radius-sm)', borderLeft: '3px solid var(--accent-amber)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Enhancing Tumour (ET)</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, margin: '4px 0' }}>-- mL</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Label 4 (ET)</div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
