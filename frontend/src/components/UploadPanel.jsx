import React, { useState } from 'react';
import { Upload, AlertCircle, CheckCircle, Loader2, Play } from 'lucide-react';
import { uploadStudy, triggerSegmentation, getCaseResults } from '../services/api';

export default function UploadPanel({
  onCaseUploaded,
  onSegmentationCompleted,
  onBaseScanSelected,
}) {
  const [files, setFiles] = useState({
    t1: null,
    t1gd: null,
    t2: null,
    flair: null,
    expert_mask: null,
  });

  const [isUploading, setIsUploading] = useState(false);
  const [isSegmenting, setIsSegmenting] = useState(false);
  const [activeCase, setActiveCase] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);
  const [errorDetails, setErrorDetails] = useState(null);

  const handleFileChange = (seq, file) => {
    setFiles((prev) => ({ ...prev, [seq]: file }));
    setErrorMessage(null);
    setErrorDetails(null);

    // If T1 or FLAIR selected, update viewer base scan immediately for live preview
    if (seq === 't1' && file) {
      onBaseScanSelected(file);
    }
  };

  const handleUpload = async () => {
    setIsUploading(true);
    setErrorMessage(null);
    setErrorDetails(null);

    try {
      const formData = new FormData();
      formData.append('t1', files.t1);
      formData.append('t1gd', files.t1gd);
      formData.append('t2', files.t2);
      formData.append('flair', files.flair);
      if (files.expert_mask) {
        formData.append('expert_mask', files.expert_mask);
      }

      const uploadResult = await uploadStudy(formData);
      setActiveCase(uploadResult);
      onCaseUploaded(uploadResult);
    } catch (err) {
      setErrorMessage(err.message || 'Upload failed');
      setErrorDetails(err.details || null);
    } finally {
      setIsUploading(false);
    }
  };

  const handleRunInference = async () => {
    if (!activeCase?.case_id) return;
    setIsSegmenting(true);
    setErrorMessage(null);

    try {
      await triggerSegmentation(activeCase.case_id);
      const results = await getCaseResults(activeCase.case_id);
      onSegmentationCompleted(results);
    } catch (err) {
      setErrorMessage(err.message || 'Model inference failed');
    } finally {
      setIsSegmenting(false);
    }
  };

  const allRequiredPresent = files.t1 && files.t1gd && files.t2 && files.flair;

  return (
    <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
      <div className="panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Upload size={18} style={{ color: 'var(--accent-cyan)' }} />
          <h2 className="panel-title">1. Study Ingestion & Inference</h2>
        </div>
        <span className="mono-val" style={{ fontSize: '0.75rem' }}>4 Modalities Required</span>
      </div>

      <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          Select 4 co-registered NIfTI files (.nii or .nii.gz, &le; 1 GB each) and optional BraTS 2021 ground-truth mask.
        </p>

        {/* File Selectors */}
        {[
          { id: 't1', label: 'T1-Weighted Sequence', req: true },
          { id: 't1gd', label: 'T1Gd (Contrast / T1CE)', req: true },
          { id: 't2', label: 'T2-Weighted Sequence', req: true },
          { id: 'flair', label: 'FLAIR Sequence', req: true },
          { id: 'expert_mask', label: 'Expert Mask (Ground Truth)', req: false },
        ].map((item) => (
          <div key={item.id} style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
              <span style={{ fontWeight: 600 }}>{item.label}</span>
              {item.req ? (
                <span style={{ color: 'var(--accent-cyan)' }}>Required</span>
              ) : (
                <span style={{ color: 'var(--text-muted)' }}>Optional</span>
              )}
            </div>
            <input
              type="file"
              accept=".nii,.nii.gz"
              onChange={(e) => handleFileChange(item.id, e.target.files?.[0] || null)}
              style={{
                fontSize: '0.75rem',
                padding: '6px',
                background: 'rgba(0, 0, 0, 0.3)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-primary)',
              }}
            />
          </div>
        ))}

        {/* Error Banner */}
        {errorMessage && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-sm)',
              background: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              color: '#fca5a5',
              fontSize: '0.8rem',
              display: 'flex',
              gap: '8px',
              alignItems: 'flex-start',
            }}
          >
            <AlertCircle size={16} style={{ marginTop: '2px', flexShrink: 0 }} />
            <div>
              <div style={{ fontWeight: 600 }}>Validation Error:</div>
              <div>{errorMessage}</div>
              {errorDetails && (
                <pre style={{ fontSize: '0.7rem', marginTop: '4px', overflowX: 'auto' }}>
                  {JSON.stringify(errorDetails, null, 2)}
                </pre>
              )}
            </div>
          </div>
        )}

        {/* Success / Uploaded Info */}
        {activeCase && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 'var(--radius-sm)',
              background: 'rgba(16, 185, 129, 0.15)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              color: '#6ee7b7',
              fontSize: '0.8rem',
              display: 'flex',
              gap: '8px',
              alignItems: 'center',
            }}
          >
            <CheckCircle size={16} style={{ flexShrink: 0 }} />
            <div>
              <strong>Case Uploaded:</strong> <span className="mono-val">{activeCase.case_id}</span>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                Grid: {activeCase.spatial_summary?.shape?.join('x')} | Spacing: {activeCase.spatial_summary?.spacing_mm?.join('x')} mm
              </div>
            </div>
          </div>
        )}

        {/* Actions */}
        {!activeCase ? (
          <button
            onClick={handleUpload}
            disabled={!allRequiredPresent || isUploading}
            className="btn btn-primary"
            style={{ width: '100%', marginTop: '6px' }}
          >
            {isUploading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Validating & Uploading...</span>
              </>
            ) : (
              <>
                <Upload size={16} />
                <span>Upload & Validate Study</span>
              </>
            )}
          </button>
        ) : (
          <button
            onClick={handleRunInference}
            disabled={isSegmenting}
            className="btn btn-primary"
            style={{
              width: '100%',
              marginTop: '6px',
              background: 'linear-gradient(135deg, var(--accent-green), var(--accent-cyan))',
            }}
          >
            {isSegmenting ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Executing 3D SegResNet Inference...</span>
              </>
            ) : (
              <>
                <Play size={16} />
                <span>Execute Tumour Segmentation</span>
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
}
