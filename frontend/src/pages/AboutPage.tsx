import { useEffect } from "react";
import { DataSourcesStrip, HowItWorks, HowWeDecide } from "../components/landing/Sections";
import { SectionHeading } from "../components/ui/Controls";
import { useHealth } from "../hooks/useMission";

const RISKS = [
  ["Arrival buffer", "Below 30 minutes or half your minimum is high risk; below your minimum is medium."],
  ["Connections", "Each same-day connection or change of train is a risk; tight changes are called out."],
  ["Punctuality", "Long train and bus journeys have no live running status in our data, so same-day arrivals carry extra risk."],
  ["Delay history", "Google Flights' “often delayed by 30+ min” flag. Cushioned when you fly the day before."],
  ["Ground transfer", "Taxi time on the day above your limit, or traffic ranges that add 20+ minutes."],
  ["Hotel distance", "More than 5 km from the venue is medium risk; more than 10 km is high."],
  ["Budget", "Any overrun is flagged; more than 10% over is high risk."],
  ["Reviews", "Hotels below your rating minimum, or recurring complaints about noise, cleanliness or check-in."],
  ["Missing data", "Estimated driving times or unknown prices are called out, never hidden."],
];

const LIMITS = [
  "Flight delays are assessed from Google Flights' delay flag, not live flight status.",
  "Cab fares are estimated at ₹100 + ₹18/km; directions give time and distance, not taxi prices.",
  "Train and bus schedules come from Google Maps transit. Fares come from Google Search when it shows one for the same service; otherwise they are estimated (≈ ₹1.25/km 3AC, ₹1.8/km AC sleeper bus) and labelled.",
  "Intercity buses appear only where Google Maps has schedules — many private operators don't publish there.",
  "Places without an airport are fine: we route through the nearest practical airport, station or road. Airports come from a built-in reference of Indian and major international airports.",
  "One-way missions only; return journeys are on the roadmap.",
  "TripMission doesn't book anything — always confirm prices and schedules before you pay.",
];

export default function AboutPage() {
  const health = useHealth();
  useEffect(() => {
    document.title = "How we decide · TripMission";
  }, []);

  return (
    <>
      <header className="container-page pb-4 pt-14">
        <p className="eyebrow">About</p>
        <h1 className="display mt-2 max-w-3xl text-[40px] leading-[1.08] sm:text-[52px]">How TripMission decides</h1>
        <p className="mt-4 max-w-3xl text-[17px] leading-relaxed text-muted">
          TripMission is a travel decision engine. SerpApi supplies live data; our engine turns it into one recommended
          journey you can defend — with the numbers to prove it.
        </p>
      </header>
      <HowWeDecide />
      <HowItWorks />
      <section className="container-page grid gap-12 py-20 lg:grid-cols-2">
        <div>
          <SectionHeading as="h3" eyebrow="Risk engine" title="What counts as risk" />
          <dl className="mt-6 divide-y divide-line border-y border-line">
            {RISKS.map(([k, v]) => (
              <div key={k} className="grid gap-1 py-3 sm:grid-cols-[160px_1fr] sm:gap-6">
                <dt className="text-[14px] font-semibold text-ink">{k}</dt>
                <dd className="text-[14px] text-muted">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div>
          <SectionHeading as="h3" eyebrow="Honesty" title="Known limitations" />
          <ul className="mt-6 space-y-3 text-[14.5px] text-muted">
            {LIMITS.map((l) => <li key={l} className="border-l-2 border-line pl-4">{l}</li>)}
          </ul>
          {health.data?.debug_mode && <div className="mt-8 rounded-md border border-line bg-surface p-5 text-[14px]">
            <p className="font-semibold text-ink">This server (debug mode)</p>
            <p className="mt-1 text-muted">
              {health.data
                ? health.data.demo_mode
                  ? "Running in DEMO MODE with a labelled demo dataset."
                  : health.data.serpapi_configured
                    ? `Live mode · SerpApi connected · ${health.data.ai_configured ? `explanations by ${health.data.ai_model}` : "rule-based explanations"} · ${health.data.cache} cache.`
                    : "Live mode, but SERPAPI_API_KEY is missing — analyses will ask you to configure it."
                : "Checking…"}
            </p>
          </div>}
        </div>
      </section>
      <DataSourcesStrip />
    </>
  );
}
