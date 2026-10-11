import { useEffect, useRef } from "react";

import { MessageItem } from "@/components/chat/MessageItem";
import { AgentStatus } from "@/components/agent/AgentStatus";
import type { ChatMessage } from "@/types/agent";

interface ChatMessagesProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  /** When provided, `[N]` citation markers jump to the cited page in the preview. */
  onCitationClick?: (page: number) => void;
}

export function ChatMessages({ messages, isStreaming, onCitationClick }: ChatMessagesProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);

  useEffect(() => {
    const element = scrollRef.current;
    if (element && pinnedRef.current) {
      element.scrollTop = element.scrollHeight;
    }
  }, [messages]);

  const handleScroll = () => {
    const element = scrollRef.current;
    if (!element) {
      return;
    }
    pinnedRef.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
  };

  const lastMessage = messages[messages.length - 1];
  const waitingForModel = isStreaming && lastMessage?.role === "user";

  return (
    <div ref={scrollRef} onScroll={handleScroll} className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-5 px-4 py-6">
        {messages.map((message) => (
          <MessageItem key={message.id} message={message} onCitationClick={onCitationClick} />
        ))}
        {waitingForModel && <AgentStatus />}
      </div>
    </div>
  );
}
