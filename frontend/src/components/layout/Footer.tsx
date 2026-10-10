import { Link } from "react-router-dom";
import { usePlanMission } from "../../hooks/useMission";
import { Logo } from "./Logo";

export function Footer() {
  const plan = usePlanMission();
  return (
    <footer className="mt-auto bg-ink text-white/70">
      <div className="container-page grid gap-10 py-14 md:grid-cols-12">
        <div className="md:col-span-5">
          <Logo inverse />
          <p className="mt-4 max-w-sm text-[14px] leading-relaxed">
            A multi-modal travel decision engine. Flights, trains, buses, hotels, maps, places and reviews — evaluated
            against your deadline, budget and buffer.
          </p>
        </div>
        <div className="md:col-span-3">
          <p className="eyebrow text-white/45">Product</p>
          <ul className="mt-3 space-y-2 text-[14px]">
            <li><button type="button" className="hover:text-white" onClick={plan}>Plan a mission</button></li>
            <li><Link className="hover:text-white" to="/#how-it-works">How it works</Link></li>
            <li><Link className="hover:text-white" to="/about">How we decide</Link></li>
          </ul>
        </div>
        <div className="md:col-span-4">
          <p className="eyebrow text-white/45">Data</p>
          <p className="mt-3 text-[14px] leading-relaxed">
            Live data via SerpApi: Google Flights, Hotels, Maps, Directions, Local and Maps Reviews. Prices and times
            change — always confirm before booking.
          </p>
        </div>
      </div>
      <div className="border-t border-white/10">
        <div className="container-page flex flex-col gap-2 py-5 text-[12.5px] text-white/45 sm:flex-row sm:justify-between">
          <span>Built for the SerpApi India Hackathon 2026 · Travel &amp; Local Discovery</span>
          <span>TripMission does not book travel or guarantee arrival.</span>
        </div>
      </div>
    </footer>
  );
}
