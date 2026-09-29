import { useState } from "react";
import { BookMarked, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { KnowledgeBaseInfo } from "@/types/knowledgeBase";

interface KnowledgeSidebarProps {
  knowledgeBases: KnowledgeBaseInfo[];
  currentKbId: string | null;
  isBusy: boolean;
  onSelect: (kbId: string) => void;
  onCreate: (name: string, description: string) => void;
  onDelete: (kbId: string) => void;
}

export function KnowledgeSidebar({
  knowledgeBases,
  currentKbId,
  isBusy,
  onSelect,
  onCreate,
  onDelete,
}: KnowledgeSidebarProps) {
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const submit = () => {
    const trimmed = name.trim();
    if (!trimmed) {
      return;
    }
    onCreate(trimmed, description.trim());
    setName("");
    setDescription("");
    setCreating(false);
  };

  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r bg-surface md:flex">
      <div className="space-y-2 p-3">
        <Button
          variant="outline"
          className="w-full justify-start"
          onClick={() => setCreating((value) => !value)}
        >
          <Plus className="size-4" />
          New knowledge base
        </Button>
        {creating && (
          <form
            className="space-y-2 rounded-lg border bg-background p-2"
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            <input
              autoFocus
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Name"
              className="w-full rounded-md border bg-background px-2 py-1.5 text-[13px] outline-none placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring"
            />
            <input
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Description (optional)"
              className="w-full rounded-md border bg-background px-2 py-1.5 text-[13px] outline-none placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring"
            />
            <Button type="submit" size="sm" className="w-full" disabled={isBusy || !name.trim()}>
              Create
            </Button>
          </form>
        )}
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {knowledgeBases.length > 0 ? (
          <ul className="space-y-0.5">
            {knowledgeBases.map((kb) => (
              <li key={kb.id} className="group relative">
                <button
                  type="button"
                  onClick={() => onSelect(kb.id)}
                  className={cn(
                    "flex w-full cursor-pointer items-center gap-2 rounded-md px-2.5 py-1.5 pr-8 text-left text-[13px] transition-colors",
                    kb.id === currentKbId
                      ? "bg-surface-raised font-medium text-foreground"
                      : "text-muted-foreground hover:bg-surface-raised/60 hover:text-foreground",
                  )}
                  title={kb.description || kb.name}
                >
                  <BookMarked className="size-3.5 shrink-0" />
                  <span className="truncate">{kb.name}</span>
                  <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">
                    {kb.documentCount}
                  </span>
                </button>
                <Button
                  variant="danger-ghost"
                  size="icon-sm"
                  className="absolute top-1/2 right-1 -translate-y-1/2 opacity-0 transition-opacity group-hover:opacity-100"
                  aria-label={`Delete ${kb.name}`}
                  onClick={() => onDelete(kb.id)}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="px-2 pt-1 text-[12.5px] leading-relaxed text-muted-foreground">
            Group your PDFs into knowledge bases here.
          </p>
        )}
      </nav>
    </aside>
  );
}
