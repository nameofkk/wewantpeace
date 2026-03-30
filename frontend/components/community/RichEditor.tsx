"use client";

import { useRef, useCallback, useEffect, useState } from "react";
import { Bold, Italic, Link as LinkIcon, Quote, List, Minus } from "lucide-react";
import DOMPurify from "dompurify";
import { renderMarkdown } from "@/lib/markdown";
import { useAppStore } from "@/lib/store";

interface RichEditorProps {
  initialValue?: string;
  onChange: (markdown: string) => void;
  placeholder?: string;
}

/* ── HTML → Markdown 변환 ── */
function htmlToMarkdown(el: HTMLElement): string {
  function process(node: Node): string {
    if (node.nodeType === Node.TEXT_NODE) {
      return node.textContent || "";
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return "";

    const element = node as HTMLElement;
    const tag = element.tagName.toLowerCase();
    const kids = Array.from(element.childNodes).map(process).join("");

    switch (tag) {
      case "strong":
      case "b":
        return kids.trim() ? `**${kids}**` : "";
      case "em":
      case "i":
        return kids.trim() ? `*${kids}*` : "";
      case "a": {
        const href = element.getAttribute("href") || "";
        return `[${kids}](${href})`;
      }
      case "blockquote":
        return kids
          .split("\n")
          .filter((l) => l.trim())
          .map((l) => `> ${l}`)
          .join("\n");
      case "ul":
      case "ol":
        return kids;
      case "li":
        return `- ${kids}\n`;
      case "hr":
        return "\n\n---\n\n";
      case "br":
        return "\n";
      case "div":
        return "\n" + kids;
      case "p":
        return "\n\n" + kids;
      default:
        return kids;
    }
  }

  let md = Array.from(el.childNodes).map(process).join("");
  md = md.replace(/\n{3,}/g, "\n\n").trim();
  // clean up empty/whitespace-only bold/italic markers
  md = md.replace(/\*\*\s*\*\*/g, "");
  md = md.replace(/(?<!\*)\*\s*\*(?!\*)/g, "");
  // clean up trailing whitespace per line
  md = md.replace(/ +$/gm, "");
  return md;
}

/* ── 컴포넌트 ── */
const BTN =
  "p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors";
const BTN_ACTIVE =
  "p-1.5 rounded-lg text-primary bg-primary/10 transition-colors";

export default function RichEditor({
  initialValue,
  onChange,
  placeholder = "",
}: RichEditorProps) {
  const editorRef = useRef<HTMLDivElement>(null);
  const loaded = useRef(false);
  const [isEmpty, setIsEmpty] = useState(true);
  const [activeFormats, setActiveFormats] = useState<Set<string>>(new Set());

  // 초기값 세팅 (한 번만)
  useEffect(() => {
    if (!editorRef.current || loaded.current) return;
    if (initialValue && initialValue.trim()) {
      const html = renderMarkdown(initialValue);
      editorRef.current.innerHTML = DOMPurify.sanitize(html);
      setIsEmpty(false);
      loaded.current = true;
      // 초기값도 onChange로 전달
      onChange(initialValue);
    }
  }, [initialValue, onChange]);

  const syncMarkdown = useCallback(() => {
    if (!editorRef.current) return;
    const text = editorRef.current.innerText?.trim() || "";
    setIsEmpty(!text);
    const md = htmlToMarkdown(editorRef.current);
    onChange(md);
  }, [onChange]);

  const checkFormats = useCallback(() => {
    const formats = new Set<string>();
    if (document.queryCommandState("bold")) formats.add("bold");
    if (document.queryCommandState("italic")) formats.add("italic");
    if (document.queryCommandState("insertUnorderedList"))
      formats.add("list");
    // blockquote check
    const sel = window.getSelection();
    if (sel && sel.rangeCount > 0) {
      let node: Node | null = sel.anchorNode;
      while (node && node !== editorRef.current) {
        if (
          node.nodeType === Node.ELEMENT_NODE &&
          (node as HTMLElement).tagName === "BLOCKQUOTE"
        ) {
          formats.add("quote");
          break;
        }
        node = node.parentNode;
      }
    }
    setActiveFormats(formats);
  }, []);

  const handleInput = useCallback(() => {
    syncMarkdown();
    checkFormats();
  }, [syncMarkdown, checkFormats]);

  const exec = useCallback(
    (cmd: string, val?: string) => {
      editorRef.current?.focus();
      document.execCommand(cmd, false, val);
      syncMarkdown();
      checkFormats();
    },
    [syncMarkdown, checkFormats],
  );

  const handleBold = () => exec("bold");
  const handleItalic = () => exec("italic");
  const handleList = () => exec("insertUnorderedList");
  const handleQuote = () => {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    // 현재 blockquote 안에 있으면 해제
    let node: Node | null = sel.anchorNode;
    let inQuote = false;
    while (node && node !== editorRef.current) {
      if (
        node.nodeType === Node.ELEMENT_NODE &&
        (node as HTMLElement).tagName === "BLOCKQUOTE"
      ) {
        inQuote = true;
        break;
      }
      node = node.parentNode;
    }
    if (inQuote) {
      exec("formatBlock", "p");
    } else {
      exec("formatBlock", "blockquote");
    }
  };
  const handleDivider = () => {
    editorRef.current?.focus();
    document.execCommand("insertHTML", false, '<hr>');
    syncMarkdown();
    checkFormats();
  };
  const lang = useAppStore((s) => s.lang);
  const handleLink = () => {
    const sel = window.getSelection();
    const selectedText = sel?.toString() || "";
    const url = window.prompt("URL:", "https://");
    if (!url) return;
    if (selectedText) {
      exec("createLink", url);
    } else {
      const linkText = window.prompt(lang === "ko" ? "링크 텍스트:" : "Link text:", "") || url;
      exec(
        "insertHTML",
        `<a href="${DOMPurify.sanitize(url)}" target="_blank" rel="noopener noreferrer">${DOMPurify.sanitize(linkText)}</a>`,
      );
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "b" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleBold();
    } else if (e.key === "i" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleItalic();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const text = e.clipboardData.getData("text/plain");
    document.execCommand("insertText", false, text);
  };

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden focus-within:border-primary transition-colors">
      {/* 툴바 */}
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-border bg-muted/20">
        <button
          type="button"
          className={activeFormats.has("bold") ? BTN_ACTIVE : BTN}
          title="Bold (Ctrl+B)"
          onMouseDown={(e) => {
            e.preventDefault();
            handleBold();
          }}
        >
          <Bold size={18} />
        </button>
        <button
          type="button"
          className={activeFormats.has("italic") ? BTN_ACTIVE : BTN}
          title="Italic (Ctrl+I)"
          onMouseDown={(e) => {
            e.preventDefault();
            handleItalic();
          }}
        >
          <Italic size={18} />
        </button>
        <button
          type="button"
          className={BTN}
          title="Link"
          onMouseDown={(e) => {
            e.preventDefault();
            handleLink();
          }}
        >
          <LinkIcon size={18} />
        </button>
        <button
          type="button"
          className={activeFormats.has("quote") ? BTN_ACTIVE : BTN}
          title="Quote"
          onMouseDown={(e) => {
            e.preventDefault();
            handleQuote();
          }}
        >
          <Quote size={18} />
        </button>
        <button
          type="button"
          className={activeFormats.has("list") ? BTN_ACTIVE : BTN}
          title="List"
          onMouseDown={(e) => {
            e.preventDefault();
            handleList();
          }}
        >
          <List size={18} />
        </button>
        <div className="w-px h-4 bg-border mx-0.5" />
        <button
          type="button"
          className={BTN}
          title="Divider"
          onMouseDown={(e) => {
            e.preventDefault();
            handleDivider();
          }}
        >
          <Minus size={18} />
        </button>
      </div>

      {/* 에디터 */}
      <div className="relative">
        {isEmpty && (
          <div className="absolute top-0 left-0 px-4 py-3 text-sm text-muted-foreground/50 pointer-events-none select-none">
            {placeholder}
          </div>
        )}
        <div
          ref={editorRef}
          contentEditable
          suppressContentEditableWarning
          className="min-h-[200px] px-4 py-3 text-sm outline-none [&_strong]:font-bold [&_em]:italic [&_a]:text-blue-400 [&_a]:underline [&_blockquote]:border-l-2 [&_blockquote]:border-muted-foreground/30 [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground [&_blockquote]:italic [&_blockquote]:my-1 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:space-y-0.5 [&_li]:text-sm [&_p]:min-h-[1.25em] [&_hr]:my-3 [&_hr]:border-t [&_hr]:border-border"
          onInput={handleInput}
          onKeyDown={handleKeyDown}
          onKeyUp={checkFormats}
          onMouseUp={checkFormats}
          onPaste={handlePaste}
        />
      </div>
    </div>
  );
}
