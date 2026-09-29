/**
 * Shared pdf.js setup (ADR-0004): configure the worker ONCE here and always
 * import pdfjs from this module — components mount in any order, so worker
 * configuration must not depend on which component loaded first.
 */

import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

export { pdfjs };
export type { PDFDocumentLoadingTask, PDFDocumentProxy, RenderTask } from "pdfjs-dist";
