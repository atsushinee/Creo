import { useState } from "react";
import { FlaskConical, Loader2, Search } from "lucide-react";

import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/hooks/useTheme";
import { useKnowledgeBase } from "@/hooks/useKnowledgeBase";
import { retrievalTest } from "@/services/kbApi";
import type { RecallTestResult } from "@/types/knowledgeBase";
import { cn } from "@/lib/utils";

/**
 * Retrieval testing (Dify-style recall test): run one query through the
 * hybrid/dense/sparse channels side by side to eyeball fusion quality.
 */
export default function RecallTestPage() {
  const { theme, toggleTheme } = useTheme();
  const kb = useKnowledgeBase();
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [docId, setDocId] = useState("all");
  const [result, setResult] = useState<RecallTestResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    if (!kb.currentKbId || !query.trim()) {
      return;
    }
    setRunning(true);
    setError(null);
    try {
      setResult(
        await retrievalTest(kb.currentKbId, {
          query: query.trim(),
          top_k: topK,
          doc_id: docId === "all" ? null : docId,
        }),
      );
    } catch (testError) {
      setError(testError instanceof Error ? testError.message : String(testError));
    } finally {
      setRunning(false);
    }
  };

  const columns: Array<{ key: keyof RecallTestResult; label: string; hint: string }> = [
    { key: "hybrid", label: "Hybrid (RRF)", hint: "BM25 + dense fusion — what the agent uses" },
    { key: "dense", label: "Dense only", hint: "bge-m3 semantic channel" },
    { key: "sparse", label: "Sparse only", hint: "server-side BM25 channel" },
  ];

  return (
    <div className="flex h-dvh flex-col bg-background text-foreground">
      <AppHeader theme={theme} onToggleTheme={toggleTheme} />

      <div className="border-b px-4 py-3">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-2">
          <FlaskConical className="size-4 shrink-0 text-muted-foreground" />
          <select
            value={kb.currentKbId ?? ""}
            onChange={(event) => {
              setResult(null);
              setDocId("all");
              void kb.selectKb(event.target.value);
            }}
            className="rounded-md border bg-background px-2 py-1.5 text-[12.5px] outline-none focus-visible:outline-2 focus-visible:outline-ring"
            aria-label="Knowledge base"
          >
            {kb.knowledgeBases.length === 0 && <option value="">No knowledge base</option>}
            {kb.knowledgeBases.map((base) => (
              <option key={base.id} value={base.id}>
                {base.name} ({base.documentCount})
              </option>
            ))}
          </select>
          <select
            value={docId}
            onChange={(event) => setDocId(event.target.value)}
            disabled={!kb.currentKbId}
            className="rounded-md border bg-background px-2 py-1.5 text-[12.5px] outline-none focus-visible:outline-2 focus-visible:outline-ring"
            aria-label="Document filter"
          >
            <option value="all">All documents</option>
            {kb.documents.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.filename}
              </option>
            ))}
          </select>
          <select
            value={topK}
            onChange={(event) => setTopK(Number(event.target.value))}
            className="rounded-md border bg-background px-2 py-1.5 text-[12.5px] outline-none focus-visible:outline-2 focus-visible:outline-ring"
            aria-label="Top K"
          >
            {[3, 5, 8, 10, 20].map((value) => (
              <option key={value} value={value}>
                top {value}
              </option>
            ))}
          </select>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                void run();
              }
            }}
            placeholder="Test query, e.g. 公司的经营范围"
            className="min-w-48 flex-1 rounded-md border bg-background px-2.5 py-1.5 text-[13px] outline-none placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring"
          />
          <Button
            size="sm"
            disabled={!kb.currentKbId || running || !query.trim()}
            onClick={() => void run()}
          >
            {running ? <Loader2 className="size-3.5 animate-spin" /> : <Search className="size-3.5" />}
            Recall
          </Button>
        </div>
        {error && <p className="mx-auto mt-2 max-w-6xl text-[12px] text-error">{error}</p>}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {!kb.currentKbId ? (
          <p className="py-16 text-center text-[13px] text-muted-foreground">
            Select a knowledge base, then run a query to compare the retrieval channels.
          </p>
        ) : (
          <div className="mx-auto grid max-w-6xl grid-cols-1 gap-3 lg:grid-cols-3">
            {columns.map((column) => (
              <section key={column.key} className="rounded-lg border bg-surface">
                <div className="border-b px-3 py-2">
                  <p className="text-[12.5px] font-medium">{column.label}</p>
                  <p className="text-[11px] text-muted-foreground">{column.hint}</p>
                </div>
                <div className="space-y-2 p-2.5">
                  {result === null ? (
                    <p className="px-1 py-4 text-[12px] text-muted-foreground">Run a query.</p>
                  ) : result[column.key].length === 0 ? (
                    <p className="px-1 py-4 text-[12px] text-muted-foreground">No hits.</p>
                  ) : (
                    result[column.key].map((hit, index) => (
                      <div key={`${hit.docId}-${hit.chunkIndex}-${index}`} className="rounded-md border bg-background p-2">
                        <div className="flex items-center gap-2 text-[10.5px] text-muted-foreground">
                          <span className="rounded-full bg-surface-raised px-1.5 py-0.5 font-medium text-foreground">
                            #{index + 1}
                          </span>
                          <span>score {hit.score.toFixed(4)}</span>
                          {hit.page > 0 && <span>· p.{hit.page}</span>}
                          <span className="truncate">
                            · {String(hit.metadata?.filename ?? hit.kbName ?? "")}
                          </span>
                        </div>
                        <p
                          className={cn(
                            "pt-1 text-[12px] leading-relaxed",
                            "line-clamp-6 whitespace-pre-wrap",
                          )}
                        >
                          {hit.text}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
