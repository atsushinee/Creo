import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";

const SUGGESTIONS = ["你好", "计算 123 * 456", "What can you help me with?"];

export function EmptyState({ onSend }: { onSend: (text: string) => void }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-4 pb-10">
      <div className="flex items-center gap-2.5">
        <Sparkles className="size-5 text-primary" strokeWidth={1.75} />
        <h1 className="text-2xl font-semibold tracking-tight">Creo</h1>
      </div>
      <p className="mt-2 text-[13.5px] text-muted-foreground">
        An agentic workspace for creative work.
      </p>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
        {SUGGESTIONS.map((suggestion) => (
          <Button key={suggestion} variant="outline" size="sm" onClick={() => onSend(suggestion)}>
            {suggestion}
          </Button>
        ))}
      </div>
    </div>
  );
}
