import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowRight, Bookmark, BookmarkCheck, CalendarDays, MapPin, Plus } from "lucide-react";
import { useEffect } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { getTrips, saveMission, unsaveMission } from "../api/account";
import type { ApiError } from "../api/client";
import { RequireAuth } from "../auth/RequireAuth";
import { RiskBadge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { EmptyState, ErrorState, Skeleton } from "../components/ui/States";
import type { Trip } from "../types/api";
import { cx, formatDate, formatMoney } from "../utils/format";
import { MODE_META, missionMeta } from "../utils/mission";

type Tab = "upcoming" | "past" | "saved";
const TABS: { id: Tab; label: string }[] = [
  { id: "upcoming", label: "Upcoming" }, { id: "past", label: "Past" }, { id: "saved", label: "Saved" },
];

function statusLabel(trip: Trip): { text: string; tone: string } {
  if (trip.status === "failed") return { text: "Couldn't complete", tone: "bg-red-wash text-red-ink" };
  if (trip.status !== "complete") return { text: "Planning…", tone: "bg-blue-wash text-blue-ink" };
  if (trip.result_status === "no_options") return { text: "No journey fits", tone: "bg-amber-wash text-amber-ink" };
  if (trip.result_status === "partial") return { text: "Closest match", tone: "bg-amber-wash text-amber-ink" };
  return { text: "Journey ready", tone: "bg-green-wash text-green-ink" };
}

function TripCard({ trip }: { trip: Trip }) {
  const queryClient = useQueryClient();
  const meta = missionMeta(trip.mission_type);
  const status = statusLabel(trip);
  const rec = trip.recommended;
  const ModeIcon = rec ? MODE_META[rec.mode].icon : null;
  const href = trip.status === "complete" ? `/results/${trip.mission_id}` : `/analyzing/${trip.mission_id}`;
  const toggle = useMutation<unknown, ApiError>({
    mutationFn: () => (trip.saved ? unsaveMission(trip.mission_id) : saveMission(trip.mission_id)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trips"] }),
  });

  return (
    <motion.li layout variants={{ hidden: { opacity: 0, y: 8 }, show: { opacity: 1, y: 0 } }}
      className="card flex flex-col overflow-hidden">
      <div className="flex items-start justify-between gap-3 px-5 pt-5">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 text-[12px]">
            <span className={cx("rounded-xs px-1.5 py-0.5 font-semibold", status.tone)}>{status.text}</span>
            {trip.mode === "demo" && <span className="rounded-xs bg-amber-wash px-1.5 py-0.5 font-semibold text-amber-ink">Demo</span>}
          </p>
          <h3 className="display mt-2 truncate text-[24px] leading-tight">
            {trip.origin} <span className="text-subtle">→</span> {trip.destination}
          </h3>
          {trip.venue && (
            <p className="mt-1 flex items-center gap-1.5 truncate text-[13.5px] text-muted">
              <MapPin className="size-3.5 shrink-0" aria-hidden />{trip.venue}
            </p>
          )}
        </div>
        {trip.status === "complete" && (
          <button type="button" onClick={() => toggle.mutate()} disabled={toggle.isPending}
            aria-pressed={trip.saved} aria-label={trip.saved ? "Remove from saved" : "Save journey"}
            className={cx("grid size-9 shrink-0 place-items-center rounded-sm transition-colors",
              trip.saved ? "text-blue hover:bg-blue-wash" : "text-muted hover:bg-paper-2 hover:text-ink")}>
            {trip.saved ? <BookmarkCheck className="size-[18px]" aria-hidden /> : <Bookmark className="size-[18px]" aria-hidden />}
          </button>
        )}
      </div>
      <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 px-5 text-[13px] text-muted tnum">
        <span className="inline-flex items-center gap-1.5"><CalendarDays className="size-3.5" aria-hidden />
          {formatDate(trip.travel_date, { weekday: "short", day: "numeric", month: "short", year: "numeric" })}</span>
        <span>{meta.label} at {trip.arrival_deadline}</span>
      </p>
      <dl className="mt-4 grid grid-cols-3 gap-3 border-t border-line px-5 py-4">
        <div className="min-w-0">
          <dt className="text-[11px] font-medium uppercase tracking-[0.06em] text-subtle">Travel by</dt>
          <dd className="mt-0.5 flex items-center gap-1.5 truncate text-[14px] font-semibold text-ink">
            {ModeIcon && <ModeIcon className="size-4 shrink-0" aria-hidden />}{rec ? MODE_META[rec.mode].label : "—"}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="text-[11px] font-medium uppercase tracking-[0.06em] text-subtle">Total cost</dt>
          <dd className="mt-0.5 truncate text-[14px] font-semibold text-ink tnum">{formatMoney(rec?.total_cost, trip.currency)}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-[11px] font-medium uppercase tracking-[0.06em] text-subtle">Score</dt>
          <dd className="mt-0.5 flex items-center gap-2 text-[14px] font-semibold text-ink tnum">
            {rec?.score ?? "—"}{rec?.risk && <RiskBadge level={rec.risk} compact />}
          </dd>
        </div>
      </dl>
      <Link to={href} className="mt-auto flex items-center justify-between border-t border-line px-5 py-3 text-[14px] font-semibold text-blue hover:bg-paper hover:text-blue-ink">
        {trip.status === "complete" ? "View journey" : "View progress"} <ArrowRight className="size-4" aria-hidden />
      </Link>
    </motion.li>
  );
}

function Trips() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const tab = (TABS.some((t) => t.id === params.get("tab")) ? params.get("tab") : "upcoming") as Tab;
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["trips"], queryFn: getTrips });
  const trips = data?.trips ?? [];
  const shown = trips.filter((t) => (tab === "saved" ? t.saved : tab === "upcoming" ? t.upcoming : !t.upcoming));
  const counts = { upcoming: trips.filter((t) => t.upcoming).length, past: trips.filter((t) => !t.upcoming).length,
                   saved: trips.filter((t) => t.saved).length };

  return (
    <div className="container-page pb-20 pt-8 sm:pt-12">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">My trips</p>
          <h1 className="display mt-2 text-[32px] leading-[1.1] sm:text-[40px]">Your missions</h1>
          <p className="mt-2 max-w-xl text-[15px] text-muted">Every journey you've planned, with the option we recommended.</p>
        </div>
        <Button onClick={() => navigate("/plan")} icon={<Plus className="size-4" aria-hidden />}>Plan a mission</Button>
      </header>

      <div role="tablist" aria-label="Trips" className="mt-8 flex gap-1 overflow-x-auto border-b border-line">
        {TABS.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={tab === t.id}
            onClick={() => setParams(t.id === "upcoming" ? {} : { tab: t.id }, { replace: true })}
            className={cx("-mb-px inline-flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-[14px] font-medium transition-colors",
              tab === t.id ? "border-ink text-ink" : "border-transparent text-muted hover:text-fg")}>
            {t.label}<span className="text-[12px] text-subtle tnum">{counts[t.id]}</span>
          </button>
        ))}
      </div>

      <div className="mt-6">
        {isLoading ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-[230px] w-full" />)}
          </div>
        ) : error ? (
          <ErrorState title="We couldn't load your trips" message={(error as ApiError).message} onRetry={() => refetch()} />
        ) : shown.length === 0 ? (
          <EmptyState
            title={tab === "saved" ? "No saved journeys yet" : tab === "past" ? "No past trips" : "No upcoming trips"}
            description={tab === "saved" ? "Open a journey and choose Save to keep it here — saving also sets up your trip emails."
              : "Plan a mission and it will appear here."}
            action={<Button size="sm" onClick={() => navigate("/plan")}>Plan a mission</Button>} />
        ) : (
          <motion.ul initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.05 } } }}
            className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {shown.map((t) => <TripCard key={t.mission_id} trip={t} />)}
          </motion.ul>
        )}
      </div>
    </div>
  );
}

export default function TripsPage() {
  useEffect(() => {
    document.title = "My trips · TripMission";
  }, []);
  return <RequireAuth reason="trips"><Trips /></RequireAuth>;
}
