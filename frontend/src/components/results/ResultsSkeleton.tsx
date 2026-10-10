import { Skeleton } from "../ui/States";

/** Mirrors the results layout so nothing jumps when data arrives. */
export function ResultsSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading results">
      <div className="border-b border-line bg-surface">
        <div className="container-page space-y-3 py-5">
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-8 w-72" />
          <div className="grid grid-cols-2 gap-6 pt-2 sm:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-9" />)}
          </div>
        </div>
      </div>
      <div className="container-page space-y-8 pt-10">
        <Skeleton className="h-10 w-2/3" />
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[118px]" />)}
        </div>
        <div className="overflow-hidden rounded-lg border border-line">
          <div className="flex gap-8 bg-ink/90 p-8">
            <div className="size-[132px] animate-pulse rounded-full border-[7px] border-white/10" />
            <div className="flex-1 space-y-3 pt-4">
              <div className="h-4 w-40 animate-pulse rounded-sm bg-white/10" />
              <div className="h-7 w-3/4 animate-pulse rounded-sm bg-white/10" />
            </div>
          </div>
          <div className="grid gap-4 p-8 sm:grid-cols-2">
            {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-7" />)}
          </div>
        </div>
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="card space-y-5 p-6 lg:col-span-7">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex gap-4"><Skeleton className="h-5 w-14" /><Skeleton className="size-6 rounded-full" /><Skeleton className="h-5 flex-1" /></div>
            ))}
          </div>
          <div className="card space-y-3 p-6 lg:col-span-5">
            <Skeleton className="h-5 w-48" />
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-4" />)}
          </div>
        </div>
      </div>
    </div>
  );
}
