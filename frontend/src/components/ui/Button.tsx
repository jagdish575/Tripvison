import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Link, type LinkProps } from "react-router-dom";
import { cx } from "../../utils/format";

type Variant = "primary" | "secondary" | "ghost" | "inverse";
type Size = "sm" | "md" | "lg";

const base =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-semibold tracking-[-0.005em] rounded-[10px] " +
  "transition-[background-color,background-position,border-color,color,transform,box-shadow] duration-300 ease-out active:translate-y-px " +
  "disabled:cursor-not-allowed disabled:opacity-55 disabled:active:translate-y-0 disabled:hover:translate-y-0 select-none";

const variants: Record<Variant, string> = {
  primary: "bg-night btn-shine text-white bg-[position:0%_50%] hover:bg-[position:100%_50%] hover:-translate-y-0.5 " +
    "shadow-[var(--shadow-glow)] hover:shadow-[0_14px_34px_-10px_rgb(240_100_63_/_0.55)]",
  secondary: "bg-surface text-fg border border-line-strong hover:border-coral/40 hover:bg-coral-wash hover:-translate-y-0.5",
  ghost: "text-fg hover:bg-paper-2",
  inverse: "bg-white text-ink btn-shine hover:-translate-y-0.5 shadow-[0_10px_30px_-12px_rgb(0_0_0_/_0.45)]",
};

const sizes: Record<Size, string> = {
  sm: "h-9 px-3 text-[13px]",
  md: "h-11 px-4 text-[14px]",
  lg: "h-12 px-6 text-[15px]",
};

export function buttonClass(variant: Variant = "primary", size: Size = "md", extra?: string) {
  return cx(base, variants[variant], sizes[size], extra);
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, icon, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button ref={ref} className={buttonClass(variant, size, className)} disabled={disabled || loading} {...rest}>
      {loading ? (
        <span aria-hidden className="size-4 animate-spin rounded-full border-2 border-current border-r-transparent" />
      ) : (
        icon
      )}
      {children}
    </button>
  );
});

interface ButtonLinkProps extends LinkProps {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
}

export function ButtonLink({ variant = "primary", size = "md", icon, className, children, ...rest }: ButtonLinkProps) {
  return (
    <Link className={buttonClass(variant, size, className as string)} {...rest}>
      {icon}
      {children}
    </Link>
  );
}
