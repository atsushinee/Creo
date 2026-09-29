import { useCallback, useEffect } from "react";

import {
  deleteSession as deleteSessionApi,
  getSessionMessages,
  getSessionTrace,
  listSessions,
  streamChat,
} from "@/services/agentApi";
import { deriveTitle, historyToMessages, useAgentStore } from "@/stores/agentStore";
import { isAbortError, useSse } from "@/hooks/useSSE";
import type { TraceEntry } from "@/types/agent";

function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

/**
 * Domain hook wiring the Agent API to the store: send messages, consume
 * events, manage sessions. Components only talk to this hook.
 */
export function useAgent() {
  const sessions = useAgentStore((state) => state.sessions);
  const currentSessionId = useAgentStore((state) => state.currentSessionId);
  const messagesBySession = useAgentStore((state) => state.messages);
  const streamingSessionId = useAgentStore((state) => state.streamingSessionId);
  const error = useAgentStore((state) => state.error);

  const setCurrentSession = useAgentStore((state) => state.setCurrentSession);
  const newChat = useAgentStore((state) => state.newChat);
  const setSessions = useAgentStore((state) => state.setSessions);
  const upsertSession = useAgentStore((state) => state.upsertSession);
  const removeSession = useAgentStore((state) => state.removeSession);
  const addUserMessage = useAgentStore((state) => state.addUserMessage);
  const setMessages = useAgentStore((state) => state.setMessages);
  const applyAgentEvent = useAgentStore((state) => state.applyAgentEvent);
  const endStreaming = useAgentStore((state) => state.endStreaming);
  const setError = useAgentStore((state) => state.setError);

  const { isStreaming, run, stop } = useSse();

  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await listSessions());
    } catch {
      // Sidebar refresh is best-effort; the next send will retry.
    }
  }, [setSessions]);

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) {
        return;
      }
      setError(null);

      let sessionId = currentSessionId;
      if (!sessionId) {
        sessionId = newChat();
      }
      setCurrentSession(sessionId);
      addUserMessage(sessionId, trimmed);

      // Show the session in the sidebar immediately; the server refresh
      // after the run reconciles title/timestamps.
      upsertSession({
        id: sessionId,
        title: deriveTitle(trimmed),
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      });

      try {
        await run(async (signal) => {
          await streamChat({
            sessionId,
            message: trimmed,
            signal,
            onEvent: (event) => applyAgentEvent(sessionId, event),
          });
        });
      } catch (streamError) {
        if (!isAbortError(streamError)) {
          setError(errorMessage(streamError));
        }
      } finally {
        endStreaming(sessionId);
        void refreshSessions();
      }
    },
    [
      applyAgentEvent,
      currentSessionId,
      endStreaming,
      newChat,
      addUserMessage,
      refreshSessions,
      run,
      setCurrentSession,
      setError,
      upsertSession,
    ],
  );

  const selectSession = useCallback(
    async (sessionId: string) => {
      setCurrentSession(sessionId);
      setError(null);
      if (messagesBySession[sessionId] === undefined) {
        try {
          const history = await getSessionMessages(sessionId);
          setMessages(sessionId, historyToMessages(history));
        } catch (loadError) {
          setMessages(sessionId, []);
          setError(errorMessage(loadError));
        }
      }
    },
    [messagesBySession, setCurrentSession, setMessages, setError],
  );

  const deleteSession = useCallback(
    async (sessionId: string) => {
      try {
        await deleteSessionApi(sessionId);
      } catch (deleteError) {
        setError(errorMessage(deleteError));
        return;
      }
      removeSession(sessionId);
      void refreshSessions();
    },
    [removeSession, refreshSessions, setError],
  );

  const startNewChat = useCallback(() => {
    setError(null);
    newChat();
  }, [newChat, setError]);

  const loadSessionTrace = useCallback((sessionId: string): Promise<TraceEntry[]> => {
    return getSessionTrace(sessionId);
  }, []);

  const currentMessages = currentSessionId ? (messagesBySession[currentSessionId] ?? []) : [];
  const isBusy = streamingSessionId !== null;

  return {
    sessions,
    currentSessionId,
    currentMessages,
    streamingSessionId,
    isStreaming,
    isBusy,
    error,
    sendMessage,
    selectSession,
    startNewChat,
    deleteSession,
    stop,
    loadSessionTrace,
    dismissError: () => setError(null),
  };
}
