import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Info } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import type { ApiError } from "../api/client";
import { ComparisonTable } from "../components/compare/ComparisonTable";
import { ConstraintSuggestions } from "../components/results/ConstraintSuggestions";
import { BudgetComparison, CostBreakdownPanel } from "../components/results/CostPanels";
import { DataSources, SoftNotices } from "../components/results/DataSources";
import { RouteNotices } from "../components/results/RouteNotices";
import { SaveMissionButton } from "../components/results/SaveMissionButton";
import { EmailPanel } from "../components/results/EmailPanel";
import { ComparisonNote, ExplanationPanel } from "../components/results/ExplanationPanel";
import { FlightCard } from "../components/results/FlightCard";
import { HotelCard } from "../components/results/HotelCard";
import { JourneyTimeline } from "../components/results/JourneyTimeline";
import { LocalDiscovery } from "../components/results/LocalDiscovery";
import { MissionSummaryBar } from "../components/results/MissionSummaryBar";
import { ModeOptions } from "../components/results/ModeOptions";
import { optionEntries, OptionSwitcher } from "../components/results/OptionSwitcher";
import { journeyTitle, RecommendationCard } from "../components/results/RecommendationCard";
import { ResultsSkeleton } from "../components/results/ResultsSkeleton";
import { ReviewInsights } from "../components/results/ReviewInsights";
import { RiskPanel } from "../components/results/RiskPanel";
import { TimeVsMoney } from "../components/results/TimeVsMoney";
import { AccessibilityNotes, TransitCard } from "../components/results/TransitCard";
import { RiskBadge } from "../components/ui/Badge";
import { ButtonLink } from "../components/ui/Button";
import { SectionHeading } from "../components/ui/Controls";
import { ErrorState, Skeleton } from "../components/ui/States";
import { useMissionStatus, useRecommendations, useStartMission } from "../hooks/useMission";
import type { Suggestion } from "../types/api";
import { formatClock, formatMoney, plural } from "../utils/format";
import { missionMeta, MODE_META, saveDraft } from "../utils/mission";

const JourneyMap = lazy(() => import("../components/results/JourneyMap"));

export function ResultsPage() {
  const { missionId } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { data: result, error, isLoading, refetch } = useRecommendations(missionId);
  const status = useMissionStatus(missionId);
  const rerun = useStartMission();

  const apiError = error as ApiError | null;
  useEffect(() => {
    if (apiError?.code === "not_ready") navigate(`/analyzing/${missionId}`, { replace: true });
  }, [apiError, missionId, navigate]);

  useEffect(() => {
    if (result) document.title = `${result.mission.origin.city} → ${result.mission.destination.city} · TripMission`;
  }, [result]);

  const entries = useMemo(() => (result ? optionEntries(result) : []), [result]);

  if (isLoading || apiError?.code === "not_ready") return <ResultsSkeleton />;
  if (apiError || !result) {
    return (
      <div className="container-page max-w-xl py-16">
        <ErrorState title={apiError?.status === 404 ? "Mission not found" : "We couldn't load these results"}
          message={apiError?.message ?? "Unknown error."} code={apiError?.code} onRetry={() => refetch()}
          actions={<ButtonLink to="/plan" variant="ghost" size="sm">Plan a new mission</ButtonLink>} />
      </div>
    );
  }

  const input = status.data?.input
    ? { ...status.data.input, arrival_deadline: status.data.input.arrival_deadline.slice(0, 5) }
    : undefined;
  const edit = input ? () => { saveDraft(input); navigate("/plan"); } : undefined;
  const apply = (s: Suggestion) => input && rerun.start({ ...input, ...s.patch, notifications: null });

  const byId = new Map(result.itineraries.map((i) => [i.id, i]));
  const recommendedId = result.categories.recommended;
  const requested = params.get("option");
  const selectedId = requested && byId.has(requested) ? requested : recommendedId ?? result.itineraries[0]?.id;
  const selected = selectedId ? byId.get(selectedId) : undefined;
  const recommended = recommendedId ? byId.get(recommendedId) : undefined;
  const selectedCategories = entries.find((e) => e.itinerary.id === selectedId)?.categories ?? [];
  const others = result.itineraries.filter((i) => !entries.some((e) => e.itinerary.id === i.id));
  const select = (id: string) => setParams(id === recommendedId ? {} : { option: id }, { replace: true, preventScrollReset: true });
  const noun = missionMeta(result.mission.mission_type).noun;
  const compareColumns = result.modes.filter((m) => m.available && m.best_id && byId.has(m.best_id))
    .map((m) => ({ itinerary: byId.get(m.best_id!)!, categories: entries.find((e) => e.itinerary.id === m.best_id)?.categories ?? [] }));

  return (
    <div className="pb-20">
      <MissionSummaryBar mission={result.mission} mode={result.mode} onEdit={edit}
        actions={result.status !== "no_options" ? <SaveMissionButton missionId={result.mission_id} /> : undefined}
        compareHref={result.status !== "no_options" ? `/compare/${result.mission_id}` : undefined} />

      <div className="container-page space-y-10 pt-6 sm:space-y-12 sm:pt-10">
        {result.mode === "demo" && (
          <p className="flex items-start gap-2 rounded-sm border border-amber/30 bg-amber-wash px-3 py-2 text-[13px] text-amber-ink">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
            Demo mode — schedules, prices, hotels and places are illustrative demo data, not live searches. The
            decision engine (costs, buffer, risk, Mission Score) is the same one used for live journeys.
          </p>
        )}

        <RouteNotices result={result} />

        {result.status !== "complete" && (
          <ConstraintSuggestions status={result.status} suggestions={result.suggestions} onApply={apply} pending={rerun.isPending} />
        )}
        {rerun.visibleError && <ErrorState title="Couldn't re-run the mission" message={rerun.visibleError.message} />}

        {result.status === "no_options" ? (
          <section className="space-y-6">
            {result.modes.length > 0 && (
              <div className="space-y-3">
                <SectionHeading as="h3" title="What we checked" />
                <ModeOptions result={result} selectedId={undefined} onSelect={select} />
              </div>
            )}
            {result.itineraries.length > 0 && (
              <div>
                <SectionHeading as="h3" title="Closest journeys we found" description="These arrive after your deadline — shown so you can see how far off they are." />
                <ul className="mt-4 divide-y divide-line rounded-md border border-line bg-surface">
                  {result.itineraries.map((it) => (
                    <li key={it.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-[14px] tnum">
                      <span className="font-medium text-ink">{MODE_META[it.mode].label} · {journeyTitle(it)}</span>
                      <span className="text-muted">at venue {formatClock(it.arrival.venue_arrival)} · {Math.abs(it.arrival.buffer_minutes)} min late</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        ) : selected && (
          <>
            <header className="max-w-3xl">
              <p className="eyebrow">{result.status === "complete" ? "Your recommended journey" : "Closest match"}</p>
              <h1 className="display mt-2 text-[28px] leading-[1.12] sm:text-[36px] lg:text-[42px]">{result.headline}</h1>
              <p className="mt-3 text-[15px] text-muted tnum">
                We compared {plural(result.funnel.itineraries_scored, "complete door-to-door journey")} against your {noun}:
                every ticket, transfer, hotel night and meal, timed to the minute you need to arrive.
              </p>
              <div className="mt-4"><SoftNotices messages={result.warnings} /></div>
            </header>

            <section aria-labelledby="options-title" className="space-y-3">
              <h2 id="options-title" className="eyebrow">Your options</h2>
              <ModeOptions result={result} selectedId={selected.id} onSelect={select} />
            </section>

            <section aria-labelledby="picks-title" className="space-y-3">
              <h2 id="picks-title" className="eyebrow">Our picks</h2>
              <OptionSwitcher entries={entries} selectedId={selected.id} onSelect={select} />
              {others.length > 0 && (
                <details className="group rounded-md border border-line bg-surface">
                  <summary className="cursor-pointer list-none px-4 py-2.5 text-[13.5px] font-medium text-fg">
                    {plural(others.length, "more shortlisted journey")} <span className="text-muted group-open:hidden">— show</span>
                  </summary>
                  <ul className="divide-y divide-line border-t border-line">
                    {others.map((it) => (
                      <li key={it.id}>
                        <button type="button" onClick={() => select(it.id)}
                          className="flex w-full flex-wrap items-center justify-between gap-3 px-4 py-2.5 text-left text-[13.5px] hover:bg-paper tnum">
                          <span className="font-medium text-ink">{MODE_META[it.mode].label} · {journeyTitle(it)}</span>
                          <span className="flex items-center gap-3 text-muted">
                            {formatMoney(it.cost.total, it.cost.currency)} · {it.arrival.buffer_minutes} min early · {it.scores.overall}
                            <RiskBadge level={it.risk.level} compact />
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </section>

            <AnimatePresence mode="wait">
              <motion.div key={selected.id} id="journey-detail" className="space-y-8"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
                <RecommendationCard itinerary={selected} mission={result.mission} categories={selectedCategories} />

                {selected.id === recommendedId && result.explanation ? (
                  <ExplanationPanel explanation={result.explanation} tradeoff={result.tradeoff?.sentence} />
                ) : recommended ? (
                  <ComparisonNote itinerary={selected} recommended={recommended} mission={result.mission} />
                ) : null}

                <div className="grid gap-6 lg:grid-cols-12 lg:gap-8">
                  <section aria-labelledby="timeline-title" className="space-y-6 lg:col-span-7">
                    <div className="card p-5 sm:p-6">
                      <div className="mb-6 flex items-baseline justify-between gap-4">
                        <h3 id="timeline-title" className="text-[17px] font-semibold tracking-[-0.01em]">Your journey, step by step</h3>
                        <span className="text-[12.5px] text-muted">Local times</span>
                      </div>
                      <JourneyTimeline itinerary={selected} mission={result.mission} />
                    </div>
                    <Suspense fallback={<Skeleton className="h-[300px] w-full" />}>
                      <JourneyMap itinerary={selected} mission={result.mission} />
                    </Suspense>
                  </section>
                  <div className="space-y-6 lg:col-span-5">
                    <RiskPanel risk={selected.risk} />
                    <CostBreakdownPanel itinerary={selected} />
                    {selected.flight ? <FlightCard flight={selected.flight} travelers={result.mission.travelers} />
                      : <TransitCard itinerary={selected} missionDate={result.mission.travel_date} />}
                    <AccessibilityNotes notes={selected.accessibility} />
                  </div>
                </div>
              </motion.div>
            </AnimatePresence>

            <section aria-labelledby="tradeoffs-title" className="space-y-4">
              <SectionHeading eyebrow="Compare modes" title={<span id="tradeoffs-title">Budget, time and money</span>} />
              <div className="grid gap-6 lg:grid-cols-2">
                <BudgetComparison result={result} selectedId={selected.id} onSelect={select} />
                <TimeVsMoney result={result} selectedId={selected.id} onSelect={select} />
              </div>
              {compareColumns.length > 1 && (
                <div className="pt-2">
                  <div className="mb-3 flex items-baseline justify-between gap-4">
                    <h3 className="text-[17px] font-semibold tracking-[-0.01em]">Compare all options</h3>
                    <Link to={`/compare/${result.mission_id}`} className="inline-flex items-center gap-1 text-[13.5px] font-semibold text-blue hover:text-blue-ink">
                      Full comparison <ArrowRight className="size-3.5" aria-hidden />
                    </Link>
                  </div>
                  <ComparisonTable columns={compareColumns} mission={result.mission} onOpen={select} />
                </div>
              )}
            </section>

            {selected.hotel && (
              <section aria-labelledby="stay-title" className="space-y-4">
                <SectionHeading eyebrow="Where you'll stay" title={<span id="stay-title">The hotel</span>} />
                <div className="grid gap-6 lg:grid-cols-12">
                  <div className="lg:col-span-7"><HotelCard itinerary={selected} mission={result.mission} /></div>
                  <div className="lg:col-span-5"><ReviewInsights insights={result.review_insights[selected.hotel.id]} /></div>
                </div>
              </section>
            )}

            <EmailPanel missionId={result.mission_id} demo={result.mode === "demo"} />
          </>
        )}

        {result.places.some((g) => g.items.length > 0) && (
          <section aria-labelledby="nearby-title" className="space-y-4">
            <SectionHeading eyebrow="Local discovery" title={<span id="nearby-title">Around {result.mission.venue.name}</span>}
              description={`Picked for your ${noun}: places that are useful before or after you arrive.`} />
            <LocalDiscovery groups={result.places} venue={result.mission.venue.name} />
          </section>
        )}

        <DataSources result={result} />
      </div>
    </div>
  );
}
