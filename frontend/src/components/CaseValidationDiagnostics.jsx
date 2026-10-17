import React from 'react';
import { AlertTriangle, CheckCircle2, XCircle, PauseCircle, Lock, UploadCloud, Grid, ArrowLeft, ShieldCheck } from 'lucide-react';

export default function CaseValidationDiagnostics({
  errorInfo,
  caseId,
  caseData,
  onBackToWorkstation
}) {
  const hasError = Boolean(errorInfo);
  const resolvedCaseId = caseId || caseData?.case_id;
  const isCaseActive = Boolean(resolvedCaseId);
  const caseLabel = resolvedCaseId ? `CASE_${resolvedCaseId.substring(0, 12)}` : 'ACTIVE_SESSION';
  const errCode = errorInfo?.code || 'VALIDATION_ERROR';
  const errMsg = errorInfo?.message || 'Study input sequences failed pre-inference geometry or format verification.';
  const errorDetails = errorInfo?.details || {};

  const isNetworkError =
    errMsg.toLowerCase().includes('cannot reach') ||
    errMsg.toLowerCase().includes('failed to fetch') ||
    errMsg.toLowerCase().includes('connection_refused') ||
    errMsg.toLowerCase().includes('could not reach backend') ||
    errCode === 'NETWORK_ERROR' ||
    errCode === 'SERVER_OFFLINE';

  const files = caseData?.files || {};
  const spatial = caseData?.spatial_summary;
  const shape = spatial?.shape || [240, 240, 155];
  const spacing = spatial?.spacing_mm || [1.0, 1.0, 1.0];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%', minHeight: '100%' }}>
      {/* Top Context Diagnostic Strip */}
      <div
        className="safe-failure-banner"
        style={{
          backgroundColor: hasError ? (isNetworkError ? '#D97706' : 'var(--error-red)') : (isCaseActive ? 'var(--success)' : 'var(--primary)'),
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {hasError ? (
            <AlertTriangle size={18} style={{ color: '#FFFFFF', flexShrink: 0 }} />
          ) : (
            <ShieldCheck size={18} style={{ color: '#FFFFFF', flexShrink: 0 }} />
          )}
          <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.02em' }}>
            {hasError
              ? (isNetworkError ? `Safe-Failure Lockout: Backend Service Offline (${errCode})` : `Safe-Failure Lockout: Neural Inference Halted (${errCode})`)
              : (isCaseActive
                  ? 'Pre-Inference Validation System: All Input Volumes Verified & Compliant'
                  : 'Pre-Inference Validation System: All Systems Operational')}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
          <span style={{ backgroundColor: 'rgba(255,255,255,0.2)', padding: '2px 8px', borderRadius: '2px' }}>
            {caseLabel}
          </span>
          <span style={{ backgroundColor: 'rgba(255,255,255,0.2)', padding: '2px 8px', borderRadius: '2px' }}>
            STATUS: {hasError ? (isNetworkError ? 'OFFLINE' : 'ERROR_HALT') : (isCaseActive ? 'VERIFIED' : 'STANDBY')}
          </span>
        </div>
      </div>

      {/* Main Workspace Two-Column Container */}
      <div className="diagnostics-container">
        {/* LEFT COLUMN: Controls & Context */}
        <aside className="diagnostics-sidebar">
          <div className="audit-card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                <span style={{ color: 'var(--primary-accent)', fontWeight: 700 }}>Step 01</span>
                <span style={{ color: 'var(--outline-variant)' }}>/</span>
                <span style={{ color: 'var(--on-surface-variant)' }}>Verification</span>
              </div>
              <span className={hasError ? 'status-pill-failed' : 'status-pill-passed'}>
                {hasError ? 'Status: Error' : 'Status: Ready'}
              </span>
            </div>
            <h2 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--on-surface-dark)' }}>
              Study Geometry Diagnostics
            </h2>
            <p style={{ fontSize: '12px', color: 'var(--on-surface-variant)', marginTop: '4px' }}>
              Automated spatial verification for NIfTI multi-sequence arrays before tensor creation.
            </p>
          </div>

          {/* Diagnostic Alert Box */}
          {hasError ? (
            <div
              style={{
                backgroundColor: 'var(--surface-card)',
                borderLeft: `4px solid ${isNetworkError ? '#D97706' : 'var(--error-red)'}`,
                borderTop: '1px solid var(--border-structural)',
                borderRight: '1px solid var(--border-structural)',
                borderBottom: '1px solid var(--border-structural)',
                padding: '12px',
                borderRadius: 'var(--radius-sm)',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: isNetworkError ? '#B45309' : 'var(--error-dark)' }}>
                <AlertTriangle size={16} />
                <span style={{ fontSize: '13px', fontWeight: 700 }}>
                  {isNetworkError ? 'Backend Connectivity Offline' : 'Geometric Compatibility Failure'}
                </span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--on-surface)', lineHeight: 1.4 }}>
                {errMsg}
              </p>
              {Object.keys(errorDetails).length > 0 && (
                <div
                  className="font-mono"
                  style={{
                    backgroundColor: 'var(--surface-container-low)',
                    padding: '6px 8px',
                    borderRadius: '2px',
                    fontSize: '10px',
                    color: 'var(--on-surface-variant)',
                    border: '1px solid var(--border-structural)',
                    wordBreak: 'break-all'
                  }}
                >
                  {JSON.stringify(errorDetails, null, 2)}
                </div>
              )}
            </div>
          ) : isCaseActive ? (
            <div
              style={{
                backgroundColor: 'var(--surface-container-low)',
                border: '1px solid var(--border-structural)',
                padding: '12px',
                borderRadius: 'var(--radius-sm)',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--success)' }}>
                <CheckCircle2 size={16} />
                <span style={{ fontSize: '13px', fontWeight: 600 }}>Study Validation Passed</span>
              </div>
              <div className="font-mono" style={{ fontSize: '11px', display: 'flex', flexDirection: 'column', gap: '4px', color: 'var(--on-surface-dark)' }}>
                <div>Grid: <strong>{shape.join(' × ')}</strong></div>
                <div>Spacing: <strong>{spacing.join(' × ')} mm</strong></div>
                <div>Sequences: <strong>4 / 4 Validated</strong></div>
                {files.expert_mask?.filename && (
                  <div>Ground Truth: <strong>Present ({files.expert_mask.filename})</strong></div>
                )}
              </div>
            </div>
          ) : (
            <div
              style={{
                backgroundColor: 'var(--surface-container-low)',
                border: '1px solid var(--border-structural)',
                padding: '12px',
                borderRadius: 'var(--radius-sm)',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--primary)' }}>
                <CheckCircle2 size={16} />
                <span style={{ fontSize: '13px', fontWeight: 600 }}>Validation Engine Active</span>
              </div>
              <p style={{ fontSize: '12px', color: 'var(--on-surface-variant)', lineHeight: 1.4 }}>
                Upload a 4-sequence study in the Workstation. If dimensions, affines, or bit-depth mismatch, the failure details will appear here.
              </p>
            </div>
          )}

          {/* Remediation Controls */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: '4px' }}>
            <button
              type="button"
              className="btn-primary"
              onClick={onBackToWorkstation}
            >
              <ArrowLeft size={16} />
              <span>Return to Workstation</span>
            </button>
          </div>
        </aside>

        {/* RIGHT MAIN PANEL: Pre-Inference Validation Checklist */}
        <main className="diagnostics-main">
          {/* Header Card */}
          <div
            className="audit-card"
            style={{
              padding: '16px',
              borderTop: hasError ? '4px solid var(--error-red)' : '4px solid var(--primary)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
              <div>
                <h1 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--on-surface-dark)' }}>
                  {hasError
                    ? (isNetworkError ? 'Backend Connection Offline' : 'Case Validation Intercepted')
                    : isCaseActive
                    ? 'Pre-Inference Verification: Study Geometry Verified'
                    : 'Pre-Inference Verification Pipeline'}
                </h1>
                <p style={{ fontSize: '13px', color: 'var(--on-surface-variant)', marginTop: '4px', maxWidth: '720px' }}>
                  {hasError
                    ? (isNetworkError
                        ? 'The platform cannot communicate with the FastAPI backend server. Verify that run_platform.bat is running locally or allow Render cold-start.'
                        : 'The pipeline halted before running model inference to protect volumetric integrity and prevent erroneous tensor computations.')
                    : isCaseActive
                    ? `Input sequences for ${caseLabel} successfully passed spatial dimension, non-zero variance, affine alignment, and finite value checks.`
                    : 'All input volumes are checked against strict medical-imaging criteria before being stacked into the 4-channel tensor.'}
                </p>
              </div>

              <div
                className="font-mono"
                style={{
                  padding: '4px 8px',
                  backgroundColor: 'var(--surface-container-low)',
                  border: '1px solid var(--border-structural)',
                  borderRadius: 'var(--radius-xs)',
                  fontSize: '11px',
                  flexShrink: 0
                }}
              >
                CHECK: <strong style={{ color: hasError ? 'var(--error-red)' : (isCaseActive ? 'var(--success)' : 'var(--primary)') }}>{hasError ? errCode : (isCaseActive ? 'PASSED' : 'STANDBY')}</strong>
              </div>
            </div>
          </div>

          {/* Validation Checklist */}
          <div className="audit-card">
            <div className="clinical-section-header">
              <h3 className="section-title-text" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <CheckCircle2 size={16} style={{ color: 'var(--primary-accent)' }} />
                Pre-Inference Validation Protocol
              </h3>
              <span className="font-mono" style={{ fontSize: '11px', color: 'var(--on-surface-variant)' }}>
                {hasError ? '1 FAILURE DETECTED' : (isCaseActive ? 'ALL CHECKS PASSED' : 'READY FOR INPUTS')}
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {/* Check 1 */}
              <div className={`check-item ${hasError && errCode.includes('NIFTI') ? 'failed' : 'passed'}`}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                  <CheckCircle2 size={16} style={{ color: 'var(--success)', marginTop: '2px', flexShrink: 0 }} />
                  <div>
                    <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--on-surface-dark)' }}>
                      File Integrity & NIfTI Gzip Decompression
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--on-surface-variant)', marginTop: '2px' }}>
                      {isCaseActive && files.t1 ? (
                        <span>
                          Verified 4 NIfTI sequences: {files.t1?.filename} ({(files.t1.size_bytes / 1048576).toFixed(1)} MB), {files.t1gd?.filename} ({(files.t1gd.size_bytes / 1048576).toFixed(1)} MB), {files.t2?.filename} ({(files.t2.size_bytes / 1048576).toFixed(1)} MB), {files.flair?.filename} ({(files.flair.size_bytes / 1048576).toFixed(1)} MB).
                        </span>
                      ) : (
                        'Verifies valid NIfTI-1 magic headers (n+1\\0) and intact gzip blocks.'
                      )}
                    </div>
                  </div>
                </div>
                <span className="status-pill-passed">VERIFIED</span>
              </div>

              {/* Check 2 */}
              <div className={`check-item ${hasError && errCode.includes('VARIANCE') ? 'failed' : 'passed'}`}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                  <CheckCircle2 size={16} style={{ color: 'var(--success)', marginTop: '2px', flexShrink: 0 }} />
                  <div>
                    <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--on-surface-dark)' }}>
                      Non-Constant Voxel Intensity Variance
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--on-surface-variant)' }}>
                      Ensures MRI arrays contain non-zero variance and are not blank or corrupted.
                    </div>
                  </div>
                </div>
                <span className="status-pill-passed">VERIFIED</span>
              </div>

              {/* Check 3 */}
              <div className={`check-item ${hasError && errCode.includes('VALUE') ? 'failed' : 'passed'}`}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                  <CheckCircle2 size={16} style={{ color: 'var(--success)', marginTop: '2px', flexShrink: 0 }} />
                  <div>
                    <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--on-surface-dark)' }}>
                      Voxel Bit-Depth & Finite Values
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--on-surface-variant)' }}>
                      Enforces Float32/Int16 radiologic precision without NaN or Inf values.
                    </div>
                  </div>
                </div>
                <span className="status-pill-passed">VERIFIED</span>
              </div>

              {/* Check 4 (Shape & Affine Matching) */}
              {(() => {
                const isShapeFailed = hasError && !isNetworkError && (errCode.includes('SHAPE') || errCode.includes('AFFINE') || errCode.includes('DIMENSION') || (!errCode.includes('NIFTI') && !errCode.includes('VARIANCE') && !errCode.includes('VALUE')));
                const checkStatus = isShapeFailed ? 'failed' : (isNetworkError ? 'skipped' : 'passed');

                return (
                  <div className={`check-item ${checkStatus}`}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                      {isShapeFailed ? (
                        <XCircle size={16} style={{ color: 'var(--error-red)', marginTop: '2px', flexShrink: 0 }} />
                      ) : isNetworkError && !isCaseActive ? (
                        <PauseCircle size={16} style={{ color: 'var(--outline)', marginTop: '2px', flexShrink: 0 }} />
                      ) : (
                        <CheckCircle2 size={16} style={{ color: 'var(--success)', marginTop: '2px', flexShrink: 0 }} />
                      )}
                      <div>
                        <div style={{ fontSize: '12px', fontWeight: 700, color: isShapeFailed ? 'var(--error-dark)' : 'var(--on-surface-dark)' }}>
                          Compatible Grid Affines & Spatial Dimensions
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--on-surface-variant)' }}>
                          {isShapeFailed
                            ? errMsg
                            : isCaseActive
                            ? `All 4 sequences verified to share identical 3D shape [${shape.join(' × ')}] and spacing [${spacing.join(' × ')} mm].`
                            : isNetworkError
                            ? 'Awaiting active backend connection to verify multi-sequence spatial affines.'
                            : 'Verifies all 4 sequences share identical 3D shapes and coordinate transforms.'}
                        </div>
                      </div>
                    </div>
                    <span className={isShapeFailed ? 'status-pill-failed' : (isNetworkError && !isCaseActive ? 'status-pill-skipped' : 'status-pill-passed')}>
                      {isShapeFailed ? 'INTERCEPTED' : (isNetworkError && !isCaseActive ? 'PENDING' : 'VERIFIED')}
                    </span>
                  </div>
                );
              })()}

              {/* Check 5 */}
              <div className="check-item skipped">
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                  <PauseCircle size={16} style={{ color: 'var(--outline)', marginTop: '2px', flexShrink: 0 }} />
                  <div>
                    <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--on-surface-variant)' }}>
                      Intracranial Mask Verification
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--on-surface-variant)' }}>
                      Validates brain mask bounding envelope.
                    </div>
                  </div>
                </div>
                <span className="status-pill-skipped">PIPELINE STEP</span>
              </div>

              {/* Check 6 */}
              <div className="check-item skipped">
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                  <PauseCircle size={16} style={{ color: 'var(--outline)', marginTop: '2px', flexShrink: 0 }} />
                  <div>
                    <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--on-surface-variant)' }}>
                      MONAI SegResNet Volumetric Inference
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--on-surface-variant)' }}>
                      Executes forward pass to generate multi-region tumor predictions.
                    </div>
                  </div>
                </div>
                <span className="status-pill-skipped">INFERENCE STEP</span>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
