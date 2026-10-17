import React from 'react';
import { TrendingUp, ArrowLeft, Calendar, ShieldCheck, Activity, Info } from 'lucide-react';
import DualCaseCompareViewer from '../components/DualCaseCompareViewer';

export default function LongitudinalView({
  caseId,
  caseResults,
  onBackToWorkstation
}) {
  const effectiveCaseId = caseResults?.case_id || caseId;

  return (
    <div className="longitudinal-page-canvas">
      {/* Page Header */}
      <div className="longitudinal-page-header">
        <div className="longitudinal-title-group">
          {onBackToWorkstation && (
            <button
              type="button"
              className="btn-secondary"
              onClick={onBackToWorkstation}
              style={{ fontSize: '11px', padding: '6px 10px', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <ArrowLeft size={13} />
              <span>Workstation</span>
            </button>
          )}
          <div>
            <div className="longitudinal-badge">
              <TrendingUp size={14} className="text-primary-blue" />
              <span>RANO VOLUMETRIC TRAJECTORY • DUAL-STUDY COMPARISON</span>
            </div>
            <h1 className="longitudinal-title">Longitudinal Study Comparison Studio</h1>
            <p className="longitudinal-subtitle">
              Synchronized side-by-side multiplanar and 3D viewers for baseline vs follow-up assessment.
              Quantitative ΔV differential metrics and automated RANO (Response Assessment in Neuro-Oncology) criteria.
            </p>
          </div>
        </div>

        <div className="longitudinal-header-meta">
          <span className="font-mono text-xs font-semibold px-2 py-1 bg-blue-50 text-blue-700 border border-blue-200">
            CURRENT BASELINE: {effectiveCaseId ? effectiveCaseId.substring(0, 14) : 'STANDBY'}
          </span>
        </div>
      </div>

      {/* Main Wide Comparison Canvas with Dual Viewers & Analysis */}
      <div className="longitudinal-canvas-body">
        <DualCaseCompareViewer defaultBaselineCaseId={effectiveCaseId} />
      </div>
    </div>
  );
}
