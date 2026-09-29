import { ErrorBanner } from "@/components/chat/ErrorBanner";
import { AppHeader } from "@/components/layout/AppHeader";
import { DocumentPanel } from "@/components/knowledge/DocumentPanel";
import { KnowledgeSidebar } from "@/components/knowledge/KnowledgeSidebar";
import { useTheme } from "@/hooks/useTheme";
import { useKnowledgeBase } from "@/hooks/useKnowledgeBase";

export default function KnowledgePage() {
  const { theme, toggleTheme } = useTheme();
  const kb = useKnowledgeBase();
  const currentKb = kb.currentKb;

  return (
    <div className="flex h-dvh flex-col bg-background text-foreground">
      <AppHeader theme={theme} onToggleTheme={toggleTheme} />

      <div className="flex min-h-0 flex-1">
        <KnowledgeSidebar
          knowledgeBases={kb.knowledgeBases}
          currentKbId={kb.currentKbId}
          isBusy={kb.isBusy}
          onSelect={(kbId) => void kb.selectKb(kbId)}
          onCreate={(name, description) => void kb.createKb(name, description)}
          onDelete={(kbId) => void kb.deleteKb(kbId)}
        />

        <main className="flex min-w-0 flex-1 flex-col">
          {currentKb ? (
            <DocumentPanel
              kb={currentKb}
              documents={kb.documents}
              traceByDoc={kb.traceByDoc}
              isBusy={kb.isBusy}
              onUpload={(file) => kb.uploadDocument(currentKb.id, file)}
              onDeleteDoc={(docId) => void kb.deleteDocument(currentKb.id, docId)}
              onReingest={(docId) => void kb.reingestDocument(currentKb.id, docId)}
              onLoadTrace={(docId) => void kb.loadTrace(currentKb.id, docId)}
              onGetFileUrl={(docId) => kb.documentFileUrl(currentKb.id, docId)}
            />
          ) : (
            <div className="flex flex-1 items-center justify-center p-6">
              <p className="text-[13px] text-muted-foreground">
                Select or create a knowledge base to upload PDFs.
              </p>
            </div>
          )}

          {kb.error && <ErrorBanner error={kb.error} onDismiss={kb.dismissError} />}
        </main>
      </div>
    </div>
  );
}
