import React, { useState } from 'react';
import UploadPanel from '../components/UploadPanel';
import NiiVueViewer from '../components/NiiVueViewer';
import VolumetricCards from '../components/VolumetricCards';
import EvaluationPanel from '../components/EvaluationPanel';
import DownloadsPanel from '../components/DownloadsPanel';
import { getMaskDownloadUrl } from '../services/api';

export default function Dashboard({ backendHealth }) {
  const [activeCase, setActiveCase] = useState(null);
  const [caseResults, setCaseResults] = useState(null);
  const [baseScanFile, setBaseScanFile] = useState(null);
  const [maskUrl, setMaskUrl] = useState(null);

  const handleCaseUploaded = (uploadData) => {
    setActiveCase(uploadData);
    setCaseResults(null);
    setMaskUrl(null);
  };

  const handleSegmentationCompleted = (resultsData) => {
    setCaseResults(resultsData);
    if (resultsData.case_id) {
      setMaskUrl(getMaskDownloadUrl(resultsData.case_id));
    }
  };

  const handleBaseScanSelected = (file) => {
    setBaseScanFile(file);
  };

  return (
    <main className="dashboard-grid">
      {/* Left Column: Input Ingestion & Case Status */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <UploadPanel
          onCaseUploaded={handleCaseUploaded}
          onSegmentationCompleted={handleSegmentationCompleted}
          onBaseScanSelected={handleBaseScanSelected}
        />

        {caseResults && (
          <>
            <DownloadsPanel caseId={caseResults.case_id} />
            <EvaluationPanel
              evaluation={caseResults.case_evaluation}
              benchmarkReference={caseResults.held_out_benchmark_reference}
              provenance={caseResults.provenance}
            />
          </>
        )}
      </div>

      {/* Right Column: 3D Visualization & Volumetrics */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <NiiVueViewer
          baseScanFile={baseScanFile}
          maskUrl={maskUrl}
          suggestedCrosshair={caseResults?.spatial_metadata?.suggested_crosshair_voxel}
        />

        <VolumetricCards
          volumes={caseResults?.regions}
          spatialMetadata={caseResults?.spatial_metadata || activeCase?.spatial_summary}
        />
      </div>
    </main>
  );
}
