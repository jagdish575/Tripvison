import { motion, type Variants } from "framer-motion";
import { BedDouble, MapPinned, MessageSquareQuote, Navigation, Plane, Store } from "lucide-react";
import { SectionHeading } from "../ui/Controls";

const view = { initial: "hidden", whileInView: "show", viewport: { once: true, margin: "-80px" } } as const;
const rise: Variants = { hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } } };
const list: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } };

/* --------------------------------------------------------------- the gap */
const TOOLS = [
  { name: "Flight & train search", answers: "Which flights and trains exist, and the fare.", misses: "Which one actually gets me there on time?" },
  { name: "Hotel search", answers: "Which hotels are available tonight.", misses: "Is it close to where I need to be?" },
  { name: "Maps", answers: "How long one drive takes.", misses: "Does it fit inside my buffer?" },
];

export function GapSection() {
  return (
    <section className="container-page py-20 sm:py-24">
      <SectionHeading eyebrow="The problem"
        title={<>Travel search tells you what exists.<br className="hidden sm:block" /> Not whether it works.</>}
        description="For an interview, an exam or a hospital appointment, a missed connection isn't an inconvenience — it's the whole trip. Today you stitch three tools together in your head." />
      <motion.div {...view} variants={list} className="mt-10 grid gap-px overflow-hidden rounded-md border border-line bg-line md:grid-cols-4">
        {TOOLS.map((t) => (
          <motion.div key={t.name} variants={rise} className="bg-surface p-6">
            <p className="text-[15px] font-semibold text-ink">{t.name}</p>
            <p className="mt-4 eyebrow text-[10.5px]">Answers</p>
            <p className="mt-1 text-[14px] text-fg">{t.answers}</p>
            <p className="mt-4 eyebrow text-[10.5px]">Never asks</p>
            <p className="mt-1 text-[14px] text-muted">{t.misses}</p>
          </motion.div>
        ))}
        <motion.div variants={rise} className="bg-ink p-6 text-white">
          <p className="text-[15px] font-semibold">TripMission</p>
          <p className="mt-4 eyebrow text-[10.5px] text-white/45">Answers</p>
          <p className="mt-1 display text-[21px] leading-snug text-white">
            Flight, train or bus — which <em>whole</em> journey gets me there on time, within budget, and what could go wrong?
          </p>
        </motion.div>
      </motion.div>
    </section>
  );
}

/* --------------------------------------------------------------- how it works */
const STEPS = [
  { title: "Tell us your mission", body: "Where you need to be, by when, and what you can spend." },
  { title: "We search live data", body: "Flights, train and bus schedules, hotels near your venue and real driving times." },
  { title: "We evaluate every journey", body: "Every mode is costed all-in — ticket, hotel, transfers, food — and timed door to venue." },
  { title: "We calculate risk", body: "Thin buffers, tight layovers, delay-prone flights, long transfers, budget overruns." },
  { title: "We recommend one", body: "With the numbers, the trade-offs, and exactly when to leave." },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-20 border-y border-line bg-surface">
      <div className="container-page py-20 sm:py-24">
        <SectionHeading eyebrow="How it works" title="From a deadline to a journey you can trust" />
        <motion.ol {...view} variants={list} className="relative mt-12 grid gap-8 md:grid-cols-5 md:gap-6">
          <motion.span aria-hidden className="absolute left-[11px] top-3 hidden h-px origin-left bg-ink md:left-3 md:right-3 md:block"
            variants={{ hidden: { scaleX: 0 }, show: { scaleX: 1, transition: { duration: 1.1, ease: [0.22, 1, 0.36, 1] } } }} />
          {STEPS.map((s, i) => (
            <motion.li key={s.title} variants={rise} className="relative flex gap-4 md:block">
              <span className="relative z-10 grid size-6 shrink-0 place-items-center rounded-full border border-ink bg-surface text-[11px] font-semibold text-ink tnum">
                {i + 1}
              </span>
              <div className="md:mt-5">
                <p className="text-[15.5px] font-semibold text-ink">{s.title}</p>
                <p className="mt-1.5 text-[14px] leading-relaxed text-muted">{s.body}</p>
              </div>
            </motion.li>
          ))}
        </motion.ol>
      </div>
    </section>
  );
}

/* --------------------------------------------------------------- how we decide */
export const TIME_CRITICAL_WEIGHTS = [
  { label: "Arrival reliability", w: 30, note: "Buffer after delay exposure, connections and traffic" },
  { label: "Budget", w: 20, note: "Total trip cost — fit to budget and vs the cheapest" },
  { label: "Ground travel", w: 15, note: "Taxi or local transit on the day vs your limit" },
  { label: "Location & stay", w: 10, note: "Hotel distance to the venue and guest rating" },
  { label: "Travel time", w: 10, note: "Time travelling vs the quickest option" },
  { label: "Convenience", w: 10, note: "Changes, night travel, walking, very early starts" },
  { label: "Review confidence", w: 5, note: "Volume and share of positive mentions" },
];

export function HowWeDecide() {
  return (
    <section className="container-page grid gap-12 py-20 sm:py-24 lg:grid-cols-12">
      <div className="lg:col-span-5">
        <SectionHeading eyebrow="How we decide" title="A scoring engine, not a chatbot" />
        <div className="mt-5 space-y-4 text-[15px] leading-relaxed text-muted">
          <p>Every recommendation comes from deterministic maths on live search results and your constraints. The same inputs always produce the same answer.</p>
          <p>AI is only used to put the result into words. It receives the engine's numbers, and its text is rejected if it contains a single number that isn't in that data.</p>
          <p>Each result has a short “How we decided” note: what is live, what is calculated and what is estimated.</p>
        </div>
      </div>
      <div className="lg:col-span-7">
        <div className="card p-6">
          <div className="flex items-baseline justify-between gap-4">
            <p className="text-[14px] font-semibold text-ink">Mission Score weights</p>
            <p className="text-[12px] text-muted">Balanced priority (default)</p>
          </div>
          <motion.ul {...view} variants={list} className="mt-5 space-y-4">
            {TIME_CRITICAL_WEIGHTS.map((w) => (
              <motion.li key={w.label} variants={rise}>
                <div className="flex items-baseline justify-between gap-4 text-[14px]">
                  <span className="font-medium text-ink">{w.label}</span>
                  <span className="font-semibold text-ink tnum">{w.w}%</span>
                </div>
                <div className="mt-1.5 h-1 rounded-full bg-line">
                  <div className="h-full rounded-full bg-ink" style={{ width: `${(w.w / 30) * 100}%` }} />
                </div>
                <p className="mt-1 text-[12.5px] text-muted">{w.note}</p>
              </motion.li>
            ))}
          </motion.ul>
          <p className="mt-6 border-t border-line pt-4 text-[12.5px] text-muted">
            “What matters most?” switches the profile: Save money puts 45% on cost, Save time 40% on travel time, Avoid risk 40% on arrival reliability.
          </p>
        </div>
      </div>
    </section>
  );
}

/* --------------------------------------------------------------- data sources */
const SOURCES = [
  { icon: Plane, name: "Google Flights", body: "Schedules, prices, layovers — and the “often delayed by 30+ min” flag." },
  { icon: BedDouble, name: "Google Hotels", body: "Rates, ratings, coordinates and per-aspect review mentions." },
  { icon: MapPinned, name: "Google Maps", body: "Pins your exact venue and every shortlisted hotel." },
  { icon: Navigation, name: "Maps Directions", body: "Driving times with traffic ranges, plus live train and bus schedules from Google Maps transit." },
  { icon: Store, name: "Google Local", body: "Cafés, pharmacies and more — chosen for your kind of mission." },
  { icon: MessageSquareQuote, name: "Maps Reviews", body: "Recent guest reviews, read for concrete signals like noise." },
];

export function DataSourcesStrip() {
  return (
    <section className="border-t border-line bg-surface">
      <div className="container-page py-20 sm:py-24">
        <SectionHeading eyebrow="Live data via SerpApi" title="Six live sources. One decision."
          description="Only promising candidates get the expensive lookups: flights and transit routes are filtered first, then hotels, directions and reviews are fetched for the best few." />
        <motion.ul {...view} variants={list} className="mt-10 grid gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
          {SOURCES.map(({ icon: Icon, name, body }) => (
            <motion.li key={name} variants={rise} className="flex gap-4">
              <span className="grid size-10 shrink-0 place-items-center rounded-sm border border-line bg-paper text-ink">
                <Icon className="size-[18px]" strokeWidth={1.8} aria-hidden />
              </span>
              <div>
                <p className="text-[15px] font-semibold text-ink">{name}</p>
                <p className="mt-1 text-[14px] leading-relaxed text-muted">{body}</p>
              </div>
            </motion.li>
          ))}
        </motion.ul>
      </div>
    </section>
  );
}
