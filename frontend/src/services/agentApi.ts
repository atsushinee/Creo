/**
 * The single network boundary of the frontend (AGENTS.md §2):
 * components → hooks → this service → Agent API.
 */

import { createSseParser } from "@/lib/sse";
import type { AgentEvent, HistoryMessage, SessionInfo } from "@/types/agent";

const API_BASE = "/api";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function readErrorDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

export interface StreamChatOptions {
  sessionId: string;
  message: string;
  onEvent: (event: AgentEvent) => void;
  signal?: AbortSignal;
  /** Document-chat scope: binds the run to a doc-scoped agent (ADR-0004). */
  docScope?: { kbId: string; docId: string };
}

/**
 * POST /api/chat and consume the SSE stream via fetch + ReadableStream
 * (EventSource cannot POST). Resolves when the stream ends.
 */
export async function streamChat(options: StreamChatOptions): Promise<void> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      session_id: options.sessionId,
      message: options.message,
      kb_id: options.docScope?.kbId ?? null,
      doc_id: options.docScope?.docId ?? null,
    }),
    signal: options.signal,
  });

  const body = response.body;
  if (!response.ok || !body) {
    throw new ApiError(await readErrorDetail(response), response.status);
  }

  const parser = createSseParser((frame) => {
    if (!frame.data) {
      return;
    }
    try {
      options.onEvent(JSON.parse(frame.data) as AgentEvent);
    } catch {
      // Malformed frame — skip rather than crash the UI.
    }
  });

  const reader = body.getReader();
  const decoder = new TextDecoder();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      parser.push(decoder.decode(value, { stream: true }));
    }
    parser.push(decoder.decode());
  } finally {
    reader.releaseLock();
  }
}

export async function listSessions(): Promise<SessionInfo[]> {
  const response = await fetch(`${API_BASE}/sessions`);
  if (!response.ok) {
    throw new ApiError(await readErrorDetail(response), response.status);
  }
  return (await response.json()) as SessionInfo[];
}

export async function getSessionMessages(
  sessionId: string,
  scope?: { kbId: string; docId: string },
): Promise<HistoryMessage[]> {
  const query = scope
    ? `?kb_id=${encodeURIComponent(scope.kbId)}&doc_id=${encodeURIComponent(scope.docId)}`
    : "";
  const response = await fetch(
    `${API_BASE}/sessions/${encodeURIComponent(sessionId)}/messages${query}`,
  );
  if (!response.ok) {
    throw new ApiError(await readErrorDetail(response), response.status);
  }
  return (await response.json()) as HistoryMessage[];
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
  if (!response.ok && response.status !== 204) {
    throw new ApiError(await readErrorDetail(response), response.status);
  }
}
