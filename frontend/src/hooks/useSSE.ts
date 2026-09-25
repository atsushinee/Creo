import { useCallback, useEffect, useRef, useState } from "react";

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export interface UseSseResult {
  /** True while a streamed request is in flight. */
  isStreaming: boolean;
  /** Run a streamed task with its own AbortController. */
  run: <T>(task: (signal: AbortSignal) => Promise<T>) => Promise<T | null>;
  /** Abort the in-flight task (Stop button). */
  stop: () => void;
}

/**
 * React glue for fetch-based SSE: owns the AbortController lifecycle so the
 * UI can stop a stream and unmount safely.
 */
export function useSse(): UseSseResult {
  const controllerRef = useRef<AbortController | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  const run = useCallback(async <T,>(task: (signal: AbortSignal) => Promise<T>): Promise<T | null> => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setIsStreaming(true);
    try {
      return await task(controller.signal);
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
      }
      setIsStreaming(false);
    }
  }, []);

  const stop = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
  }, []);

  useEffect(() => () => controllerRef.current?.abort(), []);

  return { isStreaming, run, stop };
}
