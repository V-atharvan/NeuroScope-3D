import React, { useState, useEffect } from 'react';
import { AlertTriangle, Activity, ArrowLeft, Layers, TrendingUp, Info, Loader2 } from 'lucide-react';
import { getUncertaintyProfile, getModalityAblation } from '../services/api';
import DualCaseCompareViewer from './DualCaseCompareViewer';

export default function UncertaintyAndLongitudinalView({ caseId, caseResults, onClose }) {
  const [uncertaintyData, setUncertaintyData] = useState(null);
  const [ablationData, setAblationData] = useState(null);
  const [loadingTrust, setLoadingTrust] = useState(true);
  const [trustError, setTrustError] = useState(null);

  useEffect(() => {
    if (!caseId) {
      setLoadingTrust(false);
      setUncertaintyData(null);
      setAblationData(null);
      return;
    }
    setLoadingTrust(true);
    setTrustError(null);

    Promise.all([
      getUncertaintyProfile(caseId).catch((e) => ({ error: e.message })),
      getModalityAblation(caseId).catch((e) => ({ error: e.message })),
    ])
      .then(([unc, abl]) => {
        if (unc && !unc.error) setUncertaintyData(unc.uncertainty_profile);
        if (abl && !abl.error) setAblationData(abl);
        setLoadingTrust(false);
      })
      .catch((err) => {
        setTrustError(err.message);
        setLoadingTrust(false);
      });
  }, [caseId]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%', maxWidth: '1100px', margin: '0 auto', gap: '16px', padding: '16px 20px' }}>
      {/* Header Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-structural)', paddingBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '6px 10px',
                fontSize: '11px',
                fontWeight: 600,
                backgroundColor: '#FFFFFF',
                border: '1px solid #CBD5E1',
                borderRadius: '4px',
                cursor: 'pointer',
                color: '#334155'
              }}
            >
              <ArrowLeft size={14} />
              <span>Back to Workstation</span>
            </button>
          )}
          <div>
            <h1 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--on-surface-dark)', margin: 0 }}>
              AI Trust Profiler & Longitudinal Tracker
            </h1>
            <p style={{ fontSize: '12px', color: 'var(--on-surface-variant)', margin: '2px 0 0 0' }}>
              Volumetric RANO Response Criteria • Spatial Alignment • Shannon Entropy • Modality-Ablation Sensitivity
            </p>
          </div>
        </div>
        <span style={{ backgroundColor: '#F0FDF4', color: '#166534', padding: '4px 10px', borderRadius: '4px', fontSize: '11px', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
          CASE: {caseId ? caseId.substring(0, 12) : 'STANDBY'}
        </span>
      </div>

      {/* PART 1: CASE COMPARE & VOLUMETRIC COMPARISON CHART (NOW AT THE TOP) */}
      <section style={{ backgroundColor: '#FFFFFF', border: '1px solid var(--border-structural)', borderRadius: '6px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <TrendingUp size={16} style={{ color: 'var(--primary-accent)' }} />
            <h2 style={{ fontSize: '14px', fontWeight: 700, margin: 0, color: '#0F172A' }}>
              Case Compare — Synchronized Dual-Study Multiplanar & 3D Inspector
            </h2>
          </div>
          <span style={{ fontSize: '11px', color: '#64748B' }}>
            Interactive Side-by-Side Viewports • Longitudinal RANO Volumetric Trajectory & Comparison Chart
          </span>
        </div>

        <DualCaseCompareViewer defaultBaselineCaseId={caseId} />
      </section>

      {/* PART 2: UNCERTAINTY QUANTIFICATION (SHANNON ENTROPY & BOUNDARY AMBIGUITY) */}
      <section style={{ backgroundColor: '#FFFFFF', border: '1px solid var(--border-structural)', borderRadius: '6px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Activity size={16} style={{ color: 'var(--primary-accent)' }} />
            <h2 style={{ fontSize: '14px', fontWeight: 700, margin: 0, color: '#0F172A' }}>
              Algorithmic Uncertainty Quantification (Shannon Entropy & Boundary Ambiguity)
            </h2>
          </div>
          <span style={{ fontSize: '11px', color: '#64748B' }}>
            Method: Spatial Reflection Symmetry & Boundary Shell
          </span>
        </div>

        {!caseId ? (
          <div style={{ padding: '24px', textAlign: 'center', color: '#64748B', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
            <Info size={24} style={{ color: '#94A3B8' }} />
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#334155' }}>No Active Study Selected</span>
            <p style={{ fontSize: '12px', color: '#64748B', margin: 0, maxWidth: '520px', lineHeight: 1.4 }}>
              Upload a 4-sequence brain MRI study or click <strong>&quot;Load Sample BraTS Study&quot;</strong> in the Workstation to compute voxel-wise Shannon entropy and boundary ambiguity profiles.
            </p>
          </div>
        ) : loadingTrust ? (
          <div style={{ padding: '24px', textAlign: 'center', color: '#64748B' }}>
            <Loader2 size={20} className="animate-spin" style={{ display: 'inline-block', marginRight: '6px' }} />
            <span>Computing boundary Shannon entropy...</span>
          </div>
        ) : trustError ? (
          <div style={{ color: '#DC2626', fontSize: '12px' }}>{trustError}</div>
        ) : uncertaintyData ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
            {['WT', 'TC', 'ET'].map((reg) => {
              const u = uncertaintyData[reg] || {};
              const entropy = u.mean_entropy !== undefined ? u.mean_entropy : 0;
              const boundary = u.boundary_uncertainty !== undefined ? u.boundary_uncertainty : 0;
              const rating = u.confidence_rating || 'N/A';
              const confPct = u.confidence_percentage !== undefined ? u.confidence_percentage : 100;

              return (
                <div key={reg} style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '4px', padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, fontSize: '13px', color: '#0F172A' }}>{reg} Region</span>
                    <span style={{ fontSize: '10px', fontWeight: 600, color: '#0284C7', backgroundColor: '#E0F2FE', padding: '2px 6px', borderRadius: '3px' }}>
                      {rating}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                    <span style={{ fontSize: '20px', fontWeight: 800, color: '#0F172A', fontFamily: 'var(--font-mono)' }}>
                      {confPct.toFixed(1)}%
                    </span>
                    <span style={{ fontSize: '11px', color: '#64748B' }}>Predictive Confidence</span>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '11px', color: '#475569' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Mean Entropy H(x):</span>
                      <strong className="font-mono">{entropy.toFixed(4)} bits</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Boundary Transition Uncertainty:</span>
                      <strong className="font-mono">{boundary.toFixed(4)}</strong>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{ fontSize: '12px', color: '#64748B' }}>Inference results not available. Complete segmentation on the workstation first.</div>
        )}
      </section>

      {/* PART 3: MODALITY-ABLATION SENSITIVITY PROFILER (BELOW THAT) */}
      <section style={{ backgroundColor: '#FFFFFF', border: '1px solid var(--border-structural)', borderRadius: '6px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={16} style={{ color: 'var(--primary-accent)' }} />
            <h2 style={{ fontSize: '14px', fontWeight: 700, margin: 0, color: '#0F172A' }}>
              Modality-Ablation Sensitivity Profiler
            </h2>
          </div>
          <span style={{ fontSize: '11px', color: '#64748B' }}>
            Multi-Sequence Causal Attribution
          </span>
        </div>

        {/* Mandatory Warning */}
        <div style={{ backgroundColor: '#FEF2F2', border: '1px solid #FECACA', borderRadius: '4px', padding: '10px 12px', display: 'flex', alignItems: 'center', gap: '8px', color: '#991B1B', fontSize: '11px', fontWeight: 600 }}>
          <AlertTriangle size={16} style={{ flexShrink: 0 }} />
          <span>COMPUTATIONAL SENSITIVITY ESTIMATE ONLY — NOT VALIDATED CLINICAL EVIDENCE.</span>
        </div>

        {!caseId ? (
          <div style={{ padding: '16px', textAlign: 'center', color: '#64748B', fontSize: '12px' }}>
            No active study selected. Load a study in the Workstation to evaluate multi-sequence causal contributions.
          </div>
        ) : ablationData?.sensitivities ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
            {['WT', 'TC', 'ET'].map((reg) => {
              const sens = ablationData.sensitivities[reg] || {};
              return (
                <div key={reg} style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '4px', padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, fontSize: '12px', color: '#0F172A' }}>{reg} Contribution</span>
                    <span style={{ fontSize: '10px', color: '#475569' }}>Driver: <strong>{sens.primary_driver}</strong></span>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '10px' }}>
                    {['t1gd', 'flair', 't2', 't1'].map((seq) => {
                      const val = sens[seq] || 0;
                      return (
                        <div key={seq} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ width: '38px', textTransform: 'uppercase', fontWeight: 600, color: '#475569' }}>{seq}</span>
                          <div style={{ flex: 1, height: '8px', backgroundColor: '#E2E8F0', borderRadius: '2px', overflow: 'hidden' }}>
                            <div style={{ width: `${val}%`, height: '100%', backgroundColor: 'var(--primary-accent)' }} />
                          </div>
                          <span style={{ width: '36px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{val.toFixed(1)}%</span>
                        </div>
                      );
                    })}
                  </div>
                  <p style={{ fontSize: '10px', color: '#64748B', margin: '4px 0 0 0', lineHeight: 1.3 }}>
                    {sens.clinical_significance}
                  </p>
                </div>
              );
            })}
          </div>
        ) : null}
      </section>
    </div>
  );
}
