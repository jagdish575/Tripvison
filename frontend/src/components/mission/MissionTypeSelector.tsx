import { useRef, type KeyboardEvent } from "react";
import type { MissionType } from "../../types/api";
import { cx } from "../../utils/format";
import { MISSION_TYPES } from "../../utils/mission";

export function MissionTypeSelector({ value, onChange }: { value: MissionType; onChange: (v: MissionType) => void }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const onKey = (e: KeyboardEvent, index: number) => {
    const map: Record<string, number> = { ArrowRight: 1, ArrowDown: 3, ArrowLeft: -1, ArrowUp: -3 };
    const step = map[e.key];
    if (step === undefined) return;
    e.preventDefault();
    const next = (index + step + MISSION_TYPES.length) % MISSION_TYPES.length;
    onChange(MISSION_TYPES[next].id);
    refs.current[next]?.focus();
  };

  return (
    <div role="radiogroup" aria-label="Mission type" className="grid grid-cols-3 gap-2">
      {MISSION_TYPES.map((m, i) => {
        const active = m.id === value;
        const Icon = m.icon;
        return (
          <button
            key={m.id}
            ref={(el) => { refs.current[i] = el; }}
            type="button"
            role="radio"
            aria-checked={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(m.id)}
            onKeyDown={(e) => onKey(e, i)}
            className={cx(
              "group flex h-[68px] flex-col items-start justify-between rounded-sm border px-3 py-2.5 text-left transition-colors",
              active
                ? "border-ink bg-ink text-white"
                : "border-line-strong bg-surface text-fg hover:border-subtle",
            )}
          >
            <Icon className={cx("size-[18px]", active ? "text-amber" : "text-muted group-hover:text-fg")} strokeWidth={1.8} aria-hidden />
            <span className="text-[13.5px] font-medium">{m.label}</span>
          </button>
        );
      })}
    </div>
  );
}
