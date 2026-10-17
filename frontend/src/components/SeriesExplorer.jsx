import React from 'react';

export default function SeriesExplorer({
  activeSequenceKey,
  onSelectSequence,
  volumes,
  caseData,
  runtimeSeconds
}) {
  const shape = caseData?.spatial_summary?.shape;
  const sliceCount = shape && shape[2] ? `${shape[2]} SL` : '--';
  const spacing = caseData?.spatial_summary?.spacing_mm;
  const resolutionStr = spacing ? `${spacing.map((s) => Number(s).toFixed(1)).join(' × ')} mm` : '--';

  const sequences = [
    { key: 't1', name: 'T1-Weighted Native', slices: sliceCount },
    { key: 't1gd', name: 'T1CE Contrast Enhanced', slices: sliceCount },
    { key: 't2', name: 'T2-Weighted Structural', slices: sliceCount },
    { key: 'flair', name: 'FLAIR Volumetric', slices: sliceCount },
  ];

  const wtVol = volumes?.WT?.volume_ml ? `${volumes.WT.volume_ml.toFixed(1)} cm³` : '--';
  const tcVol = volumes?.TC?.volume_ml ? `${volumes.TC.volume_ml.toFixed(1)} cm³` : '--';
  const etVol = volumes?.ET?.volume_ml ? `${volumes.ET.volume_ml.toFixed(1)} cm³` : '--';

  return (
    <aside className="series-sidebar">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {/* Series Explorer Navigation */}
        <div>
          <div className="sidebar-section-title">Series Explorer</div>
          <nav>
            {sequences.map((seq) => {
              const isSelected = activeSequenceKey === seq.key;
              return (
                <button
                  key={seq.key}
                  type="button"
                  className={`series-item-btn ${isSelected ? 'active' : ''}`}
                  onClick={() => onSelectSequence(seq.key)}
                  title={`View ${seq.name} in viewport`}
                >
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, paddingRight: '8px' }}>
                    {seq.name}
                  </span>
                  <span className="slice-tag">{seq.slices}</span>
                </button>
              );
            })}
          </nav>
        </div>

        <div style={{ height: '1px', backgroundColor: 'var(--border-structural)' }} />

        {/* Segmentation Layers Section */}
        <div>
          <div className="sidebar-section-title">Segmentation Layers</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '6px 8px',
                backgroundColor: 'var(--tissue-et)',
                color: '#0F172A',
                border: '1px solid var(--tissue-et-border)',
                borderRadius: 'var(--radius-sm)',
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                fontWeight: 600
              }}
            >
              <span>Enhancing Tumor (ET)</span>
              <span>{etVol}</span>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '6px 8px',
                backgroundColor: 'var(--tissue-tc)',
                color: '#FFFFFF',
                border: '1px solid var(--tissue-tc-border)',
                borderRadius: 'var(--radius-sm)',
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                fontWeight: 600
              }}
            >
              <span>Tumour Core (TC)</span>
              <span>{tcVol}</span>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '6px 8px',
                backgroundColor: 'var(--tissue-wt)',
                color: '#FFFFFF',
                border: '1px solid var(--tissue-wt-border)',
                borderRadius: 'var(--radius-sm)',
                fontFamily: 'var(--font-mono)',
                fontSize: '11px',
                fontWeight: 600
              }}
            >
              <span>Whole Tumour (WT)</span>
              <span>{wtVol}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Telemetry Footer */}
      <div
        style={{
          borderTop: '1px solid var(--border-structural)',
          paddingTop: '12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          fontFamily: 'var(--font-mono)',
          fontSize: '11px',
          color: 'var(--on-surface-variant)'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>Inference Device</span>
          <span style={{ fontWeight: 600, color: 'var(--on-surface-dark)' }}>PyTorch / MONAI</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>Resolution</span>
          <span style={{ color: 'var(--on-surface-dark)' }}>{resolutionStr}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>Pipeline Latency</span>
          <span style={{ color: 'var(--on-surface-dark)' }}>
            {runtimeSeconds ? `${runtimeSeconds}s` : '--'}
          </span>
        </div>
      </div>
    </aside>
  );
}
