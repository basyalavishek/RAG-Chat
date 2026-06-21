import type { QueryResponse, StatsResponse, Session, Message } from "../types";

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

export async function ingestFile(file: File): Promise<{ task_id: string; filename: string }> {
  const form = new FormData();
  form.append("file", file);
  return api("/ingest", { method: "POST", body: form });
}

export async function queryStream(
  q: string,
  onChunk: (text: string) => void,
  onDone: () => void
): Promise<{ sources?: { content: string; source: string; page?: number }[] }> {
  return streamFrom("/query/stream", q, onChunk, onDone);
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

export async function sessionIngestFile(sessionId: string, file: File): Promise<{ task_id: string; filename: string }> {
  const form = new FormData();
  form.append("file", file);
  return api(`/sessions/${sessionId}/ingest`, { method: "POST", body: form });
}

export interface IngestTaskStatus {
  status: "pending" | "processing" | "completed" | "failed";
  progress: number;
  step: string;
  message: string;
  filename?: string;
  chunks?: number;
}

export async function getIngestTask(taskId: string): Promise<IngestTaskStatus> {
  return api(`/ingest/task/${taskId}`);
}

export async function sessionQueryStream(
  sessionId: string,
  q: string,
  onChunk: (text: string) => void,
  onDone: () => void
): Promise<{ sources?: { content: string; source: string; page?: number }[] }> {
  return streamFrom(`/sessions/${sessionId}/query/stream`, q, onChunk, onDone);
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

export async function getMessages(sessionId: string): Promise<Message[]> {
  return api(`/sessions/${sessionId}/messages`);
}

export async function addMessage(
  sessionId: string,
  role: string,
  content: string,
  sources?: { content: string; source: string; page?: number }[]
): Promise<Message> {
  return api(`/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, content, sources }),
  });
}

// --- Shared stream helper ---

async function streamFrom(
  path: string,
  q: string,
  onChunk: (text: string) => void,
  onDone: () => void,
): Promise<{ sources?: { content: string; source: string; page?: number }[] }> {
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
  let buffer = "";
  let sources: { content: string; source: string; page?: number }[] | undefined;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6);
      if (data === "[DONE]") continue;
      try {
        const parsed = JSON.parse(data);
        if ("t" in parsed) {
          onChunk(parsed.t);
        }
        if ("s" in parsed) {
          sources = parsed.s;
        }
      } catch {
        // ignore malformed JSON
      }
    }
  }
  onDone();
  return { sources };
}
