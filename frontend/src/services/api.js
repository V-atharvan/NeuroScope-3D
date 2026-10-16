/**
 * NeuroScope 3D - API Client
 * Interacts with backend FastAPI services adhering to docs/API_CONTRACT.md.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

/**
 * Fetch backend health and model readiness
 */
export async function getHealth() {
  const response = await fetch(`${API_BASE_URL}/api/health`);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Upload MRI sequence study (4 required + optional expert mask)
 */
export async function uploadStudy(formData) {
  const response = await fetch(`${API_BASE_URL}/api/cases`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.message || `Upload failed with status ${response.status}`);
  }
  return response.json();
}

/**
 * Get case results and quantitation
 */
export async function getCaseResults(caseId) {
  const response = await fetch(`${API_BASE_URL}/api/cases/${caseId}/results`);
  if (!response.ok) {
    throw new Error(`Failed to fetch results: ${response.statusText}`);
  }
  return response.json();
}
