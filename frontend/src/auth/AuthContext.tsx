import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { getAuthConfig, getMe, signOut as apiSignOut } from "../api/account";
import { LoginModal } from "../components/auth/LoginModal";
import type { AuthConfig, User } from "../types/api";

export type LoginReason = "plan" | "trips" | "profile" | "save" | "generic";

interface AuthValue {
  user: User | null;
  loading: boolean;
  config: AuthConfig | undefined;
  /** Runs `action` now if signed in; otherwise opens the sign-in modal and runs it right after sign-in. */
  requireAuth: (action?: () => void, reason?: LoginReason) => void;
  openLogin: (reason?: LoginReason) => void;
  /** Always asks the user to sign in (e.g. after the server reported an expired session), then runs `action`. */
  signInThen: (action: () => void, reason?: LoginReason) => void;
  signOut: () => Promise<void>;
  /** Called by the sign-in UI with the signed-in user. */
  completeSignIn: (user: User) => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: getMe, staleTime: 5 * 60_000, retry: 1 });
  const config = useQuery({ queryKey: ["auth-config"], queryFn: getAuthConfig, staleTime: Infinity, retry: 1 });
  const [modal, setModal] = useState<LoginReason | null>(null);
  const pending = useRef<(() => void) | null>(null);
  const user = me.data?.user ?? null;

  const openLogin = useCallback((reason: LoginReason = "generic") => setModal(reason), []);

  const signInThen = useCallback((action: () => void, reason: LoginReason = "generic") => {
    queryClient.setQueryData(["me"], { user: null });
    pending.current = action;
    setModal(reason);
  }, [queryClient]);

  const requireAuth = useCallback((action?: () => void, reason: LoginReason = "generic") => {
    if (user) {
      action?.();
      return;
    }
    pending.current = action ?? null;
    setModal(reason);
  }, [user]);

  const completeSignIn = useCallback((next: User) => {
    queryClient.setQueryData(["me"], { user: next });
    // Anything cached for a previous session (trips, missions) belongs to someone else now.
    queryClient.removeQueries({ queryKey: ["trips"] });
    queryClient.removeQueries({ queryKey: ["preferences"] });
    setModal(null);
    const action = pending.current;
    pending.current = null;
    if (action) setTimeout(action, 0); // after the modal closes and `user` has propagated
  }, [queryClient]);

  const signOut = useCallback(async () => {
    try {
      await apiSignOut();
    } finally {
      queryClient.setQueryData(["me"], { user: null });
      queryClient.removeQueries({ queryKey: ["trips"] });
      queryClient.removeQueries({ queryKey: ["preferences"] });
      queryClient.removeQueries({ queryKey: ["recommendations"] });
      queryClient.removeQueries({ queryKey: ["mission"] });
    }
  }, [queryClient]);

  const close = useCallback(() => {
    pending.current = null;
    setModal(null);
  }, []);

  const value = useMemo<AuthValue>(() => ({
    user, loading: me.isLoading, config: config.data, requireAuth, openLogin, signInThen, signOut, completeSignIn,
  }), [user, me.isLoading, config.data, requireAuth, openLogin, signInThen, signOut, completeSignIn]);

  return (
    <AuthContext.Provider value={value}>
      {children}
      <LoginModal open={modal !== null} reason={modal ?? "generic"} onClose={close} />
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
