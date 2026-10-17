import React, { useState } from 'react';
import { RefreshCw, UserCheck, Activity, Info, X } from 'lucide-react';

export default function Header({
  backendHealth,
  activeTab,
  onTabChange,
  onResetStudy,
  hasValidationErrors
}) {
  const [showMobileTelemetry, setShowMobileTelemetry] = useState(false);
  const isHealthy = backendHealth && backendHealth.status === 'healthy';
  const modelLoaded = backendHealth?.model_readiness?.loaded;
  const commitId = backendHealth?.commit_id ? `#${backendHealth.commit_id.substring(0, 7)}` : '#main';

  return (
    <>
      <header className="app-header-container">
        {/* Main 64px Header Bar */}
        <div className="app-header-main">
          {/* Brand Section */}
          <div className="brand-section">
            <div className="brand-logo-icon">NS</div>
            <div className="brand-meta">
              <span className="brand-title">NeuroScope 3D</span>
            </div>
          </div>

          {/* Right Telemetry & Operator Section */}
          <div className="header-telemetry">
            {/* Desktop Pills */}
            <div className="telemetry-pill desktop-only">
              <span className={isHealthy ? 'status-dot-pulse' : 'status-dot-offline'} />
              <span>{isHealthy ? 'FastAPI Connected' : 'Connecting API...'}</span>
            </div>

            <div className="telemetry-pill desktop-only" style={{ backgroundColor: 'var(--surface-container-high)', fontWeight: 600 }}>
              {modelLoaded ? 'SegResNet Ready' : 'Model Standby'}
            </div>

            <div className="telemetry-pill desktop-only" style={{ color: 'var(--on-surface-variant)' }}>
              {commitId}
            </div>

            {/* Reset Study Button (Responsive) */}
            {onResetStudy && (
              <button
                type="button"
                className="header-nav-btn header-reset-btn"
                onClick={onResetStudy}
                title="Reset current study and clear viewports"
                aria-label="Reset current study"
              >
                <RefreshCw size={13} />
                <span className="desktop-inline">Reset Study</span>
              </button>
            )}

            <div className="header-divider desktop-only" style={{ height: '20px', width: '1px', backgroundColor: 'var(--outline-variant)' }} />

            {/* Real Session / User Role */}
            <div
              className="doctor-profile"
              onClick={() => setShowMobileTelemetry((prev) => !prev)}
              role="button"
              tabIndex={0}
              title="Session details & system telemetry"
            >
              <div className="doctor-profile-text desktop-only" style={{ textAlign: 'right', display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--on-surface-dark)', lineHeight: 1.2 }}>
                  Dr. Elena Rostova
                </span>
                <span style={{ fontSize: '10px', color: 'var(--on-surface-variant)', fontFamily: 'var(--font-mono)' }}>
                  Lead Neuro-Radiologist
                </span>
              </div>
              <div className="doctor-avatar">
                <span className={`mobile-status-dot ${isHealthy ? 'pulse-green' : 'pulse-red'}`} />
                <UserCheck size={16} />
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile Telemetry & Session Drawer / Modal */}
      {showMobileTelemetry && (
        <div className="mobile-telemetry-backdrop" onClick={() => setShowMobileTelemetry(false)}>
          <div className="mobile-telemetry-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="mobile-telemetry-header">
              <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--on-surface-dark)' }}>
                System Telemetry & Session
              </span>
              <button
                type="button"
                className="icon-btn-close"
                onClick={() => setShowMobileTelemetry(false)}
                aria-label="Close telemetry"
              >
                <X size={18} />
              </button>
            </div>

            <div className="mobile-telemetry-body">
              <div className="mobile-telemetry-row">
                <span className="telemetry-label">Backend Connection</span>
                <span className="telemetry-value">
                  <span className={isHealthy ? 'status-dot-pulse' : 'status-dot-offline'} />
                  {isHealthy ? 'FastAPI 0.115.0 Connected' : 'Connecting to API...'}
                </span>
              </div>

              <div className="mobile-telemetry-row">
                <span className="telemetry-label">Inference Engine</span>
                <span className="telemetry-value font-mono">
                  {modelLoaded ? 'MONAI SegResNet Ready' : 'Model Standby'}
                </span>
              </div>

              <div className="mobile-telemetry-row">
                <span className="telemetry-label">Build Version</span>
                <span className="telemetry-value font-mono">{commitId}</span>
              </div>

              <div className="mobile-telemetry-row">
                <span className="telemetry-label">Session Station</span>
                <span className="telemetry-value">Authorized Clinical Researcher</span>
              </div>

              {/* Quick links to Cohort and Diagnostics for mobile users */}
              <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <button
                  type="button"
                  className="mobile-drawer-btn"
                  onClick={() => {
                    onTabChange('cohort');
                    setShowMobileTelemetry(false);
                  }}
                >
                  View Held-Out Cohort (10-Case Benchmark)
                </button>
                <button
                  type="button"
                  className="mobile-drawer-btn"
                  onClick={() => {
                    onTabChange('diagnostics');
                    setShowMobileTelemetry(false);
                  }}
                >
                  View Pre-Inference Case Diagnostics
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
