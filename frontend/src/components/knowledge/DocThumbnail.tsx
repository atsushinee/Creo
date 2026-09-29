import { useEffect, useRef, useState } from "react";

import { pdfjs } from "@/lib/pdfjs";

/**
 * Page-1 cover rendered client-side with pdf.js (no backend cost). Renders
 * lazily (when scrolled into view) at the container's full width; failures
 * are surfaced in the console and leave a neutral placeholder.
 */
export function DocThumbnail({ url }: { url: string }) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [visible, setVisible] = useState(false);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const element = wrapRef.current;
    if (!element) {
      return;
    }
    const resizeObserver = new ResizeObserver(() =>
      setWidth(Math.max(0, element.clientWidth)),
    );
    resizeObserver.observe(element);
    const intersectionObserver = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setVisible(true);
        intersectionObserver.disconnect();
      }
    });
    intersectionObserver.observe(element);
    return () => {
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
    };
  }, []);

  useEffect(() => {
    if (!visible || width <= 0) {
      return;
    }
    let cancelled = false;
    const loadingTask = pdfjs.getDocument({ url });
    (async () => {
      try {
        const doc = await loadingTask.promise;
        const page = await doc.getPage(1);
        if (cancelled) {
          return;
        }
        const canvas = canvasRef.current;
        if (!canvas) {
          return;
        }
        const base = page.getViewport({ scale: 1 });
        const viewport = page.getViewport({ scale: width / base.width });
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        await page.render({ canvas, viewport }).promise;
      } catch (coverError) {
        // Covers are best-effort (dev StrictMode aborts the first mount on
        // purpose); keep the placeholder and surface real failures.
        if (
          !cancelled &&
          !(coverError instanceof Error && coverError.name === "RenderingCancelledException") &&
          !/abort/i.test(String(coverError))
        ) {
          console.warn("[DocThumbnail] cover render failed:", coverError);
        }
      }
    })();
    return () => {
      cancelled = true;
      void loadingTask.destroy();
    };
  }, [url, visible, width]);

  return (
    <div
      ref={wrapRef}
      className="w-full overflow-hidden bg-white"
      style={{ height: width > 0 ? Math.round(width * 1.414) : 140 }}
    >
      <canvas ref={canvasRef} className="block h-auto w-full" />
    </div>
  );
}
