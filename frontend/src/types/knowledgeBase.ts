/**
 * Knowledge base types (ADR-0004). Mirrors backend/app/models/knowledge.py.
 */

export type KbDocumentStatus = "pending" | "processing" | "ready" | "failed";

export interface KnowledgeBaseInfo {
  id: string;
  name: string;
  description: string;
  collectionName: string;
  documentCount: number;
  createdAt: string;
}

export interface KbDocumentInfo {
  id: string;
  kbId: string;
  filename: string;
  size: number;
  status: KbDocumentStatus;
  error: string | null;
  chunkCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface PipelineEventInfo {
  id: number;
  docId: string;
  kbId: string;
  stage: string;
  status: string;
  detail: string | null;
  durationMs: number | null;
  createdAt: string;
}

export interface RecallHit {
  text: string;
  docId: string;
  chunkIndex: number;
  page: number;
  metadata: Record<string, unknown> | null;
  score: number;
  kbId?: string;
  kbName?: string;
}

export interface RecallTestResult {
  hybrid: RecallHit[];
  dense: RecallHit[];
  sparse: RecallHit[];
}

export interface ParseElementInfo {
  type: string;
  text: string;
  pageNumber: number;
  tableHtml: string | null;
}

export interface ParseResultInfo {
  available: boolean;
  source: string | null;
  profile: string | null;
  elements: ParseElementInfo[];
}

export interface DocChunkInfo {
  text: string;
  chunkIndex: number;
  page: number;
}
