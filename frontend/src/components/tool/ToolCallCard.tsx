import type { ToolInvocation } from "@/types/agent";
import { Check, ChevronDown, X } from "lucide-react";
import { memo, useState } from "react";

import { Spinner } from "@/components/ui/spinner";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

function renderPayload(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  try {
    return JSON.stringify(value, null, 2) ?? "";
  } catch {
    return String(value);
  }
}

function PayloadSection({ label, value, isError }: { label: string; value: unknown; isError?: boolean }) {
  return (
    <section>
      <p className="pb-1 text-[11px] font-medium tracking-wider text-muted-foreground uppercase">{label}</p>
      <pre
        className={cn(
          "max-h-56 overflow-auto rounded-md bg-background/70 p-2.5 font-mono text-[12px] leading-relaxed whitespace-pre-wrap",
          "dark:bg-black/40",
          isError && "text-error",
        )}
      >
        {renderPayload(value)}
      </pre>
    </section>
  );
}

/**
 * Tool calls are first-class citizens (DESIGN.md §5): collapsed by default,
 * with an explicit running / success / error state. Memoized so finished
 * cards skip re-render during token streaming.
 */
export const ToolCallCard = memo(function ToolCallCard({ tool }: { tool: ToolInvocation }) {
  const [open, setOpen] = useState(false);
  const { t } = useI18n();

  return (
    <div className="animate-fade-in my-2 overflow-hidden rounded-[10px] border bg-surface">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-surface-raised/60"
        aria-expanded={open}
      >
        {tool.status === "running" ? (
          <Spinner className="size-3.5 shrink-0 text-primary" />
        ) : tool.status === "success" ? (
          <Check className="size-3.5 shrink-0 text-success" />
        ) : (
          <X className="size-3.5 shrink-0 text-error" />
        )}
        <span className="font-medium">{tool.toolName}</span>
        {tool.status === "running" && (
          <span className="text-[12px] text-muted-foreground">{t("tool.running")}</span>
        )}
        {tool.status === "error" && (
          <span className="text-[12px] text-error">{t("tool.failed")}</span>
        )}
        <ChevronDown
          className={cn(
            "ml-auto size-3.5 shrink-0 text-muted-foreground transition-transform duration-150",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <div className="space-y-2.5 border-t px-3 py-2.5">
          {tool.args !== undefined && <PayloadSection label={t("tool.arguments")} value={tool.args} />}
          {tool.status !== "running" && tool.result !== undefined && (
            <PayloadSection
              label={t("tool.result")}
              value={tool.result}
              isError={tool.status === "error"}
            />
          )}
        </div>
      )}
    </div>
  );
});
