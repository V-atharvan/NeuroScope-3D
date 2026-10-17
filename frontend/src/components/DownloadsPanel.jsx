import React, { useState } from 'react';
import { Download, FileText, FileCode, CheckCircle2, AlertCircle, Loader2, ChevronDown, ChevronUp, ShieldCheck, Box } from 'lucide-react';
import { downloadReportFile, downloadMaskFile, downloadAgreementMaskFile, downloadMeshFile, downloadSummaryFile, getMaskDownloadUrl, getReportDownloadUrl } from '../services/api';

export default function DownloadsPanel({ caseId, provenance, caseResults }) {
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);
  const [isDownloadingMask, setIsDownloadingMask] = useState(false);
  const [isDownloadingAgreement, setIsDownloadingAgreement] = useState(false);
  const [isDownloadingSummary, setIsDownloadingSummary] = useState(false);
  const [downloadingMeshRegion, setDownloadingMeshRegion] = useState(null);
  const [downloadSuccess, setDownloadSuccess] = useState(null);
  const [downloadError, setDownloadError] = useState(null);
  const [showPreview, setShowPreview] = useState(true);

  if (!caseId) return null;

  const availableSha = provenance?.input_sha256
    ? (provenance.input_sha256.t1gd || Object.values(provenance.input_sha256)[0])
    : null;
  const shaPreview = availableSha
    ? `${availableSha.substring(0, 8)}...${availableSha.substring(availableSha.length - 4)}`
    : '--';

  const regions = caseResults?.regions || {};
  const wtVol = regions.WT?.volume_ml !== undefined ? `${regions.WT.volume_ml.toFixed(2)} mL` : 'N/A';
  const tcVol = regions.TC?.volume_ml !== undefined ? `${regions.TC.volume_ml.toFixed(2)} mL` : 'N/A';
  const etVol = regions.ET?.volume_ml !== undefined ? `${regions.ET.volume_ml.toFixed(2)} mL` : 'N/A';

  const hasExpert = caseResults?.case_evaluation?.available === true;

  const handleExportPDF = async () => {
    setIsGeneratingPdf(true);
    setDownloadError(null);
    setDownloadSuccess(null);
    try {
      const result = await downloadReportFile(caseId);
      const sizeStr = (result.sizeBytes / 1024).toFixed(1);
      setDownloadSuccess(`Downloaded "${result.filename}" (${sizeStr} KB)`);
    } catch (err) {
      setDownloadError(err.message || 'Failed to export PDF report. Please verify backend inference status.');
    } finally {
      setIsGeneratingPdf(false);
    }
  };

  const handleExportMask = async () => {
    setIsDownloadingMask(true);
    setDownloadError(null);
    setDownloadSuccess(null);
    try {
      const result = await downloadMaskFile(caseId);
      const sizeStr = (result.sizeBytes / (1024 * 1024)).toFixed(2);
      setDownloadSuccess(`Downloaded "${result.filename}" (${sizeStr} MB)`);
    } catch (err) {
      setDownloadError(err.message || 'Failed to download NIfTI segmentation mask.');
    } finally {
      setIsDownloadingMask(false);
    }
  };

  const handleExportAgreement = async () => {
    setIsDownloadingAgreement(true);
    setDownloadError(null);
    setDownloadSuccess(null);
    try {
      const result = await downloadAgreementMaskFile(caseId, 'WT');
      const sizeStr = (result.sizeBytes / (1024 * 1024)).toFixed(2);
      setDownloadSuccess(`Downloaded Agreement Map "${result.filename}" (${sizeStr} MB)`);
    } catch (err) {
      setDownloadError(err.message || 'Failed to download expert agreement map.');
    } finally {
      setIsDownloadingAgreement(false);
    }
  };

  const handleExportSummary = async () => {
    setIsDownloadingSummary(true);
    setDownloadError(null);
    setDownloadSuccess(null);
    try {
      const result = await downloadSummaryFile(caseId);
      const sizeStr = (result.sizeBytes / 1024).toFixed(1);
      setDownloadSuccess(`Downloaded "${result.filename}" (${sizeStr} KB)`);
    } catch (err) {
      setDownloadError(err.message || 'Failed to download research summary JSON.');
    } finally {
      setIsDownloadingSummary(false);
    }
  };

  const handleExportMesh = async (region, format = 'glb') => {
    setDownloadingMeshRegion(`${region}_${format}`);
    setDownloadError(null);
    setDownloadSuccess(null);
    try {
      const result = await downloadMeshFile(caseId, region, format);
      const sizeStr = (result.sizeBytes / 1024).toFixed(1);
      setDownloadSuccess(`Downloaded 3D Mesh "${result.filename}" (${sizeStr} KB)`);
    } catch (err) {
      setDownloadError(err.message || `Failed to download 3D mesh for ${region}.`);
    } finally {
      setDownloadingMeshRegion(null);
    }
  };

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: '8px', borderTop: '1px solid var(--border-structural)', paddingTop: '10px' }}>
      <div className="clinical-section-header">
        <h2 className="section-title-text" style={{ display: 'flex', alignItems: 'center' }}>
          <span className="section-number-badge">4</span>
          Export & Provenance
        </h2>
      </div>

      {/* Success Notification */}
      {downloadSuccess && (
        <div
          role="status"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: '#ECFDF5',
            color: '#065F46',
            border: '1px solid #A7F3D0',
            borderRadius: '4px',
            padding: '8px 10px',
            fontSize: '11px',
            lineHeight: '14px',
          }}
        >
          <CheckCircle2 size={15} style={{ flexShrink: 0, color: '#059669' }} />
          <span style={{ flex: 1, wordBreak: 'break-all' }}>{downloadSuccess}</span>
          <button
            type="button"
            onClick={() => setDownloadSuccess(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#059669', fontSize: '13px' }}
          >
            ×
          </button>
        </div>
      )}

      {/* Error Notification */}
      {downloadError && (
        <div
          role="alert"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: '#FEF2F2',
            color: '#991B1B',
            border: '1px solid #FECACA',
            borderRadius: '4px',
            padding: '8px 10px',
            fontSize: '11px',
            lineHeight: '14px',
          }}
        >
          <AlertCircle size={15} style={{ flexShrink: 0, color: '#DC2626' }} />
          <span style={{ flex: 1 }}>{downloadError}</span>
          <button
            type="button"
            onClick={() => setDownloadError(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#DC2626', fontSize: '13px' }}
          >
            ×
          </button>
        </div>
      )}

      {/* Report Preview & Summary Section */}
      <div
        style={{
          backgroundColor: '#F8FAFC',
          border: '1px solid #E2E8F0',
          borderRadius: '4px',
          padding: '8px',
          fontSize: '11px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px'
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer',
            userSelect: 'none'
          }}
          onClick={() => setShowPreview(!showPreview)}
        >
          <span style={{ fontWeight: 600, color: '#0F172A', display: 'flex', alignItems: 'center', gap: '5px' }}>
            <ShieldCheck size={14} style={{ color: 'var(--primary-accent)' }} />
            4-Page Research Report Summary
          </span>
          {showPreview ? <ChevronUp size={14} color="#64748B" /> : <ChevronDown size={14} color="#64748B" />}
        </div>

        {showPreview && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', paddingTop: '4px', borderTop: '1px solid #E2E8F0', color: '#334155' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>P1 Visualizations:</span>
              <span style={{ fontWeight: 500 }}>Axial, Coronal, Sagittal Overlays</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>P1 Volumetrics:</span>
              <span style={{ fontWeight: 600, color: '#0F172A' }}>WT: {wtVol} | TC: {tcVol} | ET: {etVol}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>P2 Expert Comparison:</span>
              <span>{hasExpert ? 'Ground-Truth DSC / TPR Included' : 'Unavailable (No mask uploaded)'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>P3 Benchmarks & Audit:</span>
              <span>BraTS Cohort Mean DSC ± StdDev</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#64748B' }}>P4 Input Hashes:</span>
              <span className="font-mono" style={{ fontSize: '10px' }}>SHA-256 Verified</span>
            </div>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <button
          type="button"
          onClick={handleExportMask}
          disabled={isDownloadingMask}
          className="btn-primary"
          style={{
            backgroundColor: '#2373F4',
            color: '#FFFFFF',
            border: '1px solid #2373F4',
            cursor: isDownloadingMask ? 'wait' : 'pointer',
            opacity: isDownloadingMask ? 0.75 : 1.0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            padding: '9px 12px',
            fontSize: '12px',
            fontWeight: 600,
            borderRadius: '4px',
            boxShadow: 'var(--shadow-sm)'
          }}
        >
          {isDownloadingMask ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              <span>Downloading Segmentation Mask...</span>
            </>
          ) : (
            <>
              <Download size={14} />
              <span>Export BraTS Label NIfTI (.nii.gz)</span>
            </>
          )}
        </button>

        <button
          type="button"
          onClick={handleExportPDF}
          disabled={isGeneratingPdf}
          className="btn-secondary"
          style={{
            backgroundColor: '#578EF5',
            color: '#FFFFFF',
            border: '1px solid #578EF5',
            cursor: isGeneratingPdf ? 'wait' : 'pointer',
            opacity: isGeneratingPdf ? 0.75 : 1.0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            padding: '9px 12px',
            fontSize: '12px',
            fontWeight: 600,
            borderRadius: '4px',
            boxShadow: 'var(--shadow-sm)'
          }}
        >
          {isGeneratingPdf ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              <span>Generating 4-Page Research Report...</span>
            </>
          ) : (
            <>
              <FileText size={14} />
              <span>Download Audit PDF Report</span>
            </>
          )}
        </button>

        {hasExpert && (
          <button
            type="button"
            onClick={handleExportAgreement}
            disabled={isDownloadingAgreement}
            className="btn-secondary"
            style={{
              cursor: isDownloadingAgreement ? 'wait' : 'pointer',
              opacity: isDownloadingAgreement ? 0.75 : 1.0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              padding: '9px 12px',
              fontSize: '12px',
              fontWeight: 600,
              borderRadius: '4px',
              border: '1px solid #10B981',
              backgroundColor: '#ECFDF5',
              color: '#065F46'
            }}
          >
            {isDownloadingAgreement ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                <span>Downloading Agreement Map...</span>
              </>
            ) : (
              <>
                <Download size={14} style={{ color: '#059669' }} />
                <span>Export Expert Agreement Map (TP/FP/FN)</span>
              </>
            )}
          </button>
        )}

        <button
          type="button"
          onClick={handleExportSummary}
          disabled={isDownloadingSummary}
          className="btn-secondary"
          style={{
            cursor: isDownloadingSummary ? 'wait' : 'pointer',
            opacity: isDownloadingSummary ? 0.75 : 1.0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            padding: '8px 12px',
            fontSize: '12px',
            fontWeight: 600,
            borderRadius: '4px',
            border: '1px solid #CBD5E1',
            backgroundColor: '#F8FAFC',
            color: '#334155'
          }}
          title="Export machine-readable research summary JSON containing volumes, labels, and provenance"
        >
          {isDownloadingSummary ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              <span>Downloading Research Summary...</span>
            </>
          ) : (
            <>
              <FileCode size={14} style={{ color: 'var(--primary-accent)' }} />
              <span>Export Research Summary (.json)</span>
            </>
          )}
        </button>

        {/* 3D Polygonal Surface Meshes (World mm Space) */}
        <div
          style={{
            backgroundColor: '#F8FAFC',
            border: '1px solid #E2E8F0',
            borderRadius: '4px',
            padding: '8px',
            fontSize: '11px',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontWeight: 600, color: '#0F172A', display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Box size={14} style={{ color: 'var(--primary-accent)' }} />
              3D Surface Meshes (World mm)
            </span>
            <span style={{ fontSize: '10px', color: '#64748B' }}>Marching Cubes</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
            {[
              { id: 'WT', label: 'Whole Tumour' },
              { id: 'TC', label: 'Tumour Core' },
              { id: 'ET', label: 'Enhancing' },
              { id: 'BRAIN_SURFACE', label: 'Brain Surface' }
            ].map(({ id, label }) => {
              const isDownloading = downloadingMeshRegion === `${id}_glb`;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => handleExportMesh(id, 'glb')}
                  disabled={Boolean(downloadingMeshRegion)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '5px 8px',
                    fontSize: '10px',
                    fontWeight: 500,
                    backgroundColor: '#FFFFFF',
                    border: '1px solid #CBD5E1',
                    borderRadius: '3px',
                    cursor: downloadingMeshRegion ? 'wait' : 'pointer',
                    color: '#1E293B'
                  }}
                  title={`Download ${label} surface mesh as binary GLTF (.glb) in physical millimeter coordinates`}
                >
                  <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{label}</span>
                  {isDownloading ? (
                    <Loader2 size={11} className="animate-spin" />
                  ) : (
                    <span style={{ color: 'var(--primary-accent)', fontWeight: 700, marginLeft: '4px' }}>.GLB</span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div
        className="font-mono"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '10px',
          color: 'var(--on-surface-variant)',
          marginTop: '2px'
        }}
      >
        <span>SHA-256: {shaPreview}</span>
        <span>Local Processing • 24h Purge</span>
      </div>
    </section>
  );
}
