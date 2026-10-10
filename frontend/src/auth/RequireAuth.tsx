import type { ReactNode } from "react";
import { SignInContent } from "../components/auth/LoginModal";
import { Skeleton } from "../components/ui/States";
import { useAuth, type LoginReason } from "./AuthContext";

/** Protected page wrapper: shows the sign-in panel in place, then the page once signed in. */
export function RequireAuth({ children, reason = "generic" }: { children: ReactNode; reason?: LoginReason }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="container-page space-y-4 py-12">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (!user) {
    return (
      <div className="container-page py-10 sm:py-16">
        <div className="mx-auto max-w-[520px] rounded-lg bg-ink p-6 text-white shadow-[var(--shadow-float)] sm:p-9">
          <SignInContent reason={reason} compact />
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
