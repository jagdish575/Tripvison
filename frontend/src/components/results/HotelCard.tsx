import { BedDouble, CircleCheck, ExternalLink, MapPin, Star } from "lucide-react";
import { useState } from "react";
import type { Itinerary, MissionSummary } from "../../types/api";
import { formatCount, formatDate, formatKm, formatMinutes, formatMoney } from "../../utils/format";

export function relevance(it: Itinerary, mission: MissionSummary): string | null {
  if (!it.hotel) return null;
  const leg = it.legs.find((l) => l.from_kind === "hotel" && l.to_kind === "venue");
  if (!leg) return null;
  const when = it.strategy === "night_before" ? "on the morning of your mission" : it.mode === "flight" ? "after you drop your bags" : "from the venue";
  return `${it.hotel.distance_km !== null ? formatKm(it.hotel.distance_km) : "Close"} from ${mission.venue.name} — a ${formatMinutes(leg.duration_minutes)} taxi ride ${when}.`;
}

function HotelImage({ src, name }: { src: string | null; name: string }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div className="flex h-full min-h-[180px] w-full flex-col items-center justify-center gap-2 bg-paper-2 text-subtle">
        <BedDouble className="size-8" strokeWidth={1.4} aria-hidden />
        <span className="text-[12px]">No photo available</span>
      </div>
    );
  }
  return <img src={src} alt={`${name}`} loading="lazy" onError={() => setFailed(true)}
    className="h-full min-h-[180px] w-full object-cover" />;
}

export function HotelCard({ itinerary: it, mission }: { itinerary: Itinerary; mission: MissionSummary }) {
  const hotel = it.hotel;
  if (!hotel) return null;
  const why = relevance(it, mission);
  return (
    <article className="card grid overflow-hidden md:grid-cols-[minmax(220px,38%)_1fr]">
      <div className="relative">
        <HotelImage src={hotel.image} name={hotel.name} />
      </div>
      <div className="flex flex-col p-5 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h3 className="text-[19px] font-semibold tracking-[-0.015em] text-ink">{hotel.name}</h3>
            <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-muted tnum">
              {hotel.rating !== null && (
                <span className="inline-flex items-center gap-1 font-medium text-ink">
                  <Star className="size-3.5 fill-amber text-amber" aria-hidden /> {hotel.rating.toFixed(1)}
                  <span className="font-normal text-muted">({formatCount(hotel.reviews)} reviews)</span>
                </span>
              )}
              {hotel.hotel_class && <span>{hotel.hotel_class}-star</span>}
              {hotel.distance_km !== null && (
                <span className="inline-flex items-center gap-1"><MapPin className="size-3.5" aria-hidden />{formatKm(hotel.distance_km)} to venue</span>
              )}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className="text-[19px] font-semibold text-ink tnum">{formatMoney(hotel.price_per_night, hotel.currency)}</p>
            <p className="text-[12px] text-muted">per night</p>
          </div>
        </div>

        {why && (
          <p className="mt-4 rounded-sm border-l-2 border-blue bg-blue-wash/60 px-3 py-2 text-[13.5px] text-fg tnum">
            <span className="font-semibold">Why this hotel: </span>{why}
          </p>
        )}

        {hotel.amenities.length > 0 && (
          <ul className="mt-4 flex flex-wrap gap-1.5" aria-label="Amenities">
            {hotel.amenities.slice(0, 7).map((a) => (
              <li key={a} className="rounded-xs border border-line bg-paper px-2 py-0.5 text-[12px] text-fg">{a}</li>
            ))}
          </ul>
        )}

        <div className="mt-auto flex flex-wrap items-center justify-between gap-3 pt-5 text-[12.5px] text-muted tnum">
          <span>
            {it.hotel_check_in && it.hotel_check_out && <>{formatDate(it.hotel_check_in)} → {formatDate(it.hotel_check_out)} · {it.cost.hotel_nights} night{it.cost.hotel_nights === 1 ? "" : "s"} · {formatMoney(it.cost.hotel, it.cost.currency)} total · </>}
            {hotel.check_in_time && <>check-in {hotel.check_in_time}</>}
          </span>
          <span className="flex items-center gap-3">
            {hotel.free_cancellation && (
              <span className="inline-flex items-center gap-1 font-medium text-green-ink"><CircleCheck className="size-3.5" aria-hidden />Free cancellation</span>
            )}
            {hotel.link && (
              <a className="link inline-flex items-center gap-1" href={hotel.link} target="_blank" rel="noreferrer noopener">
                View hotel <ExternalLink className="size-3" aria-hidden />
              </a>
            )}
          </span>
        </div>
      </div>
    </article>
  );
}
