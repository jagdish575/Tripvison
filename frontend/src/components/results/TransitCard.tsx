import { Accessibility, Bus, CarFront, Footprints, Info, TrainFront, TramFront, type LucideIcon } from "lucide-react";
import type { AccessibilityNote, Itinerary } from "../../types/api";
import { cx, formatClock, formatDayLabel, formatMinutes, formatMoney } from "../../utils/format";
import { MODE_META } from "../../utils/mission";
import { SourceBadge } from "./CostPanels";

const SEGMENT_ICON: Record<string, LucideIcon> = { train: TrainFront, bus: Bus, metro: TramFront, walk: Footprints };

/** Train / bus / public-transport / road-trip main leg. Schedules are live; fares are usually estimates. */
export function TransitCard({ itinerary: it, missionDate }: { itinerary: Itinerary; missionDate: string }) {
  const meta = MODE_META[it.mode];
  const Icon = meta.icon;
  const segments = it.transit?.segments ?? [];
  return (
    <section aria-label={meta.label} className="card p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="grid size-9 place-items-center rounded-sm border border-line bg-paper text-ink"><Icon className="size-4" aria-hidden /></span>
          <div className="min-w-0">
            <p className="text-[15px] font-semibold text-ink">{it.main.title}</p>
            <p className="text-[13px] text-muted">{it.main.provider ?? meta.label}{it.main.distance_km ? ` · ${Math.round(it.main.distance_km).toLocaleString("en-IN")} km` : ""}</p>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-[17px] font-semibold text-ink tnum">{formatMoney(it.cost.ticket, it.cost.currency)}</p>
          <SourceBadge source={it.cost.ticket_source} />
        </div>
      </div>

      {segments.length > 0 ? (
        <ol className="mt-5 space-y-3">
          {segments.map((s, i) => {
            const SegIcon = SEGMENT_ICON[s.mode] ?? TramFront;
            const walk = s.mode === "walk";
            return (
              <li key={i} className={cx("flex gap-3 text-[13.5px]", walk && "text-muted")}>
                <SegIcon className={cx("mt-0.5 size-4 shrink-0", walk ? "text-subtle" : "text-ink")} aria-hidden />
                <div className="min-w-0 flex-1">
                  {walk ? <p>Walk {formatMinutes(s.duration_minutes)}{s.distance_km ? ` · ${s.distance_km} km` : ""}</p> : (
                    <>
                      <p className="font-medium text-ink">{s.name}</p>
                      <p className="text-muted tnum">
                        {s.from_stop} {formatClock(s.depart_at)}
                        {s.depart_at && <span className="text-subtle"> ({formatDayLabel(s.depart_at, missionDate).toLowerCase()})</span>}
                        {" → "}{s.to_stop} {formatClock(s.arrive_at)} · {formatMinutes(s.duration_minutes)}
                      </p>
                    </>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      ) : it.mode === "ground" ? (
        <p className="mt-5 flex items-center gap-2 text-[13.5px] text-fg tnum">
          <CarFront className="size-4" aria-hidden /> Leave {formatClock(it.main.departure_time)} · {formatMinutes(it.main.duration_minutes)} on the road
        </p>
      ) : null}

      <p className="mt-5 flex items-start gap-2 border-t border-line pt-3 text-[12.5px] leading-relaxed text-muted">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        <span>
          <span className="font-medium text-fg">Schedule: </span><SourceBadge source={it.main.schedule_source} />{" "}
          {it.main.note}
        </span>
      </p>
    </section>
  );
}

const ACCESS_TONE = { available: "text-green-ink", requested: "text-blue-ink", unavailable: "text-muted" } as const;

export function AccessibilityNotes({ notes }: { notes: AccessibilityNote[] }) {
  if (!notes.length) return null;
  return (
    <section aria-labelledby="access-title" className="card p-5 sm:p-6">
      <h3 id="access-title" className="flex items-center gap-2 text-[17px] font-semibold tracking-[-0.01em]">
        <Accessibility className="size-4" aria-hidden /> Accessibility
      </h3>
      <ul className="mt-3 space-y-2.5">
        {notes.map((n) => (
          <li key={n.need} className="text-[13.5px]">
            <span className="font-medium text-ink">{n.need}: </span>
            <span className={cx("font-medium", ACCESS_TONE[n.status])}>
              {n.status === "available" ? "Listed" : n.status === "requested" ? "Requested" : "Not confirmed"}
            </span>
            <p className="text-muted">{n.detail}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
