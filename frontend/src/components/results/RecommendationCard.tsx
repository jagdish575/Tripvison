import type { ReactNode } from "react";
import type { Category, Itinerary, MissionSummary } from "../../types/api";
import { cx, formatClock, formatMinutes, formatMoney } from "../../utils/format";
import { CATEGORY_META, MODE_META, PRIORITIES } from "../../utils/mission";
import { MissionScore } from "./MissionScore";
import { ScoreBreakdown } from "./ScoreBreakdown";

function KeyFigure({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "warn" | "bad" }) {
  return (
    <div className="min-w-0 border-l border-white/10 pl-4 first:border-l-0 first:pl-0 sm:pl-5">
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-white/50">{label}</p>
      <p className={cx("mt-1.5 truncate text-[24px] font-semibold tracking-[-0.02em] tnum sm:text-[26px]",
        tone === "bad" ? "text-[#fca5a5]" : tone === "warn" ? "text-[#fcd34d]" : "text-white")}>{value}</p>
      {sub && <p className="mt-0.5 truncate text-[12.5px] text-white/55 tnum">{sub}</p>}
    </div>
  );
}

export function journeyTitle(it: Itinerary): string {
  const main = it.mode === "flight" ? `${it.main.provider ?? ""} ${it.main.references[0] ?? ""}`.trim() : it.main.title;
  return it.hotel ? `${main} + ${it.hotel.name}` : main;
}

export function strategyLabel(it: Itinerary): string {
  const late = Number(formatClock(it.main.arrival_time).slice(0, 2)) >= 17;
  const verbs: Record<string, [string, string]> = {
    flight: ["Fly the same morning", "Fly in the"],
    train: ["Train on the day", "Train in the"],
    bus: ["Bus on the day", "Bus in the"],
    transit: ["Public transport on the day", "Arrive the"],
    ground: ["Drive there on the day", "Drive in the"],
  };
  const [sameDay, before] = verbs[it.mode] ?? verbs.flight;
  const overnight = it.strategy === "same_day" && it.main.departure_time.slice(0, 10) < it.arrival.deadline.slice(0, 10);
  if (overnight) return `Overnight ${MODE_META[it.mode].noun}`;
  return it.strategy === "same_day" ? sameDay : `${before} ${late ? "evening" : "day"} before`;
}

export function RecommendationCard({ itinerary: it, mission, categories }: {
  itinerary: Itinerary; mission: MissionSummary; categories: Category[];
}) {
  const remaining = it.cost.budget_remaining;
  const buffer = it.arrival.buffer_minutes;
  const bufferTone = buffer < 0 ? "bad" : buffer < mission.min_buffer_minutes ? "warn" : undefined;
  const riskTone = it.risk.level === "HIGH" ? "bad" : it.risk.level === "MEDIUM" ? "warn" : undefined;
  const ModeIcon = MODE_META[it.mode].icon;
  const priority = PRIORITIES.find((p) => p.id === it.scores.priority)?.label ?? "Balanced";
  const concerns = it.risk.factors.filter((f) => f.severity !== "low").length;
  const stops = it.mode === "flight"
    ? (it.main.stops === 0 ? "direct" : `${it.main.stops} stop`)
    : it.main.transfers === 0 ? "no changes" : `${it.main.transfers} change${it.main.transfers > 1 ? "s" : ""}`;

  return (
    <article className="overflow-hidden rounded-lg border border-ink bg-surface">
      <div className="bg-ink px-5 py-6 text-white sm:px-8 sm:py-7">
        <div className="flex flex-col gap-6 md:flex-row md:items-center md:gap-8">
          <MissionScore score={it.scores.overall} onDark className="shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-xs bg-white px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink">
                <ModeIcon className="size-3.5" aria-hidden /> {MODE_META[it.mode].label}
              </span>
              {categories.map((c) => (
                <span key={c} className={cx("rounded-xs px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em]",
                  c === "recommended" ? "bg-amber text-ink" : "bg-white/10 text-white")}>{CATEGORY_META[c].label}</span>
              ))}
              <span className="text-[13px] text-white/60">{strategyLabel(it)}</span>
              {it.practicality === "low" && (
                <span title="Needs a long road transfer to or from the airport"
                  className="rounded-xs border border-[#fcd34d]/50 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#fcd34d]">
                  Low practicality
                </span>
              )}
            </div>
            <h2 className="display mt-2.5 text-[26px] leading-tight text-white sm:text-[30px]">{journeyTitle(it)}</h2>
            <p className="mt-1.5 text-[14px] text-white/60 tnum">
              Departs {formatClock(it.main.departure_time)} · arrives {formatClock(it.main.arrival_time)} · {stops} ·{" "}
              {formatMinutes(it.total_travel_minutes)} door to door
              {it.cost.ticket_source === "estimated" && <span className="text-[#fcd34d]"> · estimated fare</span>}
            </p>
            {it.mode === "flight" && it.main.note && <p className="mt-2 max-w-2xl text-[13.5px] text-white/75">{it.main.note}</p>}
          </div>
        </div>
        <div className="mt-7 grid grid-cols-2 gap-y-5 border-t border-white/10 pt-6 lg:grid-cols-4">
          <KeyFigure label="Total trip cost" value={formatMoney(it.cost.total, it.cost.currency)}
            tone={remaining !== null && remaining < 0 ? "bad" : undefined}
            sub={remaining === null ? "Some prices unknown" : remaining >= 0 ? `${formatMoney(remaining, it.cost.currency)} of budget left` : `${formatMoney(-remaining, it.cost.currency)} over budget`} />
          <KeyFigure label="At the venue" value={formatClock(it.arrival.venue_arrival)}
            sub={it.arrival.leave_hotel_at ? `Leave hotel ${formatClock(it.arrival.leave_hotel_at)}` : `Required ${mission.arrival_deadline}`} />
          <KeyFigure label="Arrival buffer" value={buffer < 0 ? `${-buffer} min late` : `${buffer} min`} tone={bufferTone}
            sub={`${mission.min_buffer_minutes} min required`} />
          <KeyFigure label="Risk" value={it.risk.level.charAt(0) + it.risk.level.slice(1).toLowerCase()} tone={riskTone}
            sub={concerns === 0 ? "Nothing significant" : `${concerns} concern${concerns === 1 ? "" : "s"}`} />
        </div>
      </div>
      <div className="px-5 py-6 sm:px-8">
        <div className="mb-4 flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
          <h3 className="text-[14px] font-semibold">Score breakdown</h3>
          <p className="text-[12px] text-muted">Weights for your priority: {priority}</p>
        </div>
        <ScoreBreakdown scores={it.scores} />
      </div>
    </article>
  );
}
