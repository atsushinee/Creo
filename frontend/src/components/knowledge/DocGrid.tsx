import { useState } from "react";
import { History, RotateCcw, Trash2 } from "lucide-react";

import { DocThumbnail } from "@/components/knowledge/DocThumbnail";
import { ConfirmDialog } from "@/components/ui/dialog";
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

/**
 * Compact cover tiles (card = one page-1 cover): filename/status/actions are
 * overlaid on the image — bottom scrim with the name, status dot top-left,
 * hover actions top-right. The trace timeline expands below the tile.
 */
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
    <div className="grid grid-cols-2 gap-2">
      {documents.map((doc) => (
        <div
          key={doc.id}
          className={cn(
            "group cursor-pointer overflow-hidden rounded-lg border transition-colors",
            doc.id === selectedDocId
              ? "border-primary/60 ring-1 ring-ring"
              : "hover:border-primary/40",
          )}
          onClick={() => onSelect(doc)}
          title={`${doc.filename} · ${doc.status}${
            doc.status === "ready" ? ` · ${doc.chunkCount} chunks` : ""
          } · ${formatSize(doc.size)}`}
        >
          <div className="relative">
            <DocThumbnail url={onGetFileUrl(doc.id)} />

            <span
              className={cn(
                "absolute top-1.5 left-1.5 size-2 rounded-full ring-1 ring-white/70",
                statusDot[doc.status],
              )}
              aria-label={doc.status}
            />

            <div className="absolute top-1 right-1 flex items-center gap-0.5 rounded-md bg-black/55 p-0.5 opacity-0 transition-opacity group-hover:opacity-100">
              <button
                type="button"
                aria-label={`Trace ${doc.filename}`}
                title="Pipeline trace"
                className="flex size-6 cursor-pointer items-center justify-center rounded text-white transition-colors hover:bg-white/20"
                onClick={(event) => {
                  event.stopPropagation();
                  toggleTrace(doc);
                }}
              >
                <History className="size-3.5" />
              </button>
              {doc.status === "failed" && (
                <button
                  type="button"
                  aria-label={`Re-ingest ${doc.filename}`}
                  title="Re-ingest"
                  className="flex size-6 cursor-pointer items-center justify-center rounded text-white transition-colors hover:bg-white/20"
                  onClick={(event) => {
                    event.stopPropagation();
                    onReingest(doc.id);
                  }}
                >
                  <RotateCcw className="size-3.5" />
                </button>
              )}
              <button
                type="button"
                aria-label={`Delete ${doc.filename}`}
                title="Delete"
                disabled={doc.status === "processing"}
                className="flex size-6 cursor-pointer items-center justify-center rounded text-white transition-colors hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-40"
                onClick={(event) => {
                  event.stopPropagation();
                  setPendingDelete(doc);
                }}
              >
                <Trash2 className="size-3.5" />
              </button>
            </div>

            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/75 via-black/35 to-transparent px-1.5 pt-4 pb-1">
              <p className="truncate text-[11px] font-medium text-white" title={doc.filename}>
                {doc.filename}
              </p>
              {doc.error && (
                <p className="truncate text-[10px] text-red-300" title={doc.error}>
                  {doc.error}
                </p>
              )}
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
