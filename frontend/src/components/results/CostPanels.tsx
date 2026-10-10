import { motion } from "framer-motion";
import type { Itinerary, MissionResult, SourceType } from "../../types/api";
import { cx, formatMoney } from "../../utils/format";
import { MODE_META, SOURCE_META } from "../../utils/mission";

const SOURCE_TONE: Record<SourceType, string> = {
  live: "border-green/30 bg-green-wash text-green-ink",
  estimated: "border-amber/35 bg-amber-wash text-amber-ink",
  user_provided: "border-blue/25 bg-blue-wash text-blue-ink",
  calculated: "border-line bg-paper-2 text-fg",
};

export function SourceBadge({ source }: { source: SourceType }) {
  return (
    <span title={SOURCE_META[source].hint}
      className={cx("inline-flex h-5 items-center rounded-xs border px-1.5 text-[10px] font-semibold uppercase tracking-[0.08em]", SOURCE_TONE[source])}>
      {SOURCE_META[source].label}
    </span>
  );
}

/** Total trip cost, line by line, each with where the number came from. */
export function CostBreakdownPanel({ itinerary: it }: { itinerary: Itinerary }) {
  const cur = it.cost.currency;
  const remaining = it.cost.budget_remaining;
  return (
    <section aria-labelledby="cost-title" className="card p-5 sm:p-6">
      <div className="flex items-baseline justify-between gap-4">
        <h3 id="cost-title" className="text-[17px] font-semibold tracking-[-0.01em]">Total trip cost</h3>
        <span className="text-[12px] text-muted">Not just the ticket</span>
      </div>
      <ul className="mt-4 divide-y divide-line">
        {it.cost.items.map((item) => (
          <li key={item.key} className="flex items-start justify-between gap-4 py-2.5">
            <div className="min-w-0">
              <p className="flex flex-wrap items-center gap-2 text-[14px] font-medium text-ink">{item.label}<SourceBadge source={item.source} /></p>
              {item.detail && <p className="mt-0.5 text-[12.5px] text-muted tnum">{item.detail}</p>}
            </div>
            <span className="shrink-0 text-[14.5px] font-semibold text-ink tnum">{formatMoney(item.amount, cur)}</span>
          </li>
        ))}
      </ul>
      <div className="mt-2 flex items-center justify-between gap-4 border-t-2 border-ink pt-3">
        <p className="flex items-center gap-2 text-[15px] font-semibold text-ink">Total <SourceBadge source="calculated" /></p>
        <span className="text-[18px] font-semibold text-ink tnum">{formatMoney(it.cost.total, cur)}</span>
      </div>
      {it.cost.budget !== null && (
        <div className="mt-3 flex items-center justify-between text-[13.5px] tnum">
          <span className="text-muted">Budget {formatMoney(it.cost.budget, cur)}</span>
          {remaining !== null && (
            <span className={cx("font-semibold", remaining < 0 ? "text-red-ink" : "text-green-ink")}>
              {remaining < 0 ? `Over by ${formatMoney(-remaining, cur)}` : `${formatMoney(remaining, cur)} remaining`}
            </span>
          )}
        </div>
      )}
    </section>
  );
}

function modeBests(result: MissionResult): Itinerary[] {
  const byId = new Map(result.itineraries.map((i) => [i.id, i]));
  return result.modes.filter((m) => m.available && m.best_id).map((m) => byId.get(m.best_id!)).filter(Boolean) as Itinerary[];
}

/** One bar per travel mode against the user's budget. */
export function BudgetComparison({ result, selectedId, onSelect }: {
  result: MissionResult; selectedId?: string; onSelect: (id: string) => void;
}) {
  const options = modeBests(result);
  const budget = result.mission.budget;
  const cur = result.mission.currency;
  const scale = Math.max(budget, ...options.map((o) => o.cost.total ?? 0)) * 1.08;
  const budgetPct = (budget / scale) * 100;
  return (
    <section aria-labelledby="budget-title" className="card p-5 sm:p-6">
      <p className="eyebrow">Your budget</p>
      <p id="budget-title" className="display mt-1 text-[34px] leading-none tnum">{formatMoney(budget, cur)}</p>
      <p className="mt-2 text-[13px] text-muted">Total trip cost of the best option in each mode — tickets, hotel, ground transport and food.</p>
      <ul className="mt-6 space-y-5">
        {options.map((o, index) => {
          const total = o.cost.total ?? 0;
          const over = total > budget;
          const Icon = MODE_META[o.mode].icon;
          const selected = o.id === selectedId || result.itineraries.find((i) => i.id === selectedId)?.mode === o.mode;
          return (
            <li key={o.id}>
              <button type="button" onClick={() => onSelect(o.id)} className="w-full text-left">
                <div className="flex items-baseline justify-between gap-3">
                  <span className={cx("inline-flex items-center gap-2 text-[14px] font-medium", selected ? "text-ink" : "text-fg")}>
                    <Icon className="size-4 text-muted" aria-hidden />{MODE_META[o.mode].label}
                  </span>
                  <span className="text-[14px] tnum">
                    <span className="font-semibold text-ink">{formatMoney(o.cost.total, cur)}</span>
                    <span className={cx("ml-2 text-[12.5px]", over ? "font-semibold text-red-ink" : "text-muted")}>
                      {over ? `OVER BUDGET by ${formatMoney(total - budget, cur)}` : `${formatMoney(budget - total, cur)} remaining`}
                    </span>
                  </span>
                </div>
                <div className="relative mt-2 h-2 rounded-full bg-paper-2">
                  <motion.div className={cx("h-full rounded-full", over ? "bg-red" : selected ? "bg-ink" : "bg-ink/55")}
                    initial={{ width: 0 }} animate={{ width: `${(total / scale) * 100}%` }}
                    transition={{ duration: 0.7, delay: 0.1 + index * 0.08, ease: [0.22, 1, 0.36, 1] }} />
                  <span aria-hidden className="absolute -top-1 h-4 w-px bg-ink" style={{ left: `${budgetPct}%` }} />
                </div>
              </button>
            </li>
          );
        })}
      </ul>
      <p className="mt-4 text-[11.5px] text-subtle">The thin line marks your budget.</p>
    </section>
  );
}
