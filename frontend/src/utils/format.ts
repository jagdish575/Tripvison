const SYMBOLS: Record<string, string> = { INR: "₹", USD: "$", EUR: "€", GBP: "£" };

export function formatMoney(amount: number | null | undefined, currency = "INR"): string {
  if (amount === null || amount === undefined || Number.isNaN(amount)) return "—";
  const rounded = Math.round(amount);
  const locale = currency === "INR" ? "en-IN" : "en-US";
  const body = Math.abs(rounded).toLocaleString(locale);
  return `${rounded < 0 ? "−" : ""}${SYMBOLS[currency] ?? `${currency} `}${body}`;
}

export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "—";
  const m = Math.round(Math.abs(minutes));
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return rest === 0 ? `${h} h` : `${h} h ${rest} min`;
}

export function formatBuffer(minutes: number): string {
  if (minutes < 0) return `${formatMinutes(-minutes)} late`;
  return `${formatMinutes(minutes)} early`;
}

/** "2026-10-09T08:45:00" → "08:45" (times are already local to the place they describe). */
export function formatClock(iso: string | null | undefined): string {
  if (!iso) return "—";
  const match = /T(\d{2}):(\d{2})/.exec(iso);
  return match ? `${match[1]}:${match[2]}` : "—";
}

export function parseLocalDate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, (m ?? 1) - 1, d ?? 1);
}

export function formatDate(iso: string | null | undefined, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short" }): string {
  if (!iso) return "—";
  return parseLocalDate(iso).toLocaleDateString("en-GB", opts);
}

export function formatDayLabel(iso: string, missionDate: string): string {
  const day = iso.slice(0, 10);
  if (day === missionDate) return "Mission day";
  const diff = Math.round((parseLocalDate(day).getTime() - parseLocalDate(missionDate).getTime()) / 86_400_000);
  if (diff === -1) return "Day before";
  return formatDate(day, { weekday: "short", day: "numeric", month: "short" });
}

export function formatKm(km: number | null | undefined): string {
  if (km === null || km === undefined) return "—";
  return km < 10 ? `${km.toFixed(1)} km` : `${Math.round(km)} km`;
}

export function formatCount(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : String(n);
}

export function todayIso(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function plural(n: number, word: string, pluralWord = `${word}s`): string {
  return `${n} ${n === 1 ? word : pluralWord}`;
}

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}
