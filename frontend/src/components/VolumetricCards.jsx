import React from 'react';
import { Activity, Box } from 'lucide-react';

export default function VolumetricCards({ volumes, spatialMetadata }) {
  const wt = volumes?.WT || { voxel_count: 0, volume_ml: 0.0 };
  const tc = volumes?.TC || { voxel_count: 0, volume_ml: 0.0 };
  const et = volumes?.ET || { voxel_count: 0, volume_ml: 0.0 };

  const spacing = spatialMetadata?.voxel_spacing_mm || [1.0, 1.0, 1.0];

  return (
    <div className="glass-panel">
      <div className="panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Activity size={18} style={{ color: 'var(--accent-cyan)' }} />
          <h2 className="panel-title">2. Volumetric Quantitation (Contract FR-6)</h2>
        </div>
        <span className="mono-val" style={{ fontSize: '0.75rem' }}>
          Formula: V = N &times; {spacing[0]} &times; {spacing[1]} &times; {spacing[2]} / 1000
        </span>
      </div>

      <div
        className="panel-body"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px',
        }}
      >
        {/* Whole Tumour (WT) Card */}
        <div
          style={{
            padding: '14px',
            background: 'rgba(0, 0, 0, 0.3)',
            borderRadius: 'var(--radius-sm)',
            borderLeft: '4px solid var(--accent-red)',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
          }}
        >
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            Whole Tumour (WT)
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            {wt.volume_ml.toFixed(2)} <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>mL</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Voxel Count: <span className="mono-val">{wt.voxel_count.toLocaleString()}</span>
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            Tissue: NCR + ED + ET (Labels 1, 2, 4)
          </div>
          {wt.bounding_box_voxel && (
            <div style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', marginTop: '4px' }}>
              BBox: [{wt.bounding_box_voxel.min.join(', ')}] to [{wt.bounding_box_voxel.max.join(', ')}]
            </div>
          )}
        </div>

        {/* Tumour Core (TC) Card */}
        <div
          style={{
            padding: '14px',
            background: 'rgba(0, 0, 0, 0.3)',
            borderRadius: 'var(--radius-sm)',
            borderLeft: '4px solid var(--accent-blue)',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
          }}
        >
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            Tumour Core (TC)
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            {tc.volume_ml.toFixed(2)} <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>mL</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Voxel Count: <span className="mono-val">{tc.voxel_count.toLocaleString()}</span>
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            Tissue: NCR + ET (Labels 1, 4)
          </div>
          {tc.bounding_box_voxel && (
            <div style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', marginTop: '4px' }}>
              BBox: [{tc.bounding_box_voxel.min.join(', ')}] to [{tc.bounding_box_voxel.max.join(', ')}]
            </div>
          )}
        </div>

        {/* Enhancing Tumour (ET) Card */}
        <div
          style={{
            padding: '14px',
            background: 'rgba(0, 0, 0, 0.3)',
            borderRadius: 'var(--radius-sm)',
            borderLeft: '4px solid var(--accent-amber)',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
          }}
        >
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            Enhancing Tumour (ET)
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            {et.volume_ml.toFixed(2)} <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>mL</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Voxel Count: <span className="mono-val">{et.voxel_count.toLocaleString()}</span>
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            Tissue: Active Enhancing Tumour (Label 4)
          </div>
          {et.bounding_box_voxel && (
            <div style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', marginTop: '4px' }}>
              BBox: [{et.bounding_box_voxel.min.join(', ')}] to [{et.bounding_box_voxel.max.join(', ')}]
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
