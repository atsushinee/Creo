import { create } from "zustand";

import { localId, nowIso } from "@/lib/utils";
import type {
  AgentEvent,
  ChatMessage,
  HistoryMessage,
  MessagePart,
  SessionInfo,
  ToolInvocation,
} from "@/types/agent";

export interface AgentState {
  sessions: SessionInfo[];
  currentSessionId: string | null;
  messages: Record<string, ChatMessage[]>;
  streamingSessionId: string | null;
  activeRunId: string | null;
  error: string | null;

  setCurrentSession: (sessionId: string) => void;
  newChat: () => string;
  setSessions: (sessions: SessionInfo[]) => void;
  upsertSession: (session: SessionInfo) => void;
  removeSession: (sessionId: string) => void;
  addUserMessage: (sessionId: string, text: string) => void;
  setMessages: (sessionId: string, messages: ChatMessage[]) => void;
  applyAgentEvent: (sessionId: string, event: AgentEvent) => void;
  endStreaming: (sessionId: string) => void;
  setError: (error: string | null) => void;
}

/**
 * Pure event reducer — the only place that turns Agent Events into UI state.
 * Exported for unit tests (see src/stores/agentStore.test.ts).
 */
export function applyAgentEvent(state: AgentState, sessionId: string, event: AgentEvent): AgentState {
  switch (event.type) {
    case "run_started":
      return {
        ...state,
        streamingSessionId: sessionId,
        activeRunId: event.runId,
        messages: {
          ...state.messages,
          [sessionId]: state.messages[sessionId] ?? [],
        },
      };

    case "message_start": {
      const existing = state.messages[sessionId] ?? [];
      if (existing.some((message) => message.id === event.messageId)) {
        return state;
      }
      const message: ChatMessage = {
        id: event.messageId,
        role: "assistant",
        content: "",
        parts: [],
        status: "streaming",
        createdAt: nowIso(),
      };
      return withMessages(state, sessionId, [...existing, message]);
    }

    case "message_delta":
      return mapMessage(state, sessionId, event.messageId, (message) => {
        const parts = appendTextPart(message.parts, event.content);
        return { ...message, content: message.content + event.content, parts };
      });

    case "message_end":
      return mapMessage(state, sessionId, event.messageId, (message) =>
        message.status === "streaming" ? { ...message, status: "complete" } : message,
      );

    case "tool_start":
      return attachToolInvocation(state, sessionId, {
        toolCallId: event.toolCallId,
        toolName: event.toolName,
        args: event.args,
        status: "running",
      });

    case "tool_result":
      return resolveToolInvocation(state, sessionId, event.toolCallId, event.result, event.isError === true);

    case "error":
      return {
        ...finalizeStreamingMessages({ ...state, error: event.message }),
      };

    case "run_finished": {
      if (state.activeRunId && state.activeRunId !== event.runId) {
        return state;
      }
      return {
        ...finalizeStreamingMessages(state),
        streamingSessionId: null,
        activeRunId: null,
      };
    }

    default:
      return state;
  }
}

function withMessages(state: AgentState, sessionId: string, messages: ChatMessage[]): AgentState {
  return { ...state, messages: { ...state.messages, [sessionId]: messages } };
}

function mapMessage(
  state: AgentState,
  sessionId: string,
  messageId: string,
  mapper: (message: ChatMessage) => ChatMessage,
): AgentState {
  const messages = state.messages[sessionId];
  if (!messages?.some((message) => message.id === messageId)) {
    return state;
  }
  return withMessages(
    state,
    sessionId,
    messages.map((message) => (message.id === messageId ? mapper(message) : message)),
  );
}

function appendTextPart(parts: MessagePart[], delta: string): MessagePart[] {
  const last = parts[parts.length - 1];
  if (last?.kind === "text") {
    return [...parts.slice(0, -1), { kind: "text", text: last.text + delta }];
  }
  return [...parts, { kind: "text", text: delta }];
}

function attachToolInvocation(state: AgentState, sessionId: string, tool: ToolInvocation): AgentState {
  const messages = state.messages[sessionId] ?? [];
  if (messages.some((message) => message.parts.some((part) => part.kind === "tool" && part.tool.toolCallId === tool.toolCallId))) {
    return state;
  }

  const last = messages[messages.length - 1];
  if (last?.role === "assistant" && last.status === "streaming") {
    return withMessages(state, sessionId, [
      ...messages.slice(0, -1),
      { ...last, parts: [...last.parts, { kind: "tool", tool }] },
    ]);
  }

  // Model called a tool before streaming any text: create a holder message.
  const holder: ChatMessage = {
    id: localId("assistant"),
    role: "assistant",
    content: "",
    parts: [{ kind: "tool", tool }],
    status: "streaming",
    createdAt: nowIso(),
  };
  return withMessages(state, sessionId, [...messages, holder]);
}

function resolveToolInvocation(
  state: AgentState,
  sessionId: string,
  toolCallId: string,
  result: unknown,
  isError: boolean,
): AgentState {
  const messages = state.messages[sessionId];
  if (!messages) {
    return state;
  }
  return withMessages(
    state,
    sessionId,
    messages.map((message) => ({
      ...message,
      parts: message.parts.map((part) => {
        if (part.kind !== "tool" || part.tool.toolCallId !== toolCallId) {
          return part;
        }
        return {
          kind: "tool",
          tool: { ...part.tool, result, status: isError ? ("error" as const) : ("success" as const) },
        };
      }),
    })),
  );
}

function finalizeStreamingMessages(state: AgentState): AgentState {
  const sessionId = state.streamingSessionId;
  if (!sessionId) {
    return state;
  }
  const messages = state.messages[sessionId];
  if (!messages?.some((message) => message.status === "streaming")) {
    return state;
  }
  return withMessages(
    state,
    sessionId,
    messages.map((message) =>
      message.status === "streaming" ? { ...message, status: "complete" } : message,
    ),
  );
}

export function historyToMessages(history: HistoryMessage[]): ChatMessage[] {
  return history.map((entry) => {
    const createdAt = nowIso();
    if (entry.role === "user") {
      return {
        id: entry.id,
        role: "user",
        content: entry.content,
        parts: [],
        status: "complete",
        createdAt,
      } satisfies ChatMessage;
    }
    const parts: MessagePart[] = [];
    if (entry.content) {
      parts.push({ kind: "text", text: entry.content });
    }
    for (const tool of entry.tools) {
      parts.push({
        kind: "tool",
        tool: {
          toolCallId: tool.toolCallId,
          toolName: tool.toolName,
          args: tool.args,
          result: tool.result,
          status: tool.isError ? "error" : "success",
        },
      });
    }
    return {
      id: entry.id,
      role: "assistant",
      content: entry.content,
      parts,
      status: "complete",
      createdAt,
    } satisfies ChatMessage;
  });
}

export function deriveTitle(text: string): string {
  const collapsed = text.replace(/\s+/g, " ").trim();
  if (collapsed.length <= 48) {
    return collapsed || "New chat";
  }
  return `${collapsed.slice(0, 47).trimEnd()}…`;
}

export const useAgentStore = create<AgentState>()((set) => ({
  sessions: [],
  currentSessionId: null,
  messages: {},
  streamingSessionId: null,
  activeRunId: null,
  error: null,

  setCurrentSession: (sessionId) => set({ currentSessionId: sessionId }),

  newChat: () => {
    const sessionId = localId("session");
    set((state) => ({
      currentSessionId: sessionId,
      messages: { ...state.messages, [sessionId]: [] },
      error: null,
    }));
    return sessionId;
  },

  setSessions: (sessions) => set({ sessions }),

  upsertSession: (session) =>
    set((state) => {
      const existing = state.sessions.find((candidate) => candidate.id === session.id);
      const sessions = existing
        ? state.sessions.map((candidate) => (candidate.id === session.id ? session : candidate))
        : [session, ...state.sessions];
      return { sessions };
    }),

  removeSession: (sessionId) =>
    set((state) => {
      const messages = { ...state.messages };
      delete messages[sessionId];
      const sessions = state.sessions.filter((session) => session.id !== sessionId);
      const currentSessionId =
        state.currentSessionId === sessionId ? null : state.currentSessionId;
      return { sessions, messages, currentSessionId };
    }),

  addUserMessage: (sessionId, text) =>
    set((state) => {
      const message: ChatMessage = {
        id: localId("user"),
        role: "user",
        content: text,
        parts: [],
        status: "complete",
        createdAt: nowIso(),
      };
      return withMessages(state, sessionId, [...(state.messages[sessionId] ?? []), message]);
    }),

  setMessages: (sessionId, messages) => set((state) => withMessages(state, sessionId, messages)),

  applyAgentEvent: (sessionId, event) =>
    set((state) => applyAgentEvent(state, sessionId, event)),

  endStreaming: (sessionId) =>
    set((state) => {
      if (state.streamingSessionId !== sessionId) {
        return state;
      }
      return {
        ...finalizeStreamingMessages(state),
        streamingSessionId: null,
        activeRunId: null,
      };
    }),

  setError: (error) => set({ error }),
}));
