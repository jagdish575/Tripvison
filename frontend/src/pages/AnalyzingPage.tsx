import { useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { SearchProgress } from "../components/analysis/SearchProgress";
import { Button } from "../components/ui/Button";
import { Skeleton, ErrorState } from "../components/ui/States";
import { useMissionStatus, useStartMission } from "../hooks/useMission";
import type { Stage } from "../types/api";
import { formatDate, formatMoney } from "../utils/format";
import { missionMeta, saveDraft, STAGES } from "../utils/mission";

const STEP_MS = 420; // minimum time each stage stays visible so the checklist is readable

export function AnalyzingPage() {
  const { missionId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data, error, refetch } = useMissionStatus(missionId);
  const retry = useStartMission();
  const [shown, setShown] = useState(0);

  useEffect(() => {
    document.title = "Planning your journey · TripMission";
  }, []);

  const realIndex = (() => {
    if (!data) return 0;
    if (data.status === "complete") return STAGES.length;
    const stage = data.progress.stage;
    return STAGES.includes(stage as Stage) ? STAGES.indexOf(stage as Stage) : 0;
  })();

  useEffect(() => {
    if (shown >= realIndex) return;
    const timer = setTimeout(() => setShown((s) => Math.min(s + 1, realIndex)), STEP_MS);
    return () => clearTimeout(timer);
  }, [shown, realIndex]);

  useEffect(() => {
    if (data?.status === "complete" && shown >= STAGES.length) {
      const timer = setTimeout(() => {
        queryClient.removeQueries({ queryKey: ["recommendations", missionId] });
        navigate(`/results/${missionId}`, { replace: true });
      }, 350);
      return () => clearTimeout(timer);
    }
  }, [data?.status, shown, missionId, navigate, queryClient]);

  if (error) {
    return (
      <div className="container-page max-w-xl py-16">
        <ErrorState title="We couldn't load this mission" message={error.message} onRetry={() => refetch()} />
      </div>
    );
  }

  const input = data?.input ? { ...data.input, arrival_deadline: data.input.arrival_deadline.slice(0, 5) } : undefined;
  const meta = input ? missionMeta(input.mission_type) : null;
  const failed = data?.status === "failed";

  return (
    <div className="container-page grid max-w-[1120px] gap-10 py-10 md:grid-cols-[minmax(0,1fr)_380px] md:gap-12 md:py-16">
      <div>
        <p className="eyebrow">{failed ? "Planning stopped" : "Planning your journey"}</p>
        {input && meta ? (
          <>
            <h1 className="display mt-3 break-words text-[30px] leading-[1.1] sm:text-[42px]">
              {input.origin} <span className="text-subtle">→</span> {input.destination}
            </h1>
            <p className="mt-3 text-[15.5px] text-muted">
              {meta.label} {input.venue ? `at ${input.venue} ` : ""}by <span className="font-semibold text-ink tnum">{input.arrival_deadline}</span>
              {" "}on {formatDate(input.travel_date, { weekday: "long", day: "numeric", month: "long" })} ·{" "}
              <span className="tnum">{formatMoney(input.budget, input.currency)}</span> budget
            </p>
          </>
        ) : (
          <div className="mt-4 space-y-3">
            <Skeleton className="h-10 w-3/4" />
            <Skeleton className="h-5 w-2/3" />
          </div>
        )}

        {failed && data?.error ? (
          <ErrorState className="mt-10" title="This mission couldn't be completed" message={data.error.message}
            onRetry={input ? () => retry.start(input) : undefined}
            actions={input && (
              <Button variant="ghost" size="sm" icon={<Pencil className="size-3.5" aria-hidden />}
                onClick={() => { saveDraft(input); navigate("/plan"); }}>
                Edit mission
              </Button>
            )} />
        ) : (
          <div className="mt-10">
            <div className="h-1 w-full overflow-hidden rounded-full bg-line" role="progressbar" aria-label="Analysis progress"
              aria-valuemin={0} aria-valuemax={STAGES.length} aria-valuenow={shown}>
              <div className="h-full rounded-full bg-ink transition-[width] duration-500 ease-out"
                style={{ width: `${(shown / STAGES.length) * 100}%` }} />
            </div>
            <p className="mt-3 text-[13px] text-muted">
              {data?.mode === "demo" ? "Demo mode — using labelled demo journeys." : "Comparing live travel options. This usually takes 10–30 seconds."}
            </p>
          </div>
        )}
      </div>

      <div className="card p-6">
        <SearchProgress shownIndex={failed ? realIndex : shown} counts={data?.progress.counts ?? {}}
          activeMessage={shown === realIndex ? data?.progress.message : undefined} />
      </div>
    </div>
  );
}
