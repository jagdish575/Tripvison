import { formatBuffer, formatClock, formatKm, formatMinutes, formatMoney } from "./format";

describe("format", () => {
  it("formats rupees with Indian grouping", () => {
    expect(formatMoney(8102)).toBe("₹8,102");
    expect(formatMoney(125000)).toBe("₹1,25,000");
    expect(formatMoney(null)).toBe("—");
  });
  it("formats durations", () => {
    expect(formatMinutes(45)).toBe("45 min");
    expect(formatMinutes(60)).toBe("1 h");
    expect(formatMinutes(125)).toBe("2 h 5 min");
  });
  it("formats buffers and clock times", () => {
    expect(formatBuffer(75)).toBe("1 h 15 min early");
    expect(formatBuffer(-16)).toBe("16 min late");
    expect(formatClock("2026-10-09T08:45:00")).toBe("08:45");
    expect(formatKm(1.62)).toBe("1.6 km");
    expect(formatKm(27.4)).toBe("27 km");
  });
});
