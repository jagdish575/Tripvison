import { Quote } from "lucide-react";
import type { Explanation, Itinerary, MissionSummary } from "../../types/api";
import { formatMoney } from "../../utils/format";

export function ExplanationPanel({ explanation, tradeoff }: { explanation: Explanation; tradeoff?: string | null }) {
  return (
    <section aria-labelledby="why-title" className="card p-5 sm:p-6">
      <div className="flex items-center gap-2">
        <Quote className="size-4 text-amber" aria-hidden />
        <h3 id="why-title" className="text-[17px] font-semibold tracking-[-0.01em]">Why this option?</h3>
      </div>
      <p className="display mt-3 text-[18.5px] leading-[1.55] text-fg tnum">{explanation.text}</p>
      {tradeoff && <p className="mt-3 text-[14px] font-medium text-ink tnum">{tradeoff}</p>}
      <p className="mt-4 border-t border-line pt-3 text-[12px] text-muted">
        {explanation.source === "ai"
          ? `Written by ${explanation.model ?? "an AI model"} from the scoring engine's data, then fact-checked: every number must match the data.`
          : "Generated from the scoring engine's factors — no AI involved."}
        {explanation.note && <> {explanation.note}</>}
      </p>
    </section>
  );
}

/** For non-recommended options: a factual comparison against the recommended journey. */
export function ComparisonNote({ itinerary: it, recommended, mission }: {
  itinerary: Itinerary; recommended: Itinerary; mission: MissionSummary;
}) {
  const lines: string[] = [];
  if (it.cost.total !== null && recommended.cost.total !== null) {
    const d = recommended.cost.total - it.cost.total;
    if (Math.abs(d) >= 50) lines.push(d > 0 ? `${formatMoney(d, mission.currency)} cheaper` : `${formatMoney(-d, mission.currency)} more expensive`);
  }
  const b = it.arrival.buffer_minutes - recommended.arrival.buffer_minutes;
  if (b !== 0) lines.push(b > 0 ? `${b} min more buffer` : `${-b} min less buffer`);
  if (it.risk.level !== recommended.risk.level) lines.push(`${it.risk.level.toLowerCase()} risk instead of ${recommended.risk.level.toLowerCase()}`);
  const s = recommended.scores.overall - it.scores.overall;
  return (
    <section className="card p-5 sm:p-6">
      <h3 className="text-[17px] font-semibold tracking-[-0.01em]">Compared with the recommendation</h3>
      <p className="mt-2 text-[14.5px] text-fg tnum">
        {lines.length ? lines.join(" · ") : "Very similar on cost, buffer and risk."}
        {s > 0 && <span className="text-muted"> — scores {s} point{s === 1 ? "" : "s"} lower overall.</span>}
      </p>
      <ul className="mt-4 space-y-1.5">
        {it.scores.factors.slice(0, 6).map((f) => (
          <li key={f.key + f.label} className="flex items-center gap-2 text-[13.5px] tnum">
            <span className={f.impact === "positive" ? "text-green-ink" : f.impact === "negative" ? "text-red-ink" : "text-subtle"} aria-hidden>
              {f.impact === "positive" ? "+" : f.impact === "negative" ? "−" : "·"}
            </span>
            {f.label}
          </li>
        ))}
      </ul>
    </section>
  );
}
