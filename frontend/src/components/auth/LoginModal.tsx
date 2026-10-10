import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { signInDemo, signInWithGoogle } from "../../api/account";
import type { ApiError } from "../../api/client";
import { useAuth, type LoginReason } from "../../auth/AuthContext";
import { cx } from "../../utils/format";
import { Logo } from "../layout/Logo";
import { GoogleButton } from "./GoogleButton";

const COPY: Record<LoginReason, { title: string; body: string }> = {
  plan: { title: "Plan a real journey with TripMission",
          body: "Sign in to run your mission, save it to My trips and get updates before you leave." },
  trips: { title: "Your trips, in one place", body: "Sign in to see past, upcoming and saved journeys." },
  profile: { title: "Your TripMission account", body: "Sign in to manage email updates and travel preferences." },
  save: { title: "Save this journey", body: "Sign in to keep it in My trips and get reminders before you leave." },
  generic: { title: "Your journey starts with a better decision.",
             body: "Sign in to plan missions, save journeys and receive trip updates." },
};

/** Abstract route illustration: origin → hubs → venue, the way TripMission thinks about a trip. */
function RouteArt() {
  return (
    <svg viewBox="0 0 260 320" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="tm-fade" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0.5" />
          <stop offset="1" stopColor="#fff" stopOpacity="0.08" />
        </linearGradient>
      </defs>
      {[...Array(7)].map((_, i) => (
        <path key={i} d={`M0 ${40 + i * 42} H260`} stroke="#fff" strokeOpacity="0.05" />
      ))}
      <path d="M44 272 C 70 210, 120 214, 132 170 S 186 104, 214 52" fill="none" stroke="url(#tm-fade)" strokeWidth="2"
        strokeDasharray="1 7" strokeLinecap="round" />
      <path d="M44 272 C 96 262, 150 250, 176 214" fill="none" stroke="#fff" strokeOpacity="0.12" strokeWidth="1.5"
        strokeDasharray="4 6" />
      <circle cx="44" cy="272" r="6" fill="none" stroke="#fff" strokeWidth="2" />
      <circle cx="132" cy="170" r="4" fill="#fff" fillOpacity="0.6" />
      <circle cx="176" cy="214" r="3.5" fill="#fff" fillOpacity="0.35" />
      <circle cx="214" cy="52" r="9" fill="#F59E0B" />
      <circle cx="214" cy="52" r="17" fill="none" stroke="#F59E0B" strokeOpacity="0.35" />
    </svg>
  );
}

export function SignInContent({ reason = "generic", compact = false }: { reason?: LoginReason; compact?: boolean }) {
  const { config, completeSignIn } = useAuth();
  const [busy, setBusy] = useState<"google" | "demo" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const copy = COPY[reason];

  const google = async (credential: string) => {
    setBusy("google");
    setError(null);
    try {
      completeSignIn((await signInWithGoogle(credential)).user);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(null);
    }
  };
  const demo = async () => {
    setBusy("demo");
    setError(null);
    try {
      completeSignIn((await signInDemo()).user);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className={cx("flex flex-col", compact ? "gap-5" : "gap-6")}>
      <Logo inverse />
      <div>
        <h2 id="login-title" className="display text-[28px] leading-[1.1] text-white sm:text-[32px]">{copy.title}</h2>
        <p className="mt-3 text-[15px] leading-relaxed text-white/65">{copy.body}</p>
      </div>
      <div className="space-y-3">
        {config?.google_enabled && config.google_client_id ? (
          <GoogleButton clientId={config.google_client_id} onCredential={google} disabled={busy !== null} />
        ) : (
          <p className="rounded-sm border border-white/10 bg-white/5 px-3 py-2.5 text-[13px] text-white/60">
            Google sign-in isn't available on this server yet. You can explore everything in Demo Mode.
          </p>
        )}
        {config?.demo_enabled !== false && (
          <>
            <div className="flex items-center gap-3 text-[12px] uppercase tracking-[0.08em] text-white/35">
              <span className="h-px flex-1 bg-white/10" />or<span className="h-px flex-1 bg-white/10" />
            </div>
            <button type="button" onClick={demo} disabled={busy !== null}
              className="group flex w-full items-center justify-between gap-3 rounded-sm border border-white/15 px-4 py-3 text-left transition-colors hover:border-amber/60 hover:bg-white/5 disabled:opacity-60">
              <span>
                <span className="block text-[15px] font-semibold text-white">
                  {busy === "demo" ? "Starting demo…" : "Continue in Demo Mode"}
                </span>
                <span className="block text-[12.5px] text-white/55">No account needed · labelled demo data, no live searches</span>
              </span>
              <ArrowRight className="size-4 shrink-0 text-amber transition-transform group-hover:translate-x-0.5" aria-hidden />
            </button>
          </>
        )}
        {busy === "google" && <p className="text-[13px] text-white/70" role="status">Signing you in…</p>}
        {error && <p className="text-[13px] text-amber" role="alert">{error}</p>}
      </div>
      <p className="text-[12px] leading-relaxed text-white/40">
        We use your Google name, email and photo only to run your account and send the trip emails you choose.
        TripMission never books travel or sees your Google password.
      </p>
    </div>
  );
}

export function LoginModal({ open, reason, onClose }: { open: boolean; reason: LoginReason; onClose: () => void }) {
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && panel.current) {
        const items = panel.current.querySelectorAll<HTMLElement>("button, [href], iframe, input");
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() => panel.current?.querySelector<HTMLElement>("button")?.focus());
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      previous?.focus?.();
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[60] flex items-end justify-center sm:items-center sm:p-6"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
          <button type="button" aria-label="Close sign-in" tabIndex={-1} onClick={onClose}
            className="absolute inset-0 bg-ink/55 backdrop-blur-[2px]" />
          <motion.div ref={panel} role="dialog" aria-modal="true" aria-labelledby="login-title"
            initial={{ y: 24, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 16, opacity: 0 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="relative grid max-h-[92dvh] w-full overflow-y-auto rounded-t-lg bg-ink text-white shadow-2xl sm:max-w-[860px] sm:rounded-lg md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
            <div className="relative hidden overflow-hidden border-r border-white/10 bg-ink-2 md:block">
              <div className="absolute inset-0 p-8"><RouteArt /></div>
              <div className="absolute inset-x-0 bottom-0 p-7">
                <p className="eyebrow text-white/40">Door to door</p>
                <p className="mt-2 display text-[22px] leading-snug text-white/90">
                  Flight, train, bus or road — whichever actually gets you there.
                </p>
              </div>
            </div>
            <div className="relative p-6 pb-8 sm:p-9">
              <button type="button" onClick={onClose} aria-label="Close"
                className="absolute right-3 top-3 grid size-10 place-items-center rounded-sm text-white/60 hover:bg-white/10 hover:text-white">
                <X className="size-5" aria-hidden />
              </button>
              <SignInContent reason={reason} />
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
