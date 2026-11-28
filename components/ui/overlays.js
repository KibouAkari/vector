"use client";
import * as Dialog from "@radix-ui/react-dialog";
import * as Popover from "@radix-ui/react-popover";
import { X } from "lucide-react";
export { Dialog, Popover };
export function DialogPanel({
  title,
  description,
  children,
  className = "",
  onCloseAutoFocus,
  onEscapeKeyDown,
}) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="vector-dialog-overlay" />
      <Dialog.Content
        className={"vector-dialog " + className}
        onCloseAutoFocus={onCloseAutoFocus}
        onEscapeKeyDown={onEscapeKeyDown}
      >
        <header className="vector-dialog-header">
          <div>
            <Dialog.Title>{title}</Dialog.Title>
            {description && (
              <Dialog.Description>{description}</Dialog.Description>
            )}
          </div>
          <Dialog.Close className="vc-icon-button" aria-label="Close dialog">
            <X size={18} />
          </Dialog.Close>
        </header>
        {children}
      </Dialog.Content>
    </Dialog.Portal>
  );
}
export function PopoverPanel({ children, label, className = "", ...props }) {
  return (
    <Popover.Portal>
      <Popover.Content
        aria-label={label}
        className={"vector-popover " + className}
        sideOffset={10}
        collisionPadding={12}
        align="end"
        {...props}
      >
        {children}
      </Popover.Content>
    </Popover.Portal>
  );
}
