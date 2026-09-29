import { memo } from "react";
import type { ChatMessage } from "@/types/agent";

import { MarkdownRenderer } from "@/components/chat/MarkdownRenderer";
import { ThinkingBlock } from "@/components/chat/ThinkingBlock";
import { AgentStatus } from "@/components/agent/AgentStatus";
import { ToolCallCard } from "@/components/tool/ToolCallCard";
import { cn } from "@/lib/utils";

function StreamingCursor() {
  return (
    <span
      aria-hidden
      className="animate-blink ml-0.5 inline-block h-[1em] w-[2px] translate-y-[0.15em] bg-primary"
    />
  );
}

function UserMessage({ message }: { message: ChatMessage }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-xl rounded-br-sm bg-surface px-3.5 py-2 whitespace-pre-wrap">
        {message.content}
      </div>
    </div>
  );
}

function AssistantMessage({ message }: { message: ChatMessage }) {
  const streaming = message.status === "streaming";

  if (message.parts.length === 0) {
    return streaming ? <AgentStatus /> : null;
  }

  const lastIndex = message.parts.length - 1;
  const lastPart = message.parts[lastIndex];
  const waitingAfterTool =
    streaming && lastPart.kind === "tool" && lastPart.tool.status !== "running";

  return (
    <div className="min-w-0">
      {message.parts.map((part, index) =>
        part.kind === "tool" ? (
          <ToolCallCard key={part.tool.toolCallId} tool={part.tool} />
        ) : part.kind === "thinking" ? (
          <ThinkingBlock key={`thinking-${index}`} text={part.text} active={streaming && index === lastIndex} />
        ) : (
          <div key={`text-${index}`} className="min-w-0">
            <MarkdownRenderer content={part.text} />
            {streaming && index === lastIndex && <StreamingCursor />}
          </div>
        ),
      )}
      {waitingAfterTool && <AgentStatus />}
    </div>
  );
}

/**
 * Memoized: during streaming only the in-flight message object gets a new
 * reference (the store updates immutably per message), so finished messages
 * skip re-render/re-parse on every token delta.
 */
export const MessageItem = memo(function MessageItem({ message }: { message: ChatMessage }) {
  return (
    <article
      className={cn(
        "animate-fade-in min-w-0",
        message.role === "assistant" && "text-[14px] leading-[1.65]",
      )}
    >
      {message.role === "user" ? <UserMessage message={message} /> : <AssistantMessage message={message} />}
    </article>
  );
});
