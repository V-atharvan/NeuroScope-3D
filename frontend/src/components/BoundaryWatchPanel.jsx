import React, { useState, useEffect } from 'react';
import { ShieldCheck, AlertTriangle, AlertCircle, CheckCircle2, Target, Eye, Layers, Compass, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { getBoundaryWatch } from '../services/api';

export default function BoundaryWatchPanel({
  caseId,
  boundaryWatchData: propBoundaryWatch,
  onNavigateToCentroid,
  onNavigateToSlice
}) {
  const [data, setData] = useState(propBoundaryWatch || null);
  const [loading, setLoading] = useState(!propBoundaryWatch && Boolean(caseId));
  const [error, setError] = useState(null);
  const [isExpanded, setIsExpanded] = useState(true);

  useEffect(() => {
    if (propBoundaryWatch) {
      setData(propBoundaryWatch);
      setLoading(false);
      return;
    }
    if (!caseId) return;

    setLoading(true);
    setError(null);
    getBoundaryWatch(caseId)
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to retrieve Boundary Watch quality flags');
        setLoading(false);
      });
  }, [caseId, propBoundaryWatch]);

  if (!caseId && !data) {
    return null;
  }

  const checks = data?.checks || {};
  const components = checks.disconnected_components || {};
  const continuity = checks.slice_continuity || {};
  const border = checks.border_contact || {};
  const nesting = checks.nesting_integrity || {};
  const microVolumes = checks.micro_volumes || [];
  const riskBadge = data?.quality_risk_badge || 'Quality Verified';
  const riskColor = data?.quality_risk_color || '#10B981';
  const riskScore = data?.risk_score ?? 0;

  return (
    <div
      style={{
        backgroundColor: '#FFFFFF',
        border: '1px solid var(--border-structural)',
        borderRadius: 'var(--radius-sm)',
        display: 'flex',
        flexDirection: 'column',
        gap: '0px',
        overflow: 'hidden',
        boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
      }}
    >
      {/* Panel Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          backgroundColor: '#F8FAFC',
          borderBottom: isExpanded ? '1px solid #E2E8F0' : 'none',
          cursor: 'pointer'
        }}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldCheck size={16} style={{ color: riskColor }} />
          <div>
            <span style={{ fontSize: '13px', fontWeight: 700, color: '#0F172A' }}>
              Boundary Watch™ — Quality Assurance Flags
            </span>
            <span style={{ fontSize: '11px', color: '#64748B', marginLeft: '6px' }}>
              Geometric Continuity & Island Detection
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {loading ? (
            <Loader2 size={14} className="animate-spin" style={{ color: '#64748B' }} />
          ) : (
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                color: '#FFFFFF',
                backgroundColor: riskColor,
                padding: '2px 8px',
                borderRadius: '4px',
                fontFamily: 'var(--font-mono)'
              }}
            >
              {riskBadge} ({riskScore} pts)
            </span>
          )}
          {isExpanded ? <ChevronUp size={16} color="#64748B" /> : <ChevronDown size={16} color="#64748B" />}
        </div>
      </div>

      {isExpanded && (
        <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {loading && (
            <div style={{ padding: '14px', textAlign: 'center', color: '#64748B', fontSize: '12px' }}>
              <Loader2 size={16} className="animate-spin" style={{ display: 'inline-block', marginRight: '6px' }} />
              Running 3D connected components and spatial continuity analysis...
            </div>
          )}

          {error && (
            <div style={{ color: '#DC2626', backgroundColor: '#FEF2F2', padding: '8px 10px', borderRadius: '4px', fontSize: '11px' }}>
              {error}
            </div>
          )}

          {!loading && !error && data && (
            <>
              {/* Actionable Trainee Guidance Banner */}
              <div
                style={{
                  backgroundColor: riskScore <= 15 ? '#F0FDF4' : (riskScore <= 45 ? '#FFFBEB' : '#FEF2F2'),
                  border: `1px solid ${riskScore <= 15 ? '#BBF7D0' : (riskScore <= 45 ? '#FDE68A' : '#FECACA')}`,
                  borderRadius: '4px',
                  padding: '8px 12px',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '8px'
                }}
              >
                {riskScore <= 15 ? (
                  <CheckCircle2 size={16} style={{ color: '#16A34A', marginTop: '2px', flexShrink: 0 }} />
                ) : (
                  <AlertTriangle size={16} style={{ color: riskColor, marginTop: '2px', flexShrink: 0 }} />
                )}
                <div style={{ fontSize: '11px', color: '#1E293B', lineHeight: 1.4 }}>
                  <strong>Diagnostic Recommendation:</strong> {data.recommendation}
                </div>
              </div>

              {/* 5 Quality Diagnostic Checks Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '8px' }}>
                {/* 1. Disconnected Satellite Islands */}
                <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '4px', padding: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '11px', fontWeight: 700, color: '#334155' }}>
                      1. Connected Components (Islands)
                    </span>
                    <span
                      style={{
                        fontSize: '10px',
                        fontWeight: 600,
                        color: components.WT?.flagged ? '#DC2626' : '#16A34A',
                        backgroundColor: components.WT?.flagged ? '#FEE2E2' : '#DCFCE7',
                        padding: '1px 6px',
                        borderRadius: '3px'
                      }}
                    >
                      {components.WT?.component_count ?? 1} focus
                    </span>
                  </div>
                  <p style={{ fontSize: '10px', color: '#64748B', margin: 0 }}>
                    {components.WT?.message}
                  </p>
                  {/* Jump to satellite cluster if available */}
                  {components.WT?.satellite_centroids && components.WT.satellite_centroids.length > 0 && onNavigateToCentroid && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px' }}>
                      <span style={{ fontSize: '9px', fontWeight: 600, color: '#475569' }}>Inspect Satellite:</span>
                      {components.WT.satellite_centroids.map((coords, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => onNavigateToCentroid(coords)}
                          style={{
                            padding: '2px 6px',
                            fontSize: '9px',
                            fontWeight: 600,
                            backgroundColor: '#EFF6FF',
                            color: '#1D4ED8',
                            border: '1px solid #BFDBFE',
                            borderRadius: '3px',
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '3px'
                          }}
                        >
                          <Target size={10} />
                          <span>Island {idx + 1} [{coords.join(',')}]</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* 2. Slice Continuity & Z-Step Discontinuity */}
                <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '4px', padding: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '11px', fontWeight: 700, color: '#334155' }}>
                      2. Slice-to-Slice Continuity
                    </span>
                    <span
                      style={{
                        fontSize: '10px',
                        fontWeight: 600,
                        color: continuity.WT?.flagged ? '#D97706' : '#16A34A',
                        backgroundColor: continuity.WT?.flagged ? '#FEF3C7' : '#DCFCE7',
                        padding: '1px 6px',
                        borderRadius: '3px'
                      }}
                    >
                      {continuity.WT?.flagged ? `${continuity.WT.discontinuity_count} Stepped Jumps` : 'Smooth'}
                    </span>
                  </div>
                  <p style={{ fontSize: '10px', color: '#64748B', margin: 0 }}>
                    {continuity.WT?.message}
                  </p>
                  {/* Jump to anomalous slice buttons */}
                  {continuity.WT?.abrupt_discontinuities && continuity.WT.abrupt_discontinuities.length > 0 && onNavigateToSlice && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginTop: '4px' }}>
                      <span style={{ fontSize: '9px', fontWeight: 600, color: '#475569' }}>Inspect Slices:</span>
                      {continuity.WT.abrupt_discontinuities.map((jump, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => onNavigateToSlice(jump.slice_z)}
                          title={jump.message}
                          style={{
                            padding: '2px 6px',
                            fontSize: '9px',
                            fontWeight: 600,
                            backgroundColor: '#FEF3C7',
                            color: '#92400E',
                            border: '1px solid #FDE68A',
                            borderRadius: '3px',
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '3px'
                          }}
                        >
                          <Compass size={10} />
                          <span>Z={jump.slice_z}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* 3. Field of View (FOV) Border Contact */}
                <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '4px', padding: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '11px', fontWeight: 700, color: '#334155' }}>
                      3. Perimeter Truncation
                    </span>
                    <span
                      style={{
                        fontSize: '10px',
                        fontWeight: 600,
                        color: border.WT?.flagged ? '#DC2626' : '#16A34A',
                        backgroundColor: border.WT?.flagged ? '#FEE2E2' : '#DCFCE7',
                        padding: '1px 6px',
                        borderRadius: '3px'
                      }}
                    >
                      {border.WT?.border_touching ? `${border.WT.border_voxels} border vox` : 'Contained'}
                    </span>
                  </div>
                  <p style={{ fontSize: '10px', color: '#64748B', margin: 0 }}>
                    {border.WT?.message}
                  </p>
                </div>

                {/* 4. Hierarchical Nesting Strict Verification */}
                <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '4px', padding: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '11px', fontWeight: 700, color: '#334155' }}>
                      4. Nesting Integrity (ET ⊆ TC ⊆ WT)
                    </span>
                    <span
                      style={{
                        fontSize: '10px',
                        fontWeight: 600,
                        color: nesting.is_nesting_valid ? '#16A34A' : '#DC2626',
                        backgroundColor: nesting.is_nesting_valid ? '#DCFCE7' : '#FEE2E2',
                        padding: '1px 6px',
                        borderRadius: '3px'
                      }}
                    >
                      {nesting.is_nesting_valid ? '0 Violations' : `${nesting.total_violations} Violations`}
                    </span>
                  </div>
                  <p style={{ fontSize: '10px', color: '#64748B', margin: 0 }}>
                    {nesting.message}
                  </p>
                </div>
              </div>

              {/* Research Protocol Footer Disclaimer */}
              <div style={{ fontSize: '9px', color: '#94A3B8', borderTop: '1px dashed #E2E8F0', paddingTop: '6px' }}>
                {data.disclaimer}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
