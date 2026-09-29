import { useEffect, useRef, useState } from "react";
import { ChevronFirst, ChevronLast } from "lucide-react";

import { pdfjs } from "@/lib/pdfjs";
import { useI18n } from "@/hooks/useI18n";
import type { PDFDocumentProxy } from "pdfjs-dist";

interface ViewerPageProps {
  doc: PDFDocumentProxy;
  pageNumber: number;
  width: number;
  registerRef: (element: HTMLDivElement | null) => void;
}

/** One page, rendered lazily the first time it scrolls near the viewport. */
function ViewerPage({ doc, pageNumber, width, registerRef }: ViewerPageProps) {
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
    })().catch((renderError: unknown) => {
      // Page rendering is best-effort; aborts are expected on doc switches.
      if (!(renderError instanceof Error && renderError.name === "RenderingCancelledException")) {
        console.warn(`[PdfViewer] page ${pageNumber} render failed:`, renderError);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [visible, rendered, doc, pageNumber, width]);

  return (
    <div
      ref={(element) => {
        containerRef.current = element;
        registerRef(element);
      }}
      className="mb-3"
    >
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

function isAbortLike(error: unknown): boolean {
  const text = error instanceof Error ? `${error.name} ${error.message}` : String(error);
  return (
    /abort/i.test(text) || (error instanceof Error && error.name === "RenderingCancelledException")
  );
}

/**
 * Continuous-scroll PDF viewer for the right column. Remount via key={docId}
 * when the document changes; pages render lazily as they approach the view.
 * The header offers jump-to-page plus top/bottom shortcuts and tracks the
 * page currently in view while scrolling.
 */
export function PdfViewer({ url, title }: { url: string; title: string }) {
  const { t } = useI18n();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const pageRefs = useRef<Array<HTMLDivElement | null>>([]);
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [width, setWidth] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageInput, setPageInput] = useState("1");
  const numPages = doc?.numPages ?? 0;

  useEffect(() => {
    const loadingTask = pdfjs.getDocument({ url });
    loadingTask.promise
      .then((loaded) => setDoc(loaded))
      .catch((loadError: unknown) => {
        // StrictMode double-mounts and doc switches abort the first load on
        // purpose — that is not a failure the user should see.
        if (!isAbortLike(loadError)) {
          setError(loadError instanceof Error ? loadError.message : String(loadError));
        }
      });
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

  const handleScroll = () => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const top = container.getBoundingClientRect().top;
    let current = 1;
    pageRefs.current.forEach((element, index) => {
      if (element && element.getBoundingClientRect().top <= top + 48) {
        current = index + 1;
      }
    });
    setCurrentPage(current);
    setPageInput(String(current));
  };

  const jumpTo = (target: number) => scrollToPage(Math.round(target));

  const scrollToPage = (target: number) => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const clamped = Math.min(Math.max(1, target), Math.max(1, numPages));
    const element = pageRefs.current[clamped - 1];
    if (element) {
      const top = element.getBoundingClientRect().top - container.getBoundingClientRect().top;
      container.scrollTo({ top: container.scrollTop + top - 8, behavior: "smooth" });
    }
    setPageInput(String(clamped));
    setCurrentPage(clamped);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b px-4 py-3">
        <p className="min-w-0 flex-1 truncate text-[13px] font-medium" title={title}>
          {title}
        </p>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            aria-label={t("viewer.jumpFirst")}
            title={t("viewer.jumpFirst")}
            disabled={!doc}
            onClick={() => scrollToPage(1)}
            className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-surface hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ChevronFirst className="size-4" />
          </button>
          <span className="min-w-12 text-center text-[11.5px] text-muted-foreground">
            {currentPage} / {numPages || "?"}
          </span>
          <input
            type="number"
            min={1}
            max={numPages || 1}
            value={pageInput}
            disabled={!doc}
            onChange={(event) => setPageInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                const target = Number(pageInput);
                if (Number.isFinite(target)) {
                  jumpTo(target);
                }
                event.currentTarget.blur();
              }
            }}
            title={t("viewer.jumpPage")}
            className="w-14 rounded-md border bg-background px-1.5 py-1 text-center text-[12px] outline-none focus-visible:outline-2 focus-visible:outline-ring"
            aria-label={t("viewer.jumpPage")}
          />
          <button
            type="button"
            aria-label={t("viewer.jumpLast")}
            title={t("viewer.jumpLast")}
            disabled={!doc}
            onClick={() => scrollToPage(numPages)}
            className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-surface hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ChevronLast className="size-4" />
          </button>
        </div>
      </div>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="relative min-h-0 flex-1 overflow-y-auto p-4"
      >
        {error && <p className="py-16 text-center text-[13px] text-error">{error}</p>}
        {!doc && !error && (
          <p className="py-16 text-center text-[13px] text-muted-foreground">{t("viewer.loading")}</p>
        )}
        {doc && width > 0 && (
          <>
            {Array.from({ length: doc.numPages }, (_, index) => (
              <ViewerPage
                key={index}
                doc={doc}
                pageNumber={index + 1}
                width={width}
                registerRef={(element) => {
                  pageRefs.current[index] = element;
                }}
              />
            ))}
            <p className="pb-2 text-center text-[11px] text-muted-foreground">
              {numPages} {t("viewer.pages")}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
