import { ChevronDown, Lightbulb } from "lucide-react";
import { useState } from "react";

import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

interface ThinkingBlockProps {
  text: string;
  /** True while reasoning is the streaming tail of the message. */
  active: boolean;
}

/**
 * Collapsible reasoning display (ADR-0002 Update 1): auto-open while the
 * model is thinking, auto-collapse once the answer starts; the user can
 * always toggle it back open.
 */
export function ThinkingBlock({ text, active }: ThinkingBlockProps) {
  const { t } = useI18n();
  // null = follow `active`; after a manual toggle the user wins.
  const [userOpen, setUserOpen] = useState<boolean | null>(null);
  const open = userOpen ?? active;

  return (
    <div className="my-2 rounded-lg border bg-surface/60">
      <button
        type="button"
        onClick={() => setUserOpen(!open)}
        aria-expanded={open}
        className="flex w-full cursor-pointer items-center gap-2 px-2.5 py-1.5 text-left transition-colors hover:bg-surface-raised/60"
      >
        <Lightbulb
          className={cn(
            "size-3.5 shrink-0",
            active ? "animate-pulse text-warning" : "text-muted-foreground",
          )}
        />
        <span className="text-[12px] font-medium text-muted-foreground">
          {active ? t("thinking.thinking") : t("thinking.done")}
        </span>
        <ChevronDown
          className={cn(
            "ml-auto size-3.5 shrink-0 text-muted-foreground transition-transform duration-150",
            open && "rotate-180",
          )}
        />
      </button>
      {open && (
        <div className="max-h-56 overflow-y-auto border-t px-3 py-2 text-[12.5px] leading-relaxed whitespace-pre-wrap text-muted-foreground">
          {text}
        </div>
      )}
    </div>
  );
}
