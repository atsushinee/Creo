import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";

import { Modal } from "@/components/ui/dialog";
import { useI18n } from "@/hooks/useI18n";
import type { ParseResultInfo } from "@/types/knowledgeBase";
import { cn } from "@/lib/utils";

interface ParseResultDialogProps {
  title: string;
  onClose: () => void;
  load: () => Promise<ParseResultInfo>;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

/** Viewer for the cached Unstructured parse result (elements grouped by page). */
export function ParseResultDialog({ title, onClose, load }: ParseResultDialogProps) {
  const { t } = useI18n();
  const [result, setResult] = useState<ParseResultInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    load()
      .then((loaded) => {
        if (!cancelled) {
          setResult(loaded);
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

  const filtered = useMemo(() => {
    if (!result?.available) {
      return [];
    }
    const query = filter.trim().toLowerCase();
    if (!query) {
      return result.elements;
    }
    return result.elements.filter(
      (element) =>
        element.text.toLowerCase().includes(query) || element.type.toLowerCase().includes(query),
    );
  }, [result, filter]);

  const pages = useMemo(() => {
    const grouped = new Map<number, typeof filtered>();
    for (const element of filtered) {
      const bucket = grouped.get(element.pageNumber) ?? [];
      bucket.push(element);
      grouped.set(element.pageNumber, bucket);
    }
    return [...grouped.entries()].sort((a, b) => a[0] - b[0]);
  }, [filtered]);

  return (
    <Modal open onClose={onClose} ariaLabel={title}>
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-[14px] font-semibold" title={title}>
            {title}
          </h2>
          {result?.available && (
            <p className="text-[11.5px] text-muted-foreground">
              {t("parse.elements", { count: result.elements.length })}
              {result.profile ? ` · ${result.profile}` : ""}
            </p>
          )}
        </div>
        <button
          type="button"
          aria-label="Close"
          onClick={onClose}
          className="flex size-7 cursor-pointer items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      {result?.available && (
        <input
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder={t("parse.filter")}
          className="mt-3 w-full rounded-md border bg-background px-2.5 py-1.5 text-[12.5px] outline-none placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring"
        />
      )}

      <div className="mt-3 max-h-[60vh] overflow-y-auto rounded-lg border bg-surface/60 p-2.5">
        {error && <p className="py-6 text-center text-[12.5px] text-error">{error}</p>}
        {!error && result === null && (
          <p className="py-6 text-center text-[12.5px] text-muted-foreground">
            {t("viewer.loading")}
          </p>
        )}
        {!error && result !== null && !result.available && (
          <p className="py-6 text-center text-[12.5px] text-muted-foreground">{t("parse.empty")}</p>
        )}
        {!error &&
          pages.map(([page, elements]) => (
            <section key={page} className="mb-3">
              <p className="border-b pb-1 text-[11.5px] font-medium text-muted-foreground">
                {t("parse.page", { page })}
              </p>
              <ul className="space-y-1.5 pt-1.5">
                {elements.map((element, index) => (
                  <li
                    key={`${page}-${index}`}
                    className={cn("rounded-md bg-background p-2", element.type === "Table" && "border")}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="rounded bg-surface-raised px-1.5 py-0.5 text-[10px] font-medium">
                        {element.type}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        {t("chunks.page", { page: element.pageNumber })}
                      </span>
                    </div>
                    <p className="pt-1 text-[12px] leading-relaxed whitespace-pre-wrap">
                      {element.text}
                    </p>
                    {element.tableHtml && (
                      <details className="pt-1">
                        <summary className="cursor-pointer text-[10.5px] text-primary">
                          {t("parse.tableHtml")}
                        </summary>
                        <pre className="mt-1 max-h-40 overflow-auto rounded bg-surface p-2 font-mono text-[10.5px] leading-relaxed whitespace-pre-wrap">
                          {element.tableHtml}
                        </pre>
                      </details>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        {!error && result !== null && result.available && filtered.length === 0 && (
          <p className="py-6 text-center text-[12.5px] text-muted-foreground">{t("parse.noMatch")}</p>
        )}
      </div>
    </Modal>
  );
}
