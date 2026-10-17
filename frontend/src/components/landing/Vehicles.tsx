import { AnimatePresence, motion, useInView } from "framer-motion";
import { MapPin } from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";

/** Small decorative vehicles for the scroll "journey": plane (hero) → train (how it works) → car (arrival). */

/** Two carriages and a locomotive, facing right (or down when vertical). 120×28. */
export function TrainArt({ vertical = false, className }: { vertical?: boolean; className?: string }) {
  return (
    <svg viewBox={vertical ? "0 0 28 120" : "0 0 120 28"} className={className} aria-hidden>
      <g transform={vertical ? "translate(28 0) rotate(90)" : undefined}>
        {[0, 37].map((x) => (
          <g key={x}>
            <rect x={x} y="4" width="34" height="16" rx="3" fill="#0b1b3a" />
            {[4, 13, 22].map((w) => <rect key={w} x={x + w} y="7.5" width="7" height="5" rx="1" fill="#bfdcff" />)}
            <rect x={x} y="16" width="34" height="2" fill="#f0643f" />
          </g>
        ))}
        <path d="M74 4 H102 Q117 6 120 20 H74 Z" fill="#0b1b3a" />
        <path d="M104 7.5 Q112 9 115 14 H104 Z" fill="#bfdcff" />
        <rect x="74" y="16" width="45" height="2" fill="#f0643f" />
        <circle cx="117" cy="18" r="1.4" fill="#ffb547" />
        {[7, 27, 44, 64, 81, 108].map((cx) => <circle key={cx} cx={cx} cy="22" r="3" fill="#334155" />)}
      </g>
    </svg>
  );
}

/** Compact car facing right. 64×30. */
export function CarArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 30" className={className} aria-hidden>
      <path d="M3 21 Q3 15 9 14 L17 6.5 Q19.5 4.5 23 4.5 H39 Q43 4.5 46 7.5 L52.5 14 Q60 15 61 21 V24 H3 Z" fill="#fff" />
      <path d="M19 13 L24 8 H33 V13 Z M36 8 H40 Q42.5 8 44.5 10 L47.5 13 H36 Z" fill="#0b1b3a" />
      <circle cx="58.5" cy="18" r="1.6" fill="#ffb547" />
      <rect x="3" y="17" width="3" height="2.5" rx="1" fill="#f0643f" />
      {[15, 48].map((cx) => (
        <g key={cx}>
          <circle cx={cx} cy="24" r="5" fill="#0b1b3a" />
          <circle cx={cx} cy="24" r="2" fill="#94a3b8" />
        </g>
      ))}
    </svg>
  );
}

/* ---------------------------------------------------------------- arrival city */
// deterministic "random" so the skyline is identical on every render
function seeded(seed: number) {
  let x = seed;
  return () => ((x = (x * 16807) % 2147483647) - 1) / 2147483646;
}

interface Building { x: number; w: number; h: number; lit: { x: number; y: number }[] }

const SKYLINE: Building[] = (() => {
  const rnd = seeded(42);
  const out: Building[] = [];
  for (let x = 0; x < 1200;) {
    const w = 26 + Math.round(rnd() * 46);
    const h = 28 + Math.round(rnd() * 64);
    const lit: Building["lit"] = [];
    for (let wy = 100 - h + 8; wy < 92; wy += 10)
      for (let wx = x + 5; wx < x + w - 7; wx += 9) if (rnd() < 0.3) lit.push({ x: wx, y: wy });
    out.push({ x, w, h, lit });
    x += w + Math.round(rnd() * 6);
  }
  return out;
})();

/** Low city silhouette with a few lit windows, standing on the road. 1200×100, scales with the banner. */
function Skyline({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 1200 100" preserveAspectRatio="xMidYMax slice" className={className}>
      {SKYLINE.map((b) => (
        <g key={b.x}>
          <rect x={b.x} y={100 - b.h} width={b.w} height={b.h} fill="#0b1b3a" fillOpacity="0.82" />
          {b.lit.map((w) => <rect key={`${w.x}-${w.y}`} x={w.x} y={w.y} width="4" height="5" fill="#ffb547" fillOpacity="0.85" />)}
        </g>
      ))}
    </svg>
  );
}

// street lamps along the road, as a fraction of the banner width
const LAMPS = [0.1, 0.24, 0.38, 0.52, 0.66, 0.8];

const PUFFS = [0, 0.11, 0.22, 0.33, 0.44, 0.55, 0.66, 0.77, 0.88, 0.99];

/**
 * The last leg: once the banner is well in view, the car drives from the start of the road exactly once, trailing
 * exhaust puffs, parks beside the destination pin, and the pin drops in with "Arrived".
 */
export function ArrivalRoad() {
  const [phase, setPhase] = useState<"waiting" | "driving" | "arrived">("waiting");
  // the car waits at the start of the road; the drive begins once the road itself is in view
  const road = useRef<HTMLDivElement>(null);
  const roadInView = useInView(road, { once: true, amount: 0.9 });
  useEffect(() => {
    if (roadInView) setPhase((p) => (p === "waiting" ? "driving" : p));
  }, [roadInView]);
  return (
    <div aria-hidden>
      <Skyline className="absolute inset-x-0 bottom-14 h-24 w-full" />
      <div ref={road} className="absolute inset-x-0 bottom-0 h-14 bg-night/45">
        <span className="absolute inset-x-0 top-1/2 border-t-2 border-dashed border-white/30" />
      </div>
      {/* lamps switch on one by one as the car passes them (the drive eases out, so position ≈ √time) */}
      {LAMPS.map((f) => {
        const on = phase !== "waiting";
        const delay = 0.3 + 2.4 * f * f;
        return (
          <div key={f} className="absolute bottom-14" style={{ left: `${f * 100}%` }}>
            <span className="absolute bottom-0 left-0 h-12 w-[2px] rounded-full bg-[#94a3b8]/70" />
            <span className="absolute bottom-[46px] left-0 h-[2px] w-3 rounded-full bg-[#94a3b8]/70" />
            <span className={`absolute bottom-[42px] left-2.5 h-1.5 w-2.5 rounded-b-full transition-colors duration-300 ${on ? "bg-sunrise" : "bg-[#475569]"}`}
              style={{ transitionDelay: `${delay}s` }} />
            {/* light pool on the road */}
            <span className={`absolute -bottom-9 -left-4 h-12 w-12 rounded-full bg-sunrise/45 blur-md transition-opacity duration-500 ${on ? "opacity-100" : "opacity-0"}`}
              style={{ transitionDelay: `${delay}s` }} />
          </div>
        );
      })}
      {/* the car rides at the left of a box spanning the route; sliding that box by its own width parks the car just
          before the pin (right inset = pin gap + car width) */}
      <div className="absolute bottom-3 left-6 right-32 sm:left-12 sm:right-40">
        <motion.div className="flex justify-start" initial={false} animate={{ x: phase === "waiting" ? "0%" : "100%" }}
          transition={phase === "waiting" ? { duration: 0 } : { duration: 3, delay: 0.3, ease: [0.25, 0.8, 0.3, 1] }}
          onAnimationComplete={() => setPhase((p) => (p === "driving" ? "arrived" : p))}>
          <div className="relative">
            {/* exhaust: puffs leave the tailpipe, drift back and up, swell and fade; they stop once parked */}
            <AnimatePresence>
              {phase === "driving" && (
                <motion.span key="smoke" className="absolute -left-1 bottom-[7px]" exit={{ opacity: 0 }} transition={{ duration: 0.8 }}>
                  {PUFFS.map((d) => (
                    <span key={d} className="absolute size-4 rounded-full bg-[#e5e7eb]/85 blur-[2px] animate-puff"
                      style={{ animationDelay: `${d}s` }} />
                  ))}
                </motion.span>
              )}
            </AnimatePresence>
            <CarArt className="relative h-[30px] w-16" />
          </div>
        </motion.div>
      </div>
      <motion.span className="absolute bottom-7 right-6 flex flex-col items-center sm:right-12"
        initial={false} animate={phase === "arrived" ? { opacity: 1, y: 0 } : { opacity: 0, y: -24 }}
        transition={phase === "arrived" ? { type: "spring", stiffness: 260, damping: 12 } : { duration: 0 }}>
        <span className="mb-1 rounded-full bg-white px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-night">Arrived</span>
        <MapPin className="size-8 fill-sunrise text-white drop-shadow" strokeWidth={1.6} />
      </motion.span>
    </div>
  );
}

const City3D = lazy(() => import("./City3D"));

/** The arrival scene: real 3D when WebGL is available (three.js loads on its own), the flat street otherwise. */
export function CityArrival() {
  const [flat, setFlat] = useState(false);
  const fail = useCallback(() => setFlat(true), []);
  if (flat) return <ArrivalRoad />;
  return (
    <Suspense fallback={null}>
      <City3D onFail={fail} />
    </Suspense>
  );
}
