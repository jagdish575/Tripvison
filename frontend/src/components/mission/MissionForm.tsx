import { Mail, Sparkles } from "lucide-react";
import type { ReactNode } from "react";
import { useTemplates } from "../../hooks/useMission";
import type { AccessibilityNeed, MissionRequest, MissionType, Preference, TravelModeChoice } from "../../types/api";
import { cx, todayIso } from "../../utils/format";
import { MODE_CHOICES, MODE_META, PREFERENCES, PRIORITIES } from "../../utils/mission";
import { Segmented, Stepper, Toggle } from "../ui/Controls";
import { Field, LocationInput, MoneyInput, type FieldErrors } from "./fields";
import { MissionTypeSelector } from "./MissionTypeSelector";

type Setter = <K extends keyof MissionRequest>(key: K, value: MissionRequest[K]) => void;

const ACCESSIBILITY: { id: AccessibilityNeed; label: string }[] = [
  { id: "wheelchair", label: "Wheelchair accessibility required" },
  { id: "elevator", label: "Elevator required" },
  { id: "accessible_hotel", label: "Accessible hotel" },
  { id: "accessible_transport", label: "Accessible transport" },
];

function FormSection({ index, title, description, children }: {
  index: number; title: string; description?: string; children: ReactNode;
}) {
  return (
    <section className="grid gap-5 border-t border-line py-8 first:border-t-0 first:pt-0 md:grid-cols-[200px_1fr] md:gap-10">
      <div>
        <p className="tnum text-[12px] font-semibold text-subtle">{String(index).padStart(2, "0")}</p>
        <h2 className="mt-1 text-[17px] font-semibold tracking-[-0.01em]">{title}</h2>
        {description && <p className="mt-1 text-[13.5px] leading-relaxed text-muted">{description}</p>}
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

function Chip({ active, onClick, children, title }: { active: boolean; onClick: () => void; children: ReactNode; title?: string }) {
  return (
    <button type="button" aria-pressed={active} title={title} onClick={onClick}
      className={cx("inline-flex h-9 items-center gap-2 rounded-sm border px-3 text-[13.5px] font-medium transition-colors",
        active ? "border-blue bg-blue-wash text-blue-ink" : "border-line-strong bg-surface text-fg hover:border-subtle")}>
      {children}
    </button>
  );
}

/** Apply a mission template's defaults; every value stays editable. */
export function useApplyTemplate(set: Setter) {
  const { data } = useTemplates();
  return (type: MissionType) => {
    set("mission_type", type);
    const t = data?.templates.find((x) => x.mission_type === type);
    if (!t) return;
    set("priority", t.priority);
    set("min_buffer_minutes", t.min_buffer_minutes);
    set("max_stops", t.max_stops);
    set("hotel_required", t.hotel_required);
  };
}

export function MissionForm({ draft, errors, set }: { draft: MissionRequest; errors: FieldErrors; set: Setter }) {
  const { data: templates } = useTemplates();
  const applyTemplate = useApplyTemplate(set);
  const template = templates?.templates.find((t) => t.mission_type === draft.mission_type);
  const togglePref = (p: Preference) =>
    set("preferences", draft.preferences.includes(p) ? draft.preferences.filter((x) => x !== p) : [...draft.preferences, p]);
  const toggleMode = (m: TravelModeChoice) => {
    const next = draft.modes.includes(m) ? draft.modes.filter((x) => x !== m) : [...draft.modes, m];
    if (next.length) set("modes", next);
  };
  const toggleAccess = (a: AccessibilityNeed) =>
    set("accessibility", draft.accessibility.includes(a) ? draft.accessibility.filter((x) => x !== a) : [...draft.accessibility, a]);
  const notify = draft.notifications;

  return (
    <div>
      <FormSection index={1} title="Route" description="Where you start, exactly where you need to be, and how you could get there.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="From" htmlFor="origin" error={errors.origin} hint="City, town or airport">
            <LocationInput id="origin" value={draft.origin} onChange={(v) => set("origin", v)} placeholder="Indore"
              invalid={Boolean(errors.origin)} />
          </Field>
          <Field label="To" htmlFor="destination" error={errors.destination} hint="Any city or town — an airport isn't needed">
            <LocationInput id="destination" value={draft.destination} onChange={(v) => set("destination", v)}
              placeholder="Bengaluru" invalid={Boolean(errors.destination)} />
          </Field>
          <Field label="Venue" htmlFor="venue" className="sm:col-span-2"
            hint="The building or area you must reach — every transfer, train route and hotel distance is measured to it.">
            <input id="venue" className="field-input" value={draft.venue ?? ""} placeholder="e.g. Manyata Tech Park"
              onChange={(e) => set("venue", e.target.value)} maxLength={160} />
          </Field>
        </div>
        <div className="mt-5">
          <p className="mb-2 text-[13px] font-medium">Travel modes to compare</p>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Travel modes to compare">
            {MODE_CHOICES.map((m) => {
              const Icon = MODE_META[m.id].icon;
              return (
                <Chip key={m.id} active={draft.modes.includes(m.id)} onClick={() => toggleMode(m.id)} title={m.hint}>
                  <Icon className="size-4" aria-hidden />{m.label}
                </Chip>
              );
            })}
          </div>
          <p className="mt-2 text-[12.5px] text-muted">We skip modes that don't make sense — no flights for short trips — and route
            through the nearest airport or station when your destination doesn't have one.</p>
        </div>
      </FormSection>

      <FormSection index={2} title="Mission" description="Choosing a mission applies a template — sensible defaults you can change.">
        <MissionTypeSelector value={draft.mission_type} onChange={applyTemplate} />
        {template && (
          <p className="mt-3 flex items-start gap-2 rounded-sm bg-paper px-3 py-2.5 text-[13px] text-fg">
            <Sparkles className="mt-0.5 size-3.5 shrink-0 text-amber-ink" aria-hidden />
            <span><span className="font-medium">{template.label} template:</span> {template.highlights.join(" · ")} ·
              risk tolerance {template.risk_tolerance}. Adjust anything below.</span>
          </p>
        )}
        <div className="mt-5 flex items-center justify-between gap-4">
          <div>
            <p className="text-[14px] font-medium">Travellers</p>
            <p className="text-[13px] text-muted">Fares, cabs and food scale with the group.</p>
          </div>
          <Stepper label="travellers" value={draft.travelers} min={1} max={9} onChange={(v) => set("travelers", v)} />
        </div>
      </FormSection>

      <FormSection index={3} title="What matters most?" description="Changes the score weights — deterministic, never decided by AI.">
        <div role="radiogroup" aria-label="What matters most" className="grid gap-2 sm:grid-cols-2">
          {PRIORITIES.map((p) => {
            const active = draft.priority === p.id;
            const Icon = p.icon;
            return (
              <button key={p.id} type="button" role="radio" aria-checked={active} onClick={() => set("priority", p.id)}
                className={cx("flex items-start gap-3 rounded-sm border px-3.5 py-3 text-left transition-colors",
                  active ? "border-ink bg-ink text-white" : "border-line-strong bg-surface hover:border-subtle")}>
                <Icon className={cx("mt-0.5 size-[18px] shrink-0", active ? "text-amber" : "text-muted")} strokeWidth={1.8} aria-hidden />
                <span>
                  <span className="block text-[14px] font-semibold">{p.label}</span>
                  <span className={cx("block text-[12.5px]", active ? "text-white/65" : "text-muted")}>{p.hint}</span>
                </span>
              </button>
            );
          })}
        </div>
      </FormSection>

      <FormSection index={4} title="Timing" description="Your deadline is the hard constraint. The buffer is your safety margin.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Mission date" htmlFor="travel_date" error={errors.travel_date}>
            <input id="travel_date" type="date" className="field-input tnum" min={todayIso(0)} value={draft.travel_date}
              aria-invalid={Boolean(errors.travel_date) || undefined} onChange={(e) => set("travel_date", e.target.value)} />
          </Field>
          <Field label="Must arrive by" htmlFor="arrival_deadline" error={errors.arrival_deadline} hint="Local time at the venue">
            <input id="arrival_deadline" type="time" className="field-input tnum" value={draft.arrival_deadline}
              aria-invalid={Boolean(errors.arrival_deadline) || undefined} onChange={(e) => set("arrival_deadline", e.target.value)} />
          </Field>
        </div>
        <div className="mt-5">
          <p className="mb-2 text-[13px] font-medium">Minimum arrival buffer</p>
          <Segmented label="Minimum arrival buffer" value={draft.min_buffer_minutes} onChange={(v) => set("min_buffer_minutes", v)}
            className="w-full" options={[15, 30, 45, 60, 90, 120].map((m) => ({ value: m, label: `${m} min` }))} />
        </div>
        <div className="mt-5 rounded-sm border border-line bg-paper px-4 py-3">
          <Toggle checked={draft.allow_previous_day} onChange={(v) => {
            set("allow_previous_day", v);
            if (v) set("preferences", draft.preferences.filter((p) => p !== "same_day_only"));
          }}
            label="Consider arriving the day before"
            description="Arriving the evening before removes delay risk. We compare both automatically." />
        </div>
      </FormSection>

      <FormSection index={5} title="Budget & stay" description="Total for everyone, all-in: tickets, hotel, ground transport and food.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Total budget" htmlFor="budget" error={errors.budget}>
            <MoneyInput id="budget" value={draft.budget} onChange={(v) => set("budget", v)} invalid={Boolean(errors.budget)} />
          </Field>
          <Field label="Food estimate per day" htmlFor="food" hint="Estimated — included in the total trip cost">
            <MoneyInput id="food" value={draft.food_per_day} onChange={(v) => set("food_per_day", v)} />
          </Field>
          <Field label="Max ground travel on the day" htmlFor="max_ground"
            hint={`${draft.max_ground_minutes} minutes of taxi or local transit`}>
            <input id="max_ground" type="range" min={30} max={180} step={15} value={draft.max_ground_minutes}
              onChange={(e) => set("max_ground_minutes", Number(e.target.value))}
              className="mt-3 h-1.5 w-full cursor-pointer accent-blue" aria-valuetext={`${draft.max_ground_minutes} minutes`} />
          </Field>
          <div className="flex items-end justify-between gap-4 sm:justify-start sm:gap-6">
            <div>
              <p className="text-[13px] font-medium">Hotel nights</p>
              <p className="text-[12.5px] text-muted">Nights you'll stay</p>
            </div>
            <Stepper label="hotel nights" value={draft.stay_nights} min={1} max={14} onChange={(v) => set("stay_nights", v)} />
          </div>
        </div>
        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          <div>
            <p className="mb-2 text-[13px] font-medium">Flight stops</p>
            <Segmented label="Maximum stops" value={draft.max_stops} onChange={(v) => set("max_stops", v)} className="w-full"
              options={[{ value: 0, label: "Direct only" }, { value: 1, label: "≤ 1 stop" }, { value: 2, label: "≤ 2 stops" }]} />
          </div>
          <div>
            <p className="mb-2 text-[13px] font-medium">Minimum hotel rating</p>
            <Segmented label="Minimum hotel rating" value={draft.min_hotel_rating} onChange={(v) => set("min_hotel_rating", v)}
              className="w-full" options={[{ value: 0, label: "Any" }, { value: 3.5, label: "3.5★" }, { value: 4, label: "4.0★" }, { value: 4.5, label: "4.5★" }]} />
          </div>
        </div>
        <div className="mt-5 rounded-sm border border-line bg-paper px-4 py-3">
          <Toggle checked={draft.hotel_required} onChange={(v) => set("hotel_required", v)} label="I need a hotel"
            description="Arriving the day before always includes one. Otherwise no hotel cost is added." />
        </div>
      </FormSection>

      <FormSection index={6} title="Preferences & access" description="Small, transparent adjustments. Accessibility is only claimed when the data says so.">
        <div className="flex flex-wrap gap-2">
          {PREFERENCES.map((p) => (
            <Chip key={p.id} active={draft.preferences.includes(p.id)} title={p.hint} onClick={() => {
              togglePref(p.id);
              if (p.id === "same_day_only" && !draft.preferences.includes(p.id)) set("allow_previous_day", false);
            }}>{p.label}</Chip>
          ))}
        </div>
        <fieldset className="mt-5">
          <legend className="mb-2 text-[13px] font-medium">Accessibility (optional)</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {ACCESSIBILITY.map((a) => (
              <label key={a.id} className="flex items-center gap-2.5 text-[14px] text-fg">
                <input type="checkbox" className="size-4 accent-blue" checked={draft.accessibility.includes(a.id)}
                  onChange={() => toggleAccess(a.id)} />
                {a.label}
              </label>
            ))}
          </div>
        </fieldset>
      </FormSection>

      <FormSection index={7} title="Email updates" description="Optional. A summary, a reminder before you leave, and alerts only for meaningful changes.">
        <label className="flex items-center gap-2.5 text-[14px] font-medium text-fg">
          <input type="checkbox" className="size-4 accent-blue" checked={Boolean(notify)}
            onChange={(e) => set("notifications", e.target.checked ? { email: "", trip_summary: true, reminder: true, changes: true } : null)} />
          <Mail className="size-4 text-muted" aria-hidden /> Send me trip updates
        </label>
        {notify && (
          <div className="mt-4 space-y-3 rounded-sm border border-line bg-paper px-4 py-4">
            <Field label="Email" htmlFor="notify_email" error={errors.notifications}>
              <input id="notify_email" type="email" className="field-input" autoComplete="email" placeholder="you@example.com"
                value={notify.email} aria-invalid={Boolean(errors.notifications) || undefined}
                onChange={(e) => set("notifications", { ...notify, email: e.target.value })} />
            </Field>
            {([["trip_summary", "Trip summary"], ["reminder", "Reminder before departure"], ["changes", "Important journey changes"]] as const).map(([key, label]) => (
              <label key={key} className="flex items-center gap-2.5 text-[14px] text-fg">
                <input type="checkbox" className="size-4 accent-blue" checked={notify[key]}
                  onChange={(e) => set("notifications", { ...notify, [key]: e.target.checked })} />
                {label}
              </label>
            ))}
          </div>
        )}
      </FormSection>
    </div>
  );
}
