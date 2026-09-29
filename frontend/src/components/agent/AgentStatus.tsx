import { Spinner } from "@/components/ui/spinner";
import { useI18n } from "@/hooks/useI18n";

/**
 * High-level agent status only — no private chain-of-thought is ever shown
 * (DESIGN.md §5).
 */
export function AgentStatus({ runningTool }: { runningTool?: string }) {
  const { t } = useI18n();

  return (
    <div className="animate-fade-in flex items-center gap-2 py-1 text-[13px] text-muted-foreground">
      <Spinner className="size-3.5" />
      <span>{runningTool ? t("agent.running", { tool: runningTool }) : t("agent.thinking")}</span>
    </div>
  );
}
