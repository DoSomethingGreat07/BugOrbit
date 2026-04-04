import type { FinalAnalysisResponse, IncidentFixRequest, IncidentStateResponse, TraceRequest } from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8010";
const REQUEST_TIMEOUT_MS = 10000;

async function fetchWithTimeout(input: RequestInfo | URL, init?: RequestInit) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("Request timed out while waiting for the backend.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function analyzeTrace(payload: TraceRequest): Promise<FinalAnalysisResponse> {
  const response = await fetchWithTimeout(`${API_BASE_URL}/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Analysis failed with status ${response.status}`);
  }

  return response.json();
}

export async function fetchIncidentState(): Promise<IncidentStateResponse> {
  const response = await fetchWithTimeout(`${API_BASE_URL}/incident/state`);

  if (!response.ok) {
    throw new Error(`Incident state failed with status ${response.status}`);
  }

  return response.json();
}

export async function recordIncidentFix(payload: IncidentFixRequest): Promise<IncidentStateResponse> {
  const response = await fetchWithTimeout(`${API_BASE_URL}/incident/fix`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Recording fix failed with status ${response.status}`);
  }

  return response.json();
}
