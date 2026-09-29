import { useEffect, useRef, useState } from "react";
import * as pdfjs from "pdfjs-dist";
import type { PDFDocumentProxy } from "pdfjs-dist";

interface ViewerPageProps {
  doc: PDFDocumentProxy;
  pageNumber: number;
  width: number;
}

/** One page, rendered lazily the first time it scrolls near the viewport. */
function ViewerPage({ doc, pageNumber, width }: ViewerPageProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [rendered, setRendered] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "300px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!visible || rendered) {
      return;
    }
    let cancelled = false;
    (async () => {
      const page = await doc.getPage(pageNumber);
      if (cancelled) {
        return;
      }
      const base = page.getViewport({ scale: 1 });
      const scale = width > 0 ? width / base.width : 1;
      const viewport = page.getViewport({ scale });
      const canvas = canvasRef.current;
      if (!canvas) {
        return;
      }
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await page.render({ canvas, viewport }).promise;
      if (!cancelled) {
        setRendered(true);
      }
    })().catch(() => {
      // page rendering is best-effort; the placeholder stays
    });
    return () => {
      cancelled = true;
    };
  }, [visible, rendered, doc, pageNumber, width]);

  return (
    <div ref={containerRef} className="mb-3">
      <canvas
        ref={canvasRef}
        className={`mx-auto block w-full rounded-md border bg-white shadow-sm ${rendered ? "" : "hidden"}`}
      />
      {!rendered && (
        <div
          className="flex w-full items-center justify-center rounded-md border bg-surface text-[12px] text-muted-foreground"
          style={{ height: Math.round(width * 1.414) }}
        >
          {pageNumber}
        </div>
      )}
    </div>
  );
}

/**
 * Continuous-scroll PDF viewer for the right column. Remount via key={docId}
 * when the document changes; pages render lazily as they approach the view.
 */
export function PdfViewer({ url, title }: { url: string; title: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const loadingTask = pdfjs.getDocument({ url });
    loadingTask.promise
      .then((loaded) => setDoc(loaded))
      .catch((loadError: unknown) =>
        setError(loadError instanceof Error ? loadError.message : String(loadError)),
      );
    return () => {
      void loadingTask.destroy();
    };
  }, [url]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) {
      return;
    }
    const observer = new ResizeObserver(() => setWidth(Math.max(0, element.clientWidth - 32)));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b px-4 py-3">
        <p className="min-w-0 flex-1 truncate text-[13px] font-medium" title={title}>
          {title}
        </p>
        {doc && (
          <span className="shrink-0 text-[11.5px] text-muted-foreground">{doc.numPages} pages</span>
        )}
      </div>
      <div ref={containerRef} className="min-h-0 flex-1 overflow-y-auto p-4">
        {error && <p className="py-16 text-center text-[13px] text-error">{error}</p>}
        {!doc && !error && (
          <p className="py-16 text-center text-[13px] text-muted-foreground">Loading PDF…</p>
        )}
        {doc && width > 0 && (
          <>
            {Array.from({ length: doc.numPages }, (_, index) => (
              <ViewerPage key={index} doc={doc} pageNumber={index + 1} width={width} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
