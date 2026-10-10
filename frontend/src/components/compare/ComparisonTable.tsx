import { Check } from "lucide-react";
import type { ReactNode } from "react";
import type { Category, Itinerary, MissionSummary } from "../../types/api";
import { cx, formatClock, formatKm, formatMinutes, formatMoney } from "../../utils/format";
import { CATEGORY_META, MODE_META } from "../../utils/mission";
import { RiskBadge } from "../ui/Badge";

export interface CompareColumn { itinerary: Itinerary; categories: Category[] }

type Row = {
  label: string;
  value: (it: Itinerary) => ReactNode;
  /** numeric key for picking the best value in the row; undefined = no highlight */
  rank?: (it: Itinerary) => number | null;
  better?: "low" | "high";
};

const RISK_RANK = { LOW: 0, MEDIUM: 1, HIGH: 2 } as const;

export function buildRows(mission: MissionSummary): { group: string; rows: Row[] }[] {
  return [
    {
      group: "Outcome",
      rows: [
        { label: "Mission score", value: (it) => <span className="text-[17px] font-semibold">{it.scores.overall}</span>, rank: (it) => it.scores.overall, better: "high" },
        { label: "Risk", value: (it) => <RiskBadge level={it.risk.level} />, rank: (it) => RISK_RANK[it.risk.level], better: "low" },
        { label: "Arrival buffer", value: (it) => `${it.arrival.buffer_minutes} min`, rank: (it) => it.arrival.buffer_minutes, better: "high" },
        { label: "At the venue", value: (it) => formatClock(it.arrival.venue_arrival) },
        { label: "Meets all constraints", value: (it) => (it.constraints.all_ok ? <Check className="size-4 text-green-ink" aria-label="Yes" /> : <span className="text-muted">No</span>) },
      ],
    },
    {
      group: "Cost",
      rows: [
        { label: "Total trip cost", value: (it) => <span className="font-semibold">{formatMoney(it.cost.total, it.cost.currency)}</span>, rank: (it) => it.cost.total, better: "low" },
        { label: "Budget remaining", value: (it) => (it.cost.budget_remaining === null ? "—" : it.cost.budget_remaining >= 0
          ? formatMoney(it.cost.budget_remaining, mission.currency) : <span className="text-red-ink">{formatMoney(-it.cost.budget_remaining, mission.currency)} over</span>),
          rank: (it) => it.cost.budget_remaining, better: "high" },
        { label: "Ticket", value: (it) => <>{formatMoney(it.cost.ticket, it.cost.currency)}{it.cost.ticket_source === "estimated" && <span className="ml-1 text-[11px] font-semibold uppercase text-amber-ink">est.</span>}</> },
        { label: "Hotel", value: (it) => (it.hotel ? formatMoney(it.cost.hotel, it.cost.currency) : "—") },
        { label: "Ground (est.)", value: (it) => formatMoney(it.cost.ground, it.cost.currency) },
        { label: "Food (est.)", value: (it) => formatMoney(it.cost.food, it.cost.currency) },
      ],
    },
    {
      group: "Journey",
      rows: [
        { label: "Mode", value: (it) => MODE_META[it.mode].label },
        { label: "When", value: (it) => (it.strategy === "night_before" ? "Day before"
          : it.main.departure_time.slice(0, 10) < mission.travel_date ? "Overnight" : "Same day") },
        { label: "Service", value: (it) => (it.mode === "flight" ? `${it.main.provider ?? ""} ${it.main.references.join(" / ")}` : it.main.title) },
        { label: "Departs → arrives", value: (it) => `${formatClock(it.main.departure_time)} → ${formatClock(it.main.arrival_time)}` },
        { label: "Stops / changes", value: (it) => (it.main.transfers === 0 ? "Direct" : String(it.main.transfers)), rank: (it) => it.main.transfers, better: "low" },
        { label: "Time travelling", value: (it) => formatMinutes(it.total_travel_minutes), rank: (it) => it.total_travel_minutes, better: "low" },
      ],
    },
    {
      group: "Stay & ground",
      rows: [
        { label: "Hotel", value: (it) => it.hotel?.name ?? "—" },
        { label: "Hotel rating", value: (it) => (it.hotel?.rating ? `${it.hotel.rating.toFixed(1)}★` : "—"), rank: (it) => it.hotel?.rating ?? null, better: "high" },
        { label: "Distance to venue", value: (it) => formatKm(it.hotel?.distance_km), rank: (it) => it.hotel?.distance_km ?? null, better: "low" },
        { label: "Ground travel on the day", value: (it) => formatMinutes(it.ground_minutes_mission_day), rank: (it) => it.ground_minutes_mission_day, better: "low" },
      ],
    },
  ];
}

function bestIds(columns: CompareColumn[], row: Row): Set<string> {
  if (!row.rank || columns.length < 2) return new Set();
  const values = columns.map((c) => ({ id: c.itinerary.id, v: row.rank!(c.itinerary) })).filter((x) => x.v !== null) as { id: string; v: number }[];
  if (values.length < 2) return new Set();
  const target = row.better === "low" ? Math.min(...values.map((x) => x.v)) : Math.max(...values.map((x) => x.v));
  if (values.every((x) => x.v === target)) return new Set();
  return new Set(values.filter((x) => x.v === target).map((x) => x.id));
}

function ColumnHeader({ col, onOpen }: { col: CompareColumn; onOpen: (id: string) => void }) {
  return (
    <div>
      <p className="text-[11.5px] font-semibold uppercase tracking-[0.06em] text-ink">
        {MODE_META[col.itinerary.mode].label} · {col.categories.length ? col.categories.map((c) => CATEGORY_META[c].label).join(" · ") : "Alternative"}
      </p>
      <button type="button" onClick={() => onOpen(col.itinerary.id)} className="mt-1 text-left text-[13px] font-medium text-blue hover:text-blue-ink">
        View journey →
      </button>
    </div>
  );
}

export function ComparisonTable({ columns, mission, onOpen }: {
  columns: CompareColumn[]; mission: MissionSummary; onOpen: (id: string) => void;
}) {
  const groups = buildRows(mission);
  return (
    <>
      {/* desktop / tablet */}
      <div className="hidden overflow-x-auto rounded-md border border-line bg-surface md:block">
        <table className="w-full min-w-[720px] border-collapse text-left text-[14px]">
          <thead>
            <tr className="border-b border-line">
              <th scope="col" className="w-[200px] px-5 py-4 align-bottom"><span className="sr-only">Metric</span></th>
              {columns.map((c) => (
                <th key={c.itinerary.id} scope="col" className={cx("px-5 py-4 align-bottom", c.categories.includes("recommended") && "bg-paper")}>
                  <ColumnHeader col={c} onOpen={onOpen} />
                </th>
              ))}
            </tr>
          </thead>
          {groups.map((g) => (
            <tbody key={g.group}>
              <tr><th colSpan={columns.length + 1} scope="colgroup" className="eyebrow bg-paper-2/60 px-5 py-2 text-left">{g.group}</th></tr>
              {g.rows.map((row) => {
                const best = bestIds(columns, row);
                return (
                  <tr key={row.label} className="border-t border-line">
                    <th scope="row" className="px-5 py-3 text-[13.5px] font-normal text-muted">{row.label}</th>
                    {columns.map((c) => (
                      <td key={c.itinerary.id} className={cx("px-5 py-3 text-ink tnum", c.categories.includes("recommended") && "bg-paper")}>
                        <span className={cx("inline-flex items-center gap-1.5", best.has(c.itinerary.id) && "font-semibold")}>
                          {row.value(c.itinerary)}
                          {best.has(c.itinerary.id) && <span className="size-1.5 rounded-full bg-green" title="Best in row" aria-label="best" />}
                        </span>
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          ))}
        </table>
      </div>

      {/* mobile: one card per option */}
      <div className="space-y-4 md:hidden">
        {columns.map((c) => (
          <article key={c.itinerary.id} className="card overflow-hidden">
            <div className="flex items-start justify-between gap-3 border-b border-line bg-paper px-4 py-3">
              <ColumnHeader col={c} onOpen={onOpen} />
              <span className="text-[22px] font-semibold text-ink tnum">{c.itinerary.scores.overall}</span>
            </div>
            <dl className="divide-y divide-line px-4">
              {groups.flatMap((g) => g.rows.map((row) => ({ group: g.group, row }))).filter(({ row }) => row.label !== "Mission score").map(({ group, row }) => (
                <div key={`${group}-${row.label}`} className="flex items-center justify-between gap-4 py-2.5 text-[13.5px]">
                  <dt className="text-muted">{row.label === "Hotel" && group === "Cost" ? "Hotel (cost)" : row.label}</dt>
                  <dd className="text-right text-ink tnum">{row.value(c.itinerary)}</dd>
                </div>
              ))}
            </dl>
          </article>
        ))}
      </div>
    </>
  );
}
