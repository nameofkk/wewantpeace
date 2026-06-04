"use client";

import { Bold, Italic, Link, Quote, List } from "lucide-react";
import { useAppStore } from "@/lib/store";

interface MarkdownToolbarProps {
  textareaRef: React.RefObject<HTMLTextAreaElement>;
  onContentChange: (value: string) => void;
}

function insertAtCursor(
  textarea: HTMLTextAreaElement,
  before: string,
  after: string,
  placeholder: string,
  onContentChange: (value: string) => void,
) {
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const selected = textarea.value.substring(start, end);
  const text = selected || placeholder;
  const newValue =
    textarea.value.substring(0, start) +
    before +
    text +
    after +
    textarea.value.substring(end);

  // Update React state directly
  onContentChange(newValue);

  // Set cursor position after React re-render
  requestAnimationFrame(() => {
    const cursorPos = start + before.length + text.length;
    textarea.setSelectionRange(cursorPos, cursorPos);
    textarea.focus();
  });
}

function insertAtLineStart(
  textarea: HTMLTextAreaElement,
  prefix: string,
  placeholder: string,
  onContentChange: (value: string) => void,
) {
  const start = textarea.selectionStart;
  const textBefore = textarea.value.substring(0, start);
  const lineStart = textBefore.lastIndexOf("\n") + 1;
  const lineEnd = textarea.value.indexOf("\n", start);
  const currentLine = textarea.value.substring(
    lineStart,
    lineEnd === -1 ? textarea.value.length : lineEnd,
  );
  const text = currentLine.trim() || placeholder;
  const newValue =
    textarea.value.substring(0, lineStart) +
    prefix +
    text +
    textarea.value.substring(lineEnd === -1 ? textarea.value.length : lineEnd);

  // Update React state directly
  onContentChange(newValue);

  // Set cursor position after React re-render
  requestAnimationFrame(() => {
    const cursorPos = lineStart + prefix.length + text.length;
    textarea.setSelectionRange(cursorPos, cursorPos);
    textarea.focus();
  });
}

const BTN_CLASS =
  "p-1.5 rounded-lg hover:bg-muted/50 text-muted-foreground hover:text-foreground transition-colors";

export default function MarkdownToolbar({
  textareaRef,
  onContentChange,
}: MarkdownToolbarProps) {
  const lang = useAppStore((s) => s.lang);
  const txt = lang === "ko" ? "텍스트" : "text";
  const quote = lang === "ko" ? "인용문" : "quote";
  const list = lang === "ko" ? "목록" : "list";

  return (
    <div className="flex items-center gap-1 px-2 py-1.5 border-b border-border">
      <button
        type="button"
        className={BTN_CLASS}
        title="Bold"
        onClick={() => {
          if (textareaRef.current)
            insertAtCursor(textareaRef.current, "**", "**", txt, onContentChange);
        }}
      >
        <Bold size={18} />
      </button>
      <button
        type="button"
        className={BTN_CLASS}
        title="Italic"
        onClick={() => {
          if (textareaRef.current)
            insertAtCursor(textareaRef.current, "*", "*", txt, onContentChange);
        }}
      >
        <Italic size={18} />
      </button>
      <button
        type="button"
        className={BTN_CLASS}
        title="Link"
        onClick={() => {
          if (textareaRef.current)
            insertAtCursor(textareaRef.current, "[", "](url)", txt, onContentChange);
        }}
      >
        <Link size={18} />
      </button>
      <button
        type="button"
        className={BTN_CLASS}
        title="Quote"
        onClick={() => {
          if (textareaRef.current)
            insertAtLineStart(textareaRef.current, "> ", quote, onContentChange);
        }}
      >
        <Quote size={18} />
      </button>
      <button
        type="button"
        className={BTN_CLASS}
        title="List"
        onClick={() => {
          if (textareaRef.current)
            insertAtLineStart(textareaRef.current, "- ", list, onContentChange);
        }}
      >
        <List size={18} />
      </button>
    </div>
  );
}
