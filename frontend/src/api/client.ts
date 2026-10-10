const BASE = (import.meta.env.VITE_API_URL ?? "/api").replace(/\/$/, "") + "/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }

  get field(): string | undefined {
    const field = this.details?.field;
    if (typeof field === "string") return field;
    const fields = this.details?.fields as { field: string | null }[] | undefined;
    return fields?.[0]?.field ?? undefined;
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      credentials: "include", // the session is an HttpOnly cookie
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "network_error", "We can't reach TripMission right now. Check your connection and try again.");
  }
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    const err = (body as { error?: { code?: string; message?: string; details?: Record<string, unknown> } })?.error;
    throw new ApiError(
      response.status,
      err?.code ?? "http_error",
      err?.message ?? "Something went wrong. Please try again.",
      err?.details ?? {},
    );
  }
  return body as T;
}
