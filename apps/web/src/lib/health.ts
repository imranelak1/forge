export type CheckState = "healthy" | "unavailable" | "pending" | "unknown";
export type SystemHealth = {
  api: CheckState;
  database: CheckState;
  migrations: CheckState;
  checkedAt: string;
};

async function readCheck(check: "live" | "ready", signal?: AbortSignal) {
  const response = await fetch(`/api/v1/health/${check}`, { cache: "no-store", signal });
  const payload: unknown = await response.json();
  if (!payload || typeof payload !== "object") throw new Error("Invalid health response");
  return { ok: response.ok, payload: payload as Record<string, unknown> };
}

export async function fetchSystemHealth(signal?: AbortSignal): Promise<SystemHealth> {
  const [live, ready] = await Promise.allSettled([
    readCheck("live", signal),
    readCheck("ready", signal),
  ]);
  if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
  const readyPayload = ready.status === "fulfilled" ? ready.value.payload : undefined;
  const checks = readyPayload?.checks;
  const typedChecks =
    checks && typeof checks === "object" ? (checks as Record<string, unknown>) : {};
  return {
    api:
      live.status === "fulfilled" && live.value.ok && live.value.payload.status === "ok"
        ? "healthy"
        : "unavailable",
    database:
      typedChecks.database === "up"
        ? "healthy"
        : typedChecks.database === "down"
          ? "unavailable"
          : "unknown",
    migrations:
      typedChecks.migrations === "current"
        ? "healthy"
        : typedChecks.migrations === "pending"
          ? "pending"
          : "unknown",
    checkedAt: new Date().toISOString(),
  };
}
