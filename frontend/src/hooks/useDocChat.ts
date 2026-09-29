import { useCallback, useEffect, useMemo, useState } from "react";

import { getSessionMessages, streamChat } from "@/services/agentApi";
import { historyToMessages } from "@/stores/agentStore";
import { isAbortError, useSse } from "@/hooks/useSSE";
import type { AgentEvent, ChatMessage } from "@/types/agent";
import type { KbDocumentInfo } from "@/types/knowledgeBase";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** Fold one protocol event into the in-flight assistant message. */
function applyDocEvent(message: ChatMessage, event: AgentEvent): ChatMessage {
  switch (event.type) {
    case "message_delta": {
      const content = message.content + event.content;
      return { ...message, content, parts: [{ kind: "text", text: content }] };
    }
    case "tool_start":
      return {
        ...message,
        parts: [
          ...message.parts,
          {
            kind: "tool",
            tool: {
              toolCallId: event.toolCallId,
              toolName: event.toolName,
              args: event.args,
              status: "running",
            },
          },
        ],
      };
    case "tool_result":
      return {
        ...message,
        parts: message.parts.map((part) =>
          part.kind === "tool" && part.tool.toolCallId === event.toolCallId
            ? {
                ...part,
                tool: {
                  ...part.tool,
                  result: event.result,
                  status: event.isError ? "error" : "success",
                },
              }
            : part,
        ),
      };
    case "thinking_delta": {
      const parts =
        message.parts[0]?.kind === "thinking"
          ? [
              { kind: "thinking" as const, text: message.parts[0].text + event.content },
              ...message.parts.slice(1),
            ]
          : [{ kind: "thinking" as const, text: event.content }, ...message.parts];
      return { ...message, parts };
    }
    case "error":
      return { ...message, status: "error" };
    default:
      return message;
  }
}

export interface DocChat {
  messages: ChatMessage[];
  isStreaming: boolean;
  isBusy: boolean;
  error: string | null;
  sendMessage: (text: string) => void;
  stop: () => void;
  dismissError: () => void;
}

/**
 * Document-scoped chat (ADR-0004 Update 3): one stable session per document;
 * the backend binds these runs to a doc-scoped agent whose retrieval can only
 * see that document. Remount per document (keyed by doc id) resets state.
 */
export function useDocChat(kbId: string | null, doc: KbDocumentInfo | null): DocChat {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { isStreaming, run, stop } = useSse();
  const sessionId = useMemo(() => (doc ? `docchat-${doc.id}` : ""), [doc]);

  useEffect(() => {
    if (!doc || !kbId) {
      return;
    }
    let cancelled = false;
    getSessionMessages(sessionId, { kbId, docId: doc.id })
      .then((history) => {
        if (!cancelled) {
          setMessages(historyToMessages(history));
        }
      })
      .catch(() => {
        // No conversation yet (first message on this doc) — start clean.
        if (!cancelled) {
          setMessages([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [doc, kbId, sessionId]);

  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !doc || !kbId || isStreaming) {
        return;
      }
      setError(null);
      const assistantId = crypto.randomUUID();
      const now = new Date().toISOString();
      setMessages((previous) => [
        ...previous,
        {
          id: crypto.randomUUID(),
          role: "user",
          content: trimmed,
          parts: [{ kind: "text", text: trimmed }],
          status: "complete",
          createdAt: now,
        },
        {
          id: assistantId,
          role: "assistant",
          content: "",
          parts: [],
          status: "streaming",
          createdAt: now,
        },
      ]);

      void run(async (signal) => {
        try {
          await streamChat({
            sessionId,
            message: trimmed,
            signal,
            docScope: { kbId, docId: doc.id },
            onEvent: (event) =>
              setMessages((previous) =>
                previous.map((entry) =>
                  entry.id === assistantId ? applyDocEvent(entry, event) : entry,
                ),
              ),
          });
          setMessages((previous) =>
            previous.map((entry) =>
              entry.id === assistantId && entry.status === "streaming"
                ? { ...entry, status: "complete" }
                : entry,
            ),
          );
        } catch (streamError) {
          if (!isAbortError(streamError)) {
            setError(errorMessage(streamError));
          }
          setMessages((previous) =>
            previous.map((entry) =>
              entry.id === assistantId && entry.status === "streaming"
                ? { ...entry, status: "error" }
                : entry,
            ),
          );
        }
      });
    },
    [doc, kbId, isStreaming, run, sessionId],
  );

  return {
    messages,
    isStreaming,
    isBusy: isStreaming,
    error,
    sendMessage,
    stop,
    dismissError: () => setError(null),
  };
}
