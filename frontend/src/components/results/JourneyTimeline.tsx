import { motion } from "framer-motion";
import {
  BedDouble, Bus, Car, CarFront, CarTaxiFront, Flag, Footprints, Hourglass, Moon, Navigation, Plane, PlaneLanding,
  PlaneTakeoff, Repeat, TrainFront, TramFront, type LucideIcon,
} from "lucide-react";
import type { Itinerary, MissionSummary, TimelineKind } from "../../types/api";
import { cx, formatClock, formatDayLabel, formatKm, formatMinutes } from "../../utils/format";

const NODE_ICON: Record<TimelineKind, LucideIcon> = {
  depart: PlaneTakeoff, land: PlaneLanding, exit: Navigation, transfer: Car, hotel: BedDouble, leave: Car,
  arrive: Flag, deadline: Hourglass, board: TrainFront, change: Repeat,
};

function modeIcon(mode: string | null): LucideIcon {
  const m = (mode ?? "").toLowerCase();
  if (m.includes("flight")) return Plane;
  if (m.includes("outstation")) return CarFront;
  if (m.includes("taxi")) return CarTaxiFront;
  if (m === "train") return TrainFront;
  if (m === "bus") return Bus;
  if (m.includes("metro") || m.includes("transit")) return TramFront;
  if (m.includes("overnight")) return Moon;
  if (m.includes("buffer")) return Hourglass;
  if (m.includes("bag") || m.includes("freshen")) return BedDouble;
  return Footprints;
}

export function JourneyTimeline({ itinerary: it, mission }: { itinerary: Itinerary; mission: MissionSummary }) {
  const buffer = it.arrival.buffer_minutes;
  const bufferOk = buffer >= mission.min_buffer_minutes;
  let lastDay = "";

  return (
    <motion.ol key={it.id} className="relative" initial="hidden" animate="show"
      variants={{ hidden: {}, show: { transition: { staggerChildren: 0.06 } } }}>
      <motion.span aria-hidden className="absolute bottom-6 left-[95.5px] top-3 w-px origin-top bg-line-strong sm:left-[111.5px]"
        variants={{ hidden: { scaleY: 0 }, show: { scaleY: 1, transition: { duration: 0.7, ease: [0.22, 1, 0.36, 1] } } }} />
      {it.timeline.map((event, index) => {
        const Icon = event.kind === "board" && it.mode === "bus" ? Bus : event.kind === "depart" && it.mode === "ground"
          ? CarFront : NODE_ICON[event.kind];
        const day = formatDayLabel(event.time, mission.travel_date);
        const showDay = day !== lastDay;
        lastDay = day;
        const isDeadline = event.kind === "deadline";
        const isArrive = event.kind === "arrive";
        const isLast = index === it.timeline.length - 1;
        const ModeIcon = modeIcon(event.mode_to_next);
        const isBuffer = event.mode_to_next === "Buffer";
        return (
          <motion.li key={`${event.kind}-${index}`} className="relative grid grid-cols-[72px_24px_1fr] gap-x-3 sm:grid-cols-[88px_24px_1fr]"
            variants={{ hidden: { opacity: 0, y: 4 }, show: { opacity: 1, y: 0, transition: { duration: 0.25 } } }}>
            <div className="pt-0.5 text-right">
              <p className={cx("text-[16px] font-semibold tnum leading-tight", isDeadline ? "text-amber-ink" : "text-ink")}>
                {formatClock(event.time)}
              </p>
              {showDay && <p className="mt-0.5 text-[11px] font-medium uppercase tracking-[0.06em] text-subtle">{day}</p>}
            </div>
            <div className="relative flex justify-center">
              <span className={cx(
                "relative z-10 grid size-6 place-items-center rounded-full border",
                isDeadline ? "border-amber bg-amber text-ink" : isArrive ? "border-ink bg-ink text-white" : "border-line-strong bg-surface text-fg",
              )}>
                <Icon className="size-3.5" strokeWidth={2} aria-hidden />
              </span>
            </div>
            <div className={cx("min-w-0", isLast ? "pb-0" : "pb-2")}>
              <p className={cx("text-[15px] font-medium leading-snug", isDeadline ? "text-amber-ink" : "text-ink")}>{event.title}</p>
              {event.detail && <p className="mt-0.5 text-[13px] text-muted">{event.detail}</p>}
              {!isLast && event.mode_to_next && (
                <div className={cx(
                  "my-3 inline-flex items-center gap-2 rounded-sm px-2.5 py-1.5 text-[12.5px] tnum",
                  isBuffer
                    ? buffer < 0 ? "bg-red-wash text-red-ink" : bufferOk ? "bg-green-wash text-green-ink" : "bg-amber-wash text-amber-ink"
                    : "bg-paper-2 text-muted",
                )}>
                  <ModeIcon className="size-3.5 shrink-0" aria-hidden />
                  <span className="font-medium">{isBuffer ? "Buffer" : event.mode_to_next}</span>
                  {event.duration_to_next_minutes !== null && event.mode_to_next !== "Overnight" && (
                    <span>· {formatMinutes(event.duration_to_next_minutes)}</span>
                  )}
                  {event.distance_to_next_km !== null && <span>· {formatKm(event.distance_to_next_km)}</span>}
                </div>
              )}
              {!isLast && !event.mode_to_next && <div className="h-5" />}
            </div>
          </motion.li>
        );
      })}
    </motion.ol>
  );
}
