import { Bus, Navigation, Plane, Route, TrainFront } from "lucide-react";
import type { MissionResult, RouteNotice } from "../../types/api";
import { formatKm, formatMinutes } from "../../utils/format";

const ICON: Record<string, typeof Plane> = {
  airport_fallback: Plane, no_airport: Plane, origin_transfer: Plane, low_practicality: Plane,
  short_distance: Route, flight_skipped: Route, modes_added: Navigation,
};

function Notice({ notice }: { notice: RouteNotice }) {
  const Icon = ICON[notice.kind] ?? Route;
  return (
    <li className="flex items-start gap-3">
      <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-sm bg-blue-wash text-blue-ink">
        <Icon className="size-3.5" aria-hidden />
      </span>
      <p className="text-[14px] leading-relaxed text-fg">{notice.message}</p>
    </li>
  );
}

/** How TripMission routed this trip: airports, hubs and why some modes were skipped. Routing decisions, not errors. */
export function RouteNotices({ result }: { result: MissionResult }) {
  const route = result.route;
  if (!route) return null;
  const hubs = [
    route.destination_airport && {
      icon: Plane, label: route.destination_has_airport ? "Airport" : "Nearest practical airport",
      value: `${route.destination_airport.city} (${route.destination_airport.code}) · ${formatMinutes(route.destination_airport.transfer_minutes)} by road`,
    },
    route.railway_stations.length > 0 && { icon: TrainFront, label: "Railway stations", value: route.railway_stations.slice(0, 3).join(" · ") },
    route.bus_points.length > 0 && { icon: Bus, label: "Bus points", value: route.bus_points.slice(0, 3).join(" · ") },
  ].filter(Boolean) as { icon: typeof Plane; label: string; value: string }[];
  if (!route.notices.length && !hubs.length) return null;

  return (
    <section aria-labelledby="routing-title" className="card overflow-hidden">
      <div className="grid gap-6 p-5 sm:p-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] lg:gap-10">
        <div>
          <p id="routing-title" className="eyebrow">How we routed this trip</p>
          <p className="mt-1 text-[13px] text-muted tnum">
            {result.mission.origin.city} → {result.mission.destination.city} · about {formatKm(route.road_km)} by road
          </p>
          {route.notices.length > 0 && (
            <ul className="mt-4 space-y-3">{route.notices.map((n) => <Notice key={n.kind + n.message} notice={n} />)}</ul>
          )}
        </div>
        {hubs.length > 0 && (
          <dl className="space-y-3 border-t border-line pt-5 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
            {hubs.map(({ icon: Icon, label, value }) => (
              <div key={label} className="flex items-start gap-3">
                <Icon className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
                <div className="min-w-0">
                  <dt className="text-[11.5px] font-semibold uppercase tracking-[0.06em] text-subtle">{label}</dt>
                  <dd className="text-[14px] text-ink">{value}</dd>
                </div>
              </div>
            ))}
          </dl>
        )}
      </div>
    </section>
  );
}
