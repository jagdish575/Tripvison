import { cx } from "../../utils/format";

export function LogoMark({ inverse = false, className }: { inverse?: boolean; className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cx("size-7 shrink-0", className)} aria-hidden>
      <rect width="32" height="32" rx="7" fill={inverse ? "#F8FAFC" : "#0B1220"} />
      <circle cx="9" cy="22" r="3" fill="none" stroke={inverse ? "#0B1220" : "#F8FAFC"} strokeWidth="2" />
      <path d="M11.5 20.2 C 16 13, 19 11, 23 10" fill="none" stroke={inverse ? "#0B1220" : "#F8FAFC"} strokeWidth="2"
        strokeLinecap="round" strokeDasharray="0.1 4.2" />
      <circle cx="23.5" cy="9.5" r="3.5" fill="#F59E0B" />
    </svg>
  );
}

export function Logo({ inverse = false }: { inverse?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark inverse={inverse} />
      <span className={cx("text-[17px] font-semibold tracking-[-0.02em]", inverse ? "text-white" : "text-ink")}>
        TripMission
      </span>
    </span>
  );
}
