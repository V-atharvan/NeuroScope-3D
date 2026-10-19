import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  UploadCloud,
  Eye,
  BarChart3,
  TrendingUp,
  Activity,
  FileText,
  Database,
  AlertCircle,
  Play,
  CheckCircle2,
  Clock,
  Layers,
  RefreshCw,
  Cpu,
  HardDrive,
  ShieldCheck,
  Flame
} from 'lucide-react';
import { getActiveCases, loadSampleStudy, triggerSegmentation, getCaseResults } from '../services/api';

export default function DashboardHome({
  activeCase,
  caseResults,
  backendHealth,
  onNavigateTab,
  onLoadSample,
  onCaseSelected,
  isProcessing = false
}) {
  const [recentCases, setRecentCases] = useState([]);
  const [loadingCases, setLoadingCases] = useState(false);
  const [localLoading, setLocalLoading] = useState(false);

  const effectiveCaseId = caseResults?.case_id || activeCase?.case_id;
  const isHealthy = backendHealth && backendHealth.status === 'healthy';
  const modelLoaded = backendHealth?.model_readiness?.loaded;
  const volumes = caseResults?.regions || activeCase?.volumes || activeCase?.regions;

  const fetchRecentCases = () => {
    setLoadingCases(true);
    getActiveCases()
      .then((res) => {
        setRecentCases(res.cases || []);
      })
      .catch((err) => {
        console.warn('Could not fetch cases for dashboard:', err.message);
      })
      .finally(() => {
        setLoadingCases(false);
      });
  };

  useEffect(() => {
    fetchRecentCases();
  }, [effectiveCaseId]);

  const handleQuickLoadSample = async () => {
    setLocalLoading(true);
    try {
      if (onLoadSample) {
        await onLoadSample();
      }
    } finally {
      setLocalLoading(false);
    }
  };

  return (
    <div className="bento-dashboard-canvas">
      {/* 1. HERO AREA */}
      <section className="bento-hero-card">
        <div className="bento-hero-content">
          <div className="bento-hero-badge stagger-item">
            <Sparkles size={14} className="text-primary-blue" />
            <span>CLINICAL AI WORKSPACE • BRAIN MRI QUANTIFICATION</span>
          </div>
          <h1 className="bento-hero-title stagger-item">
            NeuroScope 3D Multi-Parametric Pipeline
          </h1>
          <p className="bento-hero-description stagger-item">
            Automated deep-learning segmentation of brain tumours into Whole Tumour (WT), Tumour Core (TC),
            and Enhancing Tumour (ET) using MONAI SegResNet. Rigorous ISO 1.0mm³ physical volumetrics,
            Shannon entropy uncertainty profiling, and longitudinal RANO assessment.
          </p>

          <div className="bento-hero-actions stagger-item">
            <button
              type="button"
              className="btn-primary bento-action-btn"
              onClick={handleQuickLoadSample}
              disabled={isProcessing || localLoading}
            >
              {localLoading ? (
                <>
                  <RefreshCw size={15} className="spin" />
                  <span>Loading BraTS Sample...</span>
                </>
              ) : (
                <>
                  <Play size={15} fill="currentColor" />
                  <span>Load Sample BraTS Study</span>
                </>
              )}
            </button>

            <button
              type="button"
              className="btn-secondary bento-action-btn"
              onClick={() => onNavigateTab('upload')}
            >
              <UploadCloud size={15} />
              <span>Upload Patient Study</span>
            </button>

            <button
              type="button"
              className="btn-secondary bento-action-btn"
              onClick={() => onNavigateTab('workstation')}
            >
              <Eye size={15} />
              <span>Open 3D Workstation</span>
            </button>
          </div>
        </div>

        {/* Hero Right: Live Status Telemetry Pill Box */}
        <div className="bento-hero-status-box">
          <div className="bento-status-row">
            <span className="bento-status-label">Inference Engine:</span>
            <span className="bento-status-val font-mono">MONAI SegResNet v0.9.1</span>
          </div>
          <div className="bento-status-row">
            <span className="bento-status-label">API Backend:</span>
            <span className={`bento-status-badge ${isHealthy ? 'valid' : 'offline'}`}>
              <span className={`status-dot ${isHealthy ? 'online' : 'offline'}`} />
              {isHealthy ? 'FastAPI Connected' : 'Backend Connecting'}
            </span>
          </div>
          <div className="bento-status-row">
            <span className="bento-status-label">Model Weights:</span>
            <span className="bento-status-val">
              {modelLoaded ? 'SegResNet BraTS21 Ready' : 'Standby / Pre-loaded'}
            </span>
          </div>
          <div className="bento-status-row">
            <span className="bento-status-label">Voxel Calibration:</span>
            <span className="bento-status-val font-mono">1.0 × 1.0 × 1.0 mm (ISO)</span>
          </div>
        </div>
      </section>

      {/* 2. ACTIVE STUDY SUMMARY BENTO CARD */}
      <section className="bento-active-study-card">
        <div className="bento-card-header">
          <div className="bento-card-title-group">
            <Layers size={16} className="text-primary-blue" />
            <h2 className="bento-card-title">Active Study Summary</h2>
          </div>
          <span className="font-mono bento-study-badge">
            {effectiveCaseId ? `CASE: ${effectiveCaseId.substring(0, 16)}` : 'STANDBY'}
          </span>
        </div>

        {effectiveCaseId ? (
          <div className="bento-active-study-grid">
            <div className="bento-stat-box">
              <span className="bento-stat-label">Subject ID</span>
              <span className="bento-stat-value font-mono">
                {activeCase?.case_id || caseResults?.case_id || 'BraTS2021_00492'}
              </span>
              <span className="bento-stat-hint">mpMRI 4-Sequence Protocol</span>
            </div>

            <div className="bento-stat-box">
              <span className="bento-stat-label">Whole Tumour (WT)</span>
              <span className="bento-stat-value font-mono" style={{ color: '#0284c7' }}>
                {volumes?.WT?.volume_ml !== undefined ? `${volumes.WT.volume_ml.toFixed(1)} mL` : '--'}
              </span>
              <span className="bento-stat-hint">
                {volumes?.WT?.voxel_count ? `${volumes.WT.voxel_count.toLocaleString()} voxels` : 'Labels 1, 2, 4'}
              </span>
            </div>

            <div className="bento-stat-box">
              <span className="bento-stat-label">Tumour Core (TC)</span>
              <span className="bento-stat-value font-mono" style={{ color: 'var(--primary-accent)' }}>
                {volumes?.TC?.volume_ml !== undefined ? `${volumes.TC.volume_ml.toFixed(1)} mL` : '--'}
              </span>
              <span className="bento-stat-hint">Labels 1, 4 (Active Core)</span>
            </div>

            <div className="bento-stat-box">
              <span className="bento-stat-label">Enhancing Tumour (ET)</span>
              <span className="bento-stat-value font-mono" style={{ color: '#ca8a04' }}>
                {volumes?.ET?.volume_ml !== undefined ? `${volumes.ET.volume_ml.toFixed(1)} mL` : '--'}
              </span>
              <span className="bento-stat-hint">Label 4 (Hyper-enhancing)</span>
            </div>

            <div className="bento-stat-box full-width">
              <div className="bento-action-row">
                <div className="bento-action-info">
                  <CheckCircle2 size={16} className="text-success-green" />
                  <span>
                    Study is ready for 3D multiplanar inspection, volumetric analysis, and clinical report export.
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    className="btn-primary"
                    style={{ fontSize: '11px', padding: '6px 12px' }}
                    onClick={() => onNavigateTab('workstation')}
                  >
                    View in Workstation
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    style={{ fontSize: '11px', padding: '6px 12px' }}
                    onClick={() => onNavigateTab('analytics')}
                  >
                    Volumetric Breakdown
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="bento-empty-prompt">
            <div className="bento-empty-icon-wrap">
              <UploadCloud size={24} className="text-secondary-blue" />
            </div>
            <div className="bento-empty-text">
              <strong>No Patient MRI Study Currently Loaded</strong>
              <p>
                Get started by clicking <strong>Load Sample BraTS Study</strong> above for an instant demonstration,
                or upload your own 4-sequence NIfTI / DICOM study in Step 1.
              </p>
            </div>
          </div>
        )}
      </section>

      {/* 3. RECENT STUDIES & TELEMETRY REGISTRY */}
      <section className="bento-recent-cases-section">
        <div className="bento-card-header">
          <div className="bento-card-title-group">
            <Database size={16} className="text-primary-blue" />
            <h2 className="bento-card-title">Study Registry & Active Cases</h2>
          </div>
          <button
            type="button"
            className="bento-refresh-btn"
            onClick={fetchRecentCases}
            disabled={loadingCases}
            title="Refresh case list"
          >
            <RefreshCw size={13} className={loadingCases ? 'spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>

        <div className="bento-table-container">
          {recentCases.length > 0 ? (
            <table className="bento-cases-table">
              <thead>
                <tr>
                  <th>Case ID</th>
                  <th>Status</th>
                  <th>Sequences</th>
                  <th>WT Volume</th>
                  <th>Last Modified</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {recentCases.map((c) => {
                  const isCurrent = (activeCase?.case_id || caseResults?.case_id) === c.case_id;
                  const wtVol = c.regions?.WT?.volume_ml;
                  return (
                    <tr key={c.case_id} className={isCurrent ? 'active-case-row' : ''}>
                      <td className="font-mono font-semibold">
                        {c.case_id}
                        {isCurrent && <span className="active-tag-inline">CURRENT</span>}
                      </td>
                      <td>
                        <span className={`status-badge-pill ${c.status === 'completed' ? 'completed' : 'pending'}`}>
                          {c.status === 'completed' ? '✓ Segmented' : 'Uploaded'}
                        </span>
                      </td>
                      <td className="font-mono text-xs">
                        {c.files ? Object.keys(c.files).filter(k => c.files[k]?.present).length : 4}/4
                      </td>
                      <td className="font-mono">
                        {wtVol !== undefined ? `${wtVol.toFixed(1)} mL` : '--'}
                      </td>
                      <td className="text-xs text-muted">
                        {c.created_at ? new Date(c.created_at).toLocaleTimeString() : 'Recent'}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn-table-action"
                          onClick={() => {
                            if (onCaseSelected) {
                              onCaseSelected(c);
                            }
                            onNavigateTab('workstation');
                          }}
                        >
                          Open in Workstation
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <div className="bento-empty-table-msg">
              <span>No persisted studies found in current session. Load the sample study to populate the registry.</span>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
