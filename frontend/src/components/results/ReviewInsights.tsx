import { MessageSquareQuote, ThumbsDown, ThumbsUp } from "lucide-react";
import type { ReviewInsights as Insights, ReviewSignal } from "../../types/api";
import { formatCount } from "../../utils/format";
import { EmptyState } from "../ui/States";

function SignalRow({ signal, kind }: { signal: ReviewSignal; kind: "strength" | "concern" }) {
  const total = signal.positive + signal.negative || 1;
  const share = Math.round(((kind === "strength" ? signal.positive : signal.negative) / total) * 100);
  return (
    <li className="py-2">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[14px] font-medium text-ink">{signal.aspect}</span>
        <span className="text-[12px] text-muted tnum">
          {kind === "strength" ? `${formatCount(signal.positive)} positive` : `${formatCount(signal.negative)} negative`} · {share}%
        </span>
      </div>
      <div className="mt-1.5 flex h-1 overflow-hidden rounded-full bg-line" aria-hidden>
        <span className="bg-green" style={{ width: `${(signal.positive / total) * 100}%` }} />
        <span className="bg-red/70" style={{ width: `${(signal.negative / total) * 100}%` }} />
      </div>
    </li>
  );
}

export function ReviewInsights({ insights }: { insights: Insights | undefined }) {
  if (!insights) {
    return (
      <EmptyState icon={<MessageSquareQuote className="size-5" aria-hidden />} title="No review signals for this hotel"
        description="Review data wasn't returned for this property, so we don't summarise anything." />
    );
  }
  const sources = insights.sources.map((s) => (s === "google_maps_reviews" ? `${insights.review_count} recent Google Maps reviews` : "Google Hotels review mentions"));
  return (
    <section aria-labelledby="reviews-title" className="card p-5 sm:p-6">
      <h3 id="reviews-title" className="text-[17px] font-semibold tracking-[-0.01em]">What guests say</h3>
      <p className="mt-1 text-[12.5px] text-muted">Signals extracted from {sources.join(" and ") || "available reviews"}. Nothing here is generated.</p>

      <div className="mt-4 grid gap-6 sm:grid-cols-2">
        <div>
          <p className="eyebrow flex items-center gap-1.5 text-green-ink"><ThumbsUp className="size-3.5" aria-hidden /> Strengths</p>
          {insights.strengths.length ? (
            <ul className="mt-1 divide-y divide-line">{insights.strengths.map((s) => <SignalRow key={s.aspect} signal={s} kind="strength" />)}</ul>
          ) : <p className="mt-2 text-[13px] text-muted">No consistent strengths mentioned.</p>}
        </div>
        <div>
          <p className="eyebrow flex items-center gap-1.5 text-amber-ink"><ThumbsDown className="size-3.5" aria-hidden /> Potential issues</p>
          {insights.concerns.length ? (
            <ul className="mt-1 divide-y divide-line">{insights.concerns.map((s) => <SignalRow key={s.aspect} signal={s} kind="concern" />)}</ul>
          ) : <p className="mt-2 text-[13px] text-muted">No recurring complaints in the reviews we read.</p>}
        </div>
      </div>

      {insights.quotes.length > 0 && (
        <div className="mt-5 space-y-3 border-t border-line pt-5">
          {insights.quotes.map((q) => (
            <figure key={q.text} className="border-l-2 pl-3" style={{ borderColor: q.sentiment === "negative" ? "#f59e0b" : "#16a34a" }}>
              <blockquote className="text-[14px] italic leading-relaxed text-fg">“{q.text}”</blockquote>
              <figcaption className="mt-1 text-[12px] text-muted">
                {q.aspect && <>{q.aspect} · </>}{q.rating !== null && <>{q.rating}★ · </>}{q.date ?? "recent"}
              </figcaption>
            </figure>
          ))}
        </div>
      )}
    </section>
  );
}
