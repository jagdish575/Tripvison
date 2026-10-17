import { ArrowRight, SlidersHorizontal } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { useStartMission } from "../../hooks/useMission";
import type { MissionRequest, MissionType } from "../../types/api";
import { cx, todayIso } from "../../utils/format";
import { defaultMission, loadDraft, MISSION_TYPES, saveDraft } from "../../utils/mission";
import { Button } from "../ui/Button";
import { ErrorState } from "../ui/States";
import { LocationInput, MoneyInput, validateMission, type FieldErrors } from "./fields";
import { useApplyTemplate } from "./MissionForm";

const cell = "h-9 w-full bg-transparent text-[15px] font-medium text-ink placeholder:text-subtle focus:outline-none";

function Cell({ label, htmlFor, error, children, className }: {
  label: string; htmlFor: string; error?: string; children: ReactNode; className?: string;
}) {
  return (
    <div className={cx("relative flex flex-col justify-center px-4 py-2.5 focus-within:bg-blue-wash/50", className)}>
      <label htmlFor={htmlFor} className={cx("eyebrow text-[10.5px]", error && "text-red-ink")}>{error ?? label}</label>
      {children}
    </div>
  );
}

export function HeroMissionBar() {
  const navigate = useNavigate();
  const [draft, setDraft] = useState<MissionRequest>(() => loadDraft() ?? defaultMission());
  const [errors, setErrors] = useState<FieldErrors>({});
  const start = useStartMission();
  const { requireAuth } = useAuth();
  const set = <K extends keyof MissionRequest>(key: K, value: MissionRequest[K]) => {
    setDraft((d) => ({ ...d, [key]: value }));
    setErrors((e) => ({ ...e, [key]: undefined }));
  };

  // The venue isn't shown in this bar: a venue picked for another city (e.g. the default "Manyata Tech Park"
  // for Bangalore) must not silently travel with a new destination.
  const setDestination = (value: string) => {
    setDraft((d) => ({ ...d, destination: value,
                       venue: value.trim().toLowerCase() === d.destination.trim().toLowerCase() ? d.venue : null }));
    setErrors((e) => ({ ...e, destination: undefined }));
  };

  const applyTemplate = useApplyTemplate(set);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const found = validateMission(draft);
    setErrors(found);
    if (Object.keys(found).length) return;
    start.start(draft);
  };

  const moreConstraints = () => {
    saveDraft(draft); // the full form opens with what was typed here — also across the sign-in popup
    requireAuth(() => navigate("/plan"), "plan");
  };

  const serverField = start.visibleError?.field as keyof MissionRequest | undefined;
  const fieldError = (k: keyof MissionRequest) => errors[k] ?? (serverField === k ? "We couldn't find this place" : undefined);

  return (
    <form onSubmit={submit} noValidate aria-label="Plan a mission" className="w-full">
      <div className="glass overflow-hidden rounded-2xl shadow-[var(--shadow-lift)] ring-1 ring-coral/10 transition-shadow duration-300 focus-within:ring-2 focus-within:ring-coral/30">
        <div className="grid grid-cols-2 divide-line md:grid-cols-[1.15fr_1.15fr_1fr] md:divide-x lg:grid-cols-[1.1fr_1.1fr_1fr_1fr_0.75fr_0.95fr_auto]">
          <Cell label="From" htmlFor="hero-origin" error={fieldError("origin")} className="border-b border-line lg:border-b-0">
            <LocationInput id="hero-origin" value={draft.origin} onChange={(v) => set("origin", v)} placeholder="City or airport"
              invalid={Boolean(fieldError("origin"))} inputClassName={cell} />
          </Cell>
          <Cell label="To" htmlFor="hero-destination" error={fieldError("destination")} className="border-b border-l border-line md:border-l-0 lg:border-b-0">
            <LocationInput id="hero-destination" value={draft.destination} onChange={setDestination}
              placeholder="City or airport" invalid={Boolean(fieldError("destination"))} inputClassName={cell} />
          </Cell>
          <Cell label="Mission" htmlFor="hero-type" className="col-span-2 border-b border-line md:col-span-1 lg:border-b-0">
            <select id="hero-type" value={draft.mission_type} onChange={(e) => applyTemplate(e.target.value as MissionType)}
              className={cx(cell, "cursor-pointer appearance-none")}>
              {MISSION_TYPES.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          </Cell>
          <Cell label="Date" htmlFor="hero-date" error={fieldError("travel_date")} className="border-b border-line lg:border-b-0">
            <input id="hero-date" type="date" min={todayIso(0)} value={draft.travel_date}
              onChange={(e) => set("travel_date", e.target.value)} className={cx(cell, "tnum")} />
          </Cell>
          <Cell label="Arrive by" htmlFor="hero-deadline" error={fieldError("arrival_deadline")} className="border-b border-l border-line md:border-l-0 lg:border-b-0">
            <input id="hero-deadline" type="time" value={draft.arrival_deadline}
              onChange={(e) => set("arrival_deadline", e.target.value)} className={cx(cell, "tnum")} />
          </Cell>
          <Cell label="Budget" htmlFor="hero-budget" error={fieldError("budget")} className="col-span-2 md:col-span-1">
            <MoneyInput id="hero-budget" value={draft.budget} onChange={(v) => set("budget", v)}
              inputClassName={cx(cell, "pl-4")} invalid={Boolean(fieldError("budget"))} />
          </Cell>
          <div className="col-span-2 flex items-center p-2 md:col-span-3 lg:col-span-1">
            <Button type="submit" size="lg" loading={start.isPending} className="w-full lg:h-full lg:min-h-[56px]">
              Find my journey
              {!start.isPending && <ArrowRight className="size-4" aria-hidden />}
            </Button>
          </div>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[13px] text-muted">
        <button type="button" onClick={moreConstraints} className="inline-flex items-center gap-1.5 font-medium text-fg transition-colors hover:text-coral">
          <SlidersHorizontal className="size-3.5" aria-hidden />
          Venue, buffer, hotel and more constraints
        </button>
        <span>Door to door · flights, trains, buses and road · no airport needed</span>
      </div>
      {start.visibleError && !serverField && (
        <ErrorState className="mt-4" title="We couldn't start this mission" message={start.visibleError.message} />
      )}
    </form>
  );
}
