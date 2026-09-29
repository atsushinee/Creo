import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

import { Modal } from "@/components/ui/dialog";
import { useI18n } from "@/hooks/useI18n";
import type { TranslationKey } from "@/lib/i18n";
import type { TraceEntry } from "@/types/agent";
import { cn } from "@/lib/utils";

interface RunTraceDialogProps {
  onClose: () => void;
  title: string;
  load: () => Promise<TraceEntry[]>;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function entryTone(type: string): string {
  if (type === "tool_result") {
    return "bg-foreground";
  }
  if (type === "error") {
    return "bg-error";
  }
  if (type === "user_message") {
    return "bg-warning";
  }
  if (type.startsWith("run_")) {
    return "bg-primary";
  }
  return "bg-muted-foreground";
}

const TYPE_LABEL_KEYS: Record<string, TranslationKey> = {
  user_message: "trace.typeUserMessage",
  run_started: "trace.typeRunStarted",
  run_finished: "trace.typeRunFinished",
  message_start: "trace.typeMessageStart",
  message_end: "trace.typeMessageEnd",
  thinking_delta: "trace.typeThinkingDelta",
  tool_start: "trace.typeToolStart",
  tool_result: "trace.typeToolResult",
  error: "trace.typeError",
};

/**
 * Session run trace (ADR-0004 Update 4): structural events with timestamps —
 * tool calls with full arguments/results, message durations, errors.
 */
export function RunTraceDialog({ onClose, title, load }: RunTraceDialogProps) {
  const { t } = useI18n();
  const [entries, setEntries] = useState<TraceEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    void (async () => {
      try {
        const loaded = await load();
        setEntries(loaded);
      } catch (loadError) {
        setError(message(loadError));
      }
    })();
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    load()
      .then((loaded) => {
        if (!cancelled) {
          setEntries(loaded);
        }
      })
      .catch((loadError: unknown) => {
        if (!cancelled) {
          setError(message(loadError));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [load]);

  return (
    <Modal open onClose={onClose} ariaLabel={title}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="min-w-0 truncate text-[14px] font-semibold">{title}</h2>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            aria-label={t("trace.refresh")}
            title={t("trace.refresh")}
            onClick={() => void refresh()}
            className="flex size-7 cursor-pointer items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
          >
            <RefreshCw className="size-3.5" />
          </button>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="flex size-7 cursor-pointer items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
          >
            ×
          </button>
        </div>
      </div>

      <div className="mt-3 max-h-[60vh] overflow-y-auto rounded-lg border bg-surface/60 p-2.5">
        {error && <p className="py-6 text-center text-[12.5px] text-error">{error}</p>}
        {!error && entries === null && (
          <p className="py-6 text-center text-[12.5px] text-muted-foreground">
            {t("viewer.loading")}
          </p>
        )}
        {!error && entries !== null && entries.length === 0 && (
          <p className="py-6 text-center text-[12.5px] text-muted-foreground">{t("trace.empty")}</p>
        )}
        {!error && entries !== null && entries.length > 0 && (
          <>
            <p className="pb-1.5 text-[10.5px] text-muted-foreground">
              {entries.some((entry) => entry.type === "tool_start")
                ? ""
                : t("trace.noToolCalls")}
            </p>
            <ol className="space-y-1">
              {entries.map((entry, index) => (
                <li key={`${entry.ts}-${index}`} className="flex items-start gap-2 text-[11.5px]">
                  <span
                    className={cn("mt-1 size-1.5 shrink-0 rounded-full", entryTone(entry.type))}
                  />
                  <span className="w-16 shrink-0 text-muted-foreground">
                    {new Date(entry.ts).toLocaleTimeString()}
                  </span>
                  <span className="w-20 shrink-0 font-medium">
                    {t(TYPE_LABEL_KEYS[entry.type] ?? "trace.typeMessageStart")}
                  </span>
                  <div className="min-w-0 flex-1">
                    {entry.type === "user_message" && typeof entry.message === "string" && (
                      <p className="break-words">{entry.message}</p>
                    )}
                    {entry.toolName && (
                      <span className="rounded bg-surface-raised px-1.5 py-0.5 text-[10.5px] font-medium">
                        {entry.toolName}
                      </span>
                    )}
                    {entry.durationMs !== undefined && (
                      <span className="pl-1.5 text-muted-foreground">{entry.durationMs} ms</span>
                    )}
                    {entry.chars !== undefined && (
                      <span className="pl-1.5 text-muted-foreground">
                        {t("trace.chars", { count: entry.chars })}
                      </span>
                    )}
                    {entry.thinkingChars !== undefined && (
                      <span className="pl-1.5 text-muted-foreground">
                        {t("trace.thinkingChars", { count: entry.thinkingChars })}
                      </span>
                    )}
                    {entry.isError && <span className="pl-1.5 text-error">{t("tool.failed")}</span>}
                    {entry.message && entry.type === "error" && (
                      <p className="break-words text-error">{entry.message}</p>
                    )}
                    {(entry.args !== undefined || entry.result !== undefined) && (
                      <details className="pt-0.5">
                        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                          {t("tool.arguments")} / {t("tool.result")}
                        </summary>
                        {entry.args !== undefined && (
                          <pre className="mt-1 max-h-40 overflow-auto rounded bg-background/70 p-2 font-mono text-[10.5px] leading-relaxed whitespace-pre-wrap">
                            {typeof entry.args === "string"
                              ? entry.args
                              : JSON.stringify(entry.args, null, 2)}
                          </pre>
                        )}
                        {entry.result !== undefined && (
                          <pre className="mt-1 max-h-40 overflow-auto rounded bg-background/70 p-2 font-mono text-[10.5px] leading-relaxed whitespace-pre-wrap">
                            {typeof entry.result === "string"
                              ? entry.result
                              : JSON.stringify(entry.result, null, 2)}
                          </pre>
                        )}
                      </details>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}
      </div>
    </Modal>
  );
}
