import { useEffect, useRef, useState } from "react";

/** Minimal typing for Google Identity Services (https://developers.google.com/identity/gsi/web). */
interface GoogleId {
  initialize(options: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: "popup";
    auto_select?: boolean; cancel_on_tap_outside?: boolean; itp_support?: boolean }): void;
  renderButton(el: HTMLElement, options: Record<string, unknown>): void;
  disableAutoSelect(): void;
}
declare global {
  interface Window { google?: { accounts: { id: GoogleId } } }
}

const GIS_SRC = "https://accounts.google.com/gsi/client";
let loader: Promise<void> | null = null;

function loadGis(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (!loader) {
    loader = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = GIS_SRC;
      script.async = true;
      script.defer = true;
      script.onload = () => resolve();
      script.onerror = () => {
        loader = null;
        reject(new Error("gis_load_failed"));
      };
      document.head.appendChild(script);
    });
  }
  return loader;
}

/** Renders Google's own "Continue with Google" button. The ID token goes straight to our backend for verification. */
export function GoogleButton({ clientId, onCredential, disabled }: {
  clientId: string; onCredential: (credential: string) => void; disabled?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const callback = useRef(onCredential);
  callback.current = onCredential;
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");

  useEffect(() => {
    let cancelled = false;
    loadGis()
      .then(() => {
        if (cancelled || !ref.current || !window.google) return;
        const google = window.google.accounts.id;
        google.initialize({ client_id: clientId, ux_mode: "popup", auto_select: false, itp_support: true,
          callback: (r) => callback.current(r.credential) });
        const width = Math.min(400, Math.max(220, Math.floor(ref.current.getBoundingClientRect().width)));
        google.renderButton(ref.current, { type: "standard", theme: "outline", size: "large", text: "continue_with",
          shape: "rectangular", logo_alignment: "left", width });
        setState("ready");
      })
      .catch(() => !cancelled && setState("failed"));
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  return (
    <div className="relative min-h-[44px] w-full">
      <div ref={ref} className={disabled ? "pointer-events-none opacity-60" : undefined} aria-busy={state === "loading"} />
      {state === "loading" && <div aria-hidden className="absolute inset-0 animate-pulse rounded-sm bg-white/10" />}
      {state === "failed" && (
        <p className="text-[13px] text-white/70" role="status">
          Google sign-in couldn't load. Check your connection, or continue in Demo Mode.
        </p>
      )}
    </div>
  );
}
