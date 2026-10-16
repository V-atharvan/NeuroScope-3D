import React, { useEffect, useRef, useState } from 'react';
import { Niivue } from '@niivue/niivue';
import { Eye, Layers, Compass, Crosshair, Box } from 'lucide-react';

export default function NiiVueViewer({
  baseScanFile,
  maskUrl,
  suggestedCrosshair,
}) {
  const canvasRef = useRef(null);
  const nvRef = useRef(null);

  const [currentSliceType, setCurrentSliceType] = useState('multi');
  const [crosshairPos, setCrosshairPos] = useState({ vox: [0, 0, 0], mm: [0, 0, 0], val: 0 });
  const [overlayOpacity, setOverlayOpacity] = useState(0.65);
  const [isOverlayVisible, setIsOverlayVisible] = useState(true);
  const [statusMessage, setStatusMessage] = useState('Viewer standby. Upload study files to visualize.');

  // Initialize NiiVue instance on mount
  useEffect(() => {
    if (!canvasRef.current) return;

    const nv = new Niivue({
      backColor: [0.03, 0.05, 0.08, 1.0],
      crosshairColor: [0.0, 0.9, 1.0, 0.75],
      show3Dcrosshair: true,
      isColorbar: false,
      loadingText: 'Loading Medical Volume...',
    });

    nv.attachToCanvas(canvasRef.current);
    nv.setSliceType(nv.sliceTypeMultiplanar);

    // Crosshair location updates
    nv.onLocationChange = (data) => {
      if (data) {
        setCrosshairPos({
          vox: data.vox ? data.vox.map((v) => Math.round(v)) : [0, 0, 0],
          mm: data.mm ? data.mm.map((m) => Number(m.toFixed(1))) : [0, 0, 0],
          val: data.values && data.values.length > 0 ? data.values[0] : 0,
        });
      }
    };

    nvRef.current = nv;

    return () => {
      // Cleanup
      try {
        nv.destroy();
      } catch (e) {
        // ignore on unmount
      }
    };
  }, []);

  // Load Base Scan when supplied
  useEffect(() => {
    const nv = nvRef.current;
    if (!nv || !baseScanFile) return;

    setStatusMessage(`Loading reference sequence: ${baseScanFile.name}...`);
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        await nv.loadFromArrayBuffer(reader.result, baseScanFile.name);
        setStatusMessage(`Loaded: ${baseScanFile.name}`);
        if (nv.volumes.length > 0) {
          nv.volumes[0].colormap = 'gray';
          nv.updateGLVolume();
        }
      } catch (err) {
        setStatusMessage(`Failed to display NIfTI volume: ${err.message}`);
      }
    };
    reader.readAsArrayBuffer(baseScanFile);
  }, [baseScanFile]);

  // Load Segmentation Overlay when mask URL changes
  useEffect(() => {
    const nv = nvRef.current;
    if (!nv || !maskUrl) return;

    setStatusMessage('Loading predicted BraTS 2021 segmentation overlay...');
    fetch(maskUrl)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.arrayBuffer();
      })
      .then(async (buffer) => {
        await nv.loadFromArrayBuffer(buffer, 'predicted_seg.nii.gz');
        if (nv.volumes.length > 1) {
          nv.setOpacity(1, overlayOpacity);
          // Set overlay colormap
          nv.volumes[1].colormap = 'roi_i8';
          nv.updateGLVolume();
        }
        setStatusMessage('Segmentation overlay loaded. BraTS labels 1 (NCR), 2 (ED), 4 (ET) active.');
      })
      .catch((err) => {
        setStatusMessage(`Could not load overlay: ${err.message}`);
      });
  }, [maskUrl]);

  // Handle Slice View Switching
  const handleSliceTypeChange = (type) => {
    const nv = nvRef.current;
    if (!nv) return;

    setCurrentSliceType(type);
    switch (type) {
      case 'multi':
        nv.setSliceType(nv.sliceTypeMultiplanar);
        break;
      case 'axial':
        nv.setSliceType(nv.sliceTypeAxial);
        break;
      case 'coronal':
        nv.setSliceType(nv.sliceTypeCoronal);
        break;
      case 'sagittal':
        nv.setSliceType(nv.sliceTypeSagittal);
        break;
      case 'render':
        nv.setSliceType(nv.sliceTypeRender);
        break;
      default:
        nv.setSliceType(nv.sliceTypeMultiplanar);
    }
  };

  // Handle Overlay Opacity change
  const handleOpacityChange = (val) => {
    const nv = nvRef.current;
    setOverlayOpacity(val);
    if (nv && nv.volumes.length > 1) {
      nv.setOpacity(1, isOverlayVisible ? val : 0.0);
    }
  };

  const toggleOverlayVisibility = () => {
    const nv = nvRef.current;
    const nextVis = !isOverlayVisible;
    setIsOverlayVisible(nextVis);
    if (nv && nv.volumes.length > 1) {
      nv.setOpacity(1, nextVis ? overlayOpacity : 0.0);
    }
  };

  return (
    <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Viewer Header with View Buttons */}
      <div className="panel-header" style={{ flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Eye size={18} style={{ color: 'var(--accent-cyan)' }} />
          <h2 className="panel-title">NiiVue 3D & Linked Multi-Planar Viewer</h2>
        </div>

        {/* View Mode Switcher */}
        <div style={{ display: 'flex', gap: '4px', background: 'rgba(0,0,0,0.3)', padding: '2px', borderRadius: 'var(--radius-sm)' }}>
          {[
            { id: 'multi', label: 'Multi-Planar' },
            { id: 'axial', label: 'Axial' },
            { id: 'coronal', label: 'Coronal' },
            { id: 'sagittal', label: 'Sagittal' },
            { id: 'render', label: '3D Render' },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => handleSliceTypeChange(item.id)}
              className="btn btn-secondary"
              style={{
                padding: '4px 10px',
                fontSize: '0.75rem',
                border: 'none',
                background: currentSliceType === item.id ? 'var(--accent-blue)' : 'transparent',
                color: currentSliceType === item.id ? '#fff' : 'var(--text-secondary)',
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main WebGL Canvas */}
      <div style={{ position: 'relative', flex: 1, minHeight: '440px', background: '#05080f' }}>
        <canvas
          ref={canvasRef}
          style={{ width: '100%', height: '100%', display: 'block' }}
        />

        {/* Crosshair Readout HUD */}
        <div
          style={{
            position: 'absolute',
            bottom: '12px',
            left: '12px',
            background: 'rgba(10, 14, 23, 0.85)',
            border: '1px solid var(--border-subtle)',
            padding: '6px 12px',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.75rem',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            gap: '14px',
            alignItems: 'center',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Crosshair size={14} style={{ color: 'var(--accent-cyan)' }} />
            <span style={{ color: 'var(--text-muted)' }}>Voxel:</span>
            <span className="mono-val">[{crosshairPos.vox.join(', ')}]</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Compass size={14} style={{ color: 'var(--accent-green)' }} />
            <span style={{ color: 'var(--text-muted)' }}>World (mm):</span>
            <span className="mono-val">[{crosshairPos.mm.join(', ')}]</span>
          </div>
        </div>

        {/* Status Pill in Canvas */}
        <div
          style={{
            position: 'absolute',
            top: '12px',
            left: '12px',
            background: 'rgba(10, 14, 23, 0.75)',
            border: '1px solid var(--border-subtle)',
            padding: '4px 10px',
            borderRadius: '9999px',
            fontSize: '0.75rem',
            color: 'var(--text-secondary)',
          }}
        >
          {statusMessage}
        </div>
      </div>

      {/* Viewer Footer: Opacity & Legend Controls */}
      <div
        style={{
          padding: '12px 18px',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          background: 'rgba(0,0,0,0.2)',
        }}
      >
        {/* Tissue Color Legend */}
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', fontSize: '0.75rem' }}>
          <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>BraTS 2021 Labels:</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: 'var(--tissue-ncr)' }}></span>
            <span>Label 1: NCR</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: 'var(--tissue-ed)' }}></span>
            <span>Label 2: ED</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: 'var(--tissue-et)' }}></span>
            <span>Label 4: ET</span>
          </div>
        </div>

        {/* Overlay Opacity Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={toggleOverlayVisibility}
            className="btn btn-secondary"
            style={{ padding: '4px 8px', fontSize: '0.75rem' }}
          >
            <Layers size={14} />
            <span>{isOverlayVisible ? 'Hide Mask' : 'Show Mask'}</span>
          </button>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Opacity:</span>
          <input
            type="range"
            min="0.1"
            max="1.0"
            step="0.05"
            value={overlayOpacity}
            onChange={(e) => handleOpacityChange(parseFloat(e.target.value))}
            style={{ width: '90px', accentColor: 'var(--accent-cyan)' }}
          />
          <span className="mono-val" style={{ fontSize: '0.75rem' }}>{Math.round(overlayOpacity * 100)}%</span>
        </div>
      </div>
    </div>
  );
}
