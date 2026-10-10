import { motion } from "framer-motion";
import { cx } from "../../utils/format";
import { CountUp } from "../ui/CountUp";

export function scoreTone(score: number, onDark = false): string {
  if (score >= 80) return onDark ? "#4ade80" : "#16a34a";
  if (score >= 60) return onDark ? "#fbbf24" : "#d97706";
  return onDark ? "#f87171" : "#dc2626";
}

export function MissionScore({ score, size = 132, onDark = false, label = "Mission score", className }: {
  score: number; size?: number; onDark?: boolean; label?: string; className?: string;
}) {
  const stroke = size >= 120 ? 7 : 5;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  return (
    <div className={cx("relative inline-grid place-items-center", className)} style={{ width: size, height: size }}
      role="img" aria-label={`${label}: ${score} out of 100`}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke}
          stroke={onDark ? "rgb(255 255 255 / 0.12)" : "#e2e8f0"} />
        <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} strokeLinecap="round"
          stroke={scoreTone(score, onDark)} strokeDasharray={c}
          initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - pct) }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center" aria-hidden>
        <span className={cx("display tnum leading-none", size >= 120 ? "text-[46px]" : "text-[26px]", onDark ? "text-white" : "text-ink")}>
          <CountUp value={score} />
        </span>
        {size >= 120 && (
          <span className={cx("mt-1 text-[11px] font-semibold uppercase tracking-[0.08em]", onDark ? "text-white/55" : "text-muted")}>
            / 100
          </span>
        )}
      </div>
    </div>
  );
}
