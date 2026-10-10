import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Check, Compass, LogOut, Mail, UserRound } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { getPreferences, updatePreferences } from "../api/account";
import type { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { RequireAuth } from "../auth/RequireAuth";
import { Avatar } from "../components/layout/Navbar";
import { Field } from "../components/mission/fields";
import { Button } from "../components/ui/Button";
import { Segmented, Toggle } from "../components/ui/Controls";
import { ErrorState, Skeleton } from "../components/ui/States";
import type { Preferences, TravelModeChoice } from "../types/api";
import { cx } from "../utils/format";
import { MODE_CHOICES, MODE_META, PRIORITIES } from "../utils/mission";

function Section({ id, icon, title, description, children }: {
  id: string; icon: ReactNode; title: string; description: string; children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`}
      className="scroll-mt-24 grid gap-5 border-t border-line py-8 first:border-t-0 first:pt-0 md:grid-cols-[240px_1fr] md:gap-10">
      <div>
        <span className="grid size-9 place-items-center rounded-sm bg-paper-2 text-ink">{icon}</span>
        <h2 id={`${id}-title`} className="mt-3 text-[17px] font-semibold tracking-[-0.01em]">{title}</h2>
        <p className="mt-1 text-[13.5px] leading-relaxed text-muted">{description}</p>
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  );
}

function SavedNote({ state }: { state: "idle" | "saving" | "saved" | "error" }) {
  if (state === "idle") return null;
  return (
    <p role="status" className={cx("text-[12.5px]", state === "error" ? "text-red-ink" : "text-muted")}>
      {state === "saving" ? "Saving…" : state === "saved" ? <span className="inline-flex items-center gap-1"><Check className="size-3.5 text-green-ink" aria-hidden />Saved</span>
        : "Couldn't save — please try again."}
    </p>
  );
}

function Profile() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["preferences"], queryFn: getPreferences });
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [saveState, setSaveState] = useState<Record<string, "idle" | "saving" | "saved" | "error">>({});
  useEffect(() => {
    if (data) setPrefs(data.preferences);
  }, [data]);
  const ready = prefs !== null;
  useEffect(() => {
    if (ready && window.location.hash) document.getElementById(window.location.hash.slice(1))?.scrollIntoView();
  }, [ready]);

  const save = useMutation<{ preferences: Preferences }, ApiError, { section: string; patch: Partial<Preferences> }>({
    mutationFn: ({ patch }) => updatePreferences(patch),
    onMutate: ({ section }) => setSaveState((s) => ({ ...s, [section]: "saving" })),
    onSuccess: (res, { section }) => {
      queryClient.setQueryData(["preferences"], (old: { preferences: Preferences } | undefined) => old && { ...old, preferences: res.preferences });
      setSaveState((s) => ({ ...s, [section]: "saved" }));
    },
    onError: (_e, { section }) => setSaveState((s) => ({ ...s, [section]: "error" })),
  });

  if (isLoading || !prefs || !user) {
    if (error) return <div className="container-page py-12"><ErrorState title="We couldn't load your settings" message={(error as ApiError).message} onRetry={() => refetch()} /></div>;
    return <div className="container-page space-y-4 py-12"><Skeleton className="h-10 w-60" /><Skeleton className="h-64 w-full" /></div>;
  }

  const setEmail = (key: keyof Preferences["email"], value: boolean) => {
    const email = { ...prefs.email, [key]: value };
    setPrefs({ ...prefs, email });
    save.mutate({ section: "email", patch: { email } });
  };
  const setNotifications = (enabled: boolean) => {
    setPrefs({ ...prefs, notifications: { enabled } });
    save.mutate({ section: "notifications", patch: { notifications: { enabled } } });
  };
  const travel = prefs.travel;
  const setTravel = (patch: Partial<Preferences["travel"]>) => setPrefs({ ...prefs, travel: { ...travel, ...patch } });
  const toggleMode = (m: TravelModeChoice) => {
    const next = travel.modes.includes(m) ? travel.modes.filter((x) => x !== m) : [...travel.modes, m];
    if (next.length) setTravel({ modes: next });
  };
  const emailOff = user.is_demo || !prefs.notifications.enabled;

  return (
    <div className="container-page pb-20 pt-8 sm:pt-12">
      <header>
        <p className="eyebrow">Profile</p>
        <h1 className="display mt-2 text-[32px] leading-[1.1] sm:text-[40px]">Account &amp; preferences</h1>
      </header>

      <div className="mt-10">
        <Section id="account" icon={<UserRound className="size-4" aria-hidden />} title="Account"
          description="How you're signed in to TripMission.">
          <div className="card flex flex-wrap items-center justify-between gap-4 p-5">
            <div className="flex min-w-0 items-center gap-4">
              <Avatar user={user} size={48} />
              <div className="min-w-0">
                <p className="truncate text-[16px] font-semibold text-ink">{user.name}</p>
                <p className="truncate text-[13.5px] text-muted">
                  {user.is_demo ? "Demo session — journeys use the labelled demo dataset" : `${user.email} · Google account`}
                </p>
              </div>
            </div>
            <Button variant="secondary" size="sm" icon={<LogOut className="size-3.5" aria-hidden />}
              onClick={async () => { await signOut(); navigate("/"); }}>
              {user.is_demo ? "End demo session" : "Sign out"}
            </Button>
          </div>
        </Section>

        <Section id="email" icon={<Mail className="size-4" aria-hidden />} title="Email preferences"
          description="When you save a journey we email you according to these choices.">
          {user.is_demo && (
            <p className="mb-4 rounded-sm bg-amber-wash px-3 py-2 text-[13px] text-amber-ink">
              Demo sessions don't send email. Sign in with Google to receive trip updates.
            </p>
          )}
          <div className="card divide-y divide-line">
            {([
              ["trip_summary", "Trip summary", "Your recommended journey, costs and timings when you save it."],
              ["departure_reminder", "Departure reminder", "A reminder about 24 hours before you leave."],
              ["journey_changes", "Important journey changes", "Only when arrival time, buffer, risk or cost change meaningfully."],
              ["price_changes", "Price changes", "When a re-check finds a different price (where live prices are available)."],
            ] as const).map(([key, label, description]) => (
              <div key={key} className="px-5 py-4">
                <Toggle checked={prefs.email[key]} onChange={(v) => setEmail(key, v)} label={label}
                  description={description} disabled={emailOff} />
              </div>
            ))}
          </div>
          <div className="mt-2 min-h-5"><SavedNote state={saveState.email ?? "idle"} /></div>
        </Section>

        <Section id="notifications" icon={<Bell className="size-4" aria-hidden />} title="Notification preferences"
          description="A single switch for every email TripMission sends you.">
          <div className="card px-5 py-4">
            <Toggle checked={prefs.notifications.enabled} onChange={setNotifications} disabled={user.is_demo}
              label="Email notifications" description="Turn off to stop all trip emails. Your preferences above are kept." />
          </div>
          <div className="mt-2 min-h-5"><SavedNote state={saveState.notifications ?? "idle"} /></div>
        </Section>

        <Section id="travel" icon={<Compass className="size-4" aria-hidden />} title="Travel preferences"
          description="Defaults for new missions. You can still change anything per mission.">
          <div className="card space-y-5 p-5">
            <Field label="Home city" htmlFor="home_city" hint="Used as the starting point of new missions">
              <input id="home_city" className="field-input sm:max-w-sm" maxLength={80} placeholder="e.g. Indore"
                value={travel.home_city ?? ""} onChange={(e) => setTravel({ home_city: e.target.value || null })} />
            </Field>
            <div>
              <p className="mb-2 text-[13px] font-medium">What matters most</p>
              <Segmented label="Default priority" value={travel.priority} onChange={(v) => setTravel({ priority: v })}
                className="flex w-full flex-wrap sm:inline-flex sm:w-auto"
                options={PRIORITIES.map((p) => ({ value: p.id, label: p.label }))} />
            </div>
            <div>
              <p className="mb-2 text-[13px] font-medium">Travel modes to compare</p>
              <div className="flex flex-wrap gap-2" role="group" aria-label="Default travel modes">
                {MODE_CHOICES.map((m) => {
                  const Icon = MODE_META[m.id].icon;
                  const active = travel.modes.includes(m.id);
                  return (
                    <button key={m.id} type="button" aria-pressed={active} onClick={() => toggleMode(m.id)}
                      className={cx("inline-flex h-9 items-center gap-2 rounded-sm border px-3 text-[13.5px] font-medium transition-colors",
                        active ? "border-blue bg-blue-wash text-blue-ink" : "border-line-strong bg-surface text-fg hover:border-subtle")}>
                      <Icon className="size-4" aria-hidden />{m.label}
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <p className="mb-2 text-[13px] font-medium">Arrival buffer <span className="font-normal text-muted">(minutes)</span></p>
              <Segmented label="Default arrival buffer" value={travel.buffer_minutes} onChange={(v) => setTravel({ buffer_minutes: v })}
                className="flex w-full sm:inline-flex sm:w-auto"
                options={[15, 30, 45, 60, 90, 120].map((m) => ({ value: m, label: String(m) }))} />
            </div>
            <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
              <Button size="sm" loading={save.isPending && save.variables?.section === "travel"}
                onClick={() => save.mutate({ section: "travel", patch: { travel } })}>Save travel preferences</Button>
              <SavedNote state={saveState.travel ?? "idle"} />
            </div>
          </div>
        </Section>
      </div>
    </div>
  );
}

export default function ProfilePage() {
  useEffect(() => {
    document.title = "Profile · TripMission";
  }, []);
  return <RequireAuth reason="profile"><Profile /></RequireAuth>;
}
