import React from 'react';

export default function DisclaimerBanner() {
  return (
    <div className="disclaimer-banner" role="alert">
      <span className="disclaimer-pill">Notice</span>
      <span>
        <strong>Research and teaching prototype only.</strong> Not for clinical diagnosis, patient care, or surgical planning.
      </span>
    </div>
  );
}
