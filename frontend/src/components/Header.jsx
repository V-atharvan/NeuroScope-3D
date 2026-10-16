import React from 'react';

export default function Header({ backendHealth }) {
  const isHealthy = backendHealth && backendHealth.status === 'healthy';
  const modelLoaded = backendHealth?.model_readiness?.loaded;

  return (
    <header className="header-bar glass-panel">
      <div className="brand">
        <div className="brand-icon">N3D</div>
        <div>
          <h1 className="brand-title">NeuroScope 3D</h1>
          <p className="brand-subtitle">Multi-Sequence Brain MRI 3D Segmentation Platform</p>
        </div>
      </div>
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <div className="status-badge">
          <span className={`status-dot ${isHealthy ? '' : 'disconnected'}`}></span>
          <span>{isHealthy ? 'Backend Connected' : 'Connecting to API...'}</span>
        </div>
        {isHealthy && (
          <div className="status-badge" style={{ fontSize: '0.75rem' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Model:</span>
            <span className="mono-val">{backendHealth.model_readiness.model_name}</span>
            <span style={{ color: modelLoaded ? 'var(--accent-green)' : 'var(--accent-amber)' }}>
              ({modelLoaded ? 'Ready' : 'Scaffold/Standby'})
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
