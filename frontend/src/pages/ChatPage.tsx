import { useState } from "react";

import { AppHeader } from "@/components/layout/AppHeader";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { ChatMessages } from "@/components/chat/ChatMessages";
import { Composer } from "@/components/chat/Composer";
import { EmptyState } from "@/components/chat/EmptyState";
import { ErrorBanner } from "@/components/chat/ErrorBanner";
import { RunTraceDialog } from "@/components/chat/RunTraceDialog";
import { useTheme } from "@/hooks/useTheme";
import { useI18n } from "@/hooks/useI18n";
import { useAgent } from "@/hooks/useAgent";

export default function ChatPage() {
  const { theme, toggleTheme } = useTheme();
  const { t } = useI18n();
  const agent = useAgent();
  const [traceSessionId, setTraceSessionId] = useState<string | null>(null);

  const hasConversation = agent.currentMessages.length > 0;

  return (
    <div className="flex h-dvh flex-col bg-background text-foreground">
      <AppHeader theme={theme} onToggleTheme={toggleTheme} />

      <div className="flex min-h-0 flex-1">
        <AppSidebar
          sessions={agent.sessions}
          currentSessionId={agent.currentSessionId}
          onSelect={(sessionId) => void agent.selectSession(sessionId)}
          onNewChat={agent.startNewChat}
          onDelete={(sessionId) => void agent.deleteSession(sessionId)}
          onTrace={(sessionId) => setTraceSessionId(sessionId)}
        />

        <main className="flex min-w-0 flex-1 flex-col">
          {hasConversation ? (
            <ChatMessages messages={agent.currentMessages} isStreaming={agent.isStreaming} />
          ) : (
            <EmptyState onSend={(text) => void agent.sendMessage(text)} />
          )}

          {agent.error && <ErrorBanner error={agent.error} onDismiss={agent.dismissError} />}

          <Composer
            isBusy={agent.isBusy}
            streaming={agent.isStreaming && agent.currentSessionId === agent.streamingSessionId}
            onSend={(text) => void agent.sendMessage(text)}
            onStop={agent.stop}
          />
        </main>
      </div>

      {traceSessionId && (
        <RunTraceDialog
          title={agent.sessions.find((s) => s.id === traceSessionId)?.title ?? t("trace.title")}
          load={() => agent.loadSessionTrace(traceSessionId)}
          onClose={() => setTraceSessionId(null)}
        />
      )}
    </div>
  );
}
