import { useEffect, useId, useState, type ReactNode } from "react";
import { searchLocations } from "../../api/missions";
import type { LocationSuggestion, MissionRequest } from "../../types/api";
import { cx, todayIso } from "../../utils/format";

export type FieldErrors = Partial<Record<keyof MissionRequest, string>>;

export function validateMission(d: MissionRequest): FieldErrors {
  const e: FieldErrors = {};
  if (d.origin.trim().length < 2) e.origin = "Where are you starting from?";
  if (d.destination.trim().length < 2) e.destination = "Where do you need to be?";
  if (d.origin.trim() && d.origin.trim().toLowerCase() === d.destination.trim().toLowerCase())
    e.destination = "Destination must differ from the origin.";
  if (!d.travel_date) e.travel_date = "Pick the day of your mission.";
  else if (d.travel_date < todayIso(0)) e.travel_date = "That date is in the past.";
  if (!/^\d{2}:\d{2}$/.test(d.arrival_deadline)) e.arrival_deadline = "When do you need to be there?";
  if (!(d.budget > 0)) e.budget = "Enter your total budget.";
  if (d.notifications && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(d.notifications.email.trim()))
    e.notifications = "Enter a valid email address, or switch off trip updates.";
  return e;
}

export function Field({ label, hint, error, children, htmlFor, className }: {
  label: string; hint?: ReactNode; error?: string; children: ReactNode; htmlFor?: string; className?: string;
}) {
  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      <label htmlFor={htmlFor} className="text-[13px] font-medium text-fg">{label}</label>
      {children}
      {error ? (
        <p id={htmlFor ? `${htmlFor}-error` : undefined} className="text-[12.5px] font-medium text-red-ink">{error}</p>
      ) : hint ? (
        <p className="text-[12.5px] text-muted">{hint}</p>
      ) : null}
    </div>
  );
}

/** Text input with city / town / airport suggestions. Places without an airport are valid — TripMission routes
 * through the nearest practical hub. */
export function LocationInput({ id, value, onChange, placeholder, invalid, className, inputClassName }: {
  id: string; value: string; onChange: (v: string) => void; placeholder?: string; invalid?: boolean;
  className?: string; inputClassName?: string;
}) {
  const listId = useId();
  const [options, setOptions] = useState<LocationSuggestion[]>([]);
  useEffect(() => {
    const q = value.trim();
    if (q.length < 2) {
      setOptions([]);
      return;
    }
    const timer = setTimeout(() => {
      searchLocations(q).then((r) => setOptions(r.results)).catch(() => setOptions([]));
    }, 180);
    return () => clearTimeout(timer);
  }, [value]);
  return (
    <div className={className}>
      <input
        id={id}
        list={listId}
        value={value}
        autoComplete="off"
        spellCheck={false}
        placeholder={placeholder}
        aria-invalid={invalid || undefined}
        aria-describedby={invalid ? `${id}-error` : undefined}
        onChange={(e) => onChange(e.target.value)}
        className={inputClassName ?? "field-input"}
      />
      <datalist id={listId}>
        {options.map((o) => (
          <option key={o.label} value={o.label}>{o.code ? `${o.code} · ${o.detail}` : o.detail}</option>
        ))}
      </datalist>
    </div>
  );
}

export function MoneyInput({ id, value, onChange, currency = "INR", invalid, inputClassName }: {
  id: string; value: number; onChange: (v: number) => void; currency?: string; invalid?: boolean; inputClassName?: string;
}) {
  const symbol = currency === "INR" ? "₹" : currency;
  return (
    <div className="relative">
      <span className="pointer-events-none absolute inset-y-0 left-3 grid place-items-center text-[15px] text-muted">{symbol}</span>
      <input
        id={id}
        inputMode="numeric"
        value={value ? value.toLocaleString("en-IN") : ""}
        aria-invalid={invalid || undefined}
        onChange={(e) => onChange(Number(e.target.value.replace(/[^\d]/g, "")) || 0)}
        className={cx(inputClassName ?? "field-input", "pl-7 tnum")}
        placeholder="10,000"
      />
    </div>
  );
}

/** @deprecated kept for older imports — use LocationInput. */
export const AirportInput = LocationInput;
