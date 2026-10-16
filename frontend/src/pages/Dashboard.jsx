import React, { useState, useEffect } from 'react';
import UploadPanel from '../components/UploadPanel';
import NiiVueViewer from '../components/NiiVueViewer';
import VolumetricCards from '../components/VolumetricCards';
import BoundaryWatchPanel from '../components/BoundaryWatchPanel';
import EvaluationPanel from '../components/EvaluationPanel';
import DownloadsPanel from '../components/DownloadsPanel';
import { loadSampleStudy, triggerSegmentation, getCaseResults } from '../services/api';

export default function Dashboard({
  activeCase,
  caseResults,
  baseScanFile,
  baseScanUrl,
  maskUrl,
  activeSequenceKey,
  onSelectSequence,
  onCaseUploaded,
  onSegmentationCompleted,
  onBaseScanSelected,
  onValidationError
}) {
  const [selectedCentroid, setSelectedCentroid] = useState(null);
  const [overlayMode, setOverlayMode] = useState('prediction'); // 'prediction' | 'agreement'
  const [agreementRegion, setAgreementRegion] = useState('WT'); // 'WT' | 'TC' | 'ET'
  const [isSegmenting, setIsSegmenting] = useState(false);
  const [layerVisibility, setLayerVisibility] = useState({
    WT: true,
    TC: true,
    ET: true,
  });

  const handleToggleLayer = (layerKey) => {
    setLayerVisibility((prev) => ({ ...prev, [layerKey]: !prev[layerKey] }));
  };

  const handleActivateAgreementLens = (reg) => {
    setAgreementRegion(reg || 'WT');
    setOverlayMode('agreement');
  };

  const handleExpertMaskUploaded = (uploadRes) => {
    if (uploadRes?.case_evaluation && caseResults) {
      onSegmentationCompleted({
        ...caseResults,
        case_evaluation: uploadRes.case_evaluation,
      });
    }
  };

  // Sync default centroid whenever new segmentation results arrive
  useEffect(() => {
    if (caseResults?.spatial_metadata?.suggested_crosshair_voxel) {
      setSelectedCentroid(caseResults.spatial_metadata.suggested_crosshair_voxel);
    } else {
      setSelectedCentroid(null);
    }
  }, [caseResults?.spatial_metadata?.suggested_crosshair_voxel]);

  const seqLabels = {
    t1: 'T1 Native',
    t1gd: 'T1CE Contrast',
    t2: 'T2-Weighted',
    flair: 'T2 FLAIR',
  };

  const activeSequenceLabel = seqLabels[activeSequenceKey] || 'T1CE';
  const effectiveCaseId = caseResults?.case_id || activeCase?.case_id;

  const handleCalculateVolumes = async () => {
    let caseIdToUse = effectiveCaseId;
    setIsSegmenting(true);
    try {
      if (!caseIdToUse) {
        // Load sample study and trigger inference
        const resp = await loadSampleStudy();
        onCaseUploaded(resp);
        caseIdToUse = resp.case_id;
      }
      await triggerSegmentation(caseIdToUse);
      const results = await getCaseResults(caseIdToUse);
      onSegmentationCompleted(results);
    } catch (err) {
      console.error('Volume calculation failed:', err);
      throw err;
    } finally {
      setIsSegmenting(false);
    }
  };

  const handleLoadSampleDirect = async () => {
    setIsSegmenting(true);
    try {
      const resp = await loadSampleStudy();
      onCaseUploaded(resp);
      await triggerSegmentation(resp.case_id);
      const results = await getCaseResults(resp.case_id);
      onSegmentationCompleted(results);
    } catch (err) {
      console.error('Failed to load sample study:', err);
      throw err;
    } finally {
      setIsSegmenting(false);
    }
  };

  const effectiveVolumes = caseResults?.regions || activeCase?.volumes || activeCase?.regions;

  return (
    <div className="workstation-two-column">
      {/* LEFT COLUMN: Study Ingestion, Volumetrics, Benchmarks, Export (380px fixed on desktop) */}
      <aside className="left-controls-col">
        <UploadPanel
          onCaseUploaded={onCaseUploaded}
          onSegmentationCompleted={onSegmentationCompleted}
          onBaseScanSelected={onBaseScanSelected}
          onValidationError={onValidationError}
        />

        <VolumetricCards
          volumes={effectiveVolumes}
          spatialMetadata={caseResults?.spatial_metadata || activeCase?.spatial_summary}
          onSelectCentroid={(vox) => setSelectedCentroid([...vox])}
          layerVisibility={layerVisibility}
          onToggleLayer={handleToggleLayer}
          onRunSegmentation={handleCalculateVolumes}
          onLoadSample={handleLoadSampleDirect}
          isSegmenting={isSegmenting}
          caseId={effectiveCaseId}
        />

        {caseResults && (
          <BoundaryWatchPanel
            caseId={caseResults.case_id}
            boundaryWatchData={caseResults.boundary_watch}
            onNavigateToCentroid={(coords) => setSelectedCentroid([...coords])}
            onNavigateToSlice={(sliceZ) => {
              const currentX = selectedCentroid?.[0] ?? 32;
              const currentY = selectedCentroid?.[1] ?? 32;
              setSelectedCentroid([currentX, currentY, sliceZ]);
            }}
          />
        )}

        <EvaluationPanel
          caseId={effectiveCaseId}
          evaluation={caseResults?.case_evaluation}
          benchmarkReference={caseResults?.held_out_benchmark_reference}
          volumes={effectiveVolumes}
          onExpertMaskUploaded={handleExpertMaskUploaded}
          onActivateAgreementLens={handleActivateAgreementLens}
        />

        {caseResults && (
          <DownloadsPanel
            caseId={caseResults.case_id}
            provenance={caseResults.provenance}
            caseResults={caseResults}
          />
        )}
      </aside>

      {/* RIGHT COLUMN: Interactive 2D/3D Multi-Planar Viewer Workspace */}
      <section className="right-viewer-col">
        <NiiVueViewer
          baseScanFile={baseScanFile}
          baseScanUrl={baseScanUrl}
          maskUrl={maskUrl}
          suggestedCrosshair={selectedCentroid}
          activeSequenceKey={activeSequenceKey}
          activeSequenceLabel={activeSequenceLabel}
          onSelectSequence={onSelectSequence}
          caseId={effectiveCaseId}
          activeCase={activeCase}
          caseResults={caseResults}
          hasExpertMask={caseResults?.case_evaluation?.available === true || activeCase?.files?.expert_mask?.present === true}
          layerVisibility={layerVisibility}
          onToggleLayer={handleToggleLayer}
          overlayMode={overlayMode}
          agreementRegion={agreementRegion}
          onSetOverlayMode={setOverlayMode}
          onSetAgreementRegion={setAgreementRegion}
        />
      </section>
    </div>
  );
}

