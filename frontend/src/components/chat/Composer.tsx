import { ArrowUp, Square } from "lucide-react";
import { memo, useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

interface ComposerProps {
  isBusy: boolean;
  streaming: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}

const MAX_TEXTAREA_HEIGHT = 160;

export const Composer = memo(function Composer({
  isBusy,
  streaming,
  onSend,
  onStop,
}: ComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useLayoutEffect(() => {
    const element = textareaRef.current;
    if (!element) {
      return;
    }
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`;
  }, [value]);

  const submit = () => {
    const text = value.trim();
    if (!text || isBusy) {
      return;
    }
    onSend(text);
    setValue("");
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <div className="shrink-0 px-4 pb-4">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 rounded-xl border bg-background px-3 py-2 shadow-soft transition-shadow focus-within:border-primary/60 focus-within:ring-2 focus-within:ring-ring">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Creo anything…"
            rows={1}
            className="max-h-40 min-h-6 flex-1 resize-none bg-transparent text-[14px] leading-relaxed outline-none placeholder:text-muted-foreground"
          />
          {streaming ? (
            <Button
              size="icon"
              onClick={onStop}
              aria-label="Stop generating"
              title="Stop generating"
              className="rounded-full bg-foreground text-background hover:opacity-80"
            >
              <Square className="size-3 fill-current" />
            </Button>
          ) : (
            <Button
              size="icon"
              onClick={submit}
              disabled={!value.trim() || isBusy}
              aria-label="Send message"
              className="rounded-full"
            >
              <ArrowUp className="size-4" />
            </Button>
          )}
        </div>
        <p className="pt-1.5 text-center text-[11px] text-muted-foreground">
          Creo can make mistakes. Verify important information.
        </p>
      </div>
    </div>
  );
});
