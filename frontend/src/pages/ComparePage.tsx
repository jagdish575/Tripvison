import { ArrowLeft } from "lucide-react";
import { useEffect, useMemo } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import type { ApiError } from "../api/client";
import { ComparisonTable, type CompareColumn } from "../components/compare/ComparisonTable";
import { optionEntries } from "../components/results/OptionSwitcher";
import { ButtonLink } from "../components/ui/Button";
import { ErrorState, Skeleton } from "../components/ui/States";
import { useRecommendations } from "../hooks/useMission";

export default function ComparePage() {
  const { missionId } = useParams();
  const navigate = useNavigate();
  const { data: result, error, isLoading, refetch } = useRecommendations(missionId);

  useEffect(() => {
    document.title = "Compare options · TripMission";
  }, []);

  const columns = useMemo<CompareColumn[]>(() => {
    if (!result) return [];
    const cols: CompareColumn[] = optionEntries(result);
    for (const it of result.itineraries) {
      if (cols.length >= 5) break;
      if (!cols.some((c) => c.itinerary.id === it.id)) cols.push({ itinerary: it, categories: [] });
    }
    return cols;
  }, [result]);

  if (isLoading) {
    return <div className="container-page space-y-4 py-12"><Skeleton className="h-10 w-80" /><Skeleton className="h-[480px]" /></div>;
  }
  if (error || !result) {
    const e = error as ApiError | null;
    return (
      <div className="container-page max-w-xl py-16">
        <ErrorState message={e?.message ?? "Unknown error"} code={e?.code} onRetry={() => refetch()}
          actions={<ButtonLink to="/plan" variant="ghost" size="sm">Plan a new mission</ButtonLink>} />
      </div>
    );
  }

  const open = (id: string) =>
    navigate(id === result.categories.recommended ? `/results/${result.mission_id}` : `/results/${result.mission_id}?option=${encodeURIComponent(id)}`);

  return (
    <div className="container-page pb-20 pt-10">
      <Link to={`/results/${result.mission_id}`} className="inline-flex items-center gap-1.5 text-[13.5px] font-medium text-muted hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> Back to recommendation
      </Link>
      <h1 className="display mt-4 text-[34px] leading-tight sm:text-[40px]">Compare your options</h1>
      <p className="mt-2 max-w-2xl text-[15px] text-muted">
        {result.mission.origin.city} → {result.mission.destination.city}. Every option below gets you there before{" "}
        {result.mission.arrival_deadline}. A green dot marks the best value in each row.
      </p>
      <div className="mt-8">
        {columns.length ? <ComparisonTable columns={columns} mission={result.mission} onOpen={open} />
          : <p className="text-muted">No journeys to compare.</p>}
      </div>
    </div>
  );
}
