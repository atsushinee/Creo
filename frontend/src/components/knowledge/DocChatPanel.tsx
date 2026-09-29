import { ChatMessages } from "@/components/chat/ChatMessages";
import { Composer } from "@/components/chat/Composer";
import { useDocChat } from "@/hooks/useDocChat";
import { useI18n } from "@/hooks/useI18n";
import type { KbDocumentInfo } from "@/types/knowledgeBase";

interface DocChatPanelProps {
  kbId: string;
  doc: KbDocumentInfo;
}

/** Middle column: chat bound to one document (doc-scoped agent, ADR-0004). */
export function DocChatPanel({ kbId, doc }: DocChatPanelProps) {
  const { t } = useI18n();
  const chat = useDocChat(kbId, doc);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 border-b px-4 py-3">
        <p className="text-[11.5px] text-muted-foreground">{t("doc.chatLabel")}</p>
        <h1 className="truncate text-[14px] font-semibold" title={doc.filename}>
          {doc.filename}
        </h1>
        <p className="text-[11.5px] text-muted-foreground">{t("doc.chatScopeNote")}</p>
      </div>

      {chat.messages.length > 0 && (
        <ChatMessages messages={chat.messages} isStreaming={chat.isStreaming} />
      )}
      {chat.messages.length === 0 && (
        <div className="flex min-h-0 flex-1 items-center justify-center px-6">
          <p className="text-center text-[12.5px] leading-relaxed text-muted-foreground">
            {t("doc.chatEmpty")}
          </p>
        </div>
      )}

      {chat.error && <p className="shrink-0 px-4 pb-2 text-[12px] text-error">{chat.error}</p>}
      <Composer
        isBusy={chat.isBusy}
        streaming={chat.isStreaming}
        onSend={chat.sendMessage}
        onStop={chat.stop}
      />
    </div>
  );
}
