import { memo } from "react";
import type { ChatMessage, MessagePart } from "@/types/agent";

import { MarkdownRenderer } from "@/components/chat/MarkdownRenderer";
import { ThinkingBlock } from "@/components/chat/ThinkingBlock";
import { AgentStatus } from "@/components/agent/AgentStatus";
import { ToolCallCard } from "@/components/tool/ToolCallCard";
import { cn } from "@/lib/utils";

/** Tools whose numbered results back the `[N]` citation markers in answers. */
const SEARCH_TOOLS = new Set(["search_knowledge_base", "search_document"]);

/**
 * Parse `"[1] filename (page 3)\n<text>..."` tool results (knowledge_tools.py)
 * into a citation-number → page map. Lines without a page stay unmapped.
 */
function parseCitationPages(result: unknown): number[] {
  if (typeof result !== "string") {
    return [];
  }
  const pages: number[] = [];
  const pattern = /^\[(\d+)\][^\n]*?\(page\s*(\d+)/gim;
  for (const match of result.matchAll(pattern)) {
    pages[Number(match[1])] = Number(match[2]);
  }
  return pages;
}

/** Pages for the citations in `parts[index]`, from the nearest preceding retrieval. */
function citationPagesForPart(parts: MessagePart[], index: number): number[] {
  for (let i = index - 1; i >= 0; i--) {
    const part = parts[i];
    if (part.kind !== "tool") {
      continue;
    }
    if (SEARCH_TOOLS.has(part.tool.toolName) && part.tool.status === "success") {
      return parseCitationPages(part.tool.result);
    }
  }
  return [];
}

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

function AssistantMessage({
  message,
  onCitationClick,
}: {
  message: ChatMessage;
  onCitationClick?: (page: number) => void;
}) {
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
            <MarkdownRenderer
              content={part.text}
              onCitation={
                onCitationClick
                  ? (citation, inlinePage) => {
                      const page =
                        inlinePage ?? citationPagesForPart(message.parts, index)[citation];
                      if (page) {
                        onCitationClick(page);
                      }
                    }
                  : undefined
              }
            />
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
export const MessageItem = memo(function MessageItem({
  message,
  onCitationClick,
}: {
  message: ChatMessage;
  onCitationClick?: (page: number) => void;
}) {
  return (
    <article
      className={cn(
        "animate-fade-in min-w-0",
        message.role === "assistant" && "text-[14px] leading-[1.65]",
      )}
    >
      {message.role === "user" ? (
        <UserMessage message={message} />
      ) : (
        <AssistantMessage message={message} onCitationClick={onCitationClick} />
      )}
    </article>
  );
});
