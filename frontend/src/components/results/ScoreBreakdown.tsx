import { motion } from "framer-motion";
import type { ScoreBreakdown as Scores } from "../../types/api";
import { cx } from "../../utils/format";

export const COMPONENT_LABELS: { key: keyof Scores; label: string; hint: string }[] = [
  { key: "arrival", label: "Arrival reliability", hint: "Buffer after delay exposure and traffic" },
  { key: "budget", label: "Budget", hint: "Total cost vs your budget" },
  { key: "ground", label: "Ground travel", hint: "Taxi time on the day vs your limit" },
  { key: "location", label: "Location & stay", hint: "Hotel distance to the venue (60%) and guest rating (40%)" },
  { key: "duration", label: "Travel time", hint: "Time spent travelling vs the quickest option" },
  { key: "convenience", label: "Convenience", hint: "Changes, night travel, walking, very early starts" },
  { key: "review", label: "Review confidence", hint: "Review volume and positive share" },
];

export function ScoreBreakdown({ scores, className }: { scores: Scores; className?: string }) {
  return (
    <dl className={cx("grid gap-x-10 gap-y-3.5 sm:grid-cols-2", className)}>
      {COMPONENT_LABELS.map(({ key, label, hint }, i) => {
        const value = scores[key] as number | null;
        const weight = scores.weights[key as string];
        return (
          <div key={key} title={hint}>
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-[13.5px] text-fg">
                {label}
                {weight !== undefined && <span className="ml-1.5 text-[11.5px] text-subtle tnum">{Math.round(weight * 100)}%</span>}
              </dt>
              <dd className="text-[14px] font-semibold text-ink tnum">{value === null ? <span className="font-normal text-subtle">n/a</span> : value}</dd>
            </div>
            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-line" aria-hidden>
              {value !== null && (
                <motion.div className={cx("h-full rounded-full", value >= 80 ? "bg-ink" : value >= 60 ? "bg-ink/70" : "bg-amber")}
                  initial={{ width: 0 }} animate={{ width: `${value}%` }}
                  transition={{ duration: 0.6, delay: 0.15 + i * 0.04, ease: [0.22, 1, 0.36, 1] }} />
              )}
            </div>
          </div>
        );
      })}
    </dl>
  );
}
