import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import type { SessionInfo } from "@/types/agent";

interface AppSidebarProps {
  sessions: SessionInfo[];
  currentSessionId: string | null;
  onSelect: (sessionId: string) => void;
  onNewChat: () => void;
  onDelete: (sessionId: string) => void;
}

export function AppSidebar({ sessions, currentSessionId, onSelect, onNewChat, onDelete }: AppSidebarProps) {
  const { t } = useI18n();

  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r bg-surface md:flex">
      <div className="p-3">
        <Button variant="outline" className="w-full justify-start" onClick={onNewChat}>
          <Plus className="size-4" />
          {t("sidebar.newChat")}
        </Button>
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {sessions.length > 0 ? (
          <>
            <p className="px-1 pt-1 pb-1.5 text-[11px] font-medium tracking-wider text-muted-foreground uppercase">
              {t("sidebar.recent")}
            </p>
            <ul className="space-y-0.5">
              {sessions.map((session) => (
                <li key={session.id} className="group relative">
                  <button
                    type="button"
                    onClick={() => onSelect(session.id)}
                    className={cn(
                      "w-full cursor-pointer truncate rounded-md px-2.5 py-1.5 pr-8 text-left text-[13px] transition-colors",
                      session.id === currentSessionId
                        ? "bg-surface-raised font-medium text-foreground"
                        : "text-muted-foreground hover:bg-surface-raised/60 hover:text-foreground",
                    )}
                    title={session.title}
                  >
                    {session.title}
                  </button>
                  <Button
                    variant="danger-ghost"
                    size="icon-sm"
                    className="absolute top-1/2 right-1 -translate-y-1/2 opacity-0 transition-opacity group-hover:opacity-100"
                    aria-label={`${t("sidebar.delete")}: ${session.title}`}
                    onClick={() => onDelete(session.id)}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="px-2 pt-1 text-[12.5px] leading-relaxed text-muted-foreground">
            {t("sidebar.empty")}
          </p>
        )}
      </nav>
    </aside>
  );
}
