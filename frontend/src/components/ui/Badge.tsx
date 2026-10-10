import { CircleAlert, ShieldCheck, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import type { RiskLevel } from "../../types/api";
import { cx } from "../../utils/format";
import { RISK_COPY } from "../../utils/mission";

export type Tone = "neutral" | "blue" | "green" | "amber" | "red" | "ink";

const tones: Record<Tone, string> = {
  neutral: "bg-paper-2 text-fg border-line",
  blue: "bg-blue-wash text-blue-ink border-blue/20",
  green: "bg-green-wash text-green-ink border-green/25",
  amber: "bg-amber-wash text-amber-ink border-amber/30",
  red: "bg-red-wash text-red-ink border-red/25",
  ink: "bg-ink text-white border-ink",
};

export function Badge({ tone = "neutral", children, className, icon }: { tone?: Tone; children: ReactNode; className?: string; icon?: ReactNode }) {
  return (
    <span
      className={cx(
        "inline-flex h-6 items-center gap-1 rounded-xs border px-2 text-[11.5px] font-semibold uppercase tracking-[0.05em]",
        tones[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  );
}

const RISK_ICON = { LOW: ShieldCheck, MEDIUM: CircleAlert, HIGH: TriangleAlert } as const;

export function RiskBadge({ level, className, compact }: { level: RiskLevel; className?: string; compact?: boolean }) {
  const Icon = RISK_ICON[level];
  const copy = RISK_COPY[level];
  return (
    <Badge tone={copy.tone as Tone} className={className} icon={<Icon className="size-3.5" strokeWidth={2.4} aria-hidden />}>
      {compact ? level : copy.label}
    </Badge>
  );
}
