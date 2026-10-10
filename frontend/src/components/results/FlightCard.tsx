import { Clock3, Plane, TriangleAlert } from "lucide-react";
import { useState } from "react";
import type { Flight } from "../../types/api";
import { formatClock, formatDate, formatMinutes, formatMoney } from "../../utils/format";

function AirlineMark({ flight }: { flight: Flight }) {
  const [failed, setFailed] = useState(false);
  if (flight.airline_logo && !failed) {
    return <img src={flight.airline_logo} alt="" className="size-9 rounded-sm border border-line bg-white object-contain p-1"
      loading="lazy" onError={() => setFailed(true)} />;
  }
  return <span className="grid size-9 place-items-center rounded-sm border border-line bg-paper text-muted"><Plane className="size-4" aria-hidden /></span>;
}

export function FlightCard({ flight, travelers }: { flight: Flight; travelers: number }) {
  return (
    <section aria-label="Flight" className="card p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <AirlineMark flight={flight} />
          <div>
            <p className="text-[15px] font-semibold text-ink">{flight.airline}</p>
            <p className="text-[13px] text-muted tnum">{flight.flight_numbers.join(" · ")} · {formatDate(flight.departure_time, { weekday: "short", day: "numeric", month: "short" })}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-[17px] font-semibold text-ink tnum">{formatMoney(flight.price, flight.currency)}</p>
          <p className="text-[12px] text-muted">{travelers > 1 ? `${travelers} travellers` : "1 traveller"}</p>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-[auto_1fr_auto] items-center gap-4">
        <div>
          <p className="text-[24px] font-semibold tracking-[-0.02em] text-ink tnum">{formatClock(flight.departure_time)}</p>
          <p className="text-[12.5px] font-medium text-muted">{flight.departure_airport}</p>
        </div>
        <div className="flex flex-col items-center">
          <p className="text-[12px] text-muted tnum">{formatMinutes(flight.duration_minutes)}</p>
          <div className="relative my-1.5 h-px w-full bg-line-strong">
            {flight.layovers.map((_, i) => (
              <span key={i} className="absolute top-1/2 size-2 -translate-y-1/2 rounded-full border border-subtle bg-surface"
                style={{ left: `${((i + 1) / (flight.layovers.length + 1)) * 100}%` }} />
            ))}
          </div>
          <p className="text-[12px] text-muted">
            {flight.stops === 0 ? "Direct" : flight.layovers.map((l) => `${l.duration_minutes} min in ${l.airport}`).join(", ")}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[24px] font-semibold tracking-[-0.02em] text-ink tnum">{formatClock(flight.arrival_time)}</p>
          <p className="text-[12.5px] font-medium text-muted">{flight.arrival_airport}</p>
        </div>
      </div>

      {flight.often_delayed && (
        <p className="mt-4 flex items-center gap-2 rounded-sm bg-amber-wash px-3 py-2 text-[13px] text-amber-ink">
          <TriangleAlert className="size-4 shrink-0" aria-hidden /> Google Flights flags this flight as often delayed by 30+ minutes.
        </p>
      )}
      {flight.segments.length > 1 && (
        <ul className="mt-4 space-y-1 border-t border-line pt-3 text-[12.5px] text-muted tnum">
          {flight.segments.map((s) => (
            <li key={s.flight_number} className="flex items-center gap-2">
              <Clock3 className="size-3.5" aria-hidden />
              {s.flight_number}: {s.departure_airport} {formatClock(s.departure_time)} → {s.arrival_airport} {formatClock(s.arrival_time)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
