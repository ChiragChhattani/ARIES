// src/services/api.js
// Handles all REST communication with the FastAPI backend.

/**
 * Normalizes any provided API URL to guarantee it points to /api/v1
 * with no duplicate segments, missing prefixes, or trailing slashes.
 */
export function getApiBase(rawUrl = import.meta?.env?.VITE_API_URL) {
  let url = (rawUrl || "").trim();
  if (!url) {
    url = import.meta?.env?.PROD
      ? "https://aries-backend-8ydf.onrender.com/api/v1"
      : "http://localhost:8000/api/v1";
  }
  // Strip all trailing slashes
  url = url.replace(/\/+$/, "");

  // If the URL does not already end with /api/v1, append it
  if (!url.endsWith("/api/v1")) {
    url = `${url}/api/v1`;
  }
  return url;
}

export const API_BASE = getApiBase();

export async function createInterview(formData) {
  const payload = {
    job_description: {
      field: formData.field,
      custom_field_name: formData.customField || "",
      title: formData.jobTitle,
      description: formData.jobDescription,
      required_skills: formData.skills
        ? formData.skills.split(",").map(s => s.trim()).filter(Boolean)
        : [],
      experience_level: formData.experienceLevel || "junior",
      difficulty: formData.difficulty || "medium",
      competencies: (formData.competencies || []).map(c => ({
        name: c.name,
        description: c.description,
        weight: c.weight || 1.0,
        required: c.required !== undefined ? c.required : true
      }))
    },
    settings: {
      difficulty: formData.difficulty || "medium",
      experience_level: formData.experienceLevel || "junior",
      max_questions: parseInt(formData.maxQuestions || 10, 10),
      timeout_minutes: 30
    },
    candidate_identifier: "Anonymous Candidate"
  };

  const res = await fetch(`${API_BASE}/interviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  
  if (!res.ok) {
    const errorBody = await res.text().catch(() => "");
    throw new Error(`Failed to create interview (${res.status}): ${errorBody}`);
  }
  return res.json();
}

export async function listInterviews() {
  const res = await fetch(`${API_BASE}/interviews`);
  if (!res.ok) {
    const errorBody = await res.text().catch(() => "");
    throw new Error(`Failed to list interviews (${res.status}): ${errorBody}`);
  }
  return res.json();
}

export async function getInterview(sessionId) {
  const res = await fetch(`${API_BASE}/interviews/${sessionId}`);
  if (!res.ok) {
    const errorBody = await res.text().catch(() => "");
    throw new Error(`Failed to fetch interview (${res.status}): ${errorBody}`);
  }
  return res.json();
}

export async function startInterview(sessionId) {
  const res = await fetch(`${API_BASE}/interviews/${sessionId}/start`, { method: "POST" });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw {
      status: res.status,
      code: errorData?.detail?.code || 'UNKNOWN_ERROR',
      message: errorData?.detail?.message || 'Failed to start interview'
    };
  }
  return res.json();
}

export async function evaluateInterview(sessionId) {
  const res = await fetch(`${API_BASE}/interviews/${sessionId}/evaluate`, { method: "POST" });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    const correlationId = res.headers.get("x-correlation-id") || errorData?.correlation_id;
    const message = errorData?.detail?.message || errorData?.detail || `Failed to evaluate interview (${res.status})`;
    const code = errorData?.detail?.code || "EVALUATION_ERROR";
    const err = new Error(message);
    err.status = res.status;
    err.code = code;
    err.correlationId = correlationId;
    throw err;
  }
  return res.json();
}

export async function logProctoringEvent(sessionId, eventType, details = "") {
  const payload = {
    event_type: eventType,
    details: details
  };
  const res = await fetch(`${API_BASE}/interviews/${sessionId}/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const errorBody = await res.text().catch(() => "");
    throw new Error(`Failed to log proctoring event (${res.status}): ${errorBody}`);
  }
  return res.json();
}

export async function submitAnswerRest(sessionId, answerText, lastQuestion = null) {
  const payload = { answer: answerText };
  if (lastQuestion) payload.last_question = lastQuestion;
  const res = await fetch(`${API_BASE}/interviews/${sessionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    const err = new Error(errorData.detail?.message || "Failed to submit answer");
    err.status = res.status;
    err.code = errorData.detail?.code;
    throw err;
  }
  return res.json();
}
