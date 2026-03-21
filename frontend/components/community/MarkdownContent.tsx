"use client";

import DOMPurify from "dompurify";
import { renderMarkdown } from "@/lib/markdown";

interface MarkdownContentProps {
  content: string;
  className?: string;
}

export default function MarkdownContent({
  content,
  className = "",
}: MarkdownContentProps) {
  const html = renderMarkdown(content);

  return (
    <div
      className={`text-sm leading-relaxed [&_strong]:font-bold [&_em]:italic [&_a]:text-blue-400 [&_a]:underline [&_blockquote]:border-l-2 [&_blockquote]:border-muted-foreground/30 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground [&_blockquote]:italic [&_ul]:list-disc [&_ul]:pl-4 [&_ul]:space-y-1 [&_p]:mb-2 [&_p:last-child]:mb-0 [&_hr]:my-4 [&_hr]:border-t [&_hr]:border-border ${className}`}
      dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }}
    />
  );
}
