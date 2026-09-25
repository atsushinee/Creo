import { ThemeToggle } from "@/components/layout/ThemeToggle";
import type { Theme } from "@/hooks/useTheme";

export function AppHeader({ theme, onToggleTheme }: { theme: Theme; onToggleTheme: () => void }) {
  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b bg-background px-4">
      <div className="flex items-baseline gap-2.5">
        <span className="text-[15px] font-semibold tracking-tight">Creo</span>
        <span className="hidden text-[12px] text-muted-foreground sm:inline">Agent Workspace</span>
      </div>
      <ThemeToggle theme={theme} onToggle={onToggleTheme} />
    </header>
  );
}
