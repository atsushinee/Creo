import { forwardRef, useImperativeHandle, useEffect, useRef, useState } from "react";
import { ChevronFirst, ChevronLast, Scan } from "lucide-react";

import { pdfjs } from "@/lib/pdfjs";
import { useI18n } from "@/hooks/useI18n";
import type { PDFDocumentProxy } from "pdfjs-dist";
import type { ElementCoordinates, ParseElementInfo } from "@/types/knowledgeBase";
import { cn } from "@/lib/utils";

interface ViewerPageProps {
  doc: PDFDocumentProxy;
  pageNumber: number;
  width: number;
  showBoxes: boolean;
  boxes: ParseElementInfo[];
  registerRef: (element: HTMLDivElement | null) => void;
}

/** Unstructured element types → design-token strokes (DESIGN.md §2). */
const TYPE_STROKE: Record<string, string> = {
  Title: "var(--primary)",
  NarrativeText: "var(--success)",
  Table: "var(--warning)",
  ListItem: "var(--error)",
  Formula: "var(--primary)",
  Header: "var(--muted-foreground)",
  Footer: "var(--muted-foreground)",
  PageNumber: "var(--muted-foreground)",
};

function strokeFor(type: string): string {
  return TYPE_STROKE[type] ?? "var(--primary)";
}

/** Map layout-space coordinates onto the rendered canvas pixel rect. */
function boxRect(
  coordinates: ElementCoordinates,
  canvasWidth: number,
  canvasHeight: number,
): { x: number; y: number; w: number; h: number } | null {
  const { points, system } = coordinates;
  if (!points?.length || !system) {
    return null;
  }
  // Both spellings appear in the wild; normalize defensively.
  const layoutWidth = system.layout_width ?? system.width ?? 0;
  const layoutHeight = system.layout_height ?? system.height ?? 0;
  if (!layoutWidth || !layoutHeight) {
    return null;
  }
  const xs = points.map((point) => point[0]);
  const ys = points.map((point) => point[1]);
  const x = (Math.min(...xs) / layoutWidth) * canvasWidth;
  const y = (Math.min(...ys) / layoutHeight) * canvasHeight;
  const w = ((Math.max(...xs) - Math.min(...xs)) / layoutWidth) * canvasWidth;
  const h = ((Math.max(...ys) - Math.min(...ys)) / layoutHeight) * canvasHeight;
  return { x, y, w: Math.max(w, 2), h: Math.max(h, 2) };
}

function BoxesOverlay({
  boxes,
  canvasWidth,
  canvasHeight,
}: {
  boxes: ParseElementInfo[];
  canvasWidth: number;
  canvasHeight: number;
}) {
  return (
    <svg
      className="absolute inset-0"
      width={canvasWidth}
      height={canvasHeight}
      viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
    >
      {boxes.map((element, index) => {
        const coordinates = element.coordinates;
        if (!coordinates) {
          return null;
        }
        const rect = boxRect(coordinates, canvasWidth, canvasHeight);
        if (!rect) {
          return null;
        }
        return (
          <rect
            key={index}
            x={rect.x}
            y={rect.y}
            width={rect.w}
            height={rect.h}
            fill="transparent"
            stroke={strokeFor(element.type)}
            strokeWidth={1.5}
            style={{ pointerEvents: "auto" }}
          >
            <title>{`${element.type}: ${element.text.slice(0, 160)}`}</title>
          </rect>
        );
      })}
    </svg>
  );
}

/** One page, rendered lazily the first time it scrolls near the viewport. */
function ViewerPage({
  doc,
  pageNumber,
  width,
  showBoxes,
  boxes,
  registerRef,
}: ViewerPageProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [canvasSize, setCanvasSize] = useState<{ w: number; h: number } | null>(null);
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
        setCanvasSize({ w: viewport.width, h: viewport.height });
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

  const pageBoxes = boxes.filter((element) => element.pageNumber === pageNumber);

  return (
    <div
      ref={(element) => {
        containerRef.current = element;
        registerRef(element);
      }}
      className="mb-3"
    >
      <div className="relative mx-auto w-fit">
        <canvas
          ref={canvasRef}
          className={`block rounded-md border bg-white shadow-sm ${rendered ? "" : "hidden"}`}
        />
        {rendered && showBoxes && canvasSize && (
          <BoxesOverlay
            boxes={pageBoxes}
            canvasWidth={canvasSize.w}
            canvasHeight={canvasSize.h}
          />
        )}
      </div>
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

interface ViewerPageProps {
  doc: PDFDocumentProxy;
  pageNumber: number;
  width: number;
  showBoxes: boolean;
  boxes: ParseElementInfo[];
  registerRef: (element: HTMLDivElement | null) => void;
}

function isAbortLike(error: unknown): boolean {
  const text = error instanceof Error ? `${error.name} ${error.message}` : String(error);
  return (
    /abort/i.test(text) || (error instanceof Error && error.name === "RenderingCancelledException")
  );
}

/** Imperative API for sibling components (e.g. citation → page jumps). */
export interface PdfViewerHandle {
  scrollToPage: (page: number) => void;
}

/**
 * Continuous-scroll PDF viewer for the right column. Remount via key={docId}
 * when the document changes; pages render lazily as they approach the view.
 * With parse elements (with coordinates) the pages gain the Unstructured-style
 * element-box overlay, color-coded by element type.
 */
export const PdfViewer = forwardRef<
  PdfViewerHandle,
  { url: string; title: string; elements?: ParseElementInfo[] }
>(function PdfViewer({ url, title, elements = [] }, ref) {
  const { t } = useI18n();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const pageRefs = useRef<Array<HTMLDivElement | null>>([]);
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [width, setWidth] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageInput, setPageInput] = useState("1");
  const [showBoxes, setShowBoxes] = useState(false);
  const numPages = doc?.numPages ?? 0;
  const hasCoordinates = elements.some((element) => element.coordinates);

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

  useImperativeHandle(ref, () => ({ scrollToPage }));

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b px-4 py-3">
        <p className="min-w-0 flex-1 truncate text-[13px] font-medium" title={title}>
          {title}
        </p>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            aria-label={t("viewer.boxes")}
            title={hasCoordinates ? t("viewer.boxes") : t("viewer.boxesUnavailable")}
            disabled={!hasCoordinates}
            onClick={() => setShowBoxes((value) => !value)}
            className={cn(
              "flex size-7 items-center justify-center rounded-md transition-colors",
              showBoxes
                ? "bg-primary text-white"
                : "text-muted-foreground hover:bg-surface hover:text-foreground",
              !hasCoordinates && "cursor-not-allowed opacity-40",
            )}
          >
            <Scan className="size-4" />
          </button>
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
                showBoxes={showBoxes}
                boxes={elements}
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
});
