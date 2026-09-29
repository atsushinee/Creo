import { CircleAlert, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";

export function ErrorBanner({ error, onDismiss }: { error: string; onDismiss: () => void }) {
  const { t } = useI18n();

  return (
    <div className="px-4 pb-2">
      <div className="mx-auto flex max-w-3xl items-start gap-2 rounded-lg border border-error/40 bg-error/8 px-3 py-2 text-[13px] text-foreground">
        <CircleAlert className="mt-0.5 size-4 shrink-0 text-error" />
        <p className="min-w-0 flex-1 break-words">{error}</p>
        <Button variant="ghost" size="icon-sm" aria-label={t("error.dismiss")} onClick={onDismiss}>
          <X className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}
