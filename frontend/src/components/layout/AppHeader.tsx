import { NavLink } from "react-router-dom";

import { LangToggle } from "@/components/layout/LangToggle";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import type { Theme } from "@/hooks/useTheme";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "rounded-md px-2.5 py-1 text-[12.5px] font-medium transition-colors",
    isActive
      ? "bg-surface text-foreground"
      : "text-muted-foreground hover:bg-surface hover:text-foreground",
  );

export function AppHeader({ theme, onToggleTheme }: { theme: Theme; onToggleTheme: () => void }) {
  const { t } = useI18n();

  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b bg-background px-4">
      <div className="flex items-center gap-4">
        <div className="flex items-baseline gap-2.5">
          <span className="text-[15px] font-semibold tracking-tight">Creo</span>
          <span className="hidden text-[12px] text-muted-foreground sm:inline">
            {t("header.subtitle")}
          </span>
        </div>
        <nav className="flex items-center gap-1">
          <NavLink to="/" end className={linkClass}>
            {t("nav.chat")}
          </NavLink>
          <NavLink to="/knowledge" className={linkClass}>
            {t("nav.knowledge")}
          </NavLink>
          <NavLink to="/knowledge/recall" className={linkClass}>
            {t("nav.recall")}
          </NavLink>
        </nav>
      </div>
      <div className="flex items-center gap-1.5">
        <LangToggle />
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      </div>
    </header>
  );
}
