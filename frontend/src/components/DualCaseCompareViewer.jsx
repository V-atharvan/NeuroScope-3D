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
import IconCrossFade from './IconCrossFade';
import { getActiveCases, loadSampleLongitudinalPair, compareLongitudinalStudies, getSequenceDownloadUrl, getMaskDownloadUrl } from '../services/api';

export default function DualCaseCompareViewer({
  defaultBaselineCaseId,
  onClose
}) {
  const [activeCases, setActiveCases] = useState([]);
  const [loadingCases, setLoadingCases] = useState(true);

  const [caseAId, setCaseAId] = useState(defaultBaselineCaseId || '');
  const [caseBId, setCaseBId] = useState('');

  const [loadingA, setLoadingA] = useState(false);
  const [errorA, setErrorA] = useState(null);
  const [loadingB, setLoadingB] = useState(false);
  const [errorB, setErrorB] = useState(null);

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
        const completedCases = list.filter((c) => c.status === 'completed');
        if (!caseAId) {
          if (defaultBaselineCaseId) {
            setCaseAId(defaultBaselineCaseId);
          } else if (completedCases.length > 0) {
            setCaseAId(completedCases[0].case_id);
          }
        }
        if (!caseBId) {
          if (completedCases.length > 1) {
            const other = completedCases.find((c) => c.case_id !== (caseAId || defaultBaselineCaseId || completedCases[0]?.case_id));
            if (other) setCaseBId(other.case_id);
          }
        }
        setLoadingCases(false);
      })
      .catch((e) => {
        console.warn('Failed to load active cases:', e);
        setLoadingCases(false);
      });
  }, [defaultBaselineCaseId]);

  // 2. Initialize Niivue instances on each canvas
  useEffect(() => {
    if (!canvasARef.current || !canvasBRef.current) return;

    const nvA = new Niivue({
      backColor: [0.05, 0.07, 0.11, 1],
      show3Dcrosshair: true,
      crosshairColor: [0.2, 0.7, 1.0, 0.8],
      isOrientCube: true,
      loadingText: '',
    });

    const nvB = new Niivue({
      backColor: [0.05, 0.07, 0.11, 1],
      show3Dcrosshair: true,
      crosshairColor: [1.0, 0.5, 0.2, 0.8],
      isOrientCube: true,
      loadingText: '',
    });

    try {
      nvA.attachToCanvas(canvasARef.current);
      nvB.attachToCanvas(canvasBRef.current);

      nvA.setSliceType(nvA.sliceTypeMultiplanar);
      nvA.setMultiplanarLayout(2); // 4 equal partitions (2x2 grid)
      nvA.opts.multiplanarForceRender = true;
      nvA.setCornerOrientationText(true);

      nvB.setSliceType(nvB.sliceTypeMultiplanar);
      nvB.setMultiplanarLayout(2); // 4 equal partitions (2x2 grid)
      nvB.opts.multiplanarForceRender = true;
      nvB.setCornerOrientationText(true);

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
    if (!nv) return;

    if (!caseAId) {
      while (nv.volumes && nv.volumes.length > 0) {
        nv.removeVolumeByIndex(0);
      }
      nv.updateGLVolume();
      setLoadingA(false);
      setErrorA(null);
      return;
    }

    let isCancelled = false;
    async function loadA() {
      setLoadingA(true);
      setErrorA(null);
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
        setLoadingA(false);
      } catch (err) {
        console.warn('Failed to load Study A:', err);
        if (!isCancelled) {
          setErrorA('Study sequence could not be loaded.');
          setLoadingA(false);
        }
      }
    }

    loadA();
    return () => { isCancelled = true; };
  }, [caseAId, seqKeyA]);

  // 4. Load Volumes into Viewport B (Follow-up)
  useEffect(() => {
    const nv = nvBRef.current;
    if (!nv) return;

    if (!caseBId) {
      while (nv.volumes && nv.volumes.length > 0) {
        nv.removeVolumeByIndex(0);
      }
      nv.updateGLVolume();
      setLoadingB(false);
      setErrorB(null);
      return;
    }

    let isCancelled = false;
    async function loadB() {
      setLoadingB(true);
      setErrorB(null);
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
        setLoadingB(false);
      } catch (err) {
        console.warn('Failed to load Study B:', err);
        if (!isCancelled) {
          setErrorB('Study sequence could not be loaded.');
          setLoadingB(false);
        }
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
      if (type === 'multi') {
        nv.setSliceType(nv.sliceTypeMultiplanar);
        nv.setMultiplanarLayout(2);
        nv.opts.multiplanarForceRender = true;
        nv.setCornerOrientationText(true);
      }
      else if (type === 'render') nv.setSliceType(nv.sliceTypeRender);
      else if (type === 'axial') nv.setSliceType(nv.sliceTypeAxial);
      nv.updateGLVolume();
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
                <option key={c.case_id} value={c.case_id} disabled={c.status === 'failed'}>
                  {c.case_id.substring(0, 16)} {c.status === 'completed' ? '✓' : `(${c.status})`}
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
                <option key={c.case_id} value={c.case_id} disabled={c.status === 'failed'}>
                  {c.case_id.substring(0, 16)} {c.status === 'completed' ? '✓' : `(${c.status})`}
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
              gap: '6px',
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
            <IconCrossFade
              isActive={Boolean(syncScroll)}
              ActiveIcon={LinkIcon}
              InactiveIcon={Unlink}
              size={12}
            />
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
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', height: '420px', minHeight: '420px', maxHeight: '420px', overflow: 'hidden' }}>
        {/* VIEWPORT A: Baseline Study */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            height: '420px',
            maxHeight: '420px',
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
              borderBottom: '1px solid #334155',
              flexShrink: 0
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
          <div style={{ flex: 1, position: 'relative', width: '100%', height: '100%', minHeight: 0, overflow: 'hidden', backgroundColor: '#0B0F19' }}>
            <canvas
              ref={canvasARef}
              className="niivue-canvas-el"
              style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', display: 'block' }}
            />
            {!caseAId ? (
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', backgroundColor: '#0B0F19', color: '#94A3B8', padding: '20px', textAlign: 'center', zIndex: 10 }}>
                <Layers size={28} style={{ color: '#475569', marginBottom: '8px' }} />
                <span style={{ fontSize: '13px', fontWeight: 600, color: '#E2E8F0' }}>No Baseline Study Selected</span>
                <p style={{ fontSize: '11px', color: '#64748B', margin: '4px 0 12px 0', maxWidth: '280px' }}>
                  Select a completed study above or load an instant demonstration pair.
                </p>
                <button
                  type="button"
                  onClick={handleLoadDemoPair}
                  disabled={isGeneratingDemo}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '5px 10px',
                    fontSize: '11px',
                    fontWeight: 600,
                    backgroundColor: '#1E293B',
                    color: '#38BDF8',
                    border: '1px solid #334155',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                >
                  <Sparkles size={12} />
                  <span>Load Demo Pair (T0 vs T1)</span>
                </button>
              </div>
            ) : loadingA ? (
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(11, 15, 25, 0.85)', color: '#38BDF8', gap: '8px', zIndex: 10 }}>
                <Loader2 size={24} className="animate-spin" />
                <span style={{ fontSize: '12px', fontWeight: 600 }}>Loading Baseline Study...</span>
              </div>
            ) : errorA ? (
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', backgroundColor: '#0B0F19', color: '#F87171', padding: '16px', textAlign: 'center', gap: '6px', zIndex: 10 }}>
                <AlertTriangle size={24} />
                <span style={{ fontSize: '12px', fontWeight: 600 }}>{errorA}</span>
              </div>
            ) : null}
          </div>
        </div>

        {/* VIEWPORT B: Follow-up Study */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            height: '420px',
            maxHeight: '420px',
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
              borderBottom: '1px solid #334155',
              flexShrink: 0
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
          <div style={{ flex: 1, position: 'relative', width: '100%', height: '100%', minHeight: 0, overflow: 'hidden', backgroundColor: '#0B0F19' }}>
            <canvas
              ref={canvasBRef}
              className="niivue-canvas-el"
              style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', display: 'block' }}
            />
            {!caseBId ? (
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', backgroundColor: '#0B0F19', color: '#94A3B8', padding: '20px', textAlign: 'center', zIndex: 10 }}>
                <Layers size={28} style={{ color: '#475569', marginBottom: '8px' }} />
                <span style={{ fontSize: '13px', fontWeight: 600, color: '#E2E8F0' }}>No Follow-up Study Selected</span>
                <p style={{ fontSize: '11px', color: '#64748B', margin: '4px 0 12px 0', maxWidth: '280px' }}>
                  Select a follow-up study above or load an instant demonstration pair.
                </p>
                <button
                  type="button"
                  onClick={handleLoadDemoPair}
                  disabled={isGeneratingDemo}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '5px 10px',
                    fontSize: '11px',
                    fontWeight: 600,
                    backgroundColor: '#1E293B',
                    color: '#F97316',
                    border: '1px solid #334155',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                >
                  <Sparkles size={12} />
                  <span>Load Demo Pair (T0 vs T1)</span>
                </button>
              </div>
            ) : loadingB ? (
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(11, 15, 25, 0.85)', color: '#F97316', gap: '8px', zIndex: 10 }}>
                <Loader2 size={24} className="animate-spin" />
                <span style={{ fontSize: '12px', fontWeight: 600 }}>Loading Follow-up Study...</span>
              </div>
            ) : errorB ? (
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', backgroundColor: '#0B0F19', color: '#F87171', padding: '16px', textAlign: 'center', gap: '6px', zIndex: 10 }}>
                <AlertTriangle size={24} />
                <span style={{ fontSize: '12px', fontWeight: 600 }}>{errorB}</span>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      {/* Volumetric RANO Assessment & Spatial Compatibility HUD (THE COMPARISON CHART) */}
      {loadingComparison ? (
        <div style={{ backgroundColor: '#FFFFFF', border: '1px solid var(--border-structural)', borderRadius: 'var(--radius-sm)', padding: '16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', color: '#64748B', fontSize: '12px' }}>
          <Loader2 size={16} className="animate-spin" style={{ color: 'var(--primary-accent)' }} />
          <span>Computing quantitative volumetric deltas & evaluating RANO response criteria...</span>
        </div>
      ) : comparisonData ? (
        <div
          style={{
            backgroundColor: '#FFFFFF',
            border: '1px solid var(--border-structural)',
            borderRadius: 'var(--radius-sm)',
            padding: '14px 16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
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

          {/* Visual Comparative Bar Chart Cards (THE COMPARISON CHART) */}
          {comparisonData.volumetric_deltas && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
              {[
                { key: 'WT', name: 'Whole Tumor (WT)' },
                { key: 'TC', name: 'Tumor Core (TC)' },
                { key: 'ET', name: 'Enhancing Tumor (ET)' }
              ].map(({ key, name }) => {
                const d = comparisonData.volumetric_deltas[key] || {};
                const base = d.baseline_volume_ml || 0;
                const follow = d.followup_volume_ml || 0;
                const maxVal = Math.max(base, follow, 0.01);
                const basePct = Math.min(100, Math.max(8, Math.round((base / maxVal) * 100)));
                const followPct = Math.min(100, Math.max(8, Math.round((follow / maxVal) * 100)));
                const isNeg = d.percentage_delta < 0;
                const isPos = d.percentage_delta > 0;

                return (
                  <div
                    key={key}
                    style={{
                      backgroundColor: '#F8FAFC',
                      border: '1px solid #E2E8F0',
                      borderRadius: '6px',
                      padding: '10px 12px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '11px', fontWeight: 700, color: '#0F172A' }}>{name}</span>
                      <span
                        style={{
                          fontSize: '10px',
                          fontWeight: 700,
                          padding: '2px 6px',
                          borderRadius: '3px',
                          backgroundColor: isNeg ? '#ECFDF5' : (isPos ? '#FEF2F2' : '#F1F5F9'),
                          color: isNeg ? '#065F46' : (isPos ? '#991B1B' : '#475569'),
                          border: `1px solid ${isNeg ? '#A7F3D0' : (isPos ? '#FECACA' : '#E2E8F0')}`
                        }}
                      >
                        {d.percentage_delta > 0 ? `+${d.percentage_delta.toFixed(1)}%` : `${d.percentage_delta?.toFixed(1)}%`}
                      </span>
                    </div>

                    {/* Comparative Bars */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '10px' }}>
                      {/* T0 Baseline */}
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748B', marginBottom: '2px' }}>
                          <span style={{ fontWeight: 600, color: '#0284C7' }}>T0 Baseline:</span>
                          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{base.toFixed(2)} mL</span>
                        </div>
                        <div style={{ width: '100%', height: '8px', backgroundColor: '#E2E8F0', borderRadius: '4px', overflow: 'hidden' }}>
                          <div className="analytics-bar-fill" style={{ width: `${basePct}%`, height: '100%', backgroundColor: '#0284C7', borderRadius: '4px' }} />
                        </div>
                      </div>

                      {/* T1 Follow-up */}
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748B', marginBottom: '2px' }}>
                          <span style={{ fontWeight: 600, color: '#EA580C' }}>T1 Follow-up:</span>
                          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{follow.toFixed(2)} mL</span>
                        </div>
                        <div style={{ width: '100%', height: '8px', backgroundColor: '#E2E8F0', borderRadius: '4px', overflow: 'hidden' }}>
                          <div className="analytics-bar-fill" style={{ width: `${followPct}%`, height: '100%', backgroundColor: '#EA580C', borderRadius: '4px' }} />
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#475569', borderTop: '1px solid #E2E8F0', paddingTop: '4px' }}>
                      <span>Absolute Delta:</span>
                      <strong style={{ fontFamily: 'var(--font-mono)', color: isNeg ? '#065F46' : (isPos ? '#991B1B' : '#475569') }}>
                        {d.absolute_delta_ml > 0 ? `+${d.absolute_delta_ml.toFixed(2)}` : d.absolute_delta_ml?.toFixed(2)} mL
                      </strong>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* 4-Column Quantitative Volumetric Delta Table */}
          {comparisonData.volumetric_deltas && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', textAlign: 'left', marginTop: '2px' }}>
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
      ) : (
        <div style={{ backgroundColor: '#F8FAFC', border: '1px dashed #CBD5E1', borderRadius: 'var(--radius-sm)', padding: '14px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#64748B', fontSize: '11px' }}>
            <TrendingUp size={16} style={{ color: '#94A3B8' }} />
            <span>Select both a Baseline (T0) and Follow-up (T1) study above to calculate volumetric deltas and RANO trajectory.</span>
          </div>
          <button
            type="button"
            onClick={handleLoadDemoPair}
            disabled={isGeneratingDemo}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 8px',
              fontSize: '11px',
              fontWeight: 600,
              backgroundColor: '#EFF6FF',
              color: '#1D4ED8',
              border: '1px solid #93C5FD',
              borderRadius: '4px',
              cursor: isGeneratingDemo ? 'wait' : 'pointer'
            }}
          >
            <Sparkles size={12} />
            <span>Load Demo Pair</span>
          </button>
        </div>
      )}
    </div>
  );
}
