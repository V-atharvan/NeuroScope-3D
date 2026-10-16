/**
 * NeuroScope 3D - REST API Service Client
 * Interacts directly with the FastAPI backend defined in docs/API_CONTRACT.md.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

/**
 * Backend operational status and model readiness
 */
export async function getHealth() {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Upload 4 required MRI sequences and optional expert mask
 */
export async function uploadStudy(formData) {
  const res = await fetch(`${API_BASE}/api/cases`, {
    method: 'POST',
    body: formData,
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const errorMsg = data.message || `Upload failed with HTTP ${res.status}`;
    const err = new Error(errorMsg);
    err.code = data.code || 'UPLOAD_FAILED';
    err.details = data.details || {};
    throw err;
  }
  return data;
}

/**
 * Validate case geometry
 */
export async function validateCase(caseId) {
  const res = await fetch(`${API_BASE}/api/cases/${caseId}/validate`);
  if (!res.ok) {
    throw new Error(`Validation request failed with HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Trigger real model inference
 */
export async function triggerSegmentation(caseId) {
  const res = await fetch(`${API_BASE}/api/cases/${caseId}/segment`, {
    method: 'POST',
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.message || `Segmentation failed with HTTP ${res.status}`);
    err.code = data.code || 'SEGMENTATION_ERROR';
    throw err;
  }
  return data;
}

/**
 * Check processing status
 */
export async function getCaseStatus(caseId) {
  const res = await fetch(`${API_BASE}/api/cases/${caseId}/status`);
  if (!res.ok) {
    throw new Error(`Failed to query case status: ${res.statusText}`);
  }
  return res.json();
}

/**
 * Get results, volumes, metrics, and provenance
 */
export async function getCaseResults(caseId) {
  const res = await fetch(`${API_BASE}/api/cases/${caseId}/results`);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Failed to fetch results with HTTP ${res.status}`);
  }
  return data;
}

/**
 * Return download URLs
 */
export function getMaskDownloadUrl(caseId) {
  return `${API_BASE}/api/cases/${caseId}/mask`;
}

export function getReportDownloadUrl(caseId) {
  return `${API_BASE}/api/cases/${caseId}/report`;
}
