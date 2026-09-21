import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(_request: Request, context: { params: Promise<{ check: string }> }) {
  const { check } = await context.params;
  if (check !== "live" && check !== "ready") {
    return NextResponse.json(
      { code: "not_found", detail: "Unknown health check" },
      { status: 404 },
    );
  }
  const requestId = crypto.randomUUID();
  try {
    const origin = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
    const response = await fetch(new URL(`/api/v1/health/${check}`, origin), {
      cache: "no-store",
      signal: AbortSignal.timeout(6_000),
      headers: { Accept: "application/json", "X-Request-ID": requestId },
      redirect: "error",
    });
    const body: unknown = await response.json();
    return NextResponse.json(body, {
      status: response.status,
      headers: {
        "Cache-Control": "no-store",
        "X-Request-ID": requestId,
        "Content-Type": response.ok ? "application/json" : "application/problem+json",
      },
    });
  } catch {
    return NextResponse.json(
      {
        type: "urn:forge:problem:upstream_unavailable",
        title: "API unavailable",
        status: 503,
        code: "upstream_unavailable",
        detail: "The Forge API could not be reached. Check the backend service and retry.",
        instance: `/api/v1/health/${check}`,
        request_id: requestId,
      },
      {
        status: 503,
        headers: {
          "Cache-Control": "no-store",
          "Content-Type": "application/problem+json",
          "X-Request-ID": requestId,
        },
      },
    );
  }
}
