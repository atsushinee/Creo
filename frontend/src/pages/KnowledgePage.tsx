import { useCallback, useEffect, useRef, useState } from "react";
import { Plus, Trash2, Upload } from "lucide-react";

import { DocChatPanel } from "@/components/knowledge/DocChatPanel";
import { DocGrid } from "@/components/knowledge/DocGrid";
import { ParseResultDialog } from "@/components/knowledge/ParseResultDialog";
import { PdfViewer, type PdfViewerHandle } from "@/components/knowledge/PdfViewer";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { ConfirmDialog, PromptDialog } from "@/components/ui/dialog";
import { ErrorBanner } from "@/components/chat/ErrorBanner";
import { useTheme } from "@/hooks/useTheme";
import { useI18n } from "@/hooks/useI18n";
import { useKnowledgeBase } from "@/hooks/useKnowledgeBase";
import type { KbDocumentInfo, KnowledgeBaseInfo, ParseElementInfo } from "@/types/knowledgeBase";

/**
 * Dify-style three-column knowledge workspace:
 *   left   — KB switcher + document cards with page-1 covers
 *   middle — chat scoped to the selected document (doc-scoped agent)
 *   right  — continuous-scroll PDF preview
 */
export default function KnowledgePage() {
  const { theme, toggleTheme } = useTheme();
  const { t } = useI18n();
  const kb = useKnowledgeBase();
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [creatingKb, setCreatingKb] = useState(false);
  const [pendingDeleteKb, setPendingDeleteKb] = useState<KnowledgeBaseInfo | null>(null);
  const [parseDoc, setParseDoc] = useState<KbDocumentInfo | null>(null);
  const [parseElements, setParseElements] = useState<ParseElementInfo[]>([]);
  const [parseElementsDocId, setParseElementsDocId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const pdfRef = useRef<PdfViewerHandle>(null);
  const currentKb = kb.currentKb;
  const selectedDoc = kb.documents.find((doc) => doc.id === selectedDocId) ?? null;
  const fetchParseResult = kb.fetchParseResult;
  const selectedDocIdStr = selectedDoc?.id ?? null;

  // Citation `[N]` markers in doc chat jump to the cited page in the preview.
  const handleCitationClick = useCallback(
    (page: number) => pdfRef.current?.scrollToPage(page),
    [],
  );

  // Parse elements (with coordinates, when cached) for the preview overlay.
  useEffect(() => {
    if (!currentKb || !selectedDocIdStr) {
      return;
    }
    let cancelled = false;
    fetchParseResult(currentKb.id, selectedDocIdStr)
      .then((result) => {
        if (cancelled) {
          return;
        }
        setParseElements(result.available ? result.elements : []);
        setParseElementsDocId(selectedDocIdStr);
      })
      .catch(() => {
        if (!cancelled) {
          setParseElements([]);
          setParseElementsDocId(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [currentKb, selectedDocIdStr, fetchParseResult]);

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
                aria-label={t("kb.select")}
              >
                {kb.knowledgeBases.length === 0 && (
                  <option value="">{t("kb.select")}</option>
                )}
                {kb.knowledgeBases.map((base) => (
                  <option key={base.id} value={base.id}>
                    {base.name} ({base.documentCount})
                  </option>
                ))}
              </select>
              <Button
                variant="outline"
                size="icon-sm"
                aria-label={t("kb.new")}
                onClick={() => setCreatingKb(true)}
              >
                <Plus className="size-3.5" />
              </Button>
              <Button
                variant="danger-ghost"
                size="icon-sm"
                aria-label={t("kb.delete")}
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
              {t("kb.upload")}
            </Button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
            {!currentKb ? (
              <p className="px-1 pt-1 text-[12.5px] leading-relaxed text-muted-foreground">
                {t("kb.emptyHint")}
              </p>
            ) : kb.documents.length === 0 ? (
              <p className="px-1 pt-1 text-[12.5px] leading-relaxed text-muted-foreground">
                {t("kb.noDocs")}
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
                onShowParse={(doc) => setParseDoc(doc)}
              />
            )}
          </div>
        </aside>

        {/* Middle: document chat */}
        <main className="flex min-w-0 flex-1 flex-col">
          {currentKb && selectedDoc ? (
            <DocChatPanel
              key={selectedDoc.id}
              kbId={currentKb.id}
              doc={selectedDoc}
              onCitationClick={handleCitationClick}
            />
          ) : (
            <div className="flex flex-1 items-center justify-center p-6">
              <p className="text-center text-[13px] text-muted-foreground">
                {t("kb.selectDocChat")}
              </p>
            </div>
          )}
          {kb.error && <ErrorBanner error={kb.error} onDismiss={kb.dismissError} />}
        </main>

        {/* Right: continuous-scroll preview */}
        <aside className="hidden w-[42%] max-w-2xl shrink-0 flex-col border-l xl:flex">
          {selectedDoc && currentKb ? (
            <PdfViewer
              ref={pdfRef}
              key={selectedDoc.id}
              url={kb.documentFileUrl(currentKb.id, selectedDoc.id)}
              title={selectedDoc.filename}
              elements={parseElementsDocId === selectedDoc.id ? parseElements : []}
            />
          ) : (
            <div className="flex flex-1 items-center justify-center p-6">
              <p className="text-[13px] text-muted-foreground">{t("kb.selectDocPreview")}</p>
            </div>
          )}
        </aside>
      </div>

      {creatingKb && (
        <PromptDialog
          title={t("kb.newTitle")}
          placeholder={t("kb.namePlaceholder")}
          confirmLabel={t("common.create")}
          cancelLabel={t("common.cancel")}
          onConfirm={(name) => {
            setCreatingKb(false);
            void kb.createKb(name, "");
          }}
          onCancel={() => setCreatingKb(false)}
        />
      )}
      {parseDoc && currentKb && (
        <ParseResultDialog
          title={`${t("parse.title")} · ${parseDoc.filename}`}
          load={() => kb.fetchParseResult(currentKb.id, parseDoc.id)}
          onClose={() => setParseDoc(null)}
        />
      )}
      <ConfirmDialog
        open={pendingDeleteKb !== null}
        title={t("kb.deleteTitle", { name: pendingDeleteKb?.name ?? "" })}
        description={t("kb.deleteDesc")}
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
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
