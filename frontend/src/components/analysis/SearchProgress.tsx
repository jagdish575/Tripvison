import { motion } from "framer-motion";
import { Check } from "lucide-react";
import type { Stage } from "../../types/api";
import { cx, plural } from "../../utils/format";
import { STAGE_LABELS, STAGES } from "../../utils/mission";

function detailFor(stage: Stage, counts: Record<string, number>): string | null {
  switch (stage) {
    case "flights":
      return counts.flights !== undefined
        ? `${plural((counts.flights ?? 0) + (counts.transit ?? 0), "travel option")} found` : null;
    case "arrival":
      return counts.flights_feasible !== undefined ? `${plural(counts.flights_feasible, "option")} can get you there` : null;
    case "hotels":
      return counts.hotels !== undefined ? `${plural(counts.hotels, "hotel")} compared` : null;
    case "scoring":
      return counts.itineraries !== undefined ? `${plural(counts.itineraries, "complete journey")} scored` : null;
    default:
      return null;
  }
}

export function SearchProgress({ shownIndex, counts, activeMessage }: {
  shownIndex: number; counts: Record<string, number>; activeMessage?: string;
}) {
  return (
    <ol className="relative" aria-live="polite">
      {STAGES.map((stage, i) => {
        const done = i < shownIndex;
        const active = i === shownIndex;
        const detail = done ? detailFor(stage, counts) : active ? activeMessage ?? null : null;
        return (
          <li key={stage} className="relative flex gap-4 pb-5 last:pb-0">
            {i < STAGES.length - 1 && (
              <span aria-hidden className="absolute left-[11px] top-7 h-[calc(100%-20px)] w-px bg-line">
                <motion.span className="absolute inset-x-0 top-0 bg-ink" initial={false}
                  animate={{ height: done ? "100%" : "0%" }} transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }} />
              </span>
            )}
            <span className={cx(
              "relative z-10 mt-0.5 grid size-6 shrink-0 place-items-center rounded-full border transition-colors duration-200",
              done ? "border-ink bg-ink text-white" : active ? "border-blue bg-surface" : "border-line-strong bg-surface",
            )}>
              {done ? (
                <motion.span initial={{ scale: 0.4, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ duration: 0.2 }}>
                  <Check className="size-3.5" strokeWidth={3} aria-hidden />
                </motion.span>
              ) : active ? (
                <span className="size-2 animate-pulse rounded-full bg-blue" aria-hidden />
              ) : null}
            </span>
            <div className="min-w-0 pt-px">
              <p className={cx("text-[15px] font-medium transition-colors", done ? "text-ink" : active ? "text-ink" : "text-subtle")}>
                {STAGE_LABELS[stage]}
                <span className="sr-only">{done ? " — done" : active ? " — in progress" : " — waiting"}</span>
              </p>
              {detail && <p className="mt-0.5 text-[13px] text-muted tnum">{detail}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
