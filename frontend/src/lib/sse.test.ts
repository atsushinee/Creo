import { describe, expect, it, vi } from "vitest";

import { createSseParser } from "@/lib/sse";

describe("createSseParser", () => {
  it("parses complete frames", () => {
    const onFrame = vi.fn();
    const parser = createSseParser(onFrame);

    parser.push('event: message_delta\ndata: {"content":"hi"}\n\n');

    expect(onFrame).toHaveBeenCalledWith({
      event: "message_delta",
      data: '{"content":"hi"}',
    });
  });

  it("buffers frames split across chunks", () => {
    const onFrame = vi.fn();
    const parser = createSseParser(onFrame);

    parser.push('event: run_started\ndata: {"runId"');
    expect(onFrame).not.toHaveBeenCalled();

    parser.push(':"r1"}\n');
    expect(onFrame).not.toHaveBeenCalled();

    parser.push("\nevent: run_finished\ndata: {\"runId\":\"r1\"}\n\n");
    expect(onFrame).toHaveBeenCalledTimes(2);
    expect(onFrame).toHaveBeenNthCalledWith(1, { event: "run_started", data: '{"runId":"r1"}' });
    expect(onFrame).toHaveBeenNthCalledWith(2, { event: "run_finished", data: '{"runId":"r1"}' });
  });

  it("handles CRLF separators", () => {
    const onFrame = vi.fn();
    const parser = createSseParser(onFrame);

    parser.push('event: error\ndata: {"message":"boom"}\r\n\r\n');

    expect(onFrame).toHaveBeenCalledWith({ event: "error", data: '{"message":"boom"}' });
  });

  it("ignores comment keep-alive lines and frames without data", () => {
    const onFrame = vi.fn();
    const parser = createSseParser(onFrame);

    parser.push(": keep-alive\n\n");
    parser.push("event: ping\n\n");

    expect(onFrame).not.toHaveBeenCalled();
  });

  it("joins multi-line data fields", () => {
    const onFrame = vi.fn();
    const parser = createSseParser(onFrame);

    parser.push("data: line1\ndata: line2\n\n");

    expect(onFrame).toHaveBeenCalledWith({ event: "message", data: "line1\nline2" });
  });
});
