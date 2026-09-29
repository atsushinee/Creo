import { useEffect, useRef } from "react";

import { pdfjs } from "@/lib/pdfjs";

/** Page-1 cover rendered client-side with pdf.js (no backend cost). */
export function DocThumbnail({ url }: { url: string }) {
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
        const viewport = page.getViewport({ scale: 240 / base.width });
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        await page.render({ canvas, viewport }).promise;
      } catch {
        // covers are best-effort; the card falls back to the plain background
      }
    })();
    return () => {
      cancelled = true;
      void loadingTask.destroy();
    };
  }, [url]);

  return (
    <div className="flex h-32 items-center justify-center overflow-hidden rounded-md border-b border-border bg-white">
      <canvas ref={canvasRef} className="block" />
    </div>
  );
}
