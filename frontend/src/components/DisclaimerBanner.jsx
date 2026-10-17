import React from 'react';
import { AlertTriangle } from 'lucide-react';

export default function DisclaimerBanner() {
  return (
    <div className="disclaimer-strip" role="alert">
      <div className="disclaimer-text">
        <AlertTriangle size={15} style={{ color: '#0F172A', flexShrink: 0 }} />
        <span>
          Research and teaching prototype only. This software does not provide medical diagnoses, treatment planning, or clinical decisions. Not FDA cleared or approved. Not for diagnostic use.
        </span>
      </div>
      <div className="disclaimer-badge">
        DICOM 3.0 / NIfTI V2
      </div>
    </div>
  );
}
