import { BadgeCheck, Calculator, ChevronDown, FlaskConical, Info, Radio, Wrench } from "lucide-react";
import type { ReactNode } from "react";
import type { MethodNote, MissionResult } from "../../types/api";
import { cx } from "../../utils/format";

const KIND: Record<MethodNote["kind"], { icon: ReactNode; tone: string }> = {
  live: { icon: <Radio className="size-4" aria-hidden />, tone: "text-green-ink bg-green-wash" },
  calculated: { icon: <Calculator className="size-4" aria-hidden />, tone: "text-blue-ink bg-blue-wash" },
  estimated: { icon: <Info className="size-4" aria-hidden />, tone: "text-amber-ink bg-amber-wash" },
  demo: { icon: <FlaskConical className="size-4" aria-hidden />, tone: "text-amber-ink bg-amber-wash" },
};

/** Developer diagnostics — only present when the server runs with DEBUG_MODE=true. */
function Diagnostics({ result }: { result: MissionResult }) {
  const ds = result.data_sources;
  if (!ds.calls) return null;
  return (
    <details className="group mt-3 rounded-md border border-dashed border-line-strong bg-paper">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-2.5 text-[13px] font-medium text-muted">
        <Wrench className="size-3.5" aria-hidden /> Developer diagnostics (DEBUG_MODE) · {ds.calls.length} requests ·{" "}
        {ds.live_calls} live · {ds.cache_hits} cached
      </summary>
      <div className="overflow-x-auto border-t border-line">
        <table className="w-full min-w-[520px] text-left text-[12.5px]">
          <thead className="text-[11px] uppercase tracking-[0.06em] text-muted">
            <tr><th className="px-4 py-2">Engine</th><th className="px-4 py-2">Purpose</th><th className="px-4 py-2">Status</th>
              <th className="px-4 py-2 text-right">ms</th></tr>
          </thead>
          <tbody className="divide-y divide-line">
            {ds.calls.map((c, i) => (
              <tr key={i}>
                <td className="px-4 py-1.5 font-mono">{c.api}</td>
                <td className="px-4 py-1.5 text-muted">{c.purpose}</td>
                <td className={cx("px-4 py-1.5", c.ok ? "text-green-ink" : "text-red-ink")}>{c.ok ? (c.cached ? "cache" : "live") : c.error}</td>
                <td className="px-4 py-1.5 text-right tnum">{c.ms}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {result.diagnostics && (
          <pre className="overflow-x-auto border-t border-line px-4 py-2 text-[11.5px] text-muted">
            {JSON.stringify(result.diagnostics, null, 2)}
          </pre>
        )}
      </div>
    </details>
  );
}

/** "How we decided" — a calm, collapsed explanation of where every number comes from. */
export function DataSources({ result }: { result: MissionResult }) {
  const fetched = new Date(result.data_sources.fetched_at);
  return (
    <section aria-labelledby="sources-title">
      <details className="group card overflow-hidden">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4">
          <span className="flex min-w-0 items-center gap-3">
            <BadgeCheck className="size-5 shrink-0 text-muted" aria-hidden />
            <span className="min-w-0">
              <span id="sources-title" className="block text-[15px] font-semibold text-ink">How we decided</span>
              <span className="block truncate text-[13px] text-muted">Data sources &amp; methodology</span>
            </span>
          </span>
          <ChevronDown className="size-4 shrink-0 text-muted transition-transform group-open:rotate-180" aria-hidden />
        </summary>
        <div className="border-t border-line px-5 py-5">
          <ul className="grid gap-4 md:grid-cols-3">
            {result.methodology.map((m) => (
              <li key={m.key} className="flex gap-3">
                <span className={cx("grid size-8 shrink-0 place-items-center rounded-sm", KIND[m.kind].tone)}>{KIND[m.kind].icon}</span>
                <div className="min-w-0">
                  <p className="text-[14px] font-semibold text-ink">{m.label}</p>
                  <p className="mt-0.5 text-[13.5px] leading-relaxed text-muted">{m.detail}</p>
                </div>
              </li>
            ))}
          </ul>
          <p className="mt-5 text-[12.5px] text-muted">
            Data checked {fetched.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}.
            Prices and schedules change — always confirm before booking. TripMission doesn't book travel.
          </p>
          <Diagnostics result={result} />
        </div>
      </details>
    </section>
  );
}

/** Friendly, non-alarming note for degraded optional data. */
export function SoftNotices({ messages }: { messages: string[] }) {
  if (!messages.length) return null;
  return (
    <ul className="space-y-1.5" aria-label="Notes about this result">
      {messages.map((m) => (
        <li key={m} className="flex items-start gap-2 text-[13px] text-muted">
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />{m}
        </li>
      ))}
    </ul>
  );
}
