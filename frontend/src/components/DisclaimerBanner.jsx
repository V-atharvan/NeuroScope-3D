import React from 'react';
import { AlertTriangle } from 'lucide-react';

export default function DisclaimerBanner() {
  return (
    <div className="disclaimer-strip" role="alert">
      <div className="disclaimer-text">
        <AlertTriangle size={15} style={{ color: '#0F172A', flexShrink: 0 }} />
        <span>
          RESEARCH AND TEACHING PROTOTYPE ONLY: THIS SOFTWARE DOES NOT PROVIDE MEDICAL DIAGNOSES, TREATMENT PLANNING, OR CLINICAL DECISIONS. RESEARCH AND TEACHING PROTOTYPE ONLY. NOT FOR CLINICAL DIAGNOSIS OR TREATMENT PLANNING. NOT FDA CLEARED.
        </span>
      </div>
      <div className="disclaimer-badge">
        DICOM 3.0 / NIfTI V2
      </div>
    </div>
  );
}
