import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";

export function EmptyState({ onSend }: { onSend: (text: string) => void }) {
  const { t } = useI18n();
  const suggestions = [t("empty.suggestion1"), t("empty.suggestion2"), t("empty.suggestion3")];

  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-4 pb-10">
      <div className="flex items-center gap-2.5">
        <Sparkles className="size-5 text-primary" strokeWidth={1.75} />
        <h1 className="text-2xl font-semibold tracking-tight">Creo</h1>
      </div>
      <p className="mt-2 text-[13.5px] text-muted-foreground">{t("empty.tagline")}</p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
        {suggestions.map((suggestion) => (
          <Button key={suggestion} variant="outline" size="sm" onClick={() => onSend(suggestion)}>
            {suggestion}
          </Button>
        ))}
      </div>
    </div>
  );
}
