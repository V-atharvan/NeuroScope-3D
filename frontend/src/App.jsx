import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import SeriesExplorer from './components/SeriesExplorer';
import WorkspaceContextStrip from './components/WorkspaceContextStrip';
import BottomNav from './components/BottomNav';
import Dashboard from './pages/Dashboard';
import ProvenanceAuditReport from './components/ProvenanceAuditReport';
import CaseValidationDiagnostics from './components/CaseValidationDiagnostics';
import CohortBenchmarkView from './components/CohortBenchmarkView';
import UncertaintyAndLongitudinalView from './components/UncertaintyAndLongitudinalView';
import { getHealth, getMaskDownloadUrl, getSequenceDownloadUrl } from './services/api';

export default function App() {
  const [backendHealth, setBackendHealth] = useState(null);
  const [activeTab, setActiveTab] = useState('workstation'); // 'workstation' | 'audit' | 'diagnostics' | 'trust' | 'cohort'
  const [workstationSubTab, setWorkstationSubTab] = useState('viewer'); // 'viewer' | 'controls' | 'series'

  const [activeCase, setActiveCase] = useState(null);
  const [caseResults, setCaseResults] = useState(null);
  const [baseScanFile, setBaseScanFile] = useState(null);
  const [baseScanUrl, setBaseScanUrl] = useState(null);
  const [maskUrl, setMaskUrl] = useState(null);
  const [activeSequenceKey, setActiveSequenceKey] = useState('t1gd');
  const [validationError, setValidationError] = useState(null);

  // Check backend health on mount
  useEffect(() => {
    getHealth()
      .then((data) => setBackendHealth(data))
      .catch((err) => {
        console.warn('Backend currently offline or starting:', err.message);
      });
  }, []);

  const handleCaseUploaded = (uploadData) => {
    setActiveCase(uploadData);
    setValidationError(null);

    // Clear local file so server-synced sequence URL is loaded
    setBaseScanFile(null);
    if (uploadData?.case_id) {
      setBaseScanUrl(getSequenceDownloadUrl(uploadData.case_id, 't1gd'));
      setActiveSequenceKey('t1gd');
    }

    // If upload response already includes precomputed or expert volumes, populate them safely
    if (uploadData?.volumes && uploadData?.has_mask) {
      setCaseResults({
        case_id: uploadData.case_id,
        status: 'completed',
        regions: uploadData.volumes,
        spatial_metadata: uploadData.spatial_summary || uploadData.spatial_metadata,
      });
      setMaskUrl(getMaskDownloadUrl(uploadData.case_id));
    } else if (uploadData?.volumes) {
      setCaseResults({
        case_id: uploadData.case_id,
        status: uploadData.status || 'uploaded',
        regions: uploadData.volumes,
        spatial_metadata: uploadData.spatial_summary || uploadData.spatial_metadata,
      });
      setMaskUrl(null);
    } else {
      setCaseResults(null);
      setMaskUrl(null);
    }
  };

  const handleSegmentationCompleted = (resultsData) => {
    setCaseResults(resultsData);
    if (resultsData.case_id) {
      setMaskUrl(getMaskDownloadUrl(resultsData.case_id));
    }
  };

  const handleBaseScanSelected = (file) => {
    setBaseScanFile(file);
    setBaseScanUrl(null);
  };

  const handleValidationError = (err) => {
    setValidationError(err);
    // Automatically switch to Diagnostics view to show the user the pre-inference check
    setActiveTab('diagnostics');
  };

  const handleSelectSequence = (seqKey) => {
    setActiveSequenceKey(seqKey);
    if (activeCase?.case_id) {
      setBaseScanFile(null);
      setBaseScanUrl(getSequenceDownloadUrl(activeCase.case_id, seqKey));
    }
  };

  const handleResetStudy = () => {
    setActiveCase(null);
    setCaseResults(null);
    setBaseScanFile(null);
    setBaseScanUrl(null);
    setMaskUrl(null);
    setValidationError(null);
    setActiveTab('workstation');
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* 1. Fixed Clinical Top Header */}
      <Header
        backendHealth={backendHealth}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onResetStudy={handleResetStudy}
        hasValidationErrors={!!validationError}
      />

      <div className="main-wrapper">
        {/* Conditional View Rendering */}
        {activeTab === 'workstation' && (
          <div style={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
            {/* Top Workspace Context Strip */}
            <WorkspaceContextStrip
              caseId={caseResults?.case_id || activeCase?.case_id}
              spatialMetadata={caseResults?.spatial_metadata || activeCase?.spatial_summary}
              backendHealth={backendHealth}
            />

            {/* Layout: Sidebar + Central Workstation with mobile responsive classes */}
            <div className={`app-layout-container workstation-layout mobile-subtab-${workstationSubTab}`}>
              <div className={`series-sidebar-wrapper ${workstationSubTab === 'series' ? 'mobile-active' : 'mobile-hidden'}`}>
                <SeriesExplorer
                  activeSequenceKey={activeSequenceKey}
                  onSelectSequence={(seq) => {
                    handleSelectSequence(seq);
                    // On mobile, after selecting a sequence, automatically return to viewer for instant visual feedback
                    if (window.innerWidth < 1024) {
                      setWorkstationSubTab('viewer');
                    }
                  }}
                  volumes={caseResults?.regions || activeCase?.volumes || activeCase?.regions}
                  caseData={activeCase}
                  runtimeSeconds={caseResults?.runtime_seconds}
                />
              </div>

              <div className={`workspace-content ${workstationSubTab === 'series' ? 'mobile-hidden' : 'mobile-active'}`}>
                <Dashboard
                  activeCase={activeCase}
                  caseResults={caseResults}
                  baseScanFile={baseScanFile}
                  baseScanUrl={baseScanUrl}
                  maskUrl={maskUrl}
                  activeSequenceKey={activeSequenceKey}
                  onSelectSequence={handleSelectSequence}
                  onCaseUploaded={handleCaseUploaded}
                  onSegmentationCompleted={handleSegmentationCompleted}
                  onBaseScanSelected={handleBaseScanSelected}
                  onValidationError={handleValidationError}
                  workstationSubTab={workstationSubTab}
                  onWorkstationSubTabChange={setWorkstationSubTab}
                />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'audit' && (
          <div className="app-layout-container" style={{ justifyContent: 'center' }}>
            <ProvenanceAuditReport
              caseId={caseResults?.case_id || activeCase?.case_id}
              caseData={activeCase}
              caseResults={caseResults}
              onClose={() => setActiveTab('workstation')}
            />
          </div>
        )}

        {activeTab === 'trust' && (
          <div className="app-layout-container" style={{ justifyContent: 'center' }}>
            <UncertaintyAndLongitudinalView
              caseId={caseResults?.case_id || activeCase?.case_id}
              caseResults={caseResults}
              onClose={() => setActiveTab('workstation')}
            />
          </div>
        )}

        {activeTab === 'cohort' && (
          <div className="app-layout-container" style={{ justifyContent: 'center' }}>
            <CohortBenchmarkView
              onClose={() => setActiveTab('workstation')}
            />
          </div>
        )}

        {activeTab === 'diagnostics' && (
          <div className="app-layout-container" style={{ justifyContent: 'center' }}>
            <CaseValidationDiagnostics
              caseId={activeCase?.case_id}
              caseData={activeCase}
              errorInfo={validationError}
              onBackToWorkstation={() => setActiveTab('workstation')}
              onUploadCorrected={() => setActiveTab('workstation')}
            />
          </div>
        )}
      </div>

      {/* Persistent Mobile & Tablet Bottom Navigation Bar (< 1024px) */}
      <BottomNav
        activeTab={activeTab}
        onTabChange={setActiveTab}
        workstationSubTab={workstationSubTab}
        onWorkstationSubTabChange={setWorkstationSubTab}
        hasValidationErrors={!!validationError}
      />
    </div>
  );
}
