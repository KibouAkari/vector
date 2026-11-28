"use client";
// Adapted from Prompt Kit prompt-input, MIT © 2025 Julien Thibeaut.
// See licenses/prompt-kit.MIT.txt and docs/UI_REFERENCES.md for the pinned source.
import { useLayoutEffect } from "react";
import { submitsOnEnter } from "../../lib/chat-presentation.mjs";
export default function PromptInput({
  value,
  onValueChange,
  textareaRef,
  blocked = false,
  attachments,
  children,
}) {
  useLayoutEffect(() => {
    const input = textareaRef.current;
    if (!input) return;
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 180) + "px";
  }, [value, textareaRef]);
  return (
    <div className="vc-prompt-input">
      {attachments}
      <textarea
        ref={textareaRef}
        rows={1}
        value={value}
        aria-label="Message Vector"
        placeholder="Message Vector…"
        onChange={(event) => onValueChange(event.target.value)}
        onKeyDown={(event) => {
          if (submitsOnEnter(event)) {
            event.preventDefault();
            if (!blocked) event.currentTarget.form?.requestSubmit();
          }
        }}
      />
      <div className="vc-prompt-actions">{children}</div>
    </div>
  );
}
