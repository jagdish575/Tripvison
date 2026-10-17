/** Hero backdrop: a dawn sky with drifting clouds and a plane drawing a dashed contrail. Purely decorative. */

const CLOUD = "M25 60a20 20 0 0 1 4-39.6A28 28 0 0 1 82 14a22 22 0 0 1 33 20 16 16 0 0 1-2 32H25Z";

const CLOUDS = [
  { top: "8%", width: 200, opacity: 0.9, duration: "95s", delay: "-10s" },
  { top: "22%", width: 130, opacity: 0.7, duration: "120s", delay: "-60s" },
  { top: "4%", width: 260, opacity: 0.6, duration: "150s", delay: "-95s" },
  { top: "38%", width: 160, opacity: 0.55, duration: "110s", delay: "-30s" },
];

// one gentle arc across the open sky above the headline; the plane follows it and the contrail draws behind it
const FLIGHT = "M -40 96 C 300 18, 700 8, 1000 48 S 1350 40, 1500 8";

export function SkyScene() {
  return (
    <div aria-hidden className="bg-dawn pointer-events-none absolute inset-0 -z-10 overflow-hidden">
      {CLOUDS.map((c, i) => (
        <svg key={i} viewBox="0 0 130 70" className="absolute left-0 animate-cloud"
          style={{ top: c.top, width: c.width, opacity: c.opacity, animationDuration: c.duration, animationDelay: c.delay }}>
          <path d={CLOUD} fill="#fff" />
        </svg>
      ))}

      <svg viewBox="0 0 1440 110" preserveAspectRatio="xMidYMid slice" className="absolute inset-x-0 top-0 h-[110px] w-full">
        <defs>
          <path id="tm-flight" d={FLIGHT} pathLength={1000} />
          {/* the contrail is dashed, so it is revealed through a solid line that draws in step with the plane */}
          <mask id="tm-contrail" maskUnits="userSpaceOnUse" x="-100" y="-100" width="1700" height="310">
            <use href="#tm-flight" fill="none" stroke="#fff" strokeWidth="8" strokeDasharray="1000"
              strokeDashoffset={1000}>
              <animate attributeName="stroke-dashoffset" values="1000;0;0" keyTimes="0;0.85;1" dur="14s" repeatCount="indefinite" />
            </use>
          </mask>
        </defs>
        <use href="#tm-flight" fill="none" stroke="rgb(11 27 58 / 0.2)" strokeWidth="2" strokeDasharray="6 10"
          strokeLinecap="round" mask="url(#tm-contrail)" />
        <g className="motion-reduce:hidden">
          {/* small airliner pointing along +x so rotate="auto" follows the path */}
          <path d="M14 0 L4 -2 L-2 -11 L-6 -11 L-2 -2 L-9 -2 L-12 -6 L-15 -6 L-13 0 L-15 6 L-12 6 L-9 2 L-2 2 L-6 11 L-2 11 L4 2 Z"
            fill="#0b1b3a" transform="scale(1.3)" />
          <animateMotion dur="14s" repeatCount="indefinite" rotate="auto" keyPoints="0;1;1" keyTimes="0;0.85;1" calcMode="linear">
            <mpath href="#tm-flight" />
          </animateMotion>
        </g>
      </svg>
    </div>
  );
}
