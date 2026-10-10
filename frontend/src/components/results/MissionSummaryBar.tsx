import { Columns3, Pencil } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { MissionSummary } from "../../types/api";
import { formatDate, formatMoney } from "../../utils/format";
import { missionMeta, PRIORITIES } from "../../utils/mission";

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="eyebrow text-[10.5px]">{label}</dt>
      <dd className="mt-0.5 truncate text-[14px] font-medium text-ink tnum">{children}</dd>
    </div>
  );
}

export function MissionSummaryBar({ mission, mode, onEdit, compareHref, actions }: {
  mission: MissionSummary; mode: "live" | "demo"; onEdit?: () => void; compareHref?: string; actions?: ReactNode;
}) {
  const meta = missionMeta(mission.mission_type);
  const Icon = meta.icon;
  return (
    <div className="border-b border-line bg-surface">
      <div className="container-page py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="eyebrow flex items-center gap-2">
              Mission summary
              {mode === "demo" && <span className="rounded-xs bg-amber-wash px-1.5 py-px text-amber-ink">Demo data</span>}
            </p>
            <p className="display mt-1 text-[26px] leading-tight sm:text-[30px]">
              {mission.origin.city} <span className="text-subtle">→</span> {mission.destination.city}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {actions}
            {compareHref && (
              <Link to={compareHref} className="inline-flex h-9 items-center gap-2 rounded-sm border border-line-strong bg-surface px-3 text-[13px] font-semibold text-fg hover:border-subtle">
                <Columns3 className="size-4" aria-hidden /> Compare options
              </Link>
            )}
            {onEdit && (
              <button type="button" onClick={onEdit} className="inline-flex h-9 items-center gap-2 rounded-sm px-3 text-[13px] font-semibold text-fg hover:bg-paper-2">
                <Pencil className="size-3.5" aria-hidden /> Edit mission
              </button>
            )}
          </div>
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 lg:grid-cols-5">
          <Fact label="Date">{formatDate(mission.travel_date, { weekday: "short", day: "numeric", month: "long" })}</Fact>
          <Fact label="Mission"><span className="inline-flex items-center gap-1.5"><Icon className="size-3.5 text-muted" aria-hidden />{meta.label} at {mission.arrival_deadline}</span></Fact>
          <Fact label="Venue">{mission.venue.name}</Fact>
          <Fact label="Budget">{formatMoney(mission.budget, mission.currency)}{mission.travelers > 1 && ` · ${mission.travelers} people`}</Fact>
          <Fact label="Buffer · priority">≥ {mission.min_buffer_minutes} min · {PRIORITIES.find((p) => p.id === mission.priority)?.label ?? "Balanced"}</Fact>
        </dl>
      </div>
    </div>
  );
}
