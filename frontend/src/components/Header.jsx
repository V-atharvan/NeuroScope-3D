import React from 'react';
import { RefreshCw, UserCheck } from 'lucide-react';

export default function Header({
  backendHealth,
  activeTab,
  onTabChange,
  onResetStudy,
  hasValidationErrors
}) {
  const isHealthy = backendHealth && backendHealth.status === 'healthy';
  const modelLoaded = backendHealth?.model_readiness?.loaded;
  const commitId = backendHealth?.commit_id ? `#${backendHealth.commit_id.substring(0, 7)}` : '#main';

  return (
    <header className="app-header">
      {/* Brand Section */}
      <div className="brand-section">
        <div className="brand-logo-icon">NS</div>
        <div className="brand-meta">
          <span className="brand-title">NeuroScope 3D</span>
          <span className="brand-subtitle">MONAI SegResNet Multimodal Brain MRI Pipeline</span>
        </div>
      </div>

      {/* Center View Navigation Tabs */}
      <nav className="header-nav">
        <button
          type="button"
          className={`header-nav-btn ${activeTab === 'workstation' ? 'active' : ''}`}
          onClick={() => onTabChange('workstation')}
        >
          Workstation (Multiplanar)
        </button>

        <button
          type="button"
          className={`header-nav-btn ${activeTab === 'audit' ? 'active' : ''}`}
          onClick={() => onTabChange('audit')}
        >
          Provenance & Audit Report
        </button>

        <button
          type="button"
          className={`header-nav-btn ${activeTab === 'trust' ? 'active' : ''}`}
          onClick={() => onTabChange('trust')}
        >
          AI Trust & Longitudinal
        </button>

        <button
          type="button"
          className={`header-nav-btn ${activeTab === 'cohort' ? 'active' : ''}`}
          onClick={() => onTabChange('cohort')}
        >
          Held-Out Cohort (10-Case)
        </button>

        <button
          type="button"
          className={`header-nav-btn ${activeTab === 'diagnostics' ? 'active' : ''}`}
          onClick={() => onTabChange('diagnostics')}
          style={{ position: 'relative' }}
        >
          Case Validation (Diagnostics)
          {hasValidationErrors && (
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                backgroundColor: 'var(--error-red)',
                display: 'inline-block'
              }}
            />
          )}
        </button>
      </nav>

      {/* Right Telemetry & Operator Section */}
      <div className="header-telemetry">
        <div className="telemetry-pill">
          <span className={isHealthy ? 'status-dot-pulse' : 'status-dot-offline'} />
          <span>{isHealthy ? 'FastAPI Connected' : 'Connecting API...'}</span>
        </div>

        <div className="telemetry-pill" style={{ backgroundColor: 'var(--surface-container-high)', fontWeight: 600 }}>
          {modelLoaded ? 'SegResNet Ready' : 'Model Standby'}
        </div>

        <div className="telemetry-pill" style={{ color: 'var(--on-surface-variant)' }}>
          {commitId}
        </div>

        {onResetStudy && (
          <button
            type="button"
            className="header-nav-btn"
            style={{
              border: '1px solid var(--outline-variant)',
              backgroundColor: 'var(--surface-card)',
              fontSize: '11px',
              padding: '4px 8px'
            }}
            onClick={onResetStudy}
            title="Reset current study and clear viewports"
          >
            <RefreshCw size={12} />
            <span>Reset Study</span>
          </button>
        )}

        <div style={{ height: '20px', width: '1px', backgroundColor: 'var(--outline-variant)' }} />

        {/* Real Session / User Role */}
        <div className="doctor-profile">
          <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--on-surface-dark)', lineHeight: 1.2 }}>
              Research Station
            </span>
            <span style={{ fontSize: '10px', color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}>
              Authorized Session
            </span>
          </div>
          <div className="doctor-avatar">
            <UserCheck size={16} />
          </div>
        </div>
      </div>
    </header>
  );
}
