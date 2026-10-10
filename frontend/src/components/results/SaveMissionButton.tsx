import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, BookmarkCheck } from "lucide-react";
import { useState } from "react";
import { getTrips, saveMission, unsaveMission } from "../../api/account";
import type { ApiError } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { cx } from "../../utils/format";

/** Save / unsave a journey. Saving also sets up trip emails according to the traveller's email preferences. */
export function SaveMissionButton({ missionId }: { missionId: string }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const trips = useQuery({ queryKey: ["trips"], queryFn: getTrips, enabled: Boolean(user), staleTime: 30_000 });
  const saved = trips.data?.trips.find((t) => t.mission_id === missionId)?.saved ?? false;
  const [note, setNote] = useState<string | null>(null);
  const toggle = useMutation<{ saved: boolean; email?: { status: string } | null }, ApiError>({
    mutationFn: () => (saved ? unsaveMission(missionId) : saveMission(missionId)),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["trips"] });
      queryClient.invalidateQueries({ queryKey: ["notifications", missionId] });
      const status = res.email?.status;
      setNote(!res.saved ? null : status === "sent" || status === "preview" ? "Saved · trip summary sent"
        : status === "failed" ? "Saved · we couldn't send the email" : "Saved to My trips");
    },
    onError: (e) => setNote(e.message),
  });
  return (
    <span className="inline-flex items-center gap-2">
      {note && <span role="status" className="hidden text-[12.5px] text-muted sm:inline">{note}</span>}
      <button type="button" onClick={() => toggle.mutate()} disabled={toggle.isPending || !user} aria-pressed={saved}
        className={cx("inline-flex h-9 items-center gap-2 rounded-sm border px-3 text-[13px] font-semibold transition-colors",
          saved ? "border-blue bg-blue-wash text-blue-ink" : "border-line-strong bg-surface text-fg hover:border-subtle")}>
        {saved ? <BookmarkCheck className="size-4" aria-hidden /> : <Bookmark className="size-4" aria-hidden />}
        {saved ? "Saved" : "Save journey"}
      </button>
    </span>
  );
}
