import { fireEvent, render, screen } from "@testing-library/react";
import type { Itinerary, MissionResult } from "../../types/api";
import { BudgetComparison, CostBreakdownPanel } from "../results/CostPanels";

function itin(id: string, mode: Itinerary["mode"], total: number, budget = 10000): Itinerary {
  return {
    id, mode, strategy: "night_before",
    main: { mode, provider: "X", title: `${mode} service`, references: [], departure_label: "A", arrival_label: "B",
      departure_time: "2026-10-09T13:10:00", arrival_time: "2026-10-09T15:15:00", duration_minutes: 125, stops: 0,
      transfers: 0, distance_km: null, schedule_source: "live", note: null, data_source: null, fare_label: "Fare" },
    flight: null, transit: null, hotel: null, hotel_check_in: null, hotel_check_out: null, legs: [], timeline: [],
    cost: { ticket: total - 1000, hotel: null, ground: 500, food: 500, total, currency: "INR", ground_estimated: true,
      hotel_nights: 0, hotel_per_night: null, ticket_price_known: true, ticket_source: mode === "flight" ? "live" : "estimated",
      budget, budget_remaining: budget - total,
      items: [
        { key: "ticket", label: "Ticket", amount: total - 1000, source: mode === "flight" ? "live" : "estimated", detail: null },
        { key: "ground", label: "Ground transport", amount: 500, source: "estimated", detail: "2 taxi rides" },
        { key: "food", label: "Food", amount: 500, source: "user_provided", detail: "₹500/day × 1 day" },
      ] },
    arrival: { venue_arrival: "2026-10-10T08:45:00", deadline: "2026-10-10T10:00:00", buffer_minutes: 75,
      required_buffer_minutes: 60, leave_hotel_at: null, effective_buffer_minutes: 75 },
    ground_minutes_mission_day: 10, ground_minutes_before: 40, total_travel_minutes: 200, door_to_venue_minutes: 1000,
    scores: { overall: 90, arrival: 90, budget: 80, ground: 100, location: null, duration: 100, review: null,
      convenience: 100, value: 80, weights: {}, priority: "balanced", factors: [] },
    risk: { level: "LOW", score: 5, factors: [], strengths: [], recommendations: [] },
    constraints: { feasible: true, within_budget: total <= budget, buffer_ok: true, ground_ok: true, rating_ok: true, all_ok: true },
    tags: [], data_quality: [], confidence: "high", practicality: "high", accessibility: [],
  };
}

describe("CostBreakdownPanel", () => {
  it("labels every cost with its source and shows the remaining budget", () => {
    render(<CostBreakdownPanel itinerary={itin("a", "train", 8000)} />);
    expect(screen.getAllByText("Estimated")).toHaveLength(2);
    expect(screen.getByText("Your input")).toBeInTheDocument();
    expect(screen.getByText("Calculated")).toBeInTheDocument();
    expect(screen.getByText("₹2,000 remaining")).toBeInTheDocument();
  });
});

describe("BudgetComparison", () => {
  it("marks options that exceed the budget and selects on click", () => {
    const flight = itin("f", "flight", 11200);
    const train = itin("t", "train", 4550);
    const result = {
      mission: { budget: 10000, currency: "INR" },
      itineraries: [flight, train],
      modes: [
        { mode: "flight", available: true, best_id: "f", options: 1, reason: null, confidence: "high", schedule_source: "live", fare_source: "live" },
        { mode: "train", available: true, best_id: "t", options: 1, reason: null, confidence: "medium", schedule_source: "live", fare_source: "estimated" },
      ],
    } as unknown as MissionResult;
    const onSelect = vi.fn();
    render(<BudgetComparison result={result} onSelect={onSelect} />);
    expect(screen.getByText("OVER BUDGET by ₹1,200")).toBeInTheDocument();
    expect(screen.getByText("₹5,450 remaining")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Train"));
    expect(onSelect).toHaveBeenCalledWith("t");
  });
});
