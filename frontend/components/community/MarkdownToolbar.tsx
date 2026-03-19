"use client";

import { Bold, Italic, Link, Quote, List } from "lucide-react";

interface MarkdownToolbarProps {
  textareaRef: React.RefObject<HTMLTextAreaElement>;
  onInsert?: () => void;
}

function insertAtCursor(
  textarea: HTMLTextAreaElement,
  before: string,
  after: string,
  placeholder: string
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
  textarea.value = newValue;
  // Trigger React's onChange
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype,
    "value"
  )?.set;
  nativeInputValueSetter?.call(textarea, newValue);
  const event = new Event("input", { bubbles: true });
  textarea.dispatchEvent(event);
  // Set cursor position
  const cursorPos = start + before.length + text.length;
  textarea.setSelectionRange(cursorPos, cursorPos);
  textarea.focus();
}

function insertAtLineStart(
  textarea: HTMLTextAreaElement,
  prefix: string,
  placeholder: string
) {
  const start = textarea.selectionStart;
  // Find the beginning of the current line
  const textBefore = textarea.value.substring(0, start);
  const lineStart = textBefore.lastIndexOf("\n") + 1;
  const currentLine = textarea.value.substring(
    lineStart,
    textarea.value.indexOf("\n", start) === -1
      ? textarea.value.length
      : textarea.value.indexOf("\n", start)
  );
  const text = currentLine.trim() || placeholder;
  const newValue =
    textarea.value.substring(0, lineStart) +
    prefix +
    text +
    textarea.value.substring(
      textarea.value.indexOf("\n", start) === -1
        ? textarea.value.length
        : textarea.value.indexOf("\n", start)
    );
  // Trigger React's onChange
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype,
    "value"
  )?.set;
  nativeInputValueSetter?.call(textarea, newValue);
  const event = new Event("input", { bubbles: true });
  textarea.dispatchEvent(event);
  // Set cursor position
  const cursorPos = lineStart + prefix.length + text.length;
  textarea.setSelectionRange(cursorPos, cursorPos);
  textarea.focus();
}

const BTN_CLASS =
  "p-1.5 rounded-lg hover:bg-muted/50 text-muted-foreground hover:text-foreground transition-colors";

export default function MarkdownToolbar({
  textareaRef,
  onInsert,
}: MarkdownToolbarProps) {
  function handle(action: () => void) {
    action();
    onInsert?.();
  }

  return (
    <div className="flex items-center gap-1 px-2 py-1.5 border-b border-border">
      <button
        type="button"
        className={BTN_CLASS}
        title="Bold"
        onClick={() =>
          handle(() => {
            if (textareaRef.current)
              insertAtCursor(textareaRef.current, "**", "**", "텍스트");
          })
        }
      >
        <Bold size={18} />
      </button>
      <button
        type="button"
        className={BTN_CLASS}
        title="Italic"
        onClick={() =>
          handle(() => {
            if (textareaRef.current)
              insertAtCursor(textareaRef.current, "*", "*", "텍스트");
          })
        }
      >
        <Italic size={18} />
      </button>
      <button
        type="button"
        className={BTN_CLASS}
        title="Link"
        onClick={() =>
          handle(() => {
            if (textareaRef.current)
              insertAtCursor(
                textareaRef.current,
                "[",
                "](url)",
                "텍스트"
              );
          })
        }
      >
        <Link size={18} />
      </button>
      <button
        type="button"
        className={BTN_CLASS}
        title="Quote"
        onClick={() =>
          handle(() => {
            if (textareaRef.current)
              insertAtLineStart(
                textareaRef.current,
                "> ",
                "인용문"
              );
          })
        }
      >
        <Quote size={18} />
      </button>
      <button
        type="button"
        className={BTN_CLASS}
        title="List"
        onClick={() =>
          handle(() => {
            if (textareaRef.current)
              insertAtLineStart(
                textareaRef.current,
                "- ",
                "목록"
              );
          })
        }
      >
        <List size={18} />
      </button>
    </div>
  );
}
