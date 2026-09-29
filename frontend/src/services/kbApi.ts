/**
 * Knowledge base network boundary (AGENTS.md §2): components → hooks → this
 * service → Knowledge API (ADR-0004).
 */

import { ApiError, readErrorDetail } from "@/services/agentApi";
import type {
  DocChunkInfo,
  KbDocumentInfo,
  KnowledgeBaseInfo,
  ParseResultInfo,
  PipelineEventInfo,
  RecallTestResult,
} from "@/types/knowledgeBase";

const API_BASE = "/api";

function kbUrl(kbId: string, suffix = ""): string {
  return `${API_BASE}/kb/${encodeURIComponent(kbId)}${suffix}`;
}

async function parseBody<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new ApiError(await readErrorDetail(response), response.status);
  }
  return (await response.json()) as T;
}

export async function listKnowledgeBases(): Promise<KnowledgeBaseInfo[]> {
  return parseBody(await fetch(`${API_BASE}/kb`));
}

export async function createKnowledgeBase(
  name: string,
  description: string,
): Promise<KnowledgeBaseInfo> {
  return parseBody(
    await fetch(`${API_BASE}/kb`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description }),
    }),
  );
}

export async function deleteKnowledgeBase(kbId: string): Promise<void> {
  const response = await fetch(kbUrl(kbId), { method: "DELETE" });
  if (!response.ok && response.status !== 204) {
    throw new ApiError(await readErrorDetail(response), response.status);
  }
}

export async function listDocuments(kbId: string): Promise<KbDocumentInfo[]> {
  return parseBody(await fetch(kbUrl(kbId, "/documents")));
}

export async function uploadDocument(kbId: string, file: File): Promise<KbDocumentInfo> {
  const form = new FormData();
  form.append("file", file);
  // No manual Content-Type here: the browser must set the multipart boundary.
  return parseBody(await fetch(kbUrl(kbId, "/documents"), { method: "POST", body: form }));
}

export async function deleteDocument(kbId: string, docId: string): Promise<void> {
  const response = await fetch(kbUrl(kbId, `/documents/${encodeURIComponent(docId)}`), {
    method: "DELETE",
  });
  if (!response.ok && response.status !== 204) {
    throw new ApiError(await readErrorDetail(response), response.status);
  }
}

export async function reingestDocument(kbId: string, docId: string): Promise<KbDocumentInfo> {
  return parseBody(
    await fetch(kbUrl(kbId, `/documents/${encodeURIComponent(docId)}/reingest`), {
      method: "POST",
    }),
  );
}

/** Inline PDF URL for the pdf.js preview (served by the backend). */
export function documentFileUrl(kbId: string, docId: string): string {
  return kbUrl(kbId, `/documents/${encodeURIComponent(docId)}/file`);
}

export async function getDocumentTrace(kbId: string, docId: string): Promise<PipelineEventInfo[]> {
  return parseBody(await fetch(kbUrl(kbId, `/documents/${encodeURIComponent(docId)}/trace`)));
}

export async function getParseResult(kbId: string, docId: string): Promise<ParseResultInfo> {
  return parseBody(await fetch(kbUrl(kbId, `/documents/${encodeURIComponent(docId)}/parse-result`)));
}

export async function getDocChunks(kbId: string, docId: string): Promise<DocChunkInfo[]> {
  return parseBody(await fetch(kbUrl(kbId, `/documents/${encodeURIComponent(docId)}/chunks`)));
}

export interface RecallTestInput {
  query: string;
  top_k: number;
  doc_id?: string | null;
}

export async function retrievalTest(
  kbId: string,
  input: RecallTestInput,
): Promise<RecallTestResult> {
  return parseBody(
    await fetch(kbUrl(kbId, "/search-test"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}
