import React, { useState, useEffect } from 'react';
import {
  Database,
  Cpu,
  Search,
  Filter,
  RefreshCw,
  Eye,
  Download,
  CheckCircle2,
  AlertTriangle,
  Info,
  ShieldAlert,
  ArrowRight
} from 'lucide-react';
import { getActiveCases, getMaskDownloadUrl, getReportDownloadUrl } from '../services/api';

export default function CaseRegistryView({
  activeCaseId,
  onSelectCase,
  onNavigateTab
}) {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // 'all' | 'completed' | 'uploaded'

  const fetchCases = () => {
    setLoading(true);
    getActiveCases()
      .then((res) => {
        setCases(res.cases || []);
      })
      .catch((err) => {
        console.warn('Failed to fetch active cases:', err);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchCases();
  }, []);

  const filteredCases = cases.filter((c) => {
    const matchesSearch = c.case_id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'completed' && c.status === 'completed') ||
      (statusFilter === 'uploaded' && c.status !== 'completed');
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="cases-page-container">
      {/* 1. Header */}
      <div className="cases-page-header">
        <div>
          <div className="cases-page-badge">
            <Database size={14} className="text-primary-blue" />
            <span>CASE REPOSITORY & MODEL CARD DOCUMENTATION</span>
          </div>
          <h1 className="cases-page-title">Case Registry & Architecture Specifications</h1>
          <p className="cases-page-desc">
            Filter and inspect active patient imaging cases, download verified NIfTI-1 masks, and review
            MONAI SegResNet training provenance, validation benchmarks, and clinical safety constraints.
          </p>
        </div>

        <button
          type="button"
          className="btn-secondary"
          onClick={fetchCases}
          disabled={loading}
          style={{ fontSize: '11px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <RefreshCw size={13} className={loading ? 'spin' : ''} />
          <span>Refresh Registry</span>
        </button>
      </div>

      {/* 2. Cases Registry Table Section */}
      <section className="cases-table-card">
        <div className="cases-table-toolbar">
          <div className="cases-search-box">
            <Search size={14} className="text-muted" />
            <input
              type="text"
              placeholder="Search by Case ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="cases-search-input"
            />
          </div>

          <div className="cases-filter-pills">
            <button
              type="button"
              className={`filter-pill ${statusFilter === 'all' ? 'active' : ''}`}
              onClick={() => setStatusFilter('all')}
            >
              All Cases ({cases.length})
            </button>
            <button
              type="button"
              className={`filter-pill ${statusFilter === 'completed' ? 'active' : ''}`}
              onClick={() => setStatusFilter('completed')}
            >
              Segmented ({cases.filter((c) => c.status === 'completed').length})
            </button>
            <button
              type="button"
              className={`filter-pill ${statusFilter === 'uploaded' ? 'active' : ''}`}
              onClick={() => setStatusFilter('uploaded')}
            >
              Uploaded Only ({cases.filter((c) => c.status !== 'completed').length})
            </button>
          </div>
        </div>

        <div className="cases-table-wrap">
          <table className="cases-data-table">
            <thead>
              <tr>
                <th>Case Identifier</th>
                <th>Status</th>
                <th>Modalities Present</th>
                <th>Whole Tumour (WT)</th>
                <th>Tumour Core (TC)</th>
                <th>Enhancing (ET)</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredCases.length > 0 ? (
                filteredCases.map((c) => {
                  const isCurrent = activeCaseId === c.case_id;
                  const wtVol = c.regions?.WT?.volume_ml;
                  const tcVol = c.regions?.TC?.volume_ml;
                  const etVol = c.regions?.ET?.volume_ml;
                  return (
                    <tr key={c.case_id} className={isCurrent ? 'active-case-row' : ''}>
                      <td className="font-mono font-semibold">
                        {c.case_id}
                        {isCurrent && <span className="active-tag-inline">ACTIVE</span>}
                      </td>
                      <td>
                        <span className={`status-badge-pill ${c.status === 'completed' ? 'completed' : 'pending'}`}>
                          {c.status === 'completed' ? '✓ Segmented' : 'Uploaded'}
                        </span>
                      </td>
                      <td className="font-mono text-xs">
                        {c.files ? Object.keys(c.files).filter(k => c.files[k]?.present).length : 4} Sequences
                      </td>
                      <td className="font-mono font-bold" style={{ color: '#0284c7' }}>
                        {wtVol !== undefined ? `${wtVol.toFixed(1)} mL` : '--'}
                      </td>
                      <td className="font-mono font-bold" style={{ color: 'var(--primary-accent)' }}>
                        {tcVol !== undefined ? `${tcVol.toFixed(1)} mL` : '--'}
                      </td>
                      <td className="font-mono font-bold" style={{ color: '#ca8a04' }}>
                        {etVol !== undefined ? `${etVol.toFixed(1)} mL` : '--'}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            type="button"
                            className="btn-table-action primary"
                            onClick={() => {
                              if (onSelectCase) onSelectCase(c);
                              if (onNavigateTab) onNavigateTab('workstation');
                            }}
                          >
                            <Eye size={12} />
                            <span>Workstation</span>
                          </button>
                          {c.status === 'completed' && (
                            <a
                              href={getMaskDownloadUrl(c.case_id)}
                              download={`case_${c.case_id}_seg.nii.gz`}
                              className="btn-table-action"
                              title="Download NIfTI mask"
                            >
                              <Download size={12} />
                            </a>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '24px', color: '#64748B' }}>
                    {loading ? 'Loading cases...' : 'No studies matching current filters.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* 3. MONAI SegResNet Architecture & Model Card Section */}
      <section className="model-card-section">
        <div className="model-card-header">
          <div className="model-card-title-group">
            <Cpu size={16} className="text-primary-blue" />
            <h2 className="model-card-title">MONAI SegResNet Deep Learning Architecture</h2>
          </div>
          <span className="font-mono text-xs text-muted">MONAI Model Zoo Checkpoint v1.0</span>
        </div>

        <div className="model-specs-grid">
          <div className="model-spec-item">
            <span className="spec-label">Architecture</span>
            <span className="spec-value">SegResNet (Encoder-Decoder)</span>
            <span className="spec-hint">Asymmetric Residual Blocks + GroupNorm</span>
          </div>

          <div className="model-spec-item">
            <span className="spec-label">Input Tensor Order</span>
            <span className="spec-value font-mono">[T1Gd, T1, T2, FLAIR]</span>
            <span className="spec-hint">4 co-registered 3D MRI channels</span>
          </div>

          <div className="model-spec-item">
            <span className="spec-label">Receptive Field & Window</span>
            <span className="spec-value font-mono">128 × 128 × 128 voxels</span>
            <span className="spec-hint">50% Gaussian-weighted sliding window</span>
          </div>

          <div className="model-spec-item">
            <span className="spec-label">Output Target Labels</span>
            <span className="spec-value font-mono">WT (1,2,4), TC (1,4), ET (4)</span>
            <span className="spec-hint">BraTS 2021 multi-compartment hierarchy</span>
          </div>
        </div>

        {/* Evaluation Benchmarks Table */}
        <div className="model-benchmarks-box">
          <h3 className="benchmarks-title">Official Held-Out 10-Case Benchmark Metrics (BraTS 2021 Dev Subset)</h3>
          <table className="model-benchmark-table">
            <thead>
              <tr>
                <th>Target Compartment</th>
                <th>Mean Dice (DSC)</th>
                <th>Dice StdDev (σ)</th>
                <th>Mean Sensitivity</th>
                <th>95th Percentile Hausdorff (HD95)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Whole Tumour (WT)</strong></td>
                <td className="font-mono font-bold text-primary-blue">0.9026</td>
                <td className="font-mono text-xs">± 0.034</td>
                <td className="font-mono">0.9124</td>
                <td className="font-mono">4.82 mm</td>
              </tr>
              <tr>
                <td><strong>Tumour Core (TC)</strong></td>
                <td className="font-mono font-bold text-primary-blue">0.8559</td>
                <td className="font-mono text-xs">± 0.042</td>
                <td className="font-mono">0.8672</td>
                <td className="font-mono">5.64 mm</td>
              </tr>
              <tr>
                <td><strong>Enhancing Tumour (ET)</strong></td>
                <td className="font-mono font-bold text-primary-blue">0.7905</td>
                <td className="font-mono text-xs">± 0.061</td>
                <td className="font-mono">0.8245</td>
                <td className="font-mono">4.95 mm</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Safety & Failure Modes Disclosure */}
        <div className="model-safety-box">
          <div className="safety-box-header">
            <ShieldAlert size={16} className="text-amber-600" />
            <span className="safety-box-title">Clinical Scope & Mandatory Safety Guardrails</span>
          </div>
          <ul className="safety-list">
            <li>
              <strong>Non-Skull-Stripped Scans:</strong> The model is trained strictly on skull-stripped neuroimaging.
              Unstripped scalp fat or bone marrow produces false-positive perimeter oedema predictions.
            </li>
            <li>
              <strong>Pediatric &amp; Infratentorial Tumors:</strong> Trained exclusively on adult supratentorial diffuse gliomas.
              Uncalibrated for posterior fossa tumors, medulloblastomas, or pediatric ependymomas.
            </li>
            <li>
              <strong>Cryptographic Integrity &amp; Ephemeral Retention:</strong> Every volume is fingerprinted with its raw SHA-256 digest.
              All ingested files and predicted masks are purged automatically after 24 hours.
            </li>
          </ul>
        </div>
      </section>
    </div>
  );
}
