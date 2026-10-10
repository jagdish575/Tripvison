import { CloudOff, KeyRound, RefreshCw, SearchX, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "../../utils/format";
import { Button } from "./Button";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cx("animate-pulse rounded-sm bg-line/70", className)} />;
}

export function EmptyState({
  title, description, icon, action, className,
}: { title: string; description?: ReactNode; icon?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cx("flex flex-col items-start gap-3 rounded-md border border-dashed border-line-strong bg-surface/60 p-6", className)}>
      <div className="text-subtle">{icon ?? <SearchX className="size-5" aria-hidden />}</div>
      <div>
        <p className="font-semibold text-ink">{title}</p>
        {description && <p className="mt-1 max-w-prose text-[14px] text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

const ERROR_ICONS: Record<string, ReactNode> = {
  network_error: <CloudOff className="size-5" aria-hidden />,
  setup_required: <KeyRound className="size-5" aria-hidden />,
  upstream_auth: <KeyRound className="size-5" aria-hidden />,
};

export function ErrorState({
  title = "Something went wrong", message, code, onRetry, actions, className,
}: {
  title?: string; message: string; code?: string; onRetry?: () => void; actions?: ReactNode; className?: string;
}) {
  return (
    <div role="alert" className={cx("rounded-md border border-red/25 bg-surface p-6", className)}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5 text-red-ink">{(code && ERROR_ICONS[code]) ?? <TriangleAlert className="size-5" aria-hidden />}</div>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-ink">{title}</p>
          <p className="mt-1 max-w-prose text-[14px] text-muted">{message}</p>
          {(onRetry || actions) && (
            <div className="mt-4 flex flex-wrap gap-2">
              {onRetry && (
                <Button variant="secondary" size="sm" onClick={onRetry} icon={<RefreshCw className="size-3.5" aria-hidden />}>
                  Try again
                </Button>
              )}
              {actions}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
