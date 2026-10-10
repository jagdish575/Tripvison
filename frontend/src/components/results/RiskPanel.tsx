import { Check, CircleAlert, TriangleAlert, Info } from "lucide-react";
import type { RiskAssessment, RiskFactor } from "../../types/api";
import { cx } from "../../utils/format";
import { RiskBadge } from "../ui/Badge";

const VERDICT = {
  LOW: "Unlikely. Nothing on this journey is close to its limit.",
  MEDIUM: "Possibly. One or two things deserve attention.",
  HIGH: "Yes — this journey has a real chance of going wrong.",
} as const;

function FactorIcon({ severity }: { severity: RiskFactor["severity"] }) {
  if (severity === "high") return <TriangleAlert className="size-4 text-red-ink" aria-label="High" />;
  if (severity === "medium") return <CircleAlert className="size-4 text-amber-ink" aria-label="Medium" />;
  return <Info className="size-4 text-subtle" aria-label="Minor" />;
}

export function RiskPanel({ risk }: { risk: RiskAssessment }) {
  return (
    <section aria-labelledby="risk-title" className="card p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <h3 id="risk-title" className="text-[17px] font-semibold tracking-[-0.01em]">Can this journey go wrong?</h3>
        <RiskBadge level={risk.level} />
      </div>
      <p className="mt-2 text-[14px] text-muted">{VERDICT[risk.level]}</p>

      {risk.strengths.length > 0 && (
        <ul className="mt-5 space-y-2">
          {risk.strengths.map((s) => (
            <li key={s} className="flex items-start gap-2.5 text-[14px] text-fg">
              <Check className="mt-0.5 size-4 shrink-0 text-green-ink" strokeWidth={2.5} aria-hidden />
              <span className="tnum">{s}</span>
            </li>
          ))}
        </ul>
      )}

      {risk.factors.length > 0 && (
        <div className="mt-5 border-t border-line pt-5">
          <p className="eyebrow mb-3">Watch out for</p>
          <ul className="space-y-3.5">
            {risk.factors.map((f) => (
              <li key={f.key + f.title} className="flex items-start gap-2.5">
                <span className="mt-0.5 shrink-0"><FactorIcon severity={f.severity} /></span>
                <div className="min-w-0">
                  <p className={cx("text-[14px] font-medium tnum", f.severity === "high" ? "text-red-ink" : "text-ink")}>{f.title}</p>
                  <p className="text-[13px] text-muted">{f.detail}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {risk.recommendations.length > 0 && (
        <div className="mt-5 rounded-sm bg-paper px-4 py-3">
          <p className="eyebrow mb-1.5">What to do</p>
          <ul className="space-y-1 text-[13.5px] text-fg">
            {risk.recommendations.map((r) => <li key={r} className="tnum">— {r}</li>)}
          </ul>
        </div>
      )}
    </section>
  );
}
