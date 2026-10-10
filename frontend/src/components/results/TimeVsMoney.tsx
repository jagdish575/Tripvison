import { motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import type { Itinerary, MissionResult } from "../../types/api";
import { cx, formatMinutes, formatMoney } from "../../utils/format";
import { MODE_META } from "../../utils/mission";
import { RiskBadge } from "../ui/Badge";

const DESKTOP = { W: 520, H: 260, font: 11 };
const PHONE = { W: 340, H: 240, font: 12 };
const PAD = { left: 52, right: 14, top: 16, bottom: 40 };

function usePhone(): boolean {
  const query = "(max-width: 639px)";
  const [phone, setPhone] = useState(() => typeof window !== "undefined" && window.matchMedia?.(query).matches === true);
  useEffect(() => {
    const mq = window.matchMedia?.(query);
    if (!mq) return;
    const update = () => setPhone(mq.matches);
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return phone;
}

function niceMax(value: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(Math.max(value, 1)));
  return Math.ceil(value / magnitude) * magnitude;
}

/** Each travel mode's best journey as a point: total cost (x) against time travelling (y). */
export function TimeVsMoney({ result, selectedId, onSelect }: {
  result: MissionResult; selectedId?: string; onSelect: (id: string) => void;
}) {
  const points = useMemo(() => {
    const byId = new Map(result.itineraries.map((i) => [i.id, i]));
    return result.modes.filter((m) => m.available && m.best_id).map((m) => byId.get(m.best_id!)!)
      .filter((i) => i && i.cost.total !== null);
  }, [result]);
  const [focusId, setFocusId] = useState<string | undefined>(undefined);
  const phone = usePhone();
  if (points.length < 2) return null;
  const { W, H, font } = phone ? PHONE : DESKTOP;

  const cur = result.mission.currency;
  const maxCost = niceMax(Math.max(...points.map((p) => p.cost.total!), result.mission.budget) * 1.05);
  const maxHours = niceMax(Math.max(...points.map((p) => p.total_travel_minutes / 60)) * 1.1);
  const x = (cost: number) => PAD.left + (cost / maxCost) * (W - PAD.left - PAD.right);
  const y = (minutes: number) => H - PAD.bottom - (minutes / 60 / maxHours) * (H - PAD.top - PAD.bottom);
  const selectedMode = result.itineraries.find((i) => i.id === selectedId)?.mode;
  const focus: Itinerary = points.find((p) => p.id === focusId) ?? points.find((p) => p.mode === selectedMode) ?? points[0];
  const delta = result.deltas[focus.id];
  const ticks = phone ? [0, 0.5, 1] : [0, 0.25, 0.5, 0.75, 1];

  return (
    <section aria-labelledby="tvm-title" className="card p-5 sm:p-6">
      <div className="flex items-baseline justify-between gap-4">
        <h3 id="tvm-title" className="text-[17px] font-semibold tracking-[-0.01em]">Time vs money</h3>
        <span className="text-[12px] text-muted">Lower-left is better</span>
      </div>
      {result.tradeoff && <p className="mt-2 text-[14.5px] text-fg tnum">{result.tradeoff.sentence}</p>}

      <svg viewBox={`0 0 ${W} ${H}`} className="mt-4 w-full" role="img"
        aria-label={`Scatter of total cost against travel time for ${points.length} travel modes`}>
        {ticks.map((t) => (
          <g key={`x${t}`}>
            <line x1={x(maxCost * t)} x2={x(maxCost * t)} y1={PAD.top} y2={H - PAD.bottom} stroke="#e2e8f0" />
            <text x={x(maxCost * t)} y={H - PAD.bottom + 18} textAnchor={t === 0 ? "start" : t === 1 ? "end" : "middle"} fontSize={font} fill="#64748b">
              {formatMoney(maxCost * t, cur)}
            </text>
          </g>
        ))}
        {ticks.map((t) => (
          <g key={`y${t}`}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(maxHours * 60 * t)} y2={y(maxHours * 60 * t)} stroke="#e2e8f0" />
            <text x={PAD.left - 8} y={y(maxHours * 60 * t) + 4} textAnchor="end" fontSize={font} fill="#64748b">{Math.round(maxHours * t)} h</text>
          </g>
        ))}
        <line x1={x(result.mission.budget)} x2={x(result.mission.budget)} y1={PAD.top} y2={H - PAD.bottom}
          stroke="#0b1220" strokeDasharray="3 4" />
        <text x={x(result.mission.budget) + 4} y={PAD.top + 10} fontSize={font - 0.5} fill="#0b1220">budget</text>
        <text x={(W + PAD.left) / 2} y={H - 4} textAnchor="middle" fontSize={font} fill="#94a3b8">Total trip cost</text>
        {points.map((p, i) => {
          const active = p.id === focus.id;
          return (
            <g key={p.id} role="button" tabIndex={0} aria-label={`${MODE_META[p.mode].label}: ${formatMoney(p.cost.total, cur)}, ${formatMinutes(p.total_travel_minutes)}`}
              onMouseEnter={() => setFocusId(p.id)} onFocus={() => setFocusId(p.id)} onClick={() => onSelect(p.id)}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect(p.id)} className="cursor-pointer outline-none">
              <motion.circle cx={x(p.cost.total!)} cy={y(p.total_travel_minutes)} r={active ? 9 : 7}
                fill={active ? "#0b1220" : "#ffffff"} stroke="#0b1220" strokeWidth={2}
                initial={{ opacity: 0, scale: 0.4 }} animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.15 + i * 0.08, duration: 0.3 }} />
              <text x={x(p.cost.total!) + 13} y={y(p.total_travel_minutes) + 4} fontSize={font + 1} fontWeight={600} fill="#0b1220">
                {MODE_META[p.mode].label}
              </text>
            </g>
          );
        })}
      </svg>

      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 rounded-sm bg-paper px-4 py-3 text-[13px] sm:grid-cols-3">
        <div><dt className="text-muted">{MODE_META[focus.mode].label} cost</dt><dd className="font-semibold text-ink tnum">{formatMoney(focus.cost.total, cur)}</dd></div>
        <div><dt className="text-muted">Time travelling</dt><dd className="font-semibold text-ink tnum">{formatMinutes(focus.total_travel_minutes)}</dd></div>
        <div><dt className="text-muted">Mission score</dt><dd className="font-semibold text-ink tnum">{focus.scores.overall}</dd></div>
        <div><dt className="text-muted">Risk</dt><dd className="mt-0.5"><RiskBadge level={focus.risk.level} compact /></dd></div>
        <div><dt className="text-muted">vs cheapest</dt><dd className={cx("font-semibold tnum", (delta?.time_saved_vs_cheapest_minutes ?? 0) > 0 ? "text-green-ink" : "text-ink")}>
          {delta?.time_saved_vs_cheapest_minutes ? (delta.time_saved_vs_cheapest_minutes > 0
            ? `${formatMinutes(delta.time_saved_vs_cheapest_minutes)} faster` : `${formatMinutes(-delta.time_saved_vs_cheapest_minutes)} slower`) : "—"}</dd></div>
        <div><dt className="text-muted">vs fastest</dt><dd className={cx("font-semibold tnum", (delta?.money_saved_vs_fastest ?? 0) > 0 ? "text-green-ink" : "text-ink")}>
          {delta?.money_saved_vs_fastest ? (delta.money_saved_vs_fastest > 0
            ? `${formatMoney(delta.money_saved_vs_fastest, cur)} cheaper` : `${formatMoney(-delta.money_saved_vs_fastest, cur)} dearer`) : "—"}</dd></div>
      </dl>
    </section>
  );
}
