import { Minus, Plus } from "lucide-react";
import { useId, type KeyboardEvent, type ReactNode } from "react";
import { cx } from "../../utils/format";

/** Accessible single-choice segmented control (radiogroup). */
export function Segmented<T extends string | number>({
  label, value, options, onChange, className,
}: {
  label: string; value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; className?: string;
}) {
  const id = useId();
  const onKey = (e: KeyboardEvent, index: number) => {
    const dir = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!dir) return;
    e.preventDefault();
    const next = options[(index + dir + options.length) % options.length];
    onChange(next.value);
    document.getElementById(`${id}-${String(next.value)}`)?.focus();
  };
  return (
    <div role="radiogroup" aria-label={label} className={cx("inline-flex rounded-sm border border-line-strong bg-surface p-0.5", className)}>
      {options.map((opt, i) => {
        const active = opt.value === value;
        return (
          <button
            key={String(opt.value)}
            id={`${id}-${String(opt.value)}`}
            type="button"
            role="radio"
            aria-checked={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(opt.value)}
            onKeyDown={(e) => onKey(e, i)}
            className={cx(
              "h-9 min-w-0 flex-1 rounded-[3px] px-1.5 text-[13px] font-medium leading-tight transition-colors tnum sm:min-w-max sm:whitespace-nowrap sm:px-3",
              active ? "bg-ink text-white" : "text-muted hover:text-fg hover:bg-paper-2",
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

export function Toggle({ checked, onChange, label, description, disabled }: {
  checked: boolean; onChange: (v: boolean) => void; label: string; description?: ReactNode; disabled?: boolean;
}) {
  const id = useId();
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <label htmlFor={id} className="text-[14px] font-medium text-fg">{label}</label>
        {description && <p className="text-[13px] text-muted">{description}</p>}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cx(
          "relative mt-0.5 h-6 w-10 shrink-0 rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-50",
          checked ? "bg-blue" : "bg-line-strong",
        )}
      >
        <span
          className={cx(
            "absolute left-0.5 top-0.5 size-5 rounded-full bg-white shadow-sm transition-transform duration-150",
            checked ? "translate-x-4" : "translate-x-0",
          )}
        />
      </button>
    </div>
  );
}

export function Stepper({ value, min, max, onChange, label }: {
  value: number; min: number; max: number; onChange: (v: number) => void; label: string;
}) {
  return (
    <div className="inline-flex h-11 items-center rounded-sm border border-line-strong bg-surface" role="group" aria-label={label}>
      <button type="button" aria-label={`Decrease ${label}`} disabled={value <= min} onClick={() => onChange(value - 1)}
        className="grid h-full w-10 place-items-center text-muted hover:text-fg disabled:opacity-40">
        <Minus className="size-4" aria-hidden />
      </button>
      <output aria-live="polite" className="w-10 text-center text-[15px] font-semibold tnum">{value}</output>
      <button type="button" aria-label={`Increase ${label}`} disabled={value >= max} onClick={() => onChange(value + 1)}
        className="grid h-full w-10 place-items-center text-muted hover:text-fg disabled:opacity-40">
        <Plus className="size-4" aria-hidden />
      </button>
    </div>
  );
}

export function SectionHeading({ eyebrow, title, description, className, as: Tag = "h2" }: {
  eyebrow?: string; title: ReactNode; description?: ReactNode; className?: string; as?: "h2" | "h3";
}) {
  return (
    <div className={className}>
      {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
      <Tag className={cx("display", Tag === "h2" ? "text-[30px] leading-[1.15] sm:text-[36px]" : "text-[24px] leading-tight")}>{title}</Tag>
      {description && <p className="mt-2 max-w-2xl text-[15px] text-muted">{description}</p>}
    </div>
  );
}
