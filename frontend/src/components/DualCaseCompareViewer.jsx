import React, { useState, useEffect, useRef } from 'react';
import { Niivue, NVImage } from '@niivue/niivue';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Layers,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  RotateCcw,
  Sliders,
  CheckCircle2,
  Loader2,
  Calendar,
  Sparkles,
  Link as LinkIcon,
  Unlink
} from 'lucide-react';
import { getActiveCases, loadSampleLongitudinalPair, compareLongitudinalStudies, getSequenceDownloadUrl, getMaskDownloadUrl } from '../services/api';

export default function DualCaseCompareViewer({
  defaultBaselineCaseId,
  onClose
}) {
  const [activeCases, setActiveCases] = useState([]);
  const [loadingCases, setLoadingCases] = useState(true);

  const [caseAId, setCaseAId] = useState(defaultBaselineCaseId || '');
  const [caseBId, setCaseBId] = useState('');

  const [seqKeyA, setSeqKeyA] = useState('t1gd');
  const [seqKeyB, setSeqKeyB] = useState('t1gd');

  const [sliceType, setSliceType] = useState('multi'); // 'multi' | 'render' | 'axial'
  const [syncScroll, setSyncScroll] = useState(true);

  const [comparisonData, setComparisonData] = useState(null);
  const [loadingComparison, setLoadingComparison] = useState(false);
  const [isGeneratingDemo, setIsGeneratingDemo] = useState(false);
  const [statusMsg, setStatusMsg] = useState('Ready for two-study comparison');

  const canvasARef = useRef(null);
  const canvasBRef = useRef(null);
  const nvARef = useRef(null);
  const nvBRef = useRef(null);

  // 1. Load active cases on mount
  useEffect(() => {
    getActiveCases()
      .then((res) => {
        const list = res.cases || [];
        setActiveCases(list);
        if (!caseAId && list.length > 0) {
          setCaseAId(list[0].case_id);
        }
        if (!caseBId && list.length > 1) {
          setCaseBId(list[1].case_id);
        }
        setLoadingCases(false);
      })
      .catch((e) => {
        console.warn('Failed to load active cases:', e);
        setLoadingCases(false);
      });
  }, []);

  // 2. Initialize Niivue instances on each canvas
  useEffect(() => {
    if (!canvasARef.current || !canvasBRef.current) return;

    const nvA = new Niivue({
      backColor: [0.05, 0.07, 0.11, 1],
      show3Dcrosshair: true,
      crosshairColor: [0.2, 0.7, 1.0, 0.8],
      isOrientCube: true,
      loadingText: 'Loading Baseline Study...',
    });

    const nvB = new Niivue({
      backColor: [0.05, 0.07, 0.11, 1],
      show3Dcrosshair: true,
      crosshairColor: [1.0, 0.5, 0.2, 0.8],
      isOrientCube: true,
      loadingText: 'Loading Follow-up Study...',
    });

    try {
      nvA.attachToCanvas(canvasARef.current);
      nvB.attachToCanvas(canvasBRef.current);

      // Link location changes if syncScroll is active
      nvA.onLocationChange = (data) => {
        if (syncScroll && nvBRef.current && data?.vox && nvBRef.current.scene) {
          try {
            const frac = nvBRef.current.vox2frac(data.vox, 0);
            nvBRef.current.scene.crosshairPos = frac;
            nvBRef.current.updateGLVolume();
          } catch (_) {}
        }
      };

      nvB.onLocationChange = (data) => {
        if (syncScroll && nvARef.current && data?.vox && nvARef.current.scene) {
          try {
            const frac = nvARef.current.vox2frac(data.vox, 0);
            nvARef.current.scene.crosshairPos = frac;
            nvARef.current.updateGLVolume();
          } catch (_) {}
        }
      };

      nvARef.current = nvA;
      nvBRef.current = nvB;
    } catch (err) {
      console.error('Error attaching Dual NiiVue instances:', err);
    }

    return () => {
      try {
        nvA.destroy();
        nvB.destroy();
      } catch (_) {}
    };
  }, []);

  // 3. Load Volumes into Viewport A (Baseline)
  useEffect(() => {
    const nv = nvARef.current;
    if (!nv || !caseAId) return;

    let isCancelled = false;
    async function loadA() {
      try {
        while (nv.volumes && nv.volumes.length > 0) {
          nv.removeVolumeByIndex(0);
        }

        const scanUrl = getSequenceDownloadUrl(caseAId, seqKeyA);
        const baseVol = await NVImage.loadFromUrl({
          url: scanUrl,
          colormap: 'gray',
          opacity: 1.0,
        });

        if (isCancelled || !baseVol) return;
        nv.addVolume(baseVol);

        // Load mask if available
        const maskUrl = getMaskDownloadUrl(caseAId);
        try {
          const maskVol = await NVImage.loadFromUrl({
            url: maskUrl,
            colormap: 'red',
            opacity: 0.65,
          });
          if (!isCancelled && maskVol) {
            nv.addVolume(maskVol);
          }
        } catch (_) {}

        nv.updateGLVolume();
      } catch (err) {
        console.warn('Failed to load Study A:', err);
      }
    }

    loadA();
    return () => { isCancelled = true; };
  }, [caseAId, seqKeyA]);

  // 4. Load Volumes into Viewport B (Follow-up)
  useEffect(() => {
    const nv = nvBRef.current;
    if (!nv || !caseBId) return;

    let isCancelled = false;
    async function loadB() {
      try {
        while (nv.volumes && nv.volumes.length > 0) {
          nv.removeVolumeByIndex(0);
        }

        const scanUrl = getSequenceDownloadUrl(caseBId, seqKeyB);
        const baseVol = await NVImage.loadFromUrl({
          url: scanUrl,
          colormap: 'gray',
          opacity: 1.0,
        });

        if (isCancelled || !baseVol) return;
        nv.addVolume(baseVol);

        // Load mask if available
        const maskUrl = getMaskDownloadUrl(caseBId);
        try {
          const maskVol = await NVImage.loadFromUrl({
            url: maskUrl,
            colormap: 'blue',
            opacity: 0.65,
          });
          if (!isCancelled && maskVol) {
            nv.addVolume(maskVol);
          }
        } catch (_) {}

        nv.updateGLVolume();
      } catch (err) {
        console.warn('Failed to load Study B:', err);
      }
    }

    loadB();
    return () => { isCancelled = true; };
  }, [caseBId, seqKeyB]);

  // 5. Run volumetric comparison whenever caseA or caseB changes
  useEffect(() => {
    if (!caseAId || !caseBId || caseAId === caseBId) {
      setComparisonData(null);
      return;
    }

    setLoadingComparison(true);
    compareLongitudinalStudies(caseAId, caseBId)
      .then((res) => {
        setComparisonData(res);
        setLoadingComparison(false);
      })
      .catch((err) => {
        console.warn('Comparison failed:', err.message);
        setComparisonData(null);
        setLoadingComparison(false);
      });
  }, [caseAId, caseBId]);

  // 6. Handle Slice Type change for both viewers
  const handleSliceTypeChange = (type) => {
    setSliceType(type);
    const nvA = nvARef.current;
    const nvB = nvBRef.current;

    const applyType = (nv) => {
      if (!nv) return;
      if (type === 'multi') nv.setSliceType(nv.sliceTypeMultiplanar);
      else if (type === 'render') nv.setSliceType(nv.sliceTypeRender);
      else if (type === 'axial') nv.setSliceType(nv.sliceTypeAxial);
    };

    applyType(nvA);
    applyType(nvB);
  };

  // 7. Load Demonstration Pair (1-click)
  const handleLoadDemoPair = async () => {
    setIsGeneratingDemo(true);
    setStatusMsg('Generating authoritative longitudinal demonstration pair (T0 Baseline vs T1 Follow-up)...');
    try {
      const res = await loadSampleLongitudinalPair();
      setCaseAId(res.baseline_case_id);
      setCaseBId(res.followup_case_id);
      setComparisonData(res.comparison);
      setStatusMsg('Demonstration pair loaded successfully.');

      // Refresh active cases list
      const casesRes = await getActiveCases();
      setActiveCases(casesRes.cases || []);
    } catch (err) {
      setStatusMsg(`Demo generation failed: ${err.message}`);
    } finally {
      setIsGeneratingDemo(false);
    }
  };

  const getRanoBadge = (category = '') => {
    if (category.includes('Progressive Disease')) {
      return (
        <span style={{ backgroundColor: '#FEE2E2', color: '#991B1B', border: '1px solid #FECACA', padding: '3px 8px', borderRadius: '4px', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}>
          <TrendingUp size={13} />
          {category}
        </span>
      );
    }
    if (category.includes('Partial Response')) {
      return (
        <span style={{ backgroundColor: '#ECFDF5', color: '#065F46', border: '1px solid #A7F3D0', padding: '3px 8px', borderRadius: '4px', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}>
          <TrendingDown size={13} />
          {category}
        </span>
      );
    }
    return (
      <span style={{ backgroundColor: '#EFF6FF', color: '#1E40AF', border: '1px solid #BFDBFE', padding: '3px 8px', borderRadius: '4px', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}>
        <Minus size={13} />
        {category || 'Stable Disease (SD)'}
      </span>
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%', gap: '12px' }}>
      {/* Top Controls Toolbar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: '#FFFFFF',
          border: '1px solid var(--border-structural)',
          borderRadius: 'var(--radius-sm)',
          padding: '10px 14px',
          flexWrap: 'wrap',
          gap: '10px'
        }}
      >
        {/* Left: Study Selectors */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          {/* Baseline Study Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#0F172A', whiteSpace: 'nowrap' }}>
              Baseline (T0):
            </span>
            <select
              value={caseAId}
              onChange={(e) => setCaseAId(e.target.value)}
              style={{ padding: '4px 8px', fontSize: '11px', border: '1px solid #CBD5E1', borderRadius: '4px', maxWidth: '200px' }}
            >
              <option value="">-- Select Baseline Study --</option>
              {activeCases.map((c) => (
                <option key={c.case_id} value={c.case_id}>
                  {c.case_id.substring(0, 16)} {c.has_mask ? '✓' : ''} ({c.status})
                </option>
              ))}
            </select>
          </div>

          <span style={{ color: '#94A3B8', fontWeight: 700 }}>&rarr;</span>

          {/* Follow-up Study Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#0F172A', whiteSpace: 'nowrap' }}>
              Follow-up (T1):
            </span>
            <select
              value={caseBId}
              onChange={(e) => setCaseBId(e.target.value)}
              style={{ padding: '4px 8px', fontSize: '11px', border: '1px solid #CBD5E1', borderRadius: '4px', maxWidth: '200px' }}
            >
              <option value="">-- Select Follow-up Study --</option>
              {activeCases.map((c) => (
                <option key={c.case_id} value={c.case_id}>
                  {c.case_id.substring(0, 16)} {c.has_mask ? '✓' : ''} ({c.status})
                </option>
              ))}
            </select>
          </div>

          {/* 1-Click Demo Pair Generator */}
          <button
            type="button"
            onClick={handleLoadDemoPair}
            disabled={isGeneratingDemo}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              padding: '4px 10px',
              fontSize: '11px',
              fontWeight: 600,
              backgroundColor: '#EFF6FF',
              color: '#1D4ED8',
              border: '1px solid #93C5FD',
              borderRadius: '4px',
              cursor: isGeneratingDemo ? 'wait' : 'pointer'
            }}
          >
            {isGeneratingDemo ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
            <span>Load Demo Pair (T0 vs T1)</span>
          </button>
        </div>

        {/* Right: Viewport Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {/* Synchronize Toggle */}
          <button
            type="button"
            onClick={() => setSyncScroll(!syncScroll)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 8px',
              fontSize: '11px',
              fontWeight: 600,
              backgroundColor: syncScroll ? '#F0FDF4' : '#F8FAFC',
              color: syncScroll ? '#166534' : '#64748B',
              border: `1px solid ${syncScroll ? '#BBF7D0' : '#CBD5E1'}`,
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            {syncScroll ? <LinkIcon size={12} /> : <Unlink size={12} />}
            <span>{syncScroll ? 'Linked Viewports' : 'Unlinked Viewports'}</span>
          </button>

          {/* View Mode Segmented Controls */}
          <div className="segmented-control">
            <button
              type="button"
              className={`segmented-btn ${sliceType === 'multi' ? 'active' : ''}`}
              onClick={() => handleSliceTypeChange('multi')}
            >
              Multiplanar
            </button>
            <button
              type="button"
              className={`segmented-btn ${sliceType === 'render' ? 'active' : ''}`}
              onClick={() => handleSliceTypeChange('render')}
            >
              3D Render
            </button>
            <button
              type="button"
              className={`segmented-btn ${sliceType === 'axial' ? 'active' : ''}`}
              onClick={() => handleSliceTypeChange('axial')}
            >
              Axial Full
            </button>
          </div>
        </div>
      </div>

      {/* Dual Canvas Grid (Side-by-Side Viewports) */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', minHeight: '440px' }}>
        {/* VIEWPORT A: Baseline Study */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: '#0F172A',
            border: '1px solid #1E293B',
            borderRadius: 'var(--radius-sm)',
            overflow: 'hidden',
            position: 'relative'
          }}
        >
          {/* Header Bar A */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '6px 10px',
              backgroundColor: '#1E293B',
              borderBottom: '1px solid #334155'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#38BDF8' }}>T0 BASELINE</span>
              <span style={{ fontSize: '10px', color: '#94A3B8', fontFamily: 'var(--font-mono)' }}>
                {caseAId ? caseAId.substring(0, 14) : 'NO CASE'}
              </span>
            </div>

            {/* Sequence Selector A */}
            <div style={{ display: 'flex', gap: '3px' }}>
              {['t1gd', 'flair', 't2', 't1'].map((seq) => (
                <button
                  key={seq}
                  type="button"
                  onClick={() => setSeqKeyA(seq)}
                  style={{
                    padding: '2px 5px',
                    fontSize: '9px',
                    fontWeight: seqKeyA === seq ? 700 : 500,
                    backgroundColor: seqKeyA === seq ? 'var(--primary-accent)' : '#0F172A',
                    color: seqKeyA === seq ? '#FFFFFF' : '#94A3B8',
                    border: '1px solid #334155',
                    borderRadius: '2px',
                    cursor: 'pointer',
                    textTransform: 'uppercase'
                  }}
                >
                  {seq}
                </button>
              ))}
            </div>
          </div>

          {/* WebGL Canvas A */}
          <div style={{ flex: 1, position: 'relative', minHeight: '380px' }}>
            <canvas ref={canvasARef} style={{ width: '100%', height: '100%', display: 'block' }} />
          </div>
        </div>

        {/* VIEWPORT B: Follow-up Study */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: '#0F172A',
            border: '1px solid #1E293B',
            borderRadius: 'var(--radius-sm)',
            overflow: 'hidden',
            position: 'relative'
          }}
        >
          {/* Header Bar B */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '6px 10px',
              backgroundColor: '#1E293B',
              borderBottom: '1px solid #334155'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#F97316' }}>T1 FOLLOW-UP</span>
              <span style={{ fontSize: '10px', color: '#94A3B8', fontFamily: 'var(--font-mono)' }}>
                {caseBId ? caseBId.substring(0, 14) : 'NO CASE'}
              </span>
            </div>

            {/* Sequence Selector B */}
            <div style={{ display: 'flex', gap: '3px' }}>
              {['t1gd', 'flair', 't2', 't1'].map((seq) => (
                <button
                  key={seq}
                  type="button"
                  onClick={() => setSeqKeyB(seq)}
                  style={{
                    padding: '2px 5px',
                    fontSize: '9px',
                    fontWeight: seqKeyB === seq ? 700 : 500,
                    backgroundColor: seqKeyB === seq ? '#F97316' : '#0F172A',
                    color: seqKeyB === seq ? '#FFFFFF' : '#94A3B8',
                    border: '1px solid #334155',
                    borderRadius: '2px',
                    cursor: 'pointer',
                    textTransform: 'uppercase'
                  }}
                >
                  {seq}
                </button>
              ))}
            </div>
          </div>

          {/* WebGL Canvas B */}
          <div style={{ flex: 1, position: 'relative', minHeight: '380px' }}>
            <canvas ref={canvasBRef} style={{ width: '100%', height: '100%', display: 'block' }} />
          </div>
        </div>
      </div>

      {/* Volumetric RANO Assessment & Spatial Compatibility HUD */}
      {comparisonData && (
        <div
          style={{
            backgroundColor: '#FFFFFF',
            border: '1px solid var(--border-structural)',
            borderRadius: 'var(--radius-sm)',
            padding: '12px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
          }}
        >
          {/* Top RANO Banner */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '12px', fontWeight: 700, color: '#0F172A' }}>
                RANO Volumetric Response Trajectory:
              </span>
              {getRanoBadge(comparisonData.rano_trajectory?.rano_category)}
            </div>

            {/* Spatial Grid Verification Chip */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: '#64748B' }}>
              <ShieldCheck size={14} color="#16A34A" />
              <span>
                {comparisonData.spatial_compatibility?.is_identical_grid
                  ? 'Spatial Alignment Verified (Identical Grid & Voxel Spacing)'
                  : 'Continuous Affine Millilitre Integrals Calibrated'}
              </span>
            </div>
          </div>

          <p style={{ fontSize: '11px', color: '#475569', margin: 0 }}>
            {comparisonData.rano_trajectory?.interpretation}
          </p>

          {/* 4-Column Quantitative Volumetric Delta Table */}
          {comparisonData.volumetric_deltas && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', textAlign: 'left', marginTop: '4px' }}>
              <thead>
                <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0', color: '#475569', fontWeight: 600 }}>
                  <th style={{ padding: '6px 10px' }}>Anatomical Region</th>
                  <th style={{ padding: '6px 10px' }}>T0 Baseline (mL)</th>
                  <th style={{ padding: '6px 10px' }}>T1 Follow-up (mL)</th>
                  <th style={{ padding: '6px 10px' }}>Absolute Delta (ΔV mL)</th>
                  <th style={{ padding: '6px 10px' }}>Percentage Delta</th>
                </tr>
              </thead>
              <tbody>
                {['WT', 'TC', 'ET'].map((reg) => {
                  const d = comparisonData.volumetric_deltas[reg] || {};
                  const isNeg = d.percentage_delta < 0;
                  const isPos = d.percentage_delta > 0;
                  return (
                    <tr key={reg} style={{ borderBottom: '1px solid #F1F5F9' }}>
                      <td style={{ padding: '6px 10px', fontWeight: 700, color: '#0F172A' }}>{reg}</td>
                      <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{d.baseline_volume_ml?.toFixed(2)} mL</td>
                      <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{d.followup_volume_ml?.toFixed(2)} mL</td>
                      <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>
                        {d.absolute_delta_ml > 0 ? `+${d.absolute_delta_ml.toFixed(2)}` : d.absolute_delta_ml?.toFixed(2)} mL
                      </td>
                      <td
                        style={{
                          padding: '6px 10px',
                          fontFamily: 'var(--font-mono)',
                          fontWeight: 700,
                          color: isNeg ? '#065F46' : (isPos ? '#991B1B' : '#475569')
                        }}
                      >
                        {d.percentage_delta > 0 ? `+${d.percentage_delta.toFixed(1)}%` : `${d.percentage_delta?.toFixed(1)}%`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
