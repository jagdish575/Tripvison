import { AnimatePresence, motion } from "framer-motion";
import { Clock3, MapPin, Star, Store } from "lucide-react";
import { useId, useState } from "react";
import type { Place, PlaceGroup } from "../../types/api";
import { cx, formatCount, formatKm } from "../../utils/format";
import { PLACE_ICONS } from "../../utils/mission";
import { EmptyState } from "../ui/States";

export function PlaceCard({ place, category }: { place: Place; category: string }) {
  const Icon = PLACE_ICONS[category] ?? Store;
  return (
    <li className="flex gap-3 rounded-md border border-line bg-surface p-4">
      <span className="grid size-9 shrink-0 place-items-center rounded-sm bg-paper-2 text-muted"><Icon className="size-4" aria-hidden /></span>
      <div className="min-w-0">
        <p className="truncate text-[14.5px] font-medium text-ink">{place.name}</p>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2.5 gap-y-0.5 text-[12.5px] text-muted tnum">
          {place.rating !== null && (
            <span className="inline-flex items-center gap-1"><Star className="size-3 fill-amber text-amber" aria-hidden />{place.rating.toFixed(1)}
              {place.reviews !== null && <span>({formatCount(place.reviews)})</span>}</span>
          )}
          {place.distance_km !== null && <span className="inline-flex items-center gap-1"><MapPin className="size-3" aria-hidden />{formatKm(place.distance_km)} from venue</span>}
        </p>
        {place.hours && <p className="mt-1 flex items-center gap-1 text-[12.5px] text-muted"><Clock3 className="size-3" aria-hidden />{place.hours}</p>}
      </div>
    </li>
  );
}

export function LocalDiscovery({ groups, venue }: { groups: PlaceGroup[]; venue: string }) {
  const [active, setActive] = useState(0);
  const id = useId();
  if (!groups.length) {
    return <EmptyState title="Nearby recommendations are temporarily unavailable" description={`Your journey to ${venue} is unaffected.`} />;
  }
  const group = groups[Math.min(active, groups.length - 1)];
  return (
    <div>
      <div role="tablist" aria-label="Nearby places" className="flex gap-1 overflow-x-auto border-b border-line">
        {groups.map((g, i) => {
          const Icon = PLACE_ICONS[g.category] ?? Store;
          return (
            <button key={g.category} role="tab" type="button" id={`${id}-tab-${i}`} aria-selected={i === active}
              aria-controls={`${id}-panel`} onClick={() => setActive(i)}
              className={cx("-mb-px inline-flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-[14px] font-medium transition-colors",
                i === active ? "border-ink text-ink" : "border-transparent text-muted hover:text-fg")}>
              <Icon className="size-4" aria-hidden />{g.label}
              <span className="text-[12px] text-subtle tnum">{g.items.length}</span>
            </button>
          );
        })}
      </div>
      <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-tab-${active}`} className="pt-4">
        <p className="mb-3 text-[13.5px] text-muted">{group.reason}</p>
        <AnimatePresence mode="wait">
          <motion.ul key={group.category} className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
            {group.items.length ? group.items.map((p) => <PlaceCard key={p.id} place={p} category={group.category} />)
              : <li className="text-[13.5px] text-muted">Nothing found nearby.</li>}
          </motion.ul>
        </AnimatePresence>
      </div>
    </div>
  );
}
