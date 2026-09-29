import { describe, expect, it } from "vitest";

import { applyAgentEvent, deriveTitle, historyToMessages, type AgentState } from "@/stores/agentStore";
import type { AgentEvent, ChatMessage } from "@/types/agent";

function initialState(sessionId: string): AgentState {
  return {
    sessions: [],
    currentSessionId: sessionId,
    messages: { [sessionId]: [] },
    streamingSessionId: null,
    activeRunId: null,
    error: null,
    setCurrentSession: () => {},
    newChat: () => sessionId,
    setSessions: () => {},
    upsertSession: () => {},
    removeSession: () => {},
    addUserMessage: () => {},
    setMessages: () => {},
    applyAgentEvent: () => {},
    endStreaming: () => {},
    setError: () => {},
  };
}

function feed(state: AgentState, sessionId: string, events: AgentEvent[]): AgentState {
  return events.reduce((current, event) => applyAgentEvent(current, sessionId, event), state);
}

function messagesOf(state: AgentState, sessionId: string): ChatMessage[] {
  return state.messages[sessionId] ?? [];
}

describe("applyAgentEvent", () => {
  const sessionId = "s1";

  it("thinking deltas accumulate at the head of the streaming message", () => {
    // Real backend order: message_start fires (message opened), then thinking
    // deltas, then text deltas — all into one streaming message.
    const state = feed(initialState(sessionId), sessionId, [
      { type: "run_started", runId: "r1" },
      { type: "message_start", messageId: "m1" },
      { type: "thinking_delta", content: "先分析问题。" },
      { type: "thinking_delta", content: "再分步计算。" },
      { type: "message_delta", messageId: "m1", content: "答案是 56088。" },
      { type: "message_end", messageId: "m1" },
      { type: "run_finished", runId: "r1" },
    ]);

    const messages = messagesOf(state, sessionId);
    expect(messages).toHaveLength(1);
    expect(messages[0].parts[0]).toEqual({
      kind: "thinking",
      text: "先分析问题。再分步计算。",
    });
    expect(messages[0].content).toBe("答案是 56088。");
    expect(messages[0].parts[1]).toEqual({ kind: "text", text: "答案是 56088。" });
  });

  it("full tool call flow produces text, tool and final answer", () => {
    const state = feed(initialState(sessionId), sessionId, [
      { type: "run_started", runId: "r1" },
      { type: "message_start", messageId: "m1" },
      { type: "message_delta", messageId: "m1", content: "Let me compute. " },
      { type: "message_end", messageId: "m1" },
      { type: "tool_start", toolCallId: "c1", toolName: "calculator", args: { expression: "123*456" } },
      { type: "tool_result", toolCallId: "c1", result: "56088" },
      { type: "message_start", messageId: "m2" },
      { type: "message_delta", messageId: "m2", content: "The result is 56088." },
      { type: "message_end", messageId: "m2" },
      { type: "run_finished", runId: "r1" },
    ]);

    const messages = messagesOf(state, sessionId);
    expect(state.activeRunId).toBeNull();
    expect(state.streamingSessionId).toBeNull();

    const toolMessage = messages[1];
    const toolPart = toolMessage.parts[0];
    expect(toolPart.kind === "tool" && toolPart.tool).toMatchObject({
      toolCallId: "c1",
      toolName: "calculator",
      args: { expression: "123*456" },
      result: "56088",
      status: "success",
    });

    const final = messages[2];
    expect(final.content).toBe("The result is 56088.");
    expect(final.status).toBe("complete");
  });

  it("keeps a streaming text message open across deltas", () => {
    const state = feed(initialState(sessionId), sessionId, [
      { type: "run_started", runId: "r1" },
      { type: "message_start", messageId: "m1" },
      { type: "message_delta", messageId: "m1", content: "Hel" },
      { type: "message_delta", messageId: "m1", content: "lo" },
    ]);

    const messages = messagesOf(state, sessionId);
    expect(messages).toHaveLength(1);
    expect(messages[0].content).toBe("Hello");
    expect(messages[0].status).toBe("streaming");
    expect(messages[0].parts).toEqual([{ kind: "text", text: "Hello" }]);
  });

  it("creates a tool holder when a tool call arrives before any text", () => {
    const state = feed(initialState(sessionId), sessionId, [
      { type: "run_started", runId: "r1" },
      { type: "tool_start", toolCallId: "c1", toolName: "calculator", args: {} },
    ]);

    const messages = messagesOf(state, sessionId);
    expect(messages).toHaveLength(1);
    expect(messages[0].role).toBe("assistant");
    expect(messages[0].parts[0].kind).toBe("tool");
  });

  it("marks a running tool as error via isError", () => {
    let state = feed(initialState(sessionId), sessionId, [
      { type: "run_started", runId: "r1" },
      { type: "tool_start", toolCallId: "c1", toolName: "calculator", args: { expression: "1/0" } },
      { type: "tool_result", toolCallId: "c1", result: "ZeroDivisionError: division by zero", isError: true },
    ]);

    const toolPart = messagesOf(state, sessionId)[0].parts[0];
    expect(toolPart.kind === "tool" && toolPart.tool.status).toBe("error");

    state = applyAgentEvent(state, sessionId, { type: "run_finished", runId: "r1" });
    expect(state.streamingSessionId).toBeNull();
  });

  it("surfaces error events and finalizes streaming messages", () => {
    const state = feed(initialState(sessionId), sessionId, [
      { type: "run_started", runId: "r1" },
      { type: "message_start", messageId: "m1" },
      { type: "message_delta", messageId: "m1", content: "partial" },
      { type: "error", message: "boom" },
      { type: "run_finished", runId: "r1" },
    ]);

    expect(state.error).toBe("boom");
    expect(messagesOf(state, sessionId)[0].status).toBe("complete");
    expect(state.streamingSessionId).toBeNull();
  });

  it("ignores tool results for unknown tool calls", () => {
    const state = feed(initialState(sessionId), sessionId, [
      { type: "run_started", runId: "r1" },
      { type: "tool_result", toolCallId: "missing", result: "x" },
    ]);

    expect(messagesOf(state, sessionId)).toHaveLength(0);
  });
});

describe("historyToMessages", () => {
  it("maps backend history into UI messages", () => {
    const messages = historyToMessages([
      { id: "1", role: "user", content: "hi", tools: [] },
      {
        id: "2",
        role: "assistant",
        content: "done",
        tools: [
          {
            toolCallId: "c1",
            toolName: "calculator",
            args: { expression: "2+2" },
            result: "4",
            isError: false,
          },
        ],
      },
    ]);

    expect(messages).toHaveLength(2);
    expect(messages[0]).toMatchObject({ role: "user", content: "hi" });
    expect(messages[1].parts).toHaveLength(2);
    const toolPart = messages[1].parts.find((part) => part.kind === "tool");
    expect(toolPart && toolPart.kind === "tool" && toolPart.tool.status).toBe("success");
  });
});

describe("deriveTitle", () => {
  it("collapses whitespace and truncates long messages", () => {
    expect(deriveTitle("  计算   123 * 456 ")).toBe("计算 123 * 456");
    expect(deriveTitle("x".repeat(100))).toHaveLength(48);
    expect(deriveTitle("x".repeat(100)).endsWith("…")).toBe(true);
    expect(deriveTitle("")).toBe("New chat");
  });
});
