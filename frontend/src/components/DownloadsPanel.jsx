import React from 'react';
import { Download, FileText, Database } from 'lucide-react';
import { getMaskDownloadUrl, getReportDownloadUrl } from '../services/api';

export default function DownloadsPanel({ caseId }) {
  if (!caseId) return null;

  return (
    <div className="glass-panel">
      <div className="panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Download size={18} style={{ color: 'var(--accent-green)' }} />
          <h2 className="panel-title">4. Export Case Artefacts</h2>
        </div>
      </div>

      <div className="panel-body" style={{ display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
        <a
          href={getMaskDownloadUrl(caseId)}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-secondary"
          style={{ flex: 1, textDecoration: 'none', justifyContent: 'center' }}
        >
          <Database size={16} />
          <span>Download Predicted NIfTI (.nii.gz)</span>
        </a>

        <a
          href={getReportDownloadUrl(caseId)}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-primary"
          style={{ flex: 1, textDecoration: 'none', justifyContent: 'center' }}
        >
          <FileText size={16} />
          <span>Download PDF Report</span>
        </a>
      </div>
    </div>
  );
}
