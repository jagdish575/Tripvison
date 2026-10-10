import type { Category, Itinerary, MissionResult } from "../../types/api";
import { cx, formatClock, formatMoney } from "../../utils/format";
import { CATEGORY_META, CATEGORY_ORDER, MODE_META } from "../../utils/mission";
import { RiskBadge } from "../ui/Badge";

export interface OptionEntry { itinerary: Itinerary; categories: Category[] }

export function optionEntries(result: MissionResult): OptionEntry[] {
  const byId = new Map(result.itineraries.map((i) => [i.id, i]));
  const entries: OptionEntry[] = [];
  for (const cat of CATEGORY_ORDER) {
    const id = result.categories[cat];
    const itin = id ? byId.get(id) : undefined;
    if (!itin) continue;
    const existing = entries.find((e) => e.itinerary.id === itin.id);
    if (existing) existing.categories.push(cat);
    else entries.push({ itinerary: itin, categories: [cat] });
  }
  return entries;
}

export function OptionSwitcher({ entries, selectedId, onSelect }: {
  entries: OptionEntry[]; selectedId: string; onSelect: (id: string) => void;
}) {
  return (
    <div role="tablist" aria-label="Journey options" className={cx("grid grid-cols-2 gap-2", entries.length === 3 && "lg:grid-cols-3", entries.length === 4 && "lg:grid-cols-4", entries.length >= 5 && "lg:grid-cols-5")}>
      {entries.map(({ itinerary: it, categories }) => {
        const active = it.id === selectedId;
        const CatIcon = CATEGORY_META[categories[0]].icon;
        return (
          <button key={it.id} role="tab" type="button" aria-selected={active} aria-controls="journey-detail"
            onClick={() => onSelect(it.id)}
            className={cx(
              "group relative flex flex-col gap-2 rounded-md border p-3.5 text-left transition-[border-color,background-color] duration-150 sm:p-4",
              active ? "border-ink bg-surface shadow-[var(--shadow-float)]" : "border-line bg-surface/70 hover:border-line-strong hover:bg-surface",
            )}>
            {active && <span aria-hidden className="absolute inset-x-3 -top-px h-0.5 rounded-full bg-blue sm:inset-x-4" />}
            <div className="flex items-start justify-between gap-2">
              <span className="text-[12px] font-semibold uppercase tracking-[0.06em] text-ink">
                <CatIcon className="mr-1 inline size-3.5 -translate-y-px" aria-hidden />
                {categories.map((c) => CATEGORY_META[c].label).join(" · ")}
              </span>
              <span className="text-[13px] font-semibold text-muted tnum">{it.scores.overall}</span>
            </div>
            <span className="text-[20px] font-semibold tracking-[-0.02em] text-ink tnum">
              {formatMoney(it.cost.total, it.cost.currency)}
            </span>
            <span className="text-[12.5px] text-muted tnum">
              {MODE_META[it.mode].label} · {it.strategy === "night_before" ? "day before" : "same day"} · at venue{" "}
              {formatClock(it.arrival.venue_arrival)} · {it.arrival.buffer_minutes} min early
            </span>
            <RiskBadge level={it.risk.level} compact className="self-start" />
          </button>
        );
      })}
    </div>
  );
}
