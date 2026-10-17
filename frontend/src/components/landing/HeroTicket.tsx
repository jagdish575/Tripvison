import { motion } from "framer-motion";
import { Briefcase } from "lucide-react";
import { MissionScore } from "../results/MissionScore";
import { RiskBadge } from "../ui/Badge";

const ROWS = [
  { k: "Plan", v: "Fly in the day before", s: "Akasa Air QP 1384 · lands 15:15" },
  { k: "At venue", v: "08:45", s: "75 min before your 10:00 interview" },
  { k: "All-in", v: "₹8,102", s: "₹1,898 under budget" },
];

/** Illustrative "boarding pass" summarising what a result looks like (demo scenario numbers). */
export function HeroTicket() {
  return (
    <motion.figure initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
      className="relative mx-auto w-full max-w-[400px]" aria-label="Example result">
      <div aria-hidden className="bg-brand animate-gradient absolute -inset-4 -z-10 rounded-[32px] opacity-40 blur-2xl" />
      <motion.div whileHover={{ rotate: -1.5, scale: 1.02 }} transition={{ type: "spring", stiffness: 200, damping: 18 }}
        className="animate-float">
      <div className="overflow-hidden rounded-2xl border border-white/70 bg-surface shadow-[var(--shadow-lift)]">
        <div className="bg-gradient-to-br from-night via-[#13285a] to-[#1e3a8a] px-6 pb-5 pt-5 text-white">
          <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.1em] text-white/50">
            <span>Mission</span><span>Thu · 9 Oct</span>
          </div>
          <div className="mt-3 flex items-end justify-between">
            <div>
              <p className="text-[34px] font-semibold leading-none tracking-[-0.02em]">IDR</p>
              <p className="mt-1 text-[12px] text-white/55">Indore</p>
            </div>
            <svg viewBox="0 0 120 30" className="mb-3 h-6 w-28 text-white/40" aria-hidden>
              <motion.path d="M4 24 C 40 2, 80 2, 116 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 4"
                initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.1, delay: 0.4 }} />
              <circle cx="116" cy="24" r="3" fill="#F59E0B" />
            </svg>
            <div className="text-right">
              <p className="text-[34px] font-semibold leading-none tracking-[-0.02em]">BLR</p>
              <p className="mt-1 text-[12px] text-white/55">Bengaluru</p>
            </div>
          </div>
          <p className="mt-4 inline-flex items-center gap-2 text-[13px] text-white/75">
            <Briefcase className="size-3.5 text-amber" aria-hidden /> Interview · Manyata Tech Park · by 10:00
          </p>
        </div>
        {/* perforation */}
        <div className="relative h-0 border-t border-dashed border-line-strong" aria-hidden>
          <span className="absolute -left-2.5 -top-2.5 size-5 rounded-full border border-line bg-paper" />
          <span className="absolute -right-2.5 -top-2.5 size-5 rounded-full border border-line bg-paper" />
        </div>
        <div className="px-6 pb-6 pt-5">
          <div className="flex items-center gap-4">
            <MissionScore score={93} size={72} />
            <div>
              <p className="eyebrow">Mission score</p>
              <p className="mt-1 text-[14px] text-muted">Best of 27 complete journeys</p>
            </div>
            <RiskBadge level="LOW" compact className="ml-auto" />
          </div>
          <dl className="mt-5 divide-y divide-line border-t border-line">
            {ROWS.map((r) => (
              <div key={r.k} className="grid grid-cols-[72px_1fr] gap-3 py-2.5">
                <dt className="pt-0.5 text-[11.5px] font-semibold uppercase tracking-[0.06em] text-subtle">{r.k}</dt>
                <dd>
                  <span className="block text-[15px] font-semibold text-ink tnum">{r.v}</span>
                  <span className="block text-[12.5px] text-muted tnum">{r.s}</span>
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
      </motion.div>
      <figcaption className="mt-3 text-center text-[12px] text-subtle">Example result from the demo scenario</figcaption>
    </motion.figure>
  );
}
