/**
 * Lightweight regex-based markdown parser.
 * XSS-safe: HTML entities are escaped FIRST, then markdown is applied.
 */

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function processInline(line: string): string {
  // Bold: **text**
  line = line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  // Italic: *text* (but not inside already-processed bold tags)
  line = line.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");
  // Links: [text](url)
  line = line.replace(
    /\[(.+?)\]\((.+?)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer" class="text-blue-400 underline">$1</a>'
  );
  return line;
}

export function renderMarkdown(text: string): string {
  // Step 1: Escape HTML entities for XSS protection
  const escaped = escapeHtml(text);

  // Step 2: Split into paragraphs by double newline
  const paragraphs = escaped.split(/\n\n+/);

  const rendered = paragraphs.map((paragraph) => {
    // Horizontal rule
    if (/^-{3,}$/.test(paragraph.trim())) {
      return '<hr class="my-4 border-t border-border">';
    }

    const lines = paragraph.split("\n");
    const processedLines: string[] = [];
    let inList = false;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // Blockquote: lines starting with "> "
      if (line.startsWith("&gt; ")) {
        if (inList) {
          processedLines.push("</ul>");
          inList = false;
        }
        const content = processInline(line.slice(5)); // "&gt; " is 5 chars
        processedLines.push(
          `<blockquote class="border-l-2 border-muted-foreground/30 pl-3 text-muted-foreground italic">${content}</blockquote>`
        );
        continue;
      }

      // List item: lines starting with "- "
      if (line.startsWith("- ")) {
        if (!inList) {
          processedLines.push('<ul class="list-disc pl-4 space-y-1">');
          inList = true;
        }
        const content = processInline(line.slice(2));
        processedLines.push(`<li>${content}</li>`);
        continue;
      }

      // Close list if we're no longer in list items
      if (inList) {
        processedLines.push("</ul>");
        inList = false;
      }

      // Regular line with inline formatting
      processedLines.push(processInline(line));
    }

    // Close any open list
    if (inList) {
      processedLines.push("</ul>");
    }

    // Join lines within a paragraph with <br> for single newlines
    // But don't add <br> between block elements (ul, blockquote, li)
    const result: string[] = [];
    for (let i = 0; i < processedLines.length; i++) {
      const current = processedLines[i];
      result.push(current);

      if (i < processedLines.length - 1) {
        const next = processedLines[i + 1];
        const isCurrentBlock =
          current.startsWith("<ul") ||
          current.startsWith("</ul>") ||
          current.startsWith("<li") ||
          current.startsWith("<blockquote");
        const isNextBlock =
          next.startsWith("<ul") ||
          next.startsWith("</ul>") ||
          next.startsWith("<li") ||
          next.startsWith("<blockquote");

        if (!isCurrentBlock && !isNextBlock) {
          result.push("<br>");
        }
      }
    }

    return result.join("");
  });

  // Join paragraphs — hr stays unwrapped, others get <p>
  return rendered
    .map((p) => p.startsWith("<hr") ? p : `<p>${p}</p>`)
    .join("");
}
