import { Button, ButtonLink } from "../components/ui/Button";
import { usePlanMission } from "../hooks/useMission";

export function NotFoundPage() {
  const plan = usePlanMission();
  return (
    <div className="container-page py-24">
      <p className="eyebrow">404</p>
      <h1 className="display mt-2 text-[40px] leading-tight">This page took a wrong turn.</h1>
      <p className="mt-3 text-muted">The link may be old, or the mission may have been created on another server.</p>
      <div className="mt-6 flex gap-2">
        <ButtonLink to="/">Go home</ButtonLink>
        <Button variant="secondary" onClick={plan}>Plan a mission</Button>
      </div>
    </div>
  );
}
