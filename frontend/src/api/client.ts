import type { IngestResponse, QueryResponse, StatsResponse, Session } from "../types";

const BASE = "/api/v1";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
    throw new Error(detail || "Request failed");
  }
  return res.json();
}

// --- Legacy (default session) ---

export async function ingestFile(file: File): Promise<IngestResponse> {
  const form = new FormData();
  form.append("file", file);
  return api("/ingest", { method: "POST", body: form });
}

export async function queryStream(
  q: string,
  onChunk: (text: string) => void,
  onDone: () => void
): Promise<void> {
  await streamFrom("/query/stream", q, onChunk, onDone);
}

export async function getStats(): Promise<StatsResponse> {
  return api("/stats");
}

export async function clearDocuments(): Promise<void> {
  await api("/clear", { method: "DELETE" });
}

// --- Session-based ---

export async function createSession(): Promise<Session> {
  return api("/sessions", { method: "POST" });
}

export async function listSessions(): Promise<Session[]> {
  return api("/sessions");
}

export async function deleteSession(id: string): Promise<void> {
  await api(`/sessions/${id}`, { method: "DELETE" });
}

export async function sessionIngestFile(sessionId: string, file: File): Promise<IngestResponse> {
  const form = new FormData();
  form.append("file", file);
  return api(`/sessions/${sessionId}/ingest`, { method: "POST", body: form });
}

export async function sessionQueryStream(
  sessionId: string,
  q: string,
  onChunk: (text: string) => void,
  onDone: () => void
): Promise<void> {
  await streamFrom(`/sessions/${sessionId}/query/stream`, q, onChunk, onDone);
}

export async function sessionClear(sessionId: string): Promise<void> {
  await api(`/sessions/${sessionId}/clear`, { method: "POST" });
}

export async function getSessionStats(sessionId: string): Promise<StatsResponse> {
  return api(`/sessions/${sessionId}/stats`);
}

export async function renameSession(sessionId: string, name: string): Promise<Session> {
  return api(`/sessions/${sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

// --- Shared stream helper ---

async function streamFrom(
  path: string,
  q: string,
  onChunk: (text: string) => void,
  onDone: () => void,
): Promise<void> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: q }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onChunk(decoder.decode(value, { stream: true }));
  }
  onDone();
}
