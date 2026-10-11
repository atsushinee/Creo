import { memo, useMemo } from "react";
import type { ComponentPropsWithoutRef } from "react";
import ReactMarkdown, { defaultUrlTransform, type Components } from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";

import { CodeBlock } from "@/components/chat/CodeBlock";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

function isBlockCode(className: string | undefined): boolean {
  return typeof className === "string" && className.includes("language-");
}

function Code({ className, children }: ComponentPropsWithoutRef<"code">) {
  if (isBlockCode(className)) {
    return <code className={className}>{children}</code>;
  }
  return (
    <code className="rounded bg-surface px-1 py-0.5 font-mono text-[0.9em]">{children}</code>
  );
}

function Anchor({ children, href, ...props }: ComponentPropsWithoutRef<"a">) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-primary underline decoration-primary/40 underline-offset-2 hover:decoration-primary"
      {...props}
    >
      {children}
    </a>
  );
}

function Table({ children }: ComponentPropsWithoutRef<"table">) {
  return (
    <div className="my-3 overflow-x-auto rounded-lg border">
      <table className="w-full border-collapse text-[13px]">{children}</table>
    </div>
  );
}

/** Standalone `[N]` / `[N, page P]` citation marker: not a link target, not a
 * reference definition. Models do not always follow the exact `[N]` format the
 * tools request — the "page P" variant is common, so parse it tolerantly and
 * carry the inline page through to the caller. */
const CITATION_RE = /(?<!\])\[(\d{1,2})(?:\s*,\s*page\s*(\d{1,3}))?\](?![:(])/gi;
const FENCE_SPLIT_RE = /(```[\s\S]*?(?:```|$))/g;

/** Allow the internal `cite://N[/P]` scheme through; defaultUrlTransform would
 * strip it to an empty href (making citation clicks navigate to the current page). */
function urlTransform(url: string): string {
  return url.startsWith("cite://") ? url : defaultUrlTransform(url);
}

/**
 * Rewrite citation markers into `cite://N[/P]` links so the custom anchor
 * component can make them clickable. Brackets are escaped so the marker text
 * still renders as `[N]`; fenced code blocks are left untouched.
 */
function linkifyCitations(content: string): string {
  return content
    .split(FENCE_SPLIT_RE)
    .map((segment, index) =>
      index % 2 === 1
        ? segment
        : segment.replace(CITATION_RE, (_match, num: string, page?: string) =>
            page
              ? `\\[${num}, page ${page}\\](cite://${num}/${page})`
              : `\\[${num}\\](cite://${num})`,
          ),
    )
    .join("");
}

const baseComponents: Components = {
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
  code: Code,
  a: Anchor,
  table: Table,
  th: ({ children }) => (
    <th className="border-b px-3 py-1.5 text-left font-medium">{children}</th>
  ),
  td: ({ children }) => <td className="border-b px-3 py-1.5 align-top">{children}</td>,
  p: ({ children }) => <p className="my-2.5 first:mt-0 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="my-2.5 list-disc space-y-1 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="my-2.5 list-decimal space-y-1 pl-5">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  h1: ({ children }) => <h1 className="mt-5 mb-2 text-[1.35em] font-semibold first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mt-5 mb-2 text-[1.2em] font-semibold first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mt-4 mb-1.5 text-[1.08em] font-semibold first:mt-0">{children}</h3>,
  h4: ({ children }) => <h4 className="mt-4 mb-1.5 font-semibold first:mt-0">{children}</h4>,
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-2 pl-3 text-muted-foreground">{children}</blockquote>
  ),
  hr: () => <hr className="my-4 border-t" />,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
};

/** Renders assistant markdown content (GFM + restrained code highlighting).
 * With `onCitation`, `[N]` / `[N, page P]` markers produced by the knowledge
 * tools become clickable and report the citation number (plus the inline page
 * when present) to the caller. */
export const MarkdownRenderer = memo(function MarkdownRenderer({
  content,
  className,
  onCitation,
}: {
  content: string;
  className?: string;
  onCitation?: (citation: number, inlinePage: number | null) => void;
}) {
  const { t } = useI18n();
  const components = useMemo<Components>(() => {
    if (!onCitation) {
      return baseComponents;
    }
    return {
      ...baseComponents,
      a: ({ children, href, ...props }) => {
        const match = typeof href === "string" ? /^cite:\/\/(\d+)(?:\/(\d+))?$/.exec(href) : null;
        if (match) {
          return (
            <button
              type="button"
              onClick={() =>
                onCitation(Number(match[1]), match[2] ? Number(match[2]) : null)
              }
              title={t("chat.citeJump")}
              aria-label={t("chat.citeJump")}
              className="cursor-pointer rounded-sm bg-surface px-0.5 font-medium text-primary transition-colors hover:bg-primary/10"
            >
              {children}
            </button>
          );
        }
        return <Anchor href={href} {...props}>{children}</Anchor>;
      },
    };
  }, [onCitation, t]);

  return (
    <div className={cn("min-w-0 break-words", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={components}
        urlTransform={urlTransform}
      >
        {onCitation ? linkifyCitations(content) : content}
      </ReactMarkdown>
    </div>
  );
});
