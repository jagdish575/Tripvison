import { motion, useMotionValueEvent, useScroll, useSpring, useTransform, type Variants } from "framer-motion";
import { BedDouble, Briefcase, Bus, Clock, GraduationCap, HeartPulse, MapPinned, MessageSquareQuote, Navigation, PartyPopper, Plane, Store, Train } from "lucide-react";
import { useRef, useState } from "react";
import { cx } from "../../utils/format";
import { SectionHeading } from "../ui/Controls";
import { TrainArt } from "./Vehicles";

const view = { initial: "hidden", whileInView: "show", viewport: { once: true, margin: "-80px" } } as const;
const rise: Variants = { hidden: { opacity: 0, y: 22 }, show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] } } };
const list: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } };

/* --------------------------------------------------------------- mission ticker */
const TICKER = [
  { icon: Briefcase, text: "Job interview" },
  { icon: GraduationCap, text: "Exam centre" },
  { icon: HeartPulse, text: "Hospital appointment" },
  { icon: PartyPopper, text: "Family wedding" },
  { icon: Train, text: "Overnight train, door to venue" },
  { icon: Bus, text: "Bus + cab under ₹3,000" },
  { icon: Plane, text: "Fly in the day before" },
  { icon: Clock, text: "60-minute buffer, checked" },
];

/** Endless strip of example missions (decorative; duplicated once so the loop is seamless). */
export function MissionTicker() {
  return (
    <div aria-hidden className="marquee-mask relative border-y border-white/60 bg-white/40 py-3.5 backdrop-blur-sm">
      <div className="flex w-max animate-marquee gap-3 hover:[animation-play-state:paused]">
        {[...TICKER, ...TICKER].map(({ icon: Icon, text }, i) => (
          <span key={i} className="inline-flex shrink-0 items-center gap-2 rounded-full border border-line bg-surface/80 px-4 py-1.5 text-[13px] font-medium text-fg shadow-sm">
            <Icon className="size-3.5 text-coral" aria-hidden />{text}
          </span>
        ))}
      </div>
    </div>
  );
}

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
      <motion.div {...view} variants={list} className="mt-10 grid gap-4 md:grid-cols-4">
        {TOOLS.map((t) => (
          <motion.div key={t.name} variants={rise} className="card card-hover rounded-2xl p-6">
            <p className="text-[15px] font-semibold text-ink">{t.name}</p>
            <p className="mt-4 eyebrow text-[10.5px]">Answers</p>
            <p className="mt-1 text-[14px] text-fg">{t.answers}</p>
            <p className="mt-4 eyebrow text-[10.5px]">Never asks</p>
            <p className="mt-1 text-[14px] text-muted">{t.misses}</p>
          </motion.div>
        ))}
        <motion.div variants={rise} whileHover={{ y: -4, scale: 1.02 }}
          className="relative isolate overflow-hidden rounded-2xl bg-gradient-to-br from-night via-[#24346e] to-[#8a3b6b] p-6 text-white shadow-[var(--shadow-glow)]">
          <span aria-hidden className="bg-stars absolute inset-0 -z-10 opacity-70" />
          <span aria-hidden className="aurora-blob -bottom-14 -right-10 -z-10 size-40 bg-sunrise/40" />
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

// sleepers between two rails
const RAIL_X = "repeating-linear-gradient(90deg, #cbd5e1 0 2px, transparent 2px 12px)";
const RAIL_Y = "repeating-linear-gradient(180deg, #cbd5e1 0 2px, transparent 2px 12px)";
const TRAIN = 120; // px, TrainArt length
const GAP = 24;    // px, md:gap-6 between step columns

/** The train is driven by scrolling: it rolls along the track and each step lights up as it arrives. */
export function HowItWorks() {
  const steps = useRef<HTMLOListElement>(null);
  const { scrollYProgress } = useScroll({ target: steps, offset: ["start 85%", "end 45%"] });
  const progress = useSpring(scrollYProgress, { stiffness: 120, damping: 24, mass: 0.4 });
  const [reached, setReached] = useState(1);
  useMotionValueEvent(scrollYProgress, "change", (v) =>
    setReached(Math.min(STEPS.length, Math.floor(v * (STEPS.length - 1) + 1.05))));
  // nose of the train on step n's circle (columns are 20% wide plus their share of the gaps; circle centre at 18px)
  const last = (STEPS.length - 1) / STEPS.length;
  const left = useTransform(progress, (v) => `calc(${v * last * 100}% + ${v * last * GAP + 18 - TRAIN}px)`);
  const top = useTransform(progress, (v) => `calc(${v * 100}% - ${v * TRAIN}px)`);

  return (
    <section id="how-it-works" className="relative isolate scroll-mt-20 overflow-hidden border-y border-line bg-surface">
      <span aria-hidden className="aurora-blob -right-40 top-0 -z-10 size-96 bg-coral/10" />
      <div className="container-page py-20 sm:py-24">
        <SectionHeading eyebrow="How it works" title="From a deadline to a journey you can trust" />

        {/* desktop: horizontal track above the steps */}
        <div aria-hidden className="relative mt-12 hidden h-9 overflow-hidden md:block">
          <span className="absolute inset-x-0 bottom-0 h-2 border-y-[1.5px] border-subtle" style={{ backgroundImage: RAIL_X }} />
          <motion.div className="absolute bottom-[5px]" style={{ left }}>
            <TrainArt className="h-7 w-[120px]" />
          </motion.div>
        </div>

        <motion.ol ref={steps} {...view} variants={list} className="relative mt-12 grid gap-8 md:mt-5 md:grid-cols-5 md:gap-6">
          {/* phones: vertical track beside the stacked steps; the train passes behind the step circles */}
          <span aria-hidden className="absolute bottom-0 left-[13px] top-0 w-2.5 border-x-[1.5px] border-subtle md:hidden"
            style={{ backgroundImage: RAIL_Y }} />
          <motion.div aria-hidden className="absolute left-[4px] md:hidden" style={{ top }}>
            <TrainArt vertical className="h-[120px] w-7" />
          </motion.div>
          {STEPS.map((s, i) => {
            const on = i < reached;
            return (
              <motion.li key={s.title} variants={rise} className="group relative flex gap-4 md:block">
                <span className={cx("relative z-10 grid size-9 shrink-0 place-items-center rounded-full text-[13px] font-semibold ring-4 ring-surface transition-[background-color,color,box-shadow,transform] duration-500 group-hover:scale-110 tnum",
                  on ? "bg-night text-white shadow-[var(--shadow-glow)]" : "border border-line-strong bg-surface text-muted")}>
                  {i + 1}
                </span>
                <div className="md:mt-4">
                  <p className={cx("text-[15.5px] font-semibold transition-colors duration-500", on ? "text-ink" : "text-muted")}>{s.title}</p>
                  <p className="mt-1.5 text-[14px] leading-relaxed text-muted">{s.body}</p>
                </div>
              </motion.li>
            );
          })}
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
        <div className="card card-hover rounded-2xl p-6 shadow-[var(--shadow-float)]">
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
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-paper-2">
                  <motion.div className="bg-brand h-full rounded-full" initial={{ width: 0 }}
                    whileInView={{ width: `${(w.w / 30) * 100}%` }} viewport={{ once: true }}
                    transition={{ duration: 1, delay: 0.15, ease: [0.22, 1, 0.36, 1] }} />
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
  { icon: Plane, tint: "from-blue to-sky", name: "Google Flights", body: "Schedules, prices, layovers — and the “often delayed by 30+ min” flag." },
  { icon: BedDouble, tint: "from-coral to-sunrise", name: "Google Hotels", body: "Rates, ratings, coordinates and per-aspect review mentions." },
  { icon: MapPinned, tint: "from-green to-sky", name: "Google Maps", body: "Pins your exact venue and every shortlisted hotel." },
  { icon: Navigation, tint: "from-amber to-sunrise", name: "Maps Directions", body: "Driving times with traffic ranges, plus live train and bus schedules from Google Maps transit." },
  { icon: Store, tint: "from-sunrise to-coral", name: "Google Local", body: "Cafés, pharmacies and more — chosen for your kind of mission." },
  { icon: MessageSquareQuote, tint: "from-sky to-blue", name: "Maps Reviews", body: "Recent guest reviews, read for concrete signals like noise." },
];

export function DataSourcesStrip() {
  return (
    <section className="relative isolate overflow-hidden border-t border-line bg-paper">
      <span aria-hidden className="aurora-blob -left-32 bottom-0 -z-10 size-96 bg-blue/10" />
      <div className="container-page py-20 sm:py-24">
        <SectionHeading eyebrow="Live data via SerpApi" title="Six live sources. One decision."
          description="Only promising candidates get the expensive lookups: flights and transit routes are filtered first, then hotels, directions and reviews are fetched for the best few." />
        <motion.ul {...view} variants={list} className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {SOURCES.map(({ icon: Icon, tint, name, body }) => (
            <motion.li key={name} variants={rise} className="card card-hover group flex gap-4 rounded-2xl p-5">
              <span className={`grid size-11 shrink-0 place-items-center rounded-xl bg-gradient-to-br ${tint} text-white shadow-md transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-110`}>
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
