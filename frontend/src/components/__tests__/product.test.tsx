import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider, useAuth } from "../../auth/AuthContext";
import type { MissionResult } from "../../types/api";
import { DataSources, SoftNotices } from "../results/DataSources";
import { RouteNotices } from "../results/RouteNotices";
import { HeroMissionBar } from "../mission/HeroMissionBar";
import { ErrorState } from "../ui/States";

function mockApi(routes: Record<string, unknown>) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${String(url).replace(/^.*\/v1/, "")}`;
    const body = routes[key];
    return new Response(JSON.stringify(body ?? { error: { code: "not_found", message: "nope" } }), {
      status: body ? 200 : 404, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function wrap(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}><AuthProvider><MemoryRouter>{ui}</MemoryRouter></AuthProvider></QueryClientProvider>);
}

const DEMO_USER = { id: "u1", email: null, name: "Demo traveller", picture: null, is_demo: true };

function GatedAction({ onRun }: { onRun: () => void }) {
  const { requireAuth, user } = useAuth();
  return <><p>{user ? `signed in: ${user.name}` : "signed out"}</p>
    <button type="button" onClick={() => requireAuth(onRun, "plan")}>Find my journey</button></>;
}

afterEach(() => vi.unstubAllGlobals());

describe("authentication gate", () => {
  it("asks to sign in, offers demo mode, then continues the original action", async () => {
    mockApi({
      "GET /auth/me": { user: null },
      "GET /auth/config": { google_client_id: null, google_enabled: false, demo_enabled: true, auth_required: true },
      "POST /auth/demo": { user: DEMO_USER },
    });
    const run = vi.fn();
    wrap(<GatedAction onRun={run} />);
    await screen.findByText("signed out");
    fireEvent.click(screen.getByRole("button", { name: "Find my journey" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Plan a real journey with TripMission");
    expect(run).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Continue in Demo Mode/ }));
    await waitFor(() => expect(run).toHaveBeenCalledOnce());
    expect(await screen.findByText("signed in: Demo traveller")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("runs immediately when already signed in", async () => {
    mockApi({ "GET /auth/me": { user: { ...DEMO_USER, is_demo: false, name: "Asha" } },
              "GET /auth/config": { google_client_id: null, google_enabled: false, demo_enabled: true, auth_required: true } });
    const run = vi.fn();
    wrap(<GatedAction onRun={run} />);
    await screen.findByText("signed in: Asha");
    fireEvent.click(screen.getByRole("button", { name: "Find my journey" }));
    expect(run).toHaveBeenCalledOnce();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

const RESULT = {
  mission_id: "m", mode: "live", warnings: ["Some local recommendations are temporarily unavailable."],
  mission: { origin: { city: "Indore" }, destination: { city: "Ujjain" } },
  data_sources: { mode: "live", calls: null, live_calls: null, cache_hits: null, fetched_at: "2026-10-08T10:00:00Z" },
  methodology: [
    { key: "live", label: "Live travel data", kind: "live", detail: "Live routes (Google Maps) — retrieved through SerpApi." },
    { key: "calculated", label: "Calculated", kind: "calculated", detail: "Total trip cost and Mission Score." },
  ],
  diagnostics: null,
  route: {
    distance_km: 52, road_km: 62, road_minutes: 88, origin_airport: null,
    destination_airport: { kind: "airport", code: "IDR", name: "Devi Ahilya Bai Holkar Airport", city: "Indore", location: null,
      distance_km: 52, road_km: 62, transfer_minutes: 88, practical: true },
    origin_has_airport: true, destination_has_airport: false, flight: "skipped", flight_practicality: null,
    flight_reason: "short", ground_search: true, ground_reason: null, modes_requested: [], modes_evaluated: [],
    notices: [{ kind: "airport_fallback", message: "Ujjain doesn't have a commercial airport. The nearest practical airport is Indore Airport (IDR)." }],
    railway_stations: ["Indore Junction", "Ujjain Junction"], bus_points: [],
  },
} as unknown as MissionResult;

describe("results transparency", () => {
  it("explains how we decided without request counts", () => {
    render(<DataSources result={RESULT} />);
    expect(screen.getByText("How we decided")).toBeInTheDocument();
    expect(screen.getByText("Live travel data")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/data requests|requests made|live lookups/i);
    expect(screen.queryByText(/Developer diagnostics/)).not.toBeInTheDocument();
  });

  it("shows routing decisions as information, not errors", () => {
    render(<RouteNotices result={RESULT} />);
    expect(screen.getByText(/doesn't have a commercial airport/)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("Indore Junction · Ujjain Junction")).toBeInTheDocument();
  });

  it("degraded optional data is a quiet note", () => {
    render(<SoftNotices messages={RESULT.warnings} />);
    expect(screen.getByText("Some local recommendations are temporarily unavailable.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("error states never print internal error codes", () => {
    render(<ErrorState message="We couldn't load live travel data right now." code="upstream_auth" />);
    expect(document.body.textContent).not.toContain("upstream_auth");
  });
});

describe("hero mission bar", () => {
  it("doesn't carry a venue from another city when the destination changes", async () => {
    sessionStorage.clear();
    const fetchMock = mockApi({
      "GET /auth/me": { user: { ...DEMO_USER, is_demo: false, name: "Asha" } },
      "GET /auth/config": { google_client_id: null, google_enabled: false, demo_enabled: true, auth_required: true },
      "POST /missions/analyze": { mission_id: "m1" },
    });
    wrap(<><GatedAction onRun={() => {}} /><HeroMissionBar /></>);
    await screen.findByText("signed in: Asha");
    fireEvent.change(document.getElementById("hero-destination")!, { target: { value: "Ujjain" } });
    fireEvent.click(document.querySelector<HTMLButtonElement>("button[type=submit]")!);
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/missions/analyze"))).toBe(true));
    const [, init] = fetchMock.mock.calls.find(([u]) => String(u).includes("/missions/analyze"))!;
    const body = JSON.parse(String(init?.body));
    expect(body.destination).toBe("Ujjain");
    expect(body.venue ?? null).toBeNull(); // not the default "Manyata Tech Park" (Bangalore)
  });
});
