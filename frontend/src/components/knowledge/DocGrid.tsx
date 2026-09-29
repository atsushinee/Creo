import { useState } from "react";
import { History, RotateCcw, Trash2 } from "lucide-react";

import { DocThumbnail } from "@/components/knowledge/DocThumbnail";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { KbDocumentInfo, PipelineEventInfo } from "@/types/knowledgeBase";

interface DocGridProps {
  documents: KbDocumentInfo[];
  traceByDoc: Record<string, PipelineEventInfo[] | undefined>;
  selectedDocId: string | null;
  onGetFileUrl: (docId: string) => string;
  onSelect: (doc: KbDocumentInfo) => void;
  onDeleteDoc: (docId: string) => void;
  onReingest: (docId: string) => void;
  onLoadTrace: (docId: string) => void;
}

const statusDot: Record<string, string> = {
  ready: "bg-success",
  failed: "bg-error",
  processing: "bg-warning",
  pending: "bg-muted-foreground",
};

function formatSize(size: number): string {
  if (size < 1024 * 1024) {
    return `${Math.max(1, Math.round(size / 1024))} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

/** Document cards: page-1 cover fills the card width, info below. */
export function DocGrid({
  documents,
  traceByDoc,
  selectedDocId,
  onGetFileUrl,
  onSelect,
  onDeleteDoc,
  onReingest,
  onLoadTrace,
}: DocGridProps) {
  const [traceDocId, setTraceDocId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<KbDocumentInfo | null>(null);

  const toggleTrace = (doc: KbDocumentInfo) => {
    if (traceDocId === doc.id) {
      setTraceDocId(null);
      return;
    }
    setTraceDocId(doc.id);
    onLoadTrace(doc.id);
  };

  return (
    <div className="flex flex-col gap-2.5">
      {documents.map((doc) => (
        <div
          key={doc.id}
          className={cn(
            "group cursor-pointer overflow-hidden rounded-lg border bg-surface transition-colors",
            doc.id === selectedDocId
              ? "border-primary/60 ring-1 ring-ring"
              : "hover:border-primary/40",
          )}
          onClick={() => onSelect(doc)}
        >
          <DocThumbnail url={onGetFileUrl(doc.id)} />
          <div className="p-2">
            <p className="truncate text-[12.5px] font-medium" title={doc.filename}>
              {doc.filename}
            </p>
            <div className="flex items-center gap-1.5 pt-1">
              <span className={cn("size-1.5 shrink-0 rounded-full", statusDot[doc.status])} />
              <span className="truncate text-[11px] text-muted-foreground">
                {doc.status === "ready" ? `${doc.chunkCount} chunks` : doc.status}
                {" · "}
                {formatSize(doc.size)}
              </span>
              <span className="ml-auto flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Trace ${doc.filename}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    toggleTrace(doc);
                  }}
                >
                  <History className="size-3" />
                </Button>
                {doc.status === "failed" && (
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Re-ingest ${doc.filename}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      onReingest(doc.id);
                    }}
                  >
                    <RotateCcw className="size-3" />
                  </Button>
                )}
                <Button
                  variant="danger-ghost"
                  size="icon-sm"
                  aria-label={`Delete ${doc.filename}`}
                  disabled={doc.status === "processing"}
                  onClick={(event) => {
                    event.stopPropagation();
                    setPendingDelete(doc);
                  }}
                >
                  <Trash2 className="size-3" />
                </Button>
              </span>
            </div>
          </div>
          {traceDocId === doc.id && (
            <div className="border-t px-2 py-1.5" onClick={(event) => event.stopPropagation()}>
              {(traceByDoc[doc.id] ?? []).length === 0 ? (
                <p className="text-[10.5px] text-muted-foreground">No pipeline events yet.</p>
              ) : (
                <ol className="space-y-0.5">
                  {(traceByDoc[doc.id] ?? []).map((event) => (
                    <li key={event.id} className="flex items-center gap-1.5 text-[10.5px]">
                      <span
                        className={cn(
                          "size-1.5 shrink-0 rounded-full",
                          event.status === "succeeded" && "bg-success",
                          event.status === "failed" && "bg-error",
                          event.status === "started" && "bg-warning",
                        )}
                      />
                      <span className="w-11 shrink-0 font-medium">{event.stage}</span>
                      <span className="shrink-0 text-muted-foreground">{event.durationMs} ms</span>
                      <span className="shrink-0 text-muted-foreground">{event.status}</span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          )}
        </div>
      ))}

      <ConfirmDialog
        open={pendingDelete !== null}
        title={`Delete "${pendingDelete?.filename ?? ""}"?`}
        description="The stored file and its indexed vectors will be removed. This cannot be undone."
        confirmLabel="Delete"
        danger
        onConfirm={() => {
          if (pendingDelete) {
            if (traceDocId === pendingDelete.id) {
              setTraceDocId(null);
            }
            onDeleteDoc(pendingDelete.id);
          }
          setPendingDelete(null);
        }}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
