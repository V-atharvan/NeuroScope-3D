import React, { useEffect, useRef, useState } from 'react';
import { Niivue, NVImage } from '@niivue/niivue';
import * as nifti from 'nifti-reader-js';
import { Eye, Check, Layers, Sliders, Target, RotateCcw } from 'lucide-react';

function updateMaskLut(maskVol, mode, reg, layers, opacity) {
  if (!maskVol) return;
  const alphaVal = Math.round(opacity * 255);

  if (mode === 'agreement') {
    const agreementLut = {
      R: [0, 16, 239, 139],
      G: [0, 185, 68, 92],
      B: [0, 129, 68, 246],
      A: [0, alphaVal, alphaVal, alphaVal],
      I: [0, 1, 2, 3],
      labels: ['TN (Transparent)', 'TP (Consensus)', 'FP (Over-predicted)', 'FN (Missed)'],
    };
    if (typeof maskVol.setColormapLabel === 'function') {
      maskVol.setColormapLabel(agreementLut);
    }
  } else {
    // BraTS 2021 labels:
    // 0: Background (100% transparent)
    // 1: Necrotic Core (NCR) -> part of WT, TC
    // 2: Edema (ED) -> part of WT
    // 4: Enhancing Tumour (ET) -> part of WT, TC, ET
    const showWT = layers.WT;
    const showTC = layers.TC;
    const showET = layers.ET;

    const bratsLut = {
      R: [0, 239, 245, 0, 6],
      G: [0, 68, 158, 0, 182],
      B: [0, 68, 11, 0, 212],
      A: [
        0,                                           // 0: BG transparent
        (showWT && showTC) ? alphaVal : 0,           // 1: NCR
        showWT ? alphaVal : 0,                       // 2: ED
        0,                                           // 3: Unused
        (showWT && showTC && showET) ? alphaVal : 0, // 4: ET
      ],
      I: [0, 1, 2, 3, 4],
      labels: [
        'Background',
        'Necrotic Core (NCR)',
        'Peritumoral Edema (ED)',
        'Unused',
        'Enhancing Tumour (ET)',
      ],
    };
    if (typeof maskVol.setColormapLabel === 'function') {
      maskVol.setColormapLabel(bratsLut);
    }
  }
}

export default function NiiVueViewer({
  baseScanFile,
  baseScanUrl,
  maskUrl,
  suggestedCrosshair,
  activeSequenceKey = 't1gd',
  activeSequenceLabel = 'T1CE',
  caseId,
  hasExpertMask = false,
  layerVisibility: propLayerVisibility,
  onToggleLayer: propOnToggleLayer,
  overlayMode: propOverlayMode,
  agreementRegion: propAgreementRegion,
  onSetOverlayMode: propOnSetOverlayMode,
  onSetAgreementRegion: propOnSetAgreementRegion,
}) {
  const canvasRef = useRef(null);
  const nvRef = useRef(null);

  const [currentSliceType, setCurrentSliceType] = useState('multi');
  const [crosshairPos, setCrosshairPos] = useState(null);
  const [volumeDims, setVolumeDims] = useState(null);
  const [isViewerReady, setIsViewerReady] = useState(false);
  const [overlayOpacity, setOverlayOpacity] = useState(0.75);
  const [wlPreset, setWlPreset] = useState('Brain');
  const [statusMessage, setStatusMessage] = useState('Standby • Ready for multi-sequence MRI study');
  const [internalOverlayMode, setInternalOverlayMode] = useState('prediction'); // 'prediction' | 'agreement'
  const [internalAgreementRegion, setInternalAgreementRegion] = useState('WT'); // 'WT' | 'TC' | 'ET'
  const [baseLoadedCount, setBaseLoadedCount] = useState(0);

  const overlayMode = propOverlayMode || internalOverlayMode;
  const agreementRegion = propAgreementRegion || internalAgreementRegion;

  const setOverlayMode = (mode) => {
    if (propOnSetOverlayMode) {
      propOnSetOverlayMode(mode);
    } else {
      setInternalOverlayMode(mode);
    }
  };

  const setAgreementRegion = (reg) => {
    if (propOnSetAgreementRegion) {
      propOnSetAgreementRegion(reg);
    } else {
      setInternalAgreementRegion(reg);
    }
  };


  const [internalLayerVisibility, setInternalLayerVisibility] = useState({
    WT: true,
    TC: true,
    ET: true,
  });

  const layerVisibility = propLayerVisibility || internalLayerVisibility;

  // Reset Camera / Scene action to canonical orientations
  const handleResetCamera = () => {
    const nv = nvRef.current;
    if (!nv || !isViewerReady) return;
    try {
      if (typeof nv.resetScene === 'function') {
        nv.resetScene();
      }
      if (suggestedCrosshair && Array.isArray(suggestedCrosshair) && suggestedCrosshair.length >= 3) {
        navigateToCentroid(suggestedCrosshair);
      } else if (typeof nv.vox2frac === 'function' && volumeDims) {
        const center = volumeDims.map((d) => Math.floor(d / 2));
        nv.scene.crosshairPos = nv.vox2frac(center, 0);
      }
      nv.updateGLVolume();
      setStatusMessage('Camera and multiplanar orientation reset to canonical views');
    } catch (e) {
      console.warn('Reset scene failed:', e.message);
    }
  };

  // Navigate crosshair to specific voxel indices and synchronize all views
  const navigateToCentroid = (coords) => {
    const nv = nvRef.current;
    if (!nv || !isViewerReady || !nv.volumes || nv.volumes.length === 0) return;
    const target = coords || suggestedCrosshair;
    if (!target || !Array.isArray(target) || target.length < 3) return;

    try {
      if (typeof nv.vox2frac === 'function') {
        const frac = nv.vox2frac(target, 0);
        nv.scene.crosshairPos = frac;
        nv.updateGLVolume();
        if (typeof nv.createOnLocationChange === 'function') {
          nv.createOnLocationChange();
        }
      }
    } catch (e) {
      console.warn('Centroid navigation failed:', e.message);
    }
  };

  // Initialize NiiVue instance on mount
  useEffect(() => {
    if (!canvasRef.current) return;
    let isCancelled = false;

    const nv = new Niivue({
      backColor: [0.0, 0.0, 0.0, 1.0], // Clinical diagnostic pure black
      crosshairColor: [0.39, 0.82, 0.96, 0.9], // Cyan #65D0F4
      show3Dcrosshair: true,
      isColorbar: false,
      loadingText: 'Rendering Multi-Planar Voxel Grid...',
      isOrientCube: true,
    });

    async function initViewer() {
      try {
        await nv.attachToCanvas(canvasRef.current);
        if (isCancelled) return;
        nv.setSliceType(nv.sliceTypeMultiplanar);
        nv.setMultiplanarLayout(2); // MULTIPLANAR_TYPE.GRID = 2 (Forces 4 equal partitions)
        nv.opts.multiplanarForceRender = true; // Always render 3D Volume in 4th partition
        nv.opts.multiplanarPadPixels = 6;
        nv.setCornerOrientationText(true);

        // Crosshair location updates synchronized across multiplanar views
        nv.onLocationChange = (data) => {
          if (data && data.vox && data.mm) {
            setCrosshairPos({
              vox: data.vox.map((v) => Math.round(v)),
              mm: data.mm.map((m) => Number(m.toFixed(1))),
              val: data.values && data.values.length > 0 ? data.values[0] : 0,
            });
          }
        };

        nvRef.current = nv;
        setIsViewerReady(true);
      } catch (err) {
        console.error('Failed to attach Niivue to canvas:', err);
        setStatusMessage(`Viewer WebGL Error: ${err.message}`);
      }
    }

    initViewer();

    return () => {
      isCancelled = true;
      try {
        nv.destroy();
      } catch (e) {
        // ignore on unmount
      }
    };
  }, []);

  // Load Base Scan (either from File object or from URL)
  useEffect(() => {
    const nv = nvRef.current;
    if (!nv || !isViewerReady) return;
    if (!baseScanFile && !baseScanUrl) return;

    let isCancelled = false;
    const name = baseScanFile ? baseScanFile.name : (baseScanUrl || 'Volume');
    setStatusMessage(`Ingesting sequence: ${activeSequenceLabel || name}...`);

    async function loadBase() {
      try {
        let volume;
        if (baseScanFile) {
          volume = await NVImage.loadFromFile({
            file: baseScanFile,
            colormap: 'gray',
            opacity: 1.0,
          });
        } else if (baseScanUrl) {
          volume = await NVImage.loadFromUrl({
            url: baseScanUrl,
            name: `${activeSequenceKey || 'sequence'}.nii.gz`,
            colormap: 'gray',
            opacity: 1.0,
          });
        }
        if (isCancelled || !volume) return;

        // Preserve existing segmentation or agreement overlay if already mounted
        const existingOverlay = (nv.volumes && nv.volumes.length > 1) ? nv.volumes[1] : null;

        while (nv.volumes && nv.volumes.length > 0) {
          nv.removeVolumeByIndex(0);
        }

        nv.addVolume(volume);
        if (existingOverlay) {
          nv.addVolume(existingOverlay);
          updateMaskLut(existingOverlay, overlayMode, agreementRegion, layerVisibility, overlayOpacity);
        }

        if (volume.dims && volume.dims.length >= 4) {
          setVolumeDims([volume.dims[1], volume.dims[2], volume.dims[3]]);
        }

        nv.updateGLVolume();
        setBaseLoadedCount((c) => c + 1);
        setStatusMessage(`Active sequence: ${activeSequenceLabel || name}`);
      } catch (err) {
        if (!isCancelled) {
          console.error('Failed to display volume:', err);
          setStatusMessage(`Failed to display volume: ${err.message}`);
        }
      }
    }

    loadBase();

    return () => {
      isCancelled = true;
    };
  }, [baseScanFile, baseScanUrl, activeSequenceKey, activeSequenceLabel, isViewerReady]);

  // Load and Validate Segmentation or Agreement Overlay
  useEffect(() => {
    const nv = nvRef.current;
    if (!nv || !isViewerReady) return;

    const isAgreement = overlayMode === 'agreement' && hasExpertMask && caseId;
    const targetUrl = isAgreement
      ? `/api/cases/${caseId}/agreement-mask?region=${agreementRegion}`
      : maskUrl;

    if (!targetUrl) {
      // Clear any leftover overlay volume when switching cases or resetting
      while (nv.volumes && nv.volumes.length > 1) {
        nv.removeVolumeByIndex(1);
      }
      nv.updateGLVolume();
      return;
    }

    let isCancelled = false;
    setStatusMessage(
      isAgreement
        ? `Loading Expert Agreement Map (${agreementRegion})...`
        : 'Loading predicted BraTS 2021 segmentation overlay...'
    );

    async function loadMask() {
      try {
        // Step 1: Pre-fetch and validate HTTP status
        const res = await fetch(targetUrl);
        if (!res.ok) {
          let errDetail = res.statusText;
          try {
            const errJson = await res.json();
            errDetail = errJson.detail || errJson.message || errDetail;
          } catch (_) {}
          throw new Error(`Failed to retrieve mask (HTTP ${res.status}: ${errDetail})`);
        }

        const arrayBuf = await res.arrayBuffer();
        if (arrayBuf.byteLength < 348) {
          throw new Error('Retrieved overlay payload is corrupted or empty.');
        }

        // Step 2: Validate NIfTI header and gzip decompression
        let niftiBuffer = arrayBuf;
        if (nifti.isCompressed(arrayBuf)) {
          niftiBuffer = nifti.decompress(arrayBuf);
        }
        if (!nifti.isNIFTI(niftiBuffer)) {
          throw new Error('Retrieved payload is not a valid NIfTI medical image.');
        }

        const hdr = nifti.readHeader(niftiBuffer);
        if (!hdr || !hdr.dims) {
          throw new Error('NIfTI volume header corrupt: dimensions are missing.');
        }

        const maskDims = [hdr.dims[1], hdr.dims[2], hdr.dims[3]];

        // Step 3: Verify spatial compatibility with reference MRI volume
        if (nv.volumes.length > 0 && nv.volumes[0].dims && nv.volumes[0].dims.length >= 4) {
          const baseDims = [nv.volumes[0].dims[1], nv.volumes[0].dims[2], nv.volumes[0].dims[3]];
          if (baseDims[0] !== maskDims[0] || baseDims[1] !== maskDims[1] || baseDims[2] !== maskDims[2]) {
            throw new Error(
              `Spatial dimension mismatch: Overlay [${maskDims.join('×')}] does not match reference MRI grid [${baseDims.join('×')}]. Overlay withheld from display to prevent clinical misalignment.`
            );
          }
        }

        // Step 4: Verify BraTS label values if prediction mode
        if (!isAgreement) {
          const imgData = nifti.readImage(hdr, niftiBuffer);
          const voxels = new Uint8Array(imgData);
          const allowedLabels = new Set([0, 1, 2, 4]);
          const sampleStep = Math.max(1, Math.floor(voxels.length / 50000));
          for (let i = 0; i < voxels.length; i += sampleStep) {
            if (!allowedLabels.has(voxels[i])) {
              console.warn(`Encountered non-standard label ${voxels[i]} in predicted mask.`);
              break;
            }
          }
        }

        // Step 5: Load validated volume into NiiVue with explicit filename
        const maskVolume = await NVImage.loadFromUrl({
          url: arrayBuf,
          name: isAgreement ? `agreement_${agreementRegion}.nii.gz` : 'predicted_seg.nii.gz',
          opacity: overlayOpacity,
        });

        if (isCancelled) return;

        // Apply custom discrete label colormap
        updateMaskLut(maskVolume, overlayMode, agreementRegion, layerVisibility, overlayOpacity);

        // Replace any existing overlay
        while (nv.volumes && nv.volumes.length > 1) {
          nv.removeVolumeByIndex(1);
        }
        nv.addVolume(maskVolume);

        setStatusMessage(
          isAgreement
            ? `Expert Agreement Active (${agreementRegion}) • 🟢 TP Consensus | 🔴 FP Over-pred | 🟣 FN Missed`
            : 'Segmentation overlay active • BraTS 2021 Labels 1 (NCR), 2 (ED), 4 (ET)'
        );
      } catch (err) {
        if (!isCancelled) {
          console.error('Mask overlay loading error:', err.message);
          setStatusMessage(`Overlay notice: ${err.message}`);
        }
      }
    }

    loadMask();

    return () => {
      isCancelled = true;
    };
  }, [maskUrl, overlayMode, agreementRegion, caseId, hasExpertMask, isViewerReady, baseLoadedCount]);

  // Synchronize colormap LUT whenever tissue visibility toggles or opacity changes
  useEffect(() => {
    const nv = nvRef.current;
    if (!nv || !isViewerReady || !nv.volumes || nv.volumes.length < 2) return;
    const maskVol = nv.volumes[1];
    updateMaskLut(maskVol, overlayMode, agreementRegion, layerVisibility, overlayOpacity);
    nv.updateGLVolume();
  }, [layerVisibility, overlayOpacity, overlayMode, agreementRegion, isViewerReady]);

  // Handle Suggested Tumor Crosshair Positioning
  useEffect(() => {
    if (suggestedCrosshair && Array.isArray(suggestedCrosshair) && suggestedCrosshair.length >= 3) {
      navigateToCentroid(suggestedCrosshair);
    }
  }, [suggestedCrosshair, isViewerReady]);

  // Handle Slice View Switching
  const handleSliceTypeChange = (type) => {
    const nv = nvRef.current;
    if (!nv) return;

    setCurrentSliceType(type);
    switch (type) {
      case 'multi':
        nv.setSliceType(nv.sliceTypeMultiplanar);
        nv.setMultiplanarLayout(2); // 4 equal partitions (2x2 grid)
        nv.opts.multiplanarForceRender = true;
        nv.opts.multiplanarPadPixels = 6;
        nv.setCornerOrientationText(true);
        break;
      case 'axial':
        nv.setSliceType(nv.sliceTypeAxial);
        break;
      case 'render':
        nv.setSliceType(nv.sliceTypeRender);
        break;
      default:
        nv.setSliceType(nv.sliceTypeMultiplanar);
        nv.setMultiplanarLayout(2);
        nv.opts.multiplanarForceRender = true;
    }
    nv.updateGLVolume();
  };

  // Handle Opacity Slider
  const handleOpacityChange = (e) => {
    const val = parseFloat(e.target.value);
    setOverlayOpacity(val);
    const nv = nvRef.current;
    if (nv && nv.volumes && nv.volumes.length > 1) {
      nv.setOpacity(1, val);
    }
  };

  // Handle Window/Level Presets
  const applyWlPreset = (preset) => {
    setWlPreset(preset);
    const nv = nvRef.current;
    if (!nv || !nv.volumes || nv.volumes.length === 0) return;

    const baseVol = nv.volumes[0];
    const robustMin = baseVol.robust_min || 0;
    const robustMax = baseVol.robust_max || 255;
    const range = robustMax - robustMin;

    switch (preset) {
      case 'Brain':
        baseVol.cal_min = robustMin + range * 0.1;
        baseVol.cal_max = robustMin + range * 0.7;
        break;
      case 'Subdural':
        baseVol.cal_min = robustMin + range * 0.2;
        baseVol.cal_max = robustMin + range * 0.9;
        break;
      case 'Bone':
        baseVol.cal_min = robustMin - range * 0.2;
        baseVol.cal_max = robustMax * 1.5;
        break;
      case 'Stroke':
        baseVol.cal_min = robustMin + range * 0.15;
        baseVol.cal_max = robustMin + range * 0.5;
        break;
      default:
        baseVol.cal_min = robustMin;
        baseVol.cal_max = robustMax;
    }
    nv.updateGLVolume();
  };

  // Toggle Tissue Layer Visibility
  const toggleLayer = (layerKey) => {
    if (propOnToggleLayer) {
      propOnToggleLayer(layerKey);
    } else {
      setInternalLayerVisibility((prev) => ({ ...prev, [layerKey]: !prev[layerKey] }));
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, overflow: 'hidden' }}>
      {/* Viewer Main Toolbar */}
      <div className="viewer-toolbar">
        {/* Viewport Switcher */}
        <div className="segmented-control">
          <button
            type="button"
            className={`segmented-btn ${currentSliceType === 'multi' ? 'active' : ''}`}
            onClick={() => handleSliceTypeChange('multi')}
          >
            Multiplanar (Axial, Coronal, Sagittal)
          </button>
          <button
            type="button"
            className={`segmented-btn ${currentSliceType === 'render' ? 'active' : ''}`}
            onClick={() => handleSliceTypeChange('render')}
          >
            3D Volume Render
          </button>
          <button
            type="button"
            className={`segmented-btn ${currentSliceType === 'axial' ? 'active' : ''}`}
            onClick={() => handleSliceTypeChange('axial')}
          >
            Axial Full
          </button>
        </div>

        {/* Overlay Mode Switcher */}
        <div className="segmented-control">
          <button
            type="button"
            className={`segmented-btn ${overlayMode === 'prediction' ? 'active' : ''}`}
            onClick={() => setOverlayMode('prediction')}
          >
            BraTS Labels
          </button>
          <button
            type="button"
            className={`segmented-btn ${overlayMode === 'agreement' ? 'active' : ''}`}
            disabled={!hasExpertMask}
            title={!hasExpertMask ? 'Upload expert ground truth mask to enable consensus overlay' : 'Color-coded TP/FP/FN consensus map'}
            onClick={() => setOverlayMode('agreement')}
            style={{ opacity: hasExpertMask ? 1 : 0.45, cursor: hasExpertMask ? 'pointer' : 'not-allowed' }}
          >
            Expert Agreement
          </button>
        </div>

        {/* Center Toolset: Mask Opacity & Color Chips / Agreement Legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          {/* Opacity Scrubber */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '11px', fontWeight: 600, color: '#0F172A', whiteSpace: 'nowrap' }}>
              Opacity: {Math.round(overlayOpacity * 100)}%
            </span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={overlayOpacity}
              onChange={handleOpacityChange}
              style={{ width: '80px', accentColor: 'var(--primary-accent)', cursor: 'pointer' }}
            />
          </div>

          <div style={{ height: '18px', width: '1px', backgroundColor: 'var(--border-subtle)' }} />

          {overlayMode === 'agreement' ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '10px', fontWeight: 600, color: '#475569' }}>Region:</span>
              {['WT', 'TC', 'ET'].map((reg) => (
                <button
                  key={reg}
                  type="button"
                  onClick={() => setAgreementRegion(reg)}
                  style={{
                    padding: '2px 7px',
                    fontSize: '10px',
                    fontWeight: agreementRegion === reg ? 700 : 500,
                    backgroundColor: agreementRegion === reg ? 'var(--primary-accent)' : '#FFFFFF',
                    color: agreementRegion === reg ? '#FFFFFF' : '#334155',
                    border: '1px solid #CBD5E1',
                    borderRadius: '3px',
                    cursor: 'pointer',
                  }}
                >
                  {reg}
                </button>
              ))}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px', marginLeft: '4px' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '3px', color: '#065F46', fontWeight: 600 }}>
                  <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#10B981', display: 'inline-block' }} />
                  TP
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '3px', color: '#991B1B', fontWeight: 600 }}>
                  <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#EF4444', display: 'inline-block' }} />
                  FP
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '3px', color: '#5B21B6', fontWeight: 600 }}>
                  <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#8B5CF6', display: 'inline-block' }} />
                  FN
                </span>
              </div>
            </div>
          ) : (
            /* Standard BraTS Layer Toggles */
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <button
                type="button"
                className="roi-chip-btn"
                style={{
                  backgroundColor: 'var(--tissue-wt)',
                  color: '#0F172A',
                  borderColor: 'var(--tissue-wt-border)',
                  opacity: layerVisibility.WT ? 1 : 0.5
                }}
                onClick={() => toggleLayer('WT')}
              >
                <Check size={11} strokeWidth={3} />
                <span>WT</span>
              </button>

              <button
                type="button"
                className="roi-chip-btn"
                style={{
                  backgroundColor: 'var(--tissue-tc)',
                  color: '#FFFFFF',
                  borderColor: 'var(--tissue-tc-border)',
                  opacity: layerVisibility.TC ? 1 : 0.5
                }}
                onClick={() => toggleLayer('TC')}
              >
                <Check size={11} strokeWidth={3} />
                <span>TC</span>
              </button>

              <button
                type="button"
                className="roi-chip-btn"
                style={{
                  backgroundColor: 'var(--tissue-et)',
                  color: '#0F172A',
                  borderColor: 'var(--tissue-et-border)',
                  opacity: layerVisibility.ET ? 1 : 0.5
                }}
                onClick={() => toggleLayer('ET')}
              >
                <Check size={11} strokeWidth={3} />
                <span>ET</span>
              </button>
            </div>
          )}
        </div>

        {/* Right Toolset: Presets & Live Coordinate Pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {/* Centroid Jump Button */}
          <button
            type="button"
            className="segmented-btn"
            disabled={!suggestedCrosshair || !Array.isArray(suggestedCrosshair) || suggestedCrosshair.length < 3}
            title={
              suggestedCrosshair && Array.isArray(suggestedCrosshair) && suggestedCrosshair.length >= 3
                ? `Jump to Tumour Centroid [${suggestedCrosshair.join(', ')}]`
                : 'Tumour centroid not available (empty mask)'
            }
            onClick={() => navigateToCentroid(suggestedCrosshair)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '3px 8px',
              fontSize: '11px',
              fontWeight: 600,
              backgroundColor: suggestedCrosshair ? '#F1F5F9' : '#F8FAFC',
              color: suggestedCrosshair ? 'var(--primary-accent)' : '#94A3B8',
              border: '1px solid var(--border-subtle)',
              borderRadius: '3px',
              cursor: suggestedCrosshair ? 'pointer' : 'not-allowed',
              opacity: suggestedCrosshair ? 1 : 0.6,
            }}
          >
            <Target size={12} strokeWidth={2.5} />
            <span>Centroid</span>
          </button>

          {/* Reset Camera / Orientation Action */}
          <button
            type="button"
            className="segmented-btn"
            title="Reset 2D crosshair and 3D camera to default canonical orientation"
            onClick={handleResetCamera}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '3px 8px',
              fontSize: '11px',
              fontWeight: 600,
              backgroundColor: '#F1F5F9',
              color: '#334155',
              border: '1px solid var(--border-subtle)',
              borderRadius: '3px',
              cursor: 'pointer',
            }}
          >
            <RotateCcw size={12} strokeWidth={2.5} />
            <span>Reset View</span>
          </button>

          {/* Window/Level Presets */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              border: '1px solid var(--border-subtle)',
              backgroundColor: '#FFFFFF',
              borderRadius: '2px',
              overflow: 'hidden'
            }}
          >
            <span
              className="font-mono"
              style={{
                padding: '2px 6px',
                backgroundColor: '#F1F5F9',
                fontSize: '10px',
                color: 'var(--on-surface-variant)'
              }}
            >
              W/L:
            </span>
            {['Brain', 'Subdural', 'Bone', 'Stroke'].map((preset) => (
              <button
                key={preset}
                type="button"
                style={{
                  padding: '2px 6px',
                  border: 'none',
                  fontSize: '10px',
                  fontWeight: wlPreset === preset ? 600 : 400,
                  backgroundColor: wlPreset === preset ? 'var(--primary-accent)' : 'transparent',
                  color: wlPreset === preset ? '#FFFFFF' : 'var(--on-surface-dark)',
                  cursor: 'pointer'
                }}
                onClick={() => applyWlPreset(preset)}
              >
                {preset}
              </button>
            ))}
          </div>

          {/* Live Coordinate Pill Badge */}
          <div className="coordinate-pill-badge">
            {crosshairPos?.vox && crosshairPos?.mm
              ? `Voxel: [${crosshairPos.vox.join(', ')}] | World: [${crosshairPos.mm.map((m) => `${m}mm`).join(', ')}]`
              : 'Voxel: [--, --, --] | World: [--, --, --]'}
          </div>
        </div>
      </div>

      {/* Viewport Canvas & HUD */}
      <div className="viewer-canvas-container">
        {/* Top HUD Header */}
        <div className="viewport-hud-header">
          <span style={{ color: 'var(--tissue-wt)', fontWeight: 700 }}>
            {currentSliceType === 'render' ? '3D VOLUME' : currentSliceType.toUpperCase()}
          </span>
          <span style={{ color: '#94A3B8' }}>|</span>
          <span>
            Z: {crosshairPos?.vox?.[2] !== undefined ? crosshairPos.vox[2] : '--'}
            {volumeDims?.[2] ? ` / ${volumeDims[2]}` : ''}
          </span>
          <span style={{ color: '#94A3B8' }}>|</span>
          <span style={{ color: 'var(--tissue-et)' }}>
            {activeSequenceLabel}{maskUrl ? ' + MONAI Seg' : ''}
          </span>
        </div>

        {/* Anatomical Orientation Badges (visible in 2D modes) */}
        {currentSliceType !== 'render' && (
          <>
            <span className="anatomical-badge" style={{ top: '8px', left: '50%', transform: 'translateX(-50%)' }}>
              A
            </span>
            <span className="anatomical-badge" style={{ bottom: '8px', left: '50%', transform: 'translateX(-50%)' }}>
              P
            </span>
            <span className="anatomical-badge" style={{ left: '8px', top: '50%', transform: 'translateY(-50%)' }}>
              R
            </span>
            <span className="anatomical-badge" style={{ right: '8px', top: '50%', transform: 'translateY(-50%)' }}>
              L
            </span>
          </>
        )}

        {/* Actual WebGL Canvas attached to NiiVue */}
        <canvas ref={canvasRef} className="niivue-canvas-el" />
      </div>
    </div>
  );
}
