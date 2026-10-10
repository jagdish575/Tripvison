import { ArrowRight, TriangleAlert } from "lucide-react";
import type { Suggestion } from "../../types/api";
import { cx } from "../../utils/format";

export function ConstraintSuggestions({ status, suggestions, onApply, pending }: {
  status: "partial" | "no_options"; suggestions: Suggestion[]; onApply: (s: Suggestion) => void; pending: boolean;
}) {
  const severe = status === "no_options";
  return (
    <section role="status" className={cx("rounded-md border p-5 sm:p-6", severe ? "border-red/25 bg-red-wash/60" : "border-amber/35 bg-amber-wash")}>
      <div className="flex items-start gap-3">
        <TriangleAlert className={cx("mt-0.5 size-5 shrink-0", severe ? "text-red-ink" : "text-amber-ink")} aria-hidden />
        <div className="min-w-0 flex-1">
          <h2 className="text-[17px] font-semibold text-ink">
            {severe ? "No journey gets you there on time." : "No journey fully satisfies your constraints."}
          </h2>
          <p className="mt-1 text-[14px] text-fg/80">
            {severe
              ? "We checked every flight we found against your deadline. Here's what would change that:"
              : "The journeys below are the closest matches. One of these changes would give you a journey that meets everything:"}
          </p>
          {suggestions.length > 0 ? (
            <ul className="mt-4 grid gap-2 sm:grid-cols-2">
              {suggestions.map((s) => {
                const actionable = Object.keys(s.patch).length > 0;
                return (
                  <li key={s.kind}>
                    <button type="button" disabled={!actionable || pending} onClick={() => onApply(s)}
                      className="group flex h-full w-full items-start justify-between gap-3 rounded-sm border border-line-strong bg-surface p-3.5 text-left transition-colors enabled:hover:border-ink disabled:cursor-default">
                      <span>
                        <span className="block text-[14px] font-semibold text-ink tnum">{s.title}</span>
                        <span className="mt-0.5 block text-[13px] text-muted tnum">{s.detail}</span>
                      </span>
                      {actionable && <ArrowRight className="mt-0.5 size-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5 group-hover:text-ink" aria-hidden />}
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="mt-3 text-[13.5px] text-muted">Try a different date or a later arrival time.</p>
          )}
          {suggestions.some((s) => Object.keys(s.patch).length) && (
            <p className="mt-3 text-[12.5px] text-muted">Choosing a suggestion re-runs the analysis with that one change.</p>
          )}
        </div>
      </div>
    </section>
  );
}
