import "leaflet/dist/leaflet.css";
import { useEffect } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMap } from "react-leaflet";
import type { LatLngTuple } from "leaflet";
import type { Itinerary, MissionSummary } from "../../types/api";

function FitBounds({ points }: { points: LatLngTuple[] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length > 1) map.fitBounds(points, { padding: [36, 36] });
  }, [map, points]);
  return null;
}

export default function JourneyMap({ itinerary, mission }: { itinerary: Itinerary; mission: MissionSummary }) {
  const hub = mission.destination_airport?.location ?? mission.destination.location;
  const airport: LatLngTuple = [hub.lat, hub.lng];
  const venue: LatLngTuple = [mission.venue.location.lat, mission.venue.location.lng];
  const hotel: LatLngTuple | null = itinerary.hotel?.location ? [itinerary.hotel.location.lat, itinerary.hotel.location.lng] : null;
  const byAir = itinerary.mode === "flight" && Boolean(mission.destination_airport);
  const path: LatLngTuple[] = byAir ? (hotel ? [airport, hotel, venue] : [airport, venue]) : hotel ? [hotel, venue] : [venue];

  return (
    <figure className="overflow-hidden rounded-md border border-line">
      <MapContainer center={venue} zoom={11} scrollWheelZoom={false} className="h-[300px] w-full" attributionControl>
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          className="tm-tiles"
        />
        <Polyline positions={path} pathOptions={{ color: "#0b1220", weight: 2, dashArray: "4 6", opacity: 0.7 }} />
        {byAir && (
          <CircleMarker center={airport} radius={7} pathOptions={{ color: "#0b1220", fillColor: "#ffffff", fillOpacity: 1, weight: 2.5 }}>
            <Tooltip direction="top" offset={[0, -6]} permanent>{mission.destination_airport?.code} airport</Tooltip>
          </CircleMarker>
        )}
        {hotel && (
          <CircleMarker center={hotel} radius={7} pathOptions={{ color: "#2563eb", fillColor: "#2563eb", fillOpacity: 1, weight: 2 }}>
            <Tooltip direction="left" offset={[-6, 0]} permanent>Hotel</Tooltip>
          </CircleMarker>
        )}
        <CircleMarker center={venue} radius={8} pathOptions={{ color: "#0b1220", fillColor: "#f59e0b", fillOpacity: 1, weight: 2 }}>
          <Tooltip direction="right" offset={[8, 0]} permanent>{mission.venue.name}</Tooltip>
        </CircleMarker>
        <FitBounds points={path} />
      </MapContainer>
      <figcaption className="border-t border-line bg-surface px-3 py-2 text-[12px] text-muted">
        Schematic route — travel times come from road and transit routing, not straight lines.
      </figcaption>
    </figure>
  );
}
