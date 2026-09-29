import { NavLink } from "react-router-dom";

import { ThemeToggle } from "@/components/layout/ThemeToggle";
import type { Theme } from "@/hooks/useTheme";
import { cn } from "@/lib/utils";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "rounded-md px-2.5 py-1 text-[12.5px] font-medium transition-colors",
    isActive
      ? "bg-surface text-foreground"
      : "text-muted-foreground hover:bg-surface hover:text-foreground",
  );

export function AppHeader({ theme, onToggleTheme }: { theme: Theme; onToggleTheme: () => void }) {
  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b bg-background px-4">
      <div className="flex items-center gap-4">
        <div className="flex items-baseline gap-2.5">
          <span className="text-[15px] font-semibold tracking-tight">Creo</span>
          <span className="hidden text-[12px] text-muted-foreground sm:inline">Agent Workspace</span>
        </div>
        <nav className="flex items-center gap-1">
          <NavLink to="/" end className={linkClass}>
            Chat
          </NavLink>
          <NavLink to="/knowledge" className={linkClass}>
            Knowledge
          </NavLink>
        </nav>
      </div>
      <ThemeToggle theme={theme} onToggle={onToggleTheme} />
    </header>
  );
}
