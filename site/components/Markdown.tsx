import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function Markdown({ source }: { source: string }) {
  return (
    <article className="prose prose-sm max-w-none dark:prose-invert prose-headings:tracking-tight prose-a:text-accent prose-code:font-mono prose-code:before:content-none prose-code:after:content-none prose-pre:bg-[var(--code-bg)] prose-pre:text-[var(--ink)] prose-table:text-xs">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{source}</ReactMarkdown>
    </article>
  );
}
