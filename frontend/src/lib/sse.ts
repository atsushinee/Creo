/**
 * Minimal streaming SSE frame parser (ADR-0003).
 *
 * Pure and testable: feed decoded chunks in any size, get complete frames out.
 * Handles CRLF, multi-line data, and comment/keep-alive lines.
 */

export interface SseFrame {
  event: string;
  data: string;
}

export interface SseParser {
  push(chunk: string): void;
}

const FRAME_SEPARATOR = "\n\n";

function parseFrame(raw: string): SseFrame | null {
  let event = "message";
  const dataLines: string[] = [];

  for (const line of raw.split("\n")) {
    if (line === "" || line.startsWith(":")) {
      continue;
    }
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).replace(/^ /, ""));
    }
    // Unknown fields (id:, retry:, ...) are intentionally ignored.
  }

  if (dataLines.length === 0) {
    return null;
  }
  return { event, data: dataLines.join("\n") };
}

export function createSseParser(onFrame: (frame: SseFrame) => void): SseParser {
  let buffer = "";

  return {
    push(chunk: string): void {
      buffer = (buffer + chunk).replaceAll("\r\n", "\n");
      let separatorIndex = buffer.indexOf(FRAME_SEPARATOR);
      while (separatorIndex !== -1) {
        const raw = buffer.slice(0, separatorIndex);
        buffer = buffer.slice(separatorIndex + FRAME_SEPARATOR.length);
        const frame = parseFrame(raw);
        if (frame) {
          onFrame(frame);
        }
        separatorIndex = buffer.indexOf(FRAME_SEPARATOR);
      }
    },
  };
}
