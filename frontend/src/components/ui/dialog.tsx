import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  ariaLabel: string;
  children: ReactNode;
  /** Overrides the default panel width (e.g. `max-w-4xl` for wide dialogs). */
  className?: string;
}

/**
 * Design-token modal (DESIGN.md §2): token colors, 12px radius, one soft
 * shadow, fade-in. Closes on Escape and backdrop click.
 */
export function Modal({ open, onClose, ariaLabel, children, className }: ModalProps) {
  useEffect(() => {
    if (!open) {
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) {
    return null;
  }
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 animate-fade-in"
      role="presentation"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        className={cn("w-full max-w-md rounded-xl border bg-background p-4 shadow-lg", className)}
        onClick={(event) => event.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Modal open={open} onClose={onCancel} ariaLabel={title}>
      <h2 className="text-[14px] font-semibold">{title}</h2>
      {description && (
        <p className="pt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">{description}</p>
      )}
      <div className="flex justify-end gap-2 pt-4">
        <Button variant="outline" size="sm" onClick={onCancel}>
          {cancelLabel}
        </Button>
        <Button
          size="sm"
          className={danger ? "bg-error text-white hover:opacity-90" : ""}
          onClick={onConfirm}
        >
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}

interface PromptDialogProps {
  title: string;
  placeholder?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: (value: string) => void;
  onCancel: () => void;
}

/**
 * Render conditionally (`{creating && <PromptDialog …/>}`): unmounting
 * resets the input, so no state-reset effect is needed.
 */
export function PromptDialog({
  title,
  placeholder,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
}: PromptDialogProps) {
  const [value, setValue] = useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }
    onConfirm(trimmed);
  };

  return (
    <Modal open onClose={onCancel} ariaLabel={title}>
      <h2 className="text-[14px] font-semibold">{title}</h2>
      <input
        autoFocus
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            submit();
          }
        }}
        placeholder={placeholder}
        className="mt-3 w-full rounded-md border bg-background px-2.5 py-2 text-[13px] outline-none placeholder:text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring"
      />
      <div className="flex justify-end gap-2 pt-4">
        <Button variant="outline" size="sm" onClick={onCancel}>
          {cancelLabel}
        </Button>
        <Button size="sm" disabled={!value.trim()} onClick={submit}>
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
