import { useRef, useState } from "react";
import { Eye, FileText, History, RotateCcw, Trash2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { PdfPreview } from "@/components/knowledge/PdfPreview";
import { cn } from "@/lib/utils";
import type {
  KbDocumentInfo,
  KbDocumentStatus,
  KnowledgeBaseInfo,
  PipelineEventInfo,
} from "@/types/knowledgeBase";

interface DocumentPanelProps {
  kb: KnowledgeBaseInfo;
  documents: KbDocumentInfo[];
  traceByDoc: Record<string, PipelineEventInfo[] | undefined>;
  isBusy: boolean;
  onUpload: (file: File) => Promise<void>;
  onDeleteDoc: (docId: string) => void;
  onReingest: (docId: string) => void;
  onLoadTrace: (docId: string) => void;
  onGetFileUrl: (docId: string) => string;
}

const statusStyles: Record<KbDocumentStatus, string> = {
  ready: "bg-success/10 text-success",
  failed: "bg-error/10 text-error",
  processing: "bg-warning/10 text-warning",
  pending: "bg-surface-raised text-muted-foreground",
};

function formatSize(size: number): string {
  if (size < 1024 * 1024) {
    return `${Math.max(1, Math.round(size / 1024))} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDetail(detail: string | null): string {
  if (!detail) {
    return "";
  }
  try {
    const parsed = JSON.parse(detail) as Record<string, unknown>;
    return Object.entries(parsed)
      .map(([key, value]) => `${key}: ${String(value)}`)
      .join(" · ");
  } catch {
    return detail;
  }
}

function TracePanel({ events }: { events: PipelineEventInfo[] }) {
  if (events.length === 0) {
    return (
      <p className="px-9 pb-2 text-[12px] text-muted-foreground">No pipeline events recorded yet.</p>
    );
  }
  return (
    <ol className="space-y-1 px-9 pb-3">
      {events.map((event) => (
        <li key={event.id} className="flex items-center gap-2 text-[11.5px]">
          <span
            className={cn(
              "size-1.5 shrink-0 rounded-full",
              event.status === "succeeded" && "bg-success",
              event.status === "failed" && "bg-error",
              event.status === "started" && "bg-warning",
            )}
          />
          <span className="w-14 shrink-0 font-medium">{event.stage}</span>
          <span className="shrink-0 text-muted-foreground">{event.status}</span>
          {event.durationMs !== null && (
            <span className="shrink-0 text-muted-foreground">{event.durationMs} ms</span>
          )}
          <span className="min-w-0 flex-1 truncate text-muted-foreground" title={event.detail ?? ""}>
            {formatDetail(event.detail)}
          </span>
          <span className="shrink-0 text-muted-foreground">
            {new Date(event.createdAt).toLocaleTimeString()}
          </span>
        </li>
      ))}
    </ol>
  );
}

export function DocumentPanel({
  kb,
  documents,
  traceByDoc,
  isBusy,
  onUpload,
  onDeleteDoc,
  onReingest,
  onLoadTrace,
  onGetFileUrl,
}: DocumentPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [previewDoc, setPreviewDoc] = useState<KbDocumentInfo | null>(null);
  const [traceDocId, setTraceDocId] = useState<string | null>(null);

  const handleFiles = async (files: FileList | null) => {
    if (!files) {
      return;
    }
    for (const file of Array.from(files)) {
      await onUpload(file);
    }
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  const toggleTrace = (doc: KbDocumentInfo) => {
    if (traceDocId === doc.id) {
      setTraceDocId(null);
      return;
    }
    setTraceDocId(doc.id);
    onLoadTrace(doc.id);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
        <div className="min-w-0">
          <h1 className="truncate text-[14px] font-semibold">{kb.name}</h1>
          {kb.description && (
            <p className="truncate text-[12px] text-muted-foreground">{kb.description}</p>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          className="hidden"
          onChange={(event) => void handleFiles(event.target.files)}
        />
        <Button size="sm" disabled={isBusy} onClick={() => inputRef.current?.click()}>
          <Upload className="size-3.5" />
          Upload PDF
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {documents.length === 0 ? (
          <p className="px-2 text-[12.5px] leading-relaxed text-muted-foreground">
            No documents yet — upload PDFs and they will be parsed, chunked and indexed
            for hybrid retrieval (BM25 + dense vectors).
          </p>
        ) : (
          <ul className="space-y-2">
            {documents.map((doc) => (
              <li key={doc.id} className="rounded-lg border bg-surface">
                <div className="flex items-center gap-3 px-3 py-2.5">
                  <FileText className="size-4 shrink-0 text-muted-foreground" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px]" title={doc.filename}>
                      {doc.filename}
                    </p>
                    {doc.error && (
                      <p className="truncate text-[11.5px] text-error" title={doc.error}>
                        {doc.error}
                      </p>
                    )}
                  </div>
                  <span
                    className={cn(
                      "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium",
                      statusStyles[doc.status],
                    )}
                  >
                    {doc.status}
                  </span>
                  <span className="hidden shrink-0 text-[11.5px] text-muted-foreground sm:inline">
                    {doc.status === "ready" ? `${doc.chunkCount} chunks · ` : ""}
                    {formatSize(doc.size)}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Preview ${doc.filename}`}
                    onClick={() => setPreviewDoc(doc)}
                  >
                    <Eye className="size-3.5" />
                  </Button>
                  <Button
                    variant={traceDocId === doc.id ? "outline" : "ghost"}
                    size="icon-sm"
                    aria-label={`Trace ${doc.filename}`}
                    onClick={() => toggleTrace(doc)}
                  >
                    <History className="size-3.5" />
                  </Button>
                  {doc.status === "failed" && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`Re-ingest ${doc.filename}`}
                      onClick={() => onReingest(doc.id)}
                    >
                      <RotateCcw className="size-3.5" />
                    </Button>
                  )}
                  <Button
                    variant="danger-ghost"
                    size="icon-sm"
                    aria-label={`Delete ${doc.filename}`}
                    disabled={doc.status === "processing"}
                    onClick={() => {
                      if (window.confirm(`Delete "${doc.filename}" and its indexed vectors?`)) {
                        if (traceDocId === doc.id) {
                          setTraceDocId(null);
                        }
                        onDeleteDoc(doc.id);
                      }
                    }}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
                {traceDocId === doc.id && (
                  <div className="border-t">
                    <TracePanel events={traceByDoc[doc.id] ?? []} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {previewDoc && (
        <PdfPreview
          key={previewDoc.id}
          url={onGetFileUrl(previewDoc.id)}
          title={previewDoc.filename}
          onClose={() => setPreviewDoc(null)}
        />
      )}
    </div>
  );
}
