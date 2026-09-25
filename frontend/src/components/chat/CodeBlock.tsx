import { Check, Copy } from "lucide-react";
import { isValidElement, type ReactNode, useRef, useState } from "react";

function extractLanguage(children: ReactNode): string {
  if (isValidElement<{ className?: string }>(children)) {
    const match = /language-([\w-]+)/.exec(children.props.className ?? "");
    return match?.[1] ?? "";
  }
  return "";
}

/**
 * Fenced code block: language label + copy button (DESIGN.md §7).
 * Receives the <code> element rendered by react-markdown.
 */
export function CodeBlock({ children }: { children?: ReactNode }) {
  const preRef = useRef<HTMLPreElement>(null);
  const [copied, setCopied] = useState(false);
  const language = extractLanguage(children);

  const copy = async () => {
    const text = preRef.current?.innerText ?? "";
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard unavailable (e.g. insecure context) — ignore.
    }
  };

  return (
    <div className="my-3 overflow-hidden rounded-lg border bg-surface text-[12.5px]">
      <div className="flex items-center justify-between border-b px-3 py-1.5">
        <span className="font-mono text-[11px] tracking-wider text-muted-foreground uppercase">
          {language || "text"}
        </span>
        <button
          type="button"
          onClick={copy}
          className="flex cursor-pointer items-center gap-1 rounded-md px-1.5 py-0.5 text-[11.5px] text-muted-foreground transition-colors hover:bg-surface-raised/60 hover:text-foreground"
          aria-label="Copy code"
        >
          {copied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre ref={preRef} className="overflow-x-auto p-3.5 font-mono leading-relaxed">
        {children}
      </pre>
    </div>
  );
}
