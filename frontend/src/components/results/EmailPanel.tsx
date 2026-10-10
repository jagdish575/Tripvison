import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { BellRing, CircleCheck, Mail, RotateCcw, SquareArrowOutUpRight, TriangleAlert } from "lucide-react";
import { useState, type FormEvent } from "react";
import type { ApiError } from "../../api/client";
import { emailPreviewHref, getNotifications, recheckMission, sendReminderNow, subscribeNotifications } from "../../api/missions";
import type { Delivery, NotificationPrefs, RecheckResult } from "../../types/api";
import { cx, formatClock } from "../../utils/format";
import { Button } from "../ui/Button";

const KIND_LABEL = { summary: "Trip summary", reminder: "Reminder", change: "Change alert" } as const;

function DeliveryNote({ delivery }: { delivery: Delivery }) {
  const failed = delivery.status === "failed";
  const Icon = failed ? TriangleAlert : CircleCheck;
  return (
    <motion.p initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} role="status"
      className={cx("flex items-start gap-2 rounded-sm px-3 py-2 text-[13px]",
        failed ? "bg-amber-wash text-amber-ink" : "bg-green-wash text-green-ink")}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>
        {delivery.message}
        {delivery.preview_url && (
          <> <a className="link font-medium" href={emailPreviewHref(delivery.preview_url)} target="_blank" rel="noreferrer">View email</a></>
        )}
      </span>
    </motion.p>
  );
}

function formatChange(field: string, value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string" && /T\d{2}:\d{2}/.test(value)) return formatClock(value);
  if (field === "buffer") return `${value} min`;
  if (field === "total_cost" && typeof value === "number") return `₹${Math.round(value).toLocaleString("en-IN")}`;
  return String(value);
}

export function EmailPanel({ missionId, demo }: { missionId: string; demo: boolean }) {
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["notifications", missionId], queryFn: () => getNotifications(missionId) });
  const [prefs, setPrefs] = useState<NotificationPrefs>({ email: "", trip_summary: true, reminder: true, changes: true });
  const [recheck, setRecheck] = useState<RecheckResult | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["notifications", missionId] });

  const subscribe = useMutation<{ summary: Delivery | null }, ApiError, NotificationPrefs>({
    mutationFn: (p) => subscribeNotifications(missionId, p), onSuccess: refresh });
  const reminder = useMutation({ mutationFn: () => sendReminderNow(missionId), onSuccess: refresh });
  const recheckRun = useMutation<RecheckResult, ApiError, number | undefined>({
    mutationFn: (delay) => recheckMission(missionId, delay),
    onSuccess: (data) => {
      setRecheck(data);
      refresh();
      queryClient.invalidateQueries({ queryKey: ["recommendations", missionId] });
    },
  });

  const sub = status.data?.subscriptions[0];
  const delivery = status.data?.delivery;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    subscribe.mutate(prefs);
  };

  return (
    <section aria-labelledby="email-title" className="card overflow-hidden">
      <div className="grid gap-8 p-5 sm:p-6 lg:grid-cols-[1fr_1.1fr]">
        <div>
          <p className="eyebrow flex items-center gap-1.5"><Mail className="size-3.5" aria-hidden /> Email updates</p>
          <h2 id="email-title" className="display mt-1 text-[26px] leading-tight">Keep this journey in your inbox</h2>
          <p className="mt-2 text-[14px] text-muted">
            A summary now, a reminder 24 hours before you leave, and an alert only if something meaningful changes —
            arrival, buffer, risk or cost. No account needed.
          </p>
          {delivery === "preview" && (
            <p className="mt-3 text-[12.5px] text-muted">
              This server has no email provider configured, so emails are generated as previews you can open here.
            </p>
          )}
        </div>

        <div>
          {!sub ? (
            <form onSubmit={submit} className="space-y-3" noValidate>
              <label htmlFor="notify-email" className="text-[13px] font-medium text-fg">Email</label>
              <input id="notify-email" type="email" required autoComplete="email" placeholder="you@example.com"
                className="field-input" value={prefs.email} onChange={(e) => setPrefs({ ...prefs, email: e.target.value })}
                aria-invalid={subscribe.error?.code === "validation_error" || undefined} />
              <fieldset className="space-y-2 pt-1">
                <legend className="sr-only">What to send</legend>
                {([["trip_summary", "Trip summary"], ["reminder", "Reminder before departure"], ["changes", "Important journey changes"]] as const).map(([key, label]) => (
                  <label key={key} className="flex items-center gap-2.5 text-[14px] text-fg">
                    <input type="checkbox" className="size-4 accent-blue" checked={prefs[key]}
                      onChange={(e) => setPrefs({ ...prefs, [key]: e.target.checked })} />
                    {label}
                  </label>
                ))}
              </fieldset>
              {subscribe.error && <p className="text-[13px] text-red-ink" role="alert">{subscribe.error.code === "validation_error" ? "Enter a valid email address." : subscribe.error.message}</p>}
              <Button type="submit" loading={subscribe.isPending} disabled={!prefs.email.includes("@")} icon={<BellRing className="size-4" aria-hidden />}>
                Send me trip updates
              </Button>
            </form>
          ) : (
            <div className="space-y-3">
              <p className="text-[14px] text-fg">
                Updates go to <span className="font-semibold text-ink">{sub.email}</span>
                <span className="text-muted"> · {[sub.trip_summary && "summary", sub.reminder && "reminder", sub.changes && "changes"].filter(Boolean).join(", ")}</span>
              </p>
              {sub.departure_at && sub.reminder && (
                <p className="text-[13px] text-muted">
                  {sub.reminder_sent_at ? "Reminder sent." : `Reminder scheduled for 24 hours before departure (${formatClock(sub.departure_at)}).`}
                </p>
              )}
              <div className="flex flex-wrap gap-2 pt-1">
                <Button size="sm" variant="secondary" loading={reminder.isPending} onClick={() => reminder.mutate()}
                  icon={<BellRing className="size-3.5" aria-hidden />}>Send reminder now</Button>
                <Button size="sm" variant="secondary" loading={recheckRun.isPending && recheckRun.variables === undefined}
                  onClick={() => recheckRun.mutate(undefined)} icon={<RotateCcw className="size-3.5" aria-hidden />}>
                  Re-check journey
                </Button>
                {demo && (
                  <Button size="sm" variant="ghost" loading={recheckRun.isPending && recheckRun.variables === 45}
                    onClick={() => recheckRun.mutate(45)}>Simulate a 45-min delay</Button>
                )}
              </div>
            </div>
          )}

          <div className="mt-4 space-y-2">
            {subscribe.data?.summary && <DeliveryNote delivery={subscribe.data.summary} />}
            {reminder.data?.results.map((r) => <DeliveryNote key={r.email} delivery={r} />)}
            {recheckRun.error && <p className="text-[13px] text-red-ink" role="alert">{recheckRun.error.message}</p>}
            <AnimatePresence>
              {recheck?.report && (
                <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
                  className={cx("rounded-sm border px-3 py-2.5 text-[13px]", recheck.report.meaningful ? "border-amber/40 bg-amber-wash" : "border-line bg-paper")}>
                  <p className="font-semibold text-ink">
                    {recheck.report.meaningful ? "Your journey needs attention" : "No meaningful change"}
                    {recheck.simulated && <span className="font-normal text-muted"> · simulated delay (demo)</span>}
                  </p>
                  {recheck.report.changes.length > 0 ? (
                    <ul className="mt-1 space-y-0.5 tnum">
                      {recheck.report.changes.map((c) => (
                        <li key={c.field} className={c.meaningful ? "text-ink" : "text-muted"}>
                          {c.label}: {formatChange(c.field, c.before)} → {formatChange(c.field, c.after)}
                        </li>
                      ))}
                    </ul>
                  ) : <p className="mt-1 text-muted">Fresh data matches what you were told.</p>}
                  {recheck.alerts.filter((a) => a.alert).map((a) => <div key={a.email} className="mt-2"><DeliveryNote delivery={a.alert!} /></div>)}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {status.data && status.data.messages.length > 0 && (
            <ul className="mt-5 divide-y divide-line border-t border-line text-[13px]">
              {status.data.messages.map((m) => (
                <li key={m.id} className="flex items-center justify-between gap-3 py-2">
                  <span className="min-w-0 truncate"><span className="font-medium text-ink">{KIND_LABEL[m.kind]}</span>
                    <span className="text-muted"> · {m.status === "preview" ? "preview" : m.status}</span></span>
                  <a className="link inline-flex shrink-0 items-center gap-1" href={emailPreviewHref(m.preview_url)} target="_blank" rel="noreferrer">
                    Open <SquareArrowOutUpRight className="size-3" aria-hidden />
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
