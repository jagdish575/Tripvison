import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { MissionTypeSelector } from "../mission/MissionTypeSelector";
import { MissionScore } from "../results/MissionScore";
import { RiskPanel } from "../results/RiskPanel";
import { ErrorState } from "../ui/States";
import type { MissionType } from "../../types/api";

describe("MissionScore", () => {
  it("exposes the score accessibly", () => {
    render(<MissionScore score={91} />);
    expect(screen.getByRole("img", { name: "Mission score: 91 out of 100" })).toBeInTheDocument();
  });
});

describe("RiskPanel", () => {
  it("shows level, strengths and factors", () => {
    render(<RiskPanel risk={{
      level: "HIGH", score: 52, strengths: ["Direct flight"], recommendations: ["Leave earlier."],
      factors: [{ key: "buffer", severity: "high", points: 40, title: "Only 15-minute arrival buffer", detail: "You asked for 60.", recommendation: null }],
    }} />);
    expect(screen.getByText("High risk")).toBeInTheDocument();
    expect(screen.getByText("Direct flight")).toBeInTheDocument();
    expect(screen.getByText("Only 15-minute arrival buffer")).toBeInTheDocument();
    expect(screen.getByText(/Leave earlier/)).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("renders the message and retry", () => {
    const retry = vi.fn();
    render(<ErrorState message="Live data took too long." code="upstream_timeout" onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Live data took too long.");
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(retry).toHaveBeenCalledOnce();
  });
});

describe("MissionTypeSelector", () => {
  function Harness() {
    const [value, setValue] = useState<MissionType>("interview");
    return <MissionTypeSelector value={value} onChange={setValue} />;
  }
  it("is a radiogroup with arrow-key navigation", () => {
    render(<Harness />);
    expect(screen.getByRole("radiogroup", { name: "Mission type" })).toBeInTheDocument();
    const interview = screen.getByRole("radio", { name: "Interview" });
    expect(interview).toHaveAttribute("aria-checked", "true");
    fireEvent.keyDown(interview, { key: "ArrowRight" });
    expect(screen.getByRole("radio", { name: "Exam" })).toHaveAttribute("aria-checked", "true");
    fireEvent.click(screen.getByRole("radio", { name: "Vacation" }));
    expect(screen.getByRole("radio", { name: "Vacation" })).toHaveAttribute("aria-checked", "true");
  });
});
