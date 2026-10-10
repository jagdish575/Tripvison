import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { StrictMode, lazy, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import { AppLayout } from "./layouts/AppLayout";
import { AnalyzingPage } from "./pages/AnalyzingPage";
import { LandingPage } from "./pages/LandingPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PlanPage } from "./pages/PlanPage";
import { ResultsPage } from "./pages/ResultsPage";
import "./styles/index.css";

const ComparePage = lazy(() => import("./pages/ComparePage"));
const AboutPage = lazy(() => import("./pages/AboutPage"));
const TripsPage = lazy(() => import("./pages/TripsPage"));
const ProfilePage = lazy(() => import("./pages/ProfilePage"));

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
});

const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: "/", element: <LandingPage /> },
      { path: "/plan", element: <RequireAuth reason="plan"><PlanPage /></RequireAuth> },
      { path: "/analyzing/:missionId", element: <RequireAuth><AnalyzingPage /></RequireAuth> },
      { path: "/results/:missionId", element: <RequireAuth><ResultsPage /></RequireAuth> },
      { path: "/compare/:missionId", element: <RequireAuth><Suspense fallback={null}><ComparePage /></Suspense></RequireAuth> },
      { path: "/about", element: <Suspense fallback={null}><AboutPage /></Suspense> },
      { path: "/trips", element: <Suspense fallback={null}><TripsPage /></Suspense> },
      { path: "/profile", element: <Suspense fallback={null}><ProfilePage /></Suspense> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user">
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </MotionConfig>
    </QueryClientProvider>
  </StrictMode>,
);
