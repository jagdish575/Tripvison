import { ArrowRight, ChevronDown } from "lucide-react";
import type { MissionRequest } from "../../types/api";
import { formatDate, formatMoney } from "../../utils/format";
import { MODE_META, missionMeta, PRIORITIES } from "../../utils/mission";
import { Button } from "../ui/Button";

function rows(draft: MissionRequest): [string, string][] {
  return [
    ["Venue", draft.venue?.trim() || "City centre"],
    ["Budget", `${formatMoney(draft.budget, draft.currency)} total`],
    ["Priority", PRIORITIES.find((p) => p.id === draft.priority)?.label ?? "Balanced"],
    ["Modes", draft.modes.map((m) => MODE_META[m].label).join(", ")],
    ["Buffer", `≥ ${draft.min_buffer_minutes} min before`],
    ["Ground travel", `≤ ${draft.max_ground_minutes} min`],
    ["Flights", draft.max_stops === 0 ? "Direct only" : `≤ ${draft.max_stops} stop${draft.max_stops > 1 ? "s" : ""}`],
    ["Hotel", draft.hotel_required ? `${draft.stay_nights} night${draft.stay_nights > 1 ? "s" : ""} · ≥ ${draft.min_hotel_rating || "any"}★` : "Only if arriving the day before"],
    ["Food", `${formatMoney(draft.food_per_day, draft.currency)}/day (est.)`],
    ["Travellers", String(draft.travelers)],
  ];
}

/** Mobile / tablet: a one-line summary that expands to the full brief. */
export function MissionBriefCompact({ draft }: { draft: MissionRequest }) {
  const meta = missionMeta(draft.mission_type);
  return (
    <details className="group card overflow-hidden">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
        <span className="min-w-0">
          <span className="eyebrow block text-[10.5px]">Mission brief</span>
          <span className="block truncate text-[15px] font-semibold text-ink">
            {draft.origin || "—"} → {draft.destination || "—"}
            <span className="font-normal text-muted"> · {meta.label} by {draft.arrival_deadline || "—"} · {formatMoney(draft.budget, draft.currency)}</span>
          </span>
        </span>
        <ChevronDown className="size-4 shrink-0 text-muted transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <dl className="divide-y divide-line border-t border-line px-4">
        {rows(draft).map(([label, value]) => <Row key={label} label={label} value={value} />)}
      </dl>
    </details>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <dt className="text-[13px] text-muted">{label}</dt>
      <dd className="text-right text-[14px] font-medium text-ink tnum">{value}</dd>
    </div>
  );
}

export function MissionBrief({ draft, pending }: { draft: MissionRequest; pending: boolean }) {
  const meta = missionMeta(draft.mission_type);
  const Icon = meta.icon;
  return (
    <aside aria-label="Mission brief" className="card overflow-hidden">
      <div className="bg-ink px-5 py-5 text-white">
        <p className="eyebrow text-white/50">Mission brief</p>
        <p className="mt-2 display break-words text-[26px] leading-tight text-white">
          {draft.origin || "—"} <span className="text-white/40">→</span> {draft.destination || "—"}
        </p>
        <p className="mt-2 inline-flex items-center gap-2 text-[14px] text-white/75">
          <Icon className="size-4 text-amber" aria-hidden />
          {meta.label} at {draft.arrival_deadline || "—"}
          {draft.travel_date && <> · {formatDate(draft.travel_date, { weekday: "short", day: "numeric", month: "short" })}</>}
        </p>
      </div>
      <dl className="divide-y divide-line px-5 py-2">
        {rows(draft).map(([label, value]) => <Row key={label} label={label} value={value} />)}
      </dl>
      <div className="border-t border-line p-4">
        <Button type="submit" size="lg" className="w-full" loading={pending}>
          Find my journey {!pending && <ArrowRight className="size-4" aria-hidden />}
        </Button>
        <p className="mt-3 text-center text-[12px] text-muted">Compares flight, train, bus and road — door to door, all-in.</p>
      </div>
    </aside>
  );
}
