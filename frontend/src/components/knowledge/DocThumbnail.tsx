import { useEffect, useRef } from "react";

import { pdfjs } from "@/lib/pdfjs";

/** Page-1 cover rendered client-side with pdf.js (no backend cost). */
export function DocThumbnail({ url, width = 240 }: { url: string; width?: number }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
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
        // Covers are best-effort (e.g. dev StrictMode aborts the first mount);
        // keep the placeholder and surface the reason for diagnosis.
        if (!cancelled) {
          console.warn("[DocThumbnail] cover render failed:", coverError);
        }
      }
    })();
    return () => {
      cancelled = true;
      void loadingTask.destroy();
    };
  }, [url, width]);

  return (
    <div
      className="flex items-center justify-center overflow-hidden rounded border bg-white"
      style={{ width, height: Math.round(width * 1.414) }}
    >
      <canvas ref={canvasRef} className="block" />
    </div>
  );
}
