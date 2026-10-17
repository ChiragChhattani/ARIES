// src/services/api.js
// Handles all REST communication with the FastAPI backend.
const rawApiBase = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
const API_BASE = rawApiBase.replace(/\/+$/, "");

export async function createInterview(formData) {
  const payload = {
    job_description: {
      field: formData.field,
      title: formData.jobTitle,
      description: formData.jobDescription,
      competencies: formData.competencies.map(c => ({ name: c.name, description: c.description }))
    },
    settings: {
      difficulty: formData.difficulty,
      experience_level: formData.experienceLevel,
      max_questions: parseInt(formData.maxQuestions, 10),
      timeout_minutes: 30
    },
    candidate_identifier: "Anonymous Candidate"
  };

  const res = await fetch(`${API_BASE}/interviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  
  if (!res.ok) throw new Error("Failed to create interview");
  return res.json();
}

export async function listInterviews() {
  const res = await fetch(`${API_BASE}/interviews`);
  if (!res.ok) throw new Error("Failed to list interviews");
  return res.json();
}

export async function getInterview(sessionId) {
  const res = await fetch(`${API_BASE}/interviews/${sessionId}`);
  if (!res.ok) throw new Error("Failed to fetch interview");
  return res.json();
}

export async function startInterview(sessionId) {
  const res = await fetch(`${API_BASE}/interviews/${sessionId}/start`, { method: "POST" });
  if (!res.ok) {
    const errorData = await res.json().catch(() => null);
    throw {
      status: res.status,
      code: errorData?.error?.code || 'UNKNOWN_ERROR',
      message: errorData?.error?.message || 'Failed to start interview'
    };
  }
  return res.json();
}

export async function evaluateInterview(sessionId) {
  const res = await fetch(`${API_BASE}/interviews/${sessionId}/evaluate`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to evaluate interview");
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
  if (!res.ok) throw new Error("Failed to log proctoring event");
  return res.json();
}
