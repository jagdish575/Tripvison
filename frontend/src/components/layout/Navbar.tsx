import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Bookmark, ChevronDown, LogOut, Mail, Map as MapIcon, Menu, Settings, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { useHealth, usePlanMission } from "../../hooks/useMission";
import type { User } from "../../types/api";
import { cx } from "../../utils/format";
import { Button } from "../ui/Button";
import { Logo } from "./Logo";

export { Logo } from "./Logo";

export function DemoBadge({ className }: { className?: string }) {
  const { data } = useHealth();
  const { user } = useAuth();
  if (!data?.demo_mode && !user?.is_demo) return null;
  return (
    <span title="Demo mode — journeys come from a labelled demo dataset, not live searches."
      className={cx("inline-flex h-6 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-xs border border-amber/40 bg-amber-wash px-2 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-amber-ink", className)}>
      <span className="size-1.5 rounded-full bg-amber" aria-hidden />
      Demo mode
    </span>
  );
}

export function Avatar({ user, size = 32 }: { user: User; size?: number }) {
  const [broken, setBroken] = useState(false);
  const initials = user.is_demo ? "D" : user.name.split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  if (user.picture && !broken) {
    return <img src={user.picture} alt="" width={size} height={size} referrerPolicy="no-referrer" onError={() => setBroken(true)}
      className="shrink-0 rounded-full object-cover ring-1 ring-line" style={{ width: size, height: size }} />;
  }
  return (
    <span aria-hidden style={{ width: size, height: size }}
      className={cx("grid shrink-0 place-items-center rounded-full text-[12px] font-semibold",
        user.is_demo ? "bg-amber-wash text-amber-ink ring-1 ring-amber/40" : "bg-ink text-white")}>
      {initials || "T"}
    </span>
  );
}

const LINKS = [
  { to: "/#how-it-works", label: "How it works" },
  { to: "/about", label: "How we decide" },
  { to: "/trips", label: "My trips", auth: true },
];

const MENU = [
  { to: "/trips", label: "My trips", icon: MapIcon },
  { to: "/trips?tab=saved", label: "Saved missions", icon: Bookmark },
  { to: "/profile#email", label: "Email preferences", icon: Mail },
  { to: "/profile", label: "Settings", icon: Settings },
];

function ProfileMenu({ user }: { user: User }) {
  const [open, setOpen] = useState(false);
  const { signOut } = useAuth();
  const navigate = useNavigate();
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={root} className="relative">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open}
        aria-label={`Account menu for ${user.name}`}
        className="flex items-center gap-1.5 rounded-full p-0.5 pr-1.5 transition-colors hover:bg-paper-2">
        <Avatar user={user} />
        <ChevronDown className={cx("size-4 text-muted transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div role="menu" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.14 }}
            className="absolute right-0 top-[calc(100%+8px)] w-64 overflow-hidden rounded-md border border-line bg-surface shadow-[var(--shadow-float)]">
            <div className="flex items-center gap-3 border-b border-line px-4 py-3.5">
              <Avatar user={user} size={36} />
              <div className="min-w-0">
                <p className="truncate text-[14px] font-semibold text-ink">{user.name}</p>
                <p className="truncate text-[12.5px] text-muted">{user.is_demo ? "Demo session · no account" : user.email}</p>
              </div>
            </div>
            <div className="py-1.5">
              {MENU.map(({ to, label, icon: Icon }) => (
                <Link key={label} role="menuitem" to={to} onClick={() => setOpen(false)}
                  className="flex items-center gap-3 px-4 py-2 text-[14px] text-fg hover:bg-paper">
                  <Icon className="size-4 text-muted" aria-hidden />{label}
                </Link>
              ))}
            </div>
            <div className="border-t border-line py-1.5">
              <button type="button" role="menuitem"
                onClick={async () => { setOpen(false); await signOut(); navigate("/"); }}
                className="flex w-full items-center gap-3 px-4 py-2 text-left text-[14px] text-fg hover:bg-paper">
                <LogOut className="size-4 text-muted" aria-hidden />{user.is_demo ? "End demo session" : "Sign out"}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

const navLink = "relative rounded-sm px-3 py-2 text-[14px] font-medium transition-colors hover:text-ink " +
  "after:absolute after:inset-x-3 after:bottom-1 after:h-0.5 after:origin-left after:scale-x-0 after:rounded-full " +
  "after:bg-gradient-to-r after:from-blue after:to-coral after:transition-transform after:duration-300 hover:after:scale-x-100";

export function Navbar() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, requireAuth, signOut } = useAuth();
  const plan = usePlanMission();
  useEffect(() => setOpen(false), [location.pathname, location.search, location.hash]);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const go = (to: string, auth?: boolean) => (auth ? requireAuth(() => navigate(to), "trips") : navigate(to));
  const isActive = (to: string) => (to.startsWith("/#") ? false : location.pathname === to);

  return (
    <header className={cx("sticky top-0 z-40 border-b backdrop-blur-xl transition-[background-color,box-shadow,border-color] duration-300",
      scrolled ? "border-white/60 bg-white/75 shadow-[0_8px_30px_-16px_rgb(30_27_75_/_0.25)]" : "border-transparent bg-paper/40")}>
      <span aria-hidden className={cx("bg-brand absolute inset-x-0 bottom-0 h-px animate-gradient transition-opacity duration-300",
        scrolled ? "opacity-70" : "opacity-0")} />
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded-sm focus:bg-ink focus:px-3 focus:py-2 focus:text-white">
        Skip to content
      </a>
      <nav className="container-page flex h-14 items-center gap-3 md:h-16" aria-label="Primary">
        <Link to="/" aria-label="TripMission home" className="shrink-0"><Logo /></Link>
        <span className="hidden sm:inline-flex"><DemoBadge /></span>

        <div className="ml-6 hidden items-center gap-0.5 lg:flex">
          {LINKS.map((l) => (
            l.auth ? (
              <button key={l.to} type="button" onClick={() => go(l.to, true)}
                className={cx(navLink, isActive(l.to) ? "text-ink after:scale-x-100" : "text-muted")}>
                {l.label}
              </button>
            ) : (
              <NavLink key={l.to} to={l.to}
                className={cx(navLink, isActive(l.to) ? "text-ink after:scale-x-100" : "text-muted")}>
                {l.label}
              </NavLink>
            )
          ))}
        </div>

        <div className="ml-auto hidden items-center gap-2 md:flex">
          <Button size="sm" onClick={plan}>Plan a mission <ArrowRight className="size-3.5" aria-hidden /></Button>
          {user && <ProfileMenu user={user} />}
        </div>

        <div className="ml-auto flex items-center gap-1 md:hidden">
          {user && <Avatar user={user} size={28} />}
          <button type="button" className="grid size-10 place-items-center rounded-sm text-ink hover:bg-paper-2"
            aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} aria-controls="mobile-menu"
            onClick={() => setOpen((o) => !o)}>
            {open ? <X className="size-5" aria-hidden /> : <Menu className="size-5" aria-hidden />}
          </button>
        </div>
      </nav>

      {/* tablet: links row */}
      <div className="hidden border-t border-line/70 md:block lg:hidden">
        <div className="container-page flex h-10 items-center gap-1 overflow-x-auto">
          {LINKS.map((l) => (
            <button key={l.to} type="button" onClick={() => go(l.to, l.auth)}
              className="shrink-0 rounded-sm px-2.5 py-1.5 text-[13.5px] font-medium text-muted hover:text-ink">{l.label}</button>
          ))}
        </div>
      </div>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div id="mobile-menu" key="mobile" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden border-t border-line bg-paper md:hidden">
            <div className="container-page flex flex-col py-3">
              <div className="sm:hidden"><DemoBadge className="mb-2" /></div>
              {LINKS.map((l) => (
                <button key={l.to} type="button" onClick={() => { setOpen(false); go(l.to, l.auth); }}
                  className="py-3 text-left text-[16px] font-medium text-fg">{l.label}</button>
              ))}
              {user ? (
                <div className="mt-2 border-t border-line pt-3">
                  <div className="flex items-center gap-3 py-2">
                    <Avatar user={user} size={36} />
                    <div className="min-w-0">
                      <p className="truncate text-[14.5px] font-semibold text-ink">{user.name}</p>
                      <p className="truncate text-[12.5px] text-muted">{user.is_demo ? "Demo session" : user.email}</p>
                    </div>
                  </div>
                  <Link to="/profile" className="block py-2.5 text-[15px] text-fg">Profile &amp; settings</Link>
                  <Link to="/trips?tab=saved" className="block py-2.5 text-[15px] text-fg">Saved missions</Link>
                  <button type="button" onClick={async () => { setOpen(false); await signOut(); navigate("/"); }}
                    className="block py-2.5 text-left text-[15px] text-fg">{user.is_demo ? "End demo session" : "Sign out"}</button>
                </div>
              ) : null}
              <Button size="lg" className="mt-3 w-full" onClick={() => { setOpen(false); plan(); }}>
                Plan a mission <ArrowRight className="size-4" aria-hidden />
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
