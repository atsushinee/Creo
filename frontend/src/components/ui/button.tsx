import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type ButtonVariant = "primary" | "outline" | "ghost" | "danger-ghost";
type ButtonSize = "sm" | "md" | "icon" | "icon-sm";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-40",
  outline: "border bg-background hover:bg-surface disabled:opacity-40",
  ghost: "hover:bg-surface disabled:opacity-40",
  "danger-ghost": "text-muted-foreground hover:bg-error/10 hover:text-error",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-7 rounded-md px-2.5 text-[12.5px]",
  md: "h-8 rounded-lg px-3 text-[13px]",
  icon: "size-8 rounded-lg",
  "icon-sm": "size-6 rounded-md",
};

export function Button({ className, variant = "primary", size = "md", type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex cursor-pointer items-center justify-center gap-1.5 font-medium transition-colors duration-150",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
        "disabled:cursor-not-allowed",
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...props}
    />
  );
}
