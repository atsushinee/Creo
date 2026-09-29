import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import * as pdfjs from "pdfjs-dist";
import type { PDFDocumentLoadingTask, PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

import { Button } from "@/components/ui/button";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

interface PdfPreviewProps {
  url: string;
  title: string;
  onClose: () => void;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/**
 * Minimal pdf.js viewer: page-by-page canvas rendering inside an overlay.
 * The PDF itself is streamed from the backend's inline file endpoint.
 */
export function PdfPreview({ url, title, onClose }: PdfPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const loadingTaskRef = useRef<PDFDocumentLoadingTask | null>(null);
  const renderTaskRef = useRef<RenderTask | null>(null);
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Initial state (above) is the reset: DocumentPanel remounts this
    // component via key={docId}, so the effect only loads and renders.
    let cancelled = false;
    const loadingTask = pdfjs.getDocument({ url });
    loadingTaskRef.current = loadingTask;
    loadingTask.promise
      .then((loaded) => {
        if (cancelled) {
          return;
        }
        setDoc(loaded);
        setLoading(false);
      })
      .catch((loadError: unknown) => {
        if (!cancelled && !loadingTask.destroyed) {
          setError(message(loadError));
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      renderTaskRef.current?.cancel();
      void loadingTask.destroy(); // v6: teardown lives on the loading task
      loadingTaskRef.current = null;
    };
  }, [url]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!doc || !canvas) {
      return;
    }
    let cancelled = false;
    (async () => {
      const pdfPage = await doc.getPage(page);
      if (cancelled) {
        return;
      }
      const viewport = pdfPage.getViewport({ scale: 1.6 });
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      renderTaskRef.current?.cancel();
      const task = pdfPage.render({ canvas, viewport }); // v6: canvas, not ctx
      renderTaskRef.current = task;
      await task.promise;
    })().catch((renderError: unknown) => {
      if (
        !cancelled &&
        !(renderError instanceof Error && renderError.name === "RenderingCancelledException")
      ) {
        setError(message(renderError));
      }
    });
    return () => {
      cancelled = true;
      renderTaskRef.current?.cancel();
    };
  }, [doc, page]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="flex h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-xl border bg-background shadow-lg"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b px-4 py-2.5">
          <p className="min-w-0 flex-1 truncate text-[13px] font-medium" title={title}>
            {title}
          </p>
          <div className="flex shrink-0 items-center gap-1">
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Previous page"
              disabled={page <= 1}
              onClick={() => setPage((value) => Math.max(1, value - 1))}
            >
              <ChevronLeft className="size-4" />
            </Button>
            <span className="min-w-14 text-center text-[12px] text-muted-foreground">
              {loading ? "…" : `${page} / ${doc?.numPages ?? "?"}`}
            </span>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Next page"
              disabled={!doc || page >= doc.numPages}
              onClick={() => setPage((value) => Math.min(doc?.numPages ?? 1, value + 1))}
            >
              <ChevronRight className="size-4" />
            </Button>
            <Button variant="ghost" size="icon-sm" aria-label="Close preview" onClick={onClose}>
              <X className="size-4" />
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-auto bg-surface p-4">
          {loading && (
            <p className="py-16 text-center text-[13px] text-muted-foreground">Loading PDF…</p>
          )}
          {error && <p className="py-16 text-center text-[13px] text-error">{error}</p>}
          <div className="flex justify-center">
            <canvas
              ref={canvasRef}
              className={`max-w-full rounded-md border shadow-sm ${loading || error ? "hidden" : ""}`}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
