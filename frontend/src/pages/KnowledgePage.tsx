import { useRef, useState } from "react";
import { Plus, Trash2, Upload } from "lucide-react";

import { DocChatPanel } from "@/components/knowledge/DocChatPanel";
import { DocGrid } from "@/components/knowledge/DocGrid";
import { PdfViewer } from "@/components/knowledge/PdfViewer";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { ConfirmDialog, PromptDialog } from "@/components/ui/dialog";
import { ErrorBanner } from "@/components/chat/ErrorBanner";
import { useTheme } from "@/hooks/useTheme";
import { useKnowledgeBase } from "@/hooks/useKnowledgeBase";
import type { KnowledgeBaseInfo } from "@/types/knowledgeBase";

/**
 * Dify-style three-column knowledge workspace:
 *   left   — KB switcher + document cards with page-1 covers
 *   middle — chat scoped to the selected document (doc-scoped agent)
 *   right  — continuous-scroll PDF preview
 */
export default function KnowledgePage() {
  const { theme, toggleTheme } = useTheme();
  const kb = useKnowledgeBase();
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [creatingKb, setCreatingKb] = useState(false);
  const [pendingDeleteKb, setPendingDeleteKb] = useState<KnowledgeBaseInfo | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const currentKb = kb.currentKb;
  const selectedDoc = kb.documents.find((doc) => doc.id === selectedDocId) ?? null;

  const uploadFiles = async (files: FileList | null) => {
    if (!currentKb || !files) {
      return;
    }
    for (const file of Array.from(files)) {
      await kb.uploadDocument(currentKb.id, file);
    }
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  return (
    <div className="flex h-dvh flex-col bg-background text-foreground">
      <AppHeader theme={theme} onToggleTheme={toggleTheme} />

      <div className="flex min-h-0 flex-1">
        {/* Left: KB switcher + document cards */}
        <aside className="hidden w-64 shrink-0 flex-col border-r bg-surface md:flex">
          <div className="space-y-2 p-3">
            <div className="flex items-center gap-1">
              <select
                value={kb.currentKbId ?? ""}
                onChange={(event) => void kb.selectKb(event.target.value)}
                className="min-w-0 flex-1 rounded-md border bg-background px-2 py-1.5 text-[12.5px] outline-none focus-visible:outline-2 focus-visible:outline-ring"
                aria-label="Knowledge base"
              >
                {kb.knowledgeBases.length === 0 && <option value="">No knowledge base</option>}
                {kb.knowledgeBases.map((base) => (
                  <option key={base.id} value={base.id}>
                    {base.name} ({base.documentCount})
                  </option>
                ))}
              </select>
              <Button variant="outline" size="icon-sm" aria-label="New knowledge base" onClick={() => setCreatingKb(true)}>
                <Plus className="size-3.5" />
              </Button>
              <Button
                variant="danger-ghost"
                size="icon-sm"
                aria-label="Delete knowledge base"
                disabled={!currentKb}
                onClick={() => setPendingDeleteKb(currentKb)}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf"
              multiple
              className="hidden"
              onChange={(event) => void uploadFiles(event.target.files)}
            />
            <Button
              variant="outline"
              className="w-full justify-start"
              disabled={!currentKb || kb.isBusy}
              onClick={() => inputRef.current?.click()}
            >
              <Upload className="size-4" />
              Upload PDF
            </Button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
            {!currentKb ? (
              <p className="px-1 pt-1 text-[12.5px] leading-relaxed text-muted-foreground">
                Create a knowledge base, then upload PDFs. Click a card to chat about it.
              </p>
            ) : kb.documents.length === 0 ? (
              <p className="px-1 pt-1 text-[12.5px] leading-relaxed text-muted-foreground">
                No documents yet — upload PDFs to index them.
              </p>
            ) : (
              <DocGrid
                documents={kb.documents}
                traceByDoc={kb.traceByDoc}
                selectedDocId={selectedDocId}
                onGetFileUrl={(docId) => kb.documentFileUrl(currentKb.id, docId)}
                onSelect={(doc) => setSelectedDocId(doc.id)}
                onDeleteDoc={(docId) => void kb.deleteDocument(currentKb.id, docId)}
                onReingest={(docId) => void kb.reingestDocument(currentKb.id, docId)}
                onLoadTrace={(docId) => void kb.loadTrace(currentKb.id, docId)}
              />
            )}
          </div>
        </aside>

        {/* Middle: document chat */}
        <main className="flex min-w-0 flex-1 flex-col">
          {currentKb && selectedDoc ? (
            <DocChatPanel key={selectedDoc.id} kbId={currentKb.id} doc={selectedDoc} />
          ) : (
            <div className="flex flex-1 items-center justify-center p-6">
              <p className="text-center text-[13px] text-muted-foreground">
                Select a document on the left to start a scoped conversation.
              </p>
            </div>
          )}
          {kb.error && <ErrorBanner error={kb.error} onDismiss={kb.dismissError} />}
        </main>

        {/* Right: continuous-scroll preview */}
        <aside className="hidden w-[42%] max-w-2xl shrink-0 flex-col border-l xl:flex">
          {selectedDoc && currentKb ? (
            <PdfViewer
              key={selectedDoc.id}
              url={kb.documentFileUrl(currentKb.id, selectedDoc.id)}
              title={selectedDoc.filename}
            />
          ) : (
            <div className="flex flex-1 items-center justify-center p-6">
              <p className="text-[13px] text-muted-foreground">Select a document to preview it.</p>
            </div>
          )}
        </aside>
      </div>

      {creatingKb && (
        <PromptDialog
          title="New knowledge base"
          placeholder="Knowledge base name"
          confirmLabel="Create"
          onConfirm={(name) => {
            setCreatingKb(false);
            void kb.createKb(name, "");
          }}
          onCancel={() => setCreatingKb(false)}
        />
      )}
      <ConfirmDialog
        open={pendingDeleteKb !== null}
        title={`Delete knowledge base "${pendingDeleteKb?.name ?? ""}"?`}
        description="All uploaded documents, their indexed vectors and pipeline traces will be removed. This cannot be undone."
        confirmLabel="Delete"
        danger
        onConfirm={() => {
          if (pendingDeleteKb) {
            setSelectedDocId(null);
            void kb.deleteKb(pendingDeleteKb.id);
          }
          setPendingDeleteKb(null);
        }}
        onCancel={() => setPendingDeleteKb(null)}
      />
    </div>
  );
}
