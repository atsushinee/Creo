import { useCallback, useEffect, useState } from "react";

import * as kbApi from "@/services/kbApi";
import type {
  KbDocumentInfo,
  KnowledgeBaseInfo,
  PipelineEventInfo,
} from "@/types/knowledgeBase";

function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

/**
 * Domain hook for the knowledge base page (ADR-0004): KB CRUD, uploads and
 * document status polling. Components only talk to this hook.
 */
export function useKnowledgeBase() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseInfo[]>([]);
  const [currentKbId, setCurrentKbId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<KbDocumentInfo[]>([]);
  const [traceByDoc, setTraceByDoc] = useState<Record<string, PipelineEventInfo[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const refreshKnowledgeBases = useCallback(async () => {
    try {
      setKnowledgeBases(await kbApi.listKnowledgeBases());
    } catch (loadError) {
      setError(errorMessage(loadError));
    }
  }, []);

  const refreshDocuments = useCallback(async (kbId: string) => {
    try {
      setDocuments(await kbApi.listDocuments(kbId));
    } catch (loadError) {
      setError(errorMessage(loadError));
    }
  }, []);

  // Initial load: fetch KBs and auto-select the first one so the page is
  // usable right after a restart (state resets, data does not).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const bases = await kbApi.listKnowledgeBases();
        if (cancelled) {
          return;
        }
        setKnowledgeBases(bases);
        if (bases.length > 0) {
          const first = bases[0];
          setCurrentKbId(first.id);
          setDocuments(await kbApi.listDocuments(first.id));
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(errorMessage(loadError));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Poll while any document is pending/processing (ingestion is async).
  useEffect(() => {
    if (!currentKbId) {
      return;
    }
    const active = documents.some(
      (doc) => doc.status === "pending" || doc.status === "processing",
    );
    if (!active) {
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshDocuments(currentKbId);
    }, 2500);
    return () => window.clearTimeout(timer);
  }, [currentKbId, documents, refreshDocuments]);

  const selectKb = useCallback(
    async (kbId: string) => {
      setCurrentKbId(kbId);
      setDocuments([]);
      await refreshDocuments(kbId);
    },
    [refreshDocuments],
  );

  const createKb = useCallback(
    async (name: string, description: string) => {
      setIsBusy(true);
      setError(null);
      try {
        const kb = await kbApi.createKnowledgeBase(name, description);
        await refreshKnowledgeBases();
        setCurrentKbId(kb.id);
        setDocuments([]);
      } catch (createError) {
        setError(errorMessage(createError));
      } finally {
        setIsBusy(false);
      }
    },
    [refreshKnowledgeBases],
  );

  const deleteKb = useCallback(
    async (kbId: string) => {
      try {
        await kbApi.deleteKnowledgeBase(kbId);
      } catch (deleteError) {
        setError(errorMessage(deleteError));
        return;
      }
      setCurrentKbId((current) => (current === kbId ? null : current));
      setDocuments([]);
      await refreshKnowledgeBases();
    },
    [refreshKnowledgeBases],
  );

  const uploadDocument = useCallback(
    async (kbId: string, file: File) => {
      setIsBusy(true);
      setError(null);
      try {
        await kbApi.uploadDocument(kbId, file);
        await Promise.all([refreshDocuments(kbId), refreshKnowledgeBases()]);
      } catch (uploadError) {
        setError(errorMessage(uploadError));
      } finally {
        setIsBusy(false);
      }
    },
    [refreshDocuments, refreshKnowledgeBases],
  );

  const deleteDocument = useCallback(
    async (kbId: string, docId: string) => {
      try {
        await kbApi.deleteDocument(kbId, docId);
        await refreshDocuments(kbId);
        await refreshKnowledgeBases();
      } catch (deleteError) {
        setError(errorMessage(deleteError));
      }
    },
    [refreshDocuments, refreshKnowledgeBases],
  );

  const reingestDocument = useCallback(
    async (kbId: string, docId: string) => {
      try {
        await kbApi.reingestDocument(kbId, docId);
        await refreshDocuments(kbId);
      } catch (ingestError) {
        setError(errorMessage(ingestError));
      }
    },
    [refreshDocuments],
  );

  const loadTrace = useCallback(async (kbId: string, docId: string) => {
    try {
      const events = await kbApi.getDocumentTrace(kbId, docId);
      setTraceByDoc((previous) => ({ ...previous, [docId]: events }));
    } catch (traceError) {
      setError(errorMessage(traceError));
    }
  }, []);

  const documentFileUrl = useCallback(
    (kbId: string, docId: string) => kbApi.documentFileUrl(kbId, docId),
    [],
  );

  const currentKb = knowledgeBases.find((kb) => kb.id === currentKbId) ?? null;

  return {
    knowledgeBases,
    currentKbId,
    currentKb,
    documents,
    traceByDoc,
    error,
    isBusy,
    selectKb,
    createKb,
    deleteKb,
    uploadDocument,
    deleteDocument,
    reingestDocument,
    loadTrace,
    documentFileUrl,
    dismissError: () => setError(null),
  };
}