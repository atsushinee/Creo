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

/**
 * Bounding-box projection from the Unstructured parse result. `points` are
 * pixel coordinates in the layout system used to normalize onto the page.
 * Unstructured has shipped two shapes: layout dims nested inside a `system`
 * object, or `system` as a plain string ("PixelSpace") with the dims flattened
 * onto the coordinates object — both must be handled.
 */
export interface ElementCoordinates {
  points: number[][];
  system: string | Record<string, number> | null;
  layout_width?: number;
  layout_height?: number;
  width?: number;
  height?: number;
}

export interface ParseElementInfo {
  type: string;
  text: string;
  pageNumber: number;
  tableHtml: string | null;
  coordinates?: ElementCoordinates | null;
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
