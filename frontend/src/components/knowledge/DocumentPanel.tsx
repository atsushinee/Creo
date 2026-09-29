import { useRef } from "react";
import { FileText, RotateCcw, Trash2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { KbDocumentInfo, KbDocumentStatus, KnowledgeBaseInfo } from "@/types/knowledgeBase";

interface DocumentPanelProps {
  kb: KnowledgeBaseInfo;
  documents: KbDocumentInfo[];
  isBusy: boolean;
  onUpload: (file: File) => Promise<void>;
  onDeleteDoc: (docId: string) => void;
  onReingest: (docId: string) => void;
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

export function DocumentPanel({
  kb,
  documents,
  isBusy,
  onUpload,
  onDeleteDoc,
  onReingest,
}: DocumentPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);

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
              <li
                key={doc.id}
                className="flex items-center gap-3 rounded-lg border bg-surface px-3 py-2.5"
              >
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
                  onClick={() => onDeleteDoc(doc.id)}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
