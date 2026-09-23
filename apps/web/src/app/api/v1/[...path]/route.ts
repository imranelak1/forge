import { validOAuthCallbackRedirect } from "@/lib/oauth";
import { validGitHubCallbackRedirect } from "@/features/github/types";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const uuid = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}";
const routes: [RegExp, string[]][] = [
  [/^auth\/(csrf|me|sessions|providers|connections)$/, ["GET"]],
  [/^auth\/oauth\/(github|google)\/start$/, ["POST"]],
  [/^auth\/oauth\/(github|google)\/callback$/, ["GET"]],
  [/^auth\/(register|login|refresh|logout)$/, ["POST"]],
  [/^auth\/(verify-email|password-reset)\/(request|confirm)$/, ["POST"]],
  [new RegExp(`^auth/sessions/${uuid}$`), ["DELETE"]],
  [/^organizations$/, ["GET", "POST"]],
  [new RegExp(`^organizations/${uuid}$`), ["GET", "PATCH", "DELETE"]],
  [new RegExp(`^organizations/${uuid}/(members|audit)$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/members/${uuid}$`), ["PATCH", "DELETE"]],
  [new RegExp(`^organizations/${uuid}/invitations$`), ["POST"]],
  [new RegExp(`^organizations/${uuid}/integrations/github$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/integrations/github/authorize$`), ["POST"]],
  [
    new RegExp(`^organizations/${uuid}/integrations/github/authorizations/${uuid}/installations$`),
    ["GET"],
  ],
  [new RegExp(`^organizations/${uuid}/integrations/github/connections$`), ["POST"]],
  [new RegExp(`^organizations/${uuid}/integrations/github/connections/${uuid}$`), ["DELETE"]],
  [
    new RegExp(
      `^organizations/${uuid}/integrations/github/connections/${uuid}/(refresh|selection)$`,
    ),
    ["POST"],
  ],
  [
    new RegExp(`^organizations/${uuid}/integrations/github/connections/${uuid}/repositories$`),
    ["GET"],
  ],
  [new RegExp(`^organizations/${uuid}/repositories$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/repositories/${uuid}/sync-runs$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/repositories/${uuid}/sync$`), ["POST"]],
  [new RegExp(`^organizations/${uuid}/metrics/pull-requests$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/(pull-requests|commits)$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/(pull-requests|commits|issues)/${uuid}$`), ["GET"]],
  [
    new RegExp(
      `^organizations/${uuid}/pull-requests/${uuid}/(reviews|transitions|commits|issues)$`,
    ),
    ["GET"],
  ],
  [new RegExp(`^organizations/${uuid}/commits/${uuid}/(files|pull-requests)$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/issues/${uuid}/pull-requests$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/repositories/${uuid}/issues$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/metrics/(ci|deployments)$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/(workflow-runs|deployments)$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/(workflow-runs|deployments)/${uuid}$`), ["GET"]],
  [
    new RegExp(`^organizations/${uuid}/workflow-runs/${uuid}/(jobs|pull-requests|commits)$`),
    ["GET"],
  ],
  [new RegExp(`^organizations/${uuid}/deployments/${uuid}/(statuses|commits)$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/repositories/${uuid}/environments$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/repositories/${uuid}/environments/classification$`), ["PUT"]],
  [new RegExp(`^organizations/${uuid}/(metrics/tests|test-runs|tests)$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/test-runs/${uuid}$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/test-runs/${uuid}/(suites|cases)$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/tests/${uuid}/history$`), ["GET"]],
  [new RegExp(`^organizations/${uuid}/repositories/${uuid}/test-policy$`), ["GET", "PATCH"]],
  [new RegExp(`^organizations/${uuid}/repositories/${uuid}/service-tokens$`), ["GET", "POST"]],
  [new RegExp(`^organizations/${uuid}/service-tokens/${uuid}$`), ["DELETE"]],
  [/^integrations\/github\/callback$/, ["GET"]],
  [/^invitations\/accept$/, ["POST"]],
];
const maxBody = 16_384;
async function readBounded(
  stream: ReadableStream<Uint8Array>,
  maximum: number,
  timeout: number,
): Promise<string> {
  const reader = stream.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const expired = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      void reader.cancel();
      reject(new Error("timeout"));
    }, timeout);
  });
  try {
    while (true) {
      const { done, value } = await Promise.race([reader.read(), expired]);
      if (done) break;
      size += value.byteLength;
      if (size > maximum) {
        await reader.cancel();
        throw new Error("too_large");
      }
      chunks.push(value);
    }
    return Buffer.concat(chunks).toString("utf8");
  } finally {
    clearTimeout(timer);
    reader.releaseLock();
  }
}
const reply = (status: number, detail: string) =>
  Response.json(
    { detail },
    {
      status,
      headers: {
        "Cache-Control": "no-store",
        "Content-Type": "application/problem+json",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
      },
    },
  );

function validOrigin(request: Request) {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  const configured = process.env.FORGE_PUBLIC_ORIGIN;
  if (configured) {
    try {
      if (origin === new URL(configured).origin) return true;
    } catch {
      return false;
    }
  }
  if (process.env.NODE_ENV === "production") return false;
  const expected = new URL(request.url);
  const supplied = new URL(origin);
  return (
    supplied.origin === expected.origin ||
    (["localhost", "127.0.0.1"].includes(expected.hostname) &&
      ["localhost", "127.0.0.1"].includes(supplied.hostname) &&
      expected.protocol === supplied.protocol &&
      expected.port === supplied.port)
  );
}

async function proxy(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const target = path.join("/");
  const rule = routes.find(([pattern]) => pattern.test(target));
  if (!rule) return reply(404, "This API route is not available.");
  if (!rule[1].includes(request.method))
    return reply(405, "This method is not available for this route.");
  const mutating = request.method !== "GET";
  try {
    if (mutating && !validOrigin(request))
      return reply(403, "The request origin was not accepted.");
  } catch {
    return reply(403, "The request origin was not accepted.");
  }
  if (mutating && !request.headers.get("x-csrf-token"))
    return reply(403, "The session protection token is missing. Please retry.");

  const incoming = new URL(request.url);
  const oauthCallback = /^auth\/oauth\/(github|google)\/callback$/.test(target);
  const githubCallback = target === "integrations/github/callback";
  const callback = oauthCallback || githubCallback;
  const analyticsList = new RegExp(
    `^organizations/${uuid}/(metrics/pull-requests|pull-requests|commits|repositories/${uuid}/issues)$`,
  ).test(target);
  const pullRequestList = new RegExp(`^organizations/${uuid}/pull-requests$`).test(target);
  const issueList = new RegExp(`^organizations/${uuid}/repositories/${uuid}/issues$`).test(target);
  const ciList = new RegExp(`^organizations/${uuid}/(metrics/ci|workflow-runs)$`).test(target);
  const deploymentList = new RegExp(
    `^organizations/${uuid}/(metrics/deployments|deployments)$`,
  ).test(target);
  const workflowCollection = new RegExp(`^organizations/${uuid}/workflow-runs$`).test(target);
  const deploymentCollection = new RegExp(`^organizations/${uuid}/deployments$`).test(target);
  const testMetrics = new RegExp(`^organizations/${uuid}/metrics/tests$`).test(target);
  const testReports = new RegExp(`^organizations/${uuid}/test-runs$`).test(target);
  const testCandidates = new RegExp(`^organizations/${uuid}/tests$`).test(target);
  const testHistory = new RegExp(`^organizations/${uuid}/tests/${uuid}/history$`).test(target);
  const testCases = new RegExp(`^organizations/${uuid}/test-runs/${uuid}/cases$`).test(target);
  const testAnalytics = testMetrics || testReports || testCandidates || testHistory || testCases;
  const analyticsParameters: Record<string, number> = analyticsList
    ? {
        from: 40,
        to: 40,
        author: 100,
        ...(!issueList ? { repository: 36 } : {}),
        ...(pullRequestList ? { state: 12, cohort: 12, metric: 24, eligibility: 12 } : {}),
        ...(issueList ? { state: 12 } : {}),
      }
    : {};
  if (ciList || deploymentList)
    Object.assign(analyticsParameters, {
      from: 40,
      to: 40,
      repository: 36,
      ...(ciList ? { workflow: 19, branch: 255 } : { environment: 255, classification: 16 }),
      ...(workflowCollection ? { cohort: 12, outcome: 12, metric: 12, eligibility: 12 } : {}),
      ...(deploymentCollection ? { cohort: 12, eligibility: 12 } : {}),
    });
  if (testMetrics || testReports || testCandidates || testHistory)
    Object.assign(analyticsParameters, {
      branch: 255,
      environment: 255,
      to: 40,
      ...(!testCandidates ? { from: 40 } : {}),
      ...(!testHistory ? { repository: 36 } : {}),
      ...(testReports ? { status: 12 } : {}),
      ...(testCandidates ? { potential_only: 5 } : {}),
    });
  if (testCases) Object.assign(analyticsParameters, { status: 12 });
  const upstream = new URL(
    `/api/v1/${target}`,
    process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000",
  );
  const callbackParameters: Record<string, number> = {
    code: 4096,
    state: 2048,
    iss: 2048,
    error: 256,
    error_description: 2048,
    error_uri: 2048,
    scope: 2048,
    authuser: 16,
    prompt: 128,
    hd: 254,
  };
  if (incoming.search.length > 16_384) return reply(400, "Unsupported query parameters.");
  for (const [key, value] of incoming.searchParams) {
    // OAuth clients must ignore unrecognized response extensions (RFC 6749,
    // section 4.1.2). Drop them here; they cannot affect upstream routing or login.
    // Known security fields still have size and duplicate checks below.
    if (callback && !Object.hasOwn(callbackParameters, key)) continue;
    const maximum = callback
      ? Object.hasOwn(callbackParameters, key)
        ? callbackParameters[key]
        : undefined
      : ["cursor", "limit"].includes(key)
        ? 2048
        : Object.hasOwn(analyticsParameters, key)
          ? analyticsParameters[key]
          : undefined;
    if (
      request.method !== "GET" ||
      !maximum ||
      value.length > maximum ||
      upstream.searchParams.has(key)
    )
      return reply(400, "Unsupported query parameters.");
    if (
      (analyticsList || ciList || deploymentList || testAnalytics) &&
      Object.hasOwn(analyticsParameters, key)
    ) {
      const valid =
        key === "status"
          ? (testCases
              ? ["passed", "failed", "error", "skipped"]
              : ["queued", "processing", "completed", "failed"]
            ).includes(value)
          : key === "potential_only"
            ? ["true", "false"].includes(value)
            : key === "repository"
              ? new RegExp(`^${uuid}$`).test(value)
              : key === "from" || key === "to"
                ? /^\d{4}-\d{2}-\d{2}T/.test(value) &&
                  /(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
                  Number.isFinite(Date.parse(value))
                : key === "state"
                  ? (issueList
                      ? ["all", "open", "closed"]
                      : ["all", "open", "closed", "merged"]
                    ).includes(value)
                  : key === "cohort"
                    ? (ciList
                        ? ["activity", "completed"]
                        : deploymentList
                          ? ["created", "success"]
                          : ["activity", "merged"]
                      ).includes(value)
                    : key === "metric"
                      ? (ciList
                          ? ["duration", "queue"]
                          : ["cycle_time", "review_wait", "approval_to_merge"]
                        ).includes(value)
                      : key === "eligibility"
                        ? ["eligible", "excluded", "all"].includes(value)
                        : key === "outcome"
                          ? ["all", "success", "failure", "other"].includes(value)
                          : key === "classification"
                            ? ["production", "nonproduction", "unknown", "all"].includes(value)
                            : key === "workflow"
                              ? /^[1-9]\d{0,18}$/.test(value)
                              : !/[\u0000-\u001f\u007f]/.test(value);
      if (!valid) return reply(400, "Unsupported query parameters.");
    }
    upstream.searchParams.set(key, value);
  }

  let body: string | undefined;
  if (mutating && request.body) {
    if (Number(request.headers.get("content-length") ?? 0) > maxBody)
      return reply(413, "The request is too large.");
    try {
      const payload = await readBounded(request.body, maxBody, 10_000);
      // Next can expose an empty stream for a bodyless POST or DELETE. Only an
      // actual payload needs a JSON media type; forward empty requests without a body.
      if (payload.length > 0) {
        if (
          request.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase() !==
          "application/json"
        )
          return reply(415, "Use a JSON request body.");
        JSON.parse(payload);
        body = payload;
      }
    } catch (error) {
      if (error instanceof Error && error.message === "too_large")
        return reply(413, "The request is too large.");
      if (error instanceof Error && error.message === "timeout")
        return reply(408, "The request body timed out.");
      return reply(400, "The JSON request body is invalid.");
    }
  }

  const requestId = crypto.randomUUID();
  const headers = new Headers({ Accept: "application/json", "X-Request-ID": requestId });
  const cookie = request.headers.get("cookie");
  if (cookie)
    headers.set(
      "Cookie",
      cookie
        .split(";")
        .filter((item) => /^\s*forge_(access|refresh|csrf|preauth|oauth|github_app)=/.test(item))
        .join(";"),
    );
  for (const key of ["origin", "x-csrf-token"]) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }
  if (body !== undefined) headers.set("Content-Type", "application/json");
  try {
    const result = await fetch(upstream, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      redirect: callback ? "manual" : "error",
      signal: AbortSignal.timeout(10_000),
    });
    const responseHeaders = new Headers({
      "Cache-Control": "no-store",
      "X-Request-ID": requestId,
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
    });
    if (callback && result.status >= 300 && result.status < 400) {
      const destination = result.headers.get("Location");
      if (
        result.status !== 303 ||
        !destination ||
        !(githubCallback
          ? validGitHubCallbackRedirect(destination)
          : validOAuthCallbackRedirect(destination))
      )
        return reply(502, "The sign-in response could not be verified. Please start again.");
      responseHeaders.set("Location", destination);
      for (const cookieValue of result.headers.getSetCookie())
        responseHeaders.append("Set-Cookie", cookieValue);
      return new Response(null, { status: 303, headers: responseHeaders });
    }
    responseHeaders.set(
      "Content-Type",
      result.headers.get("Content-Type")?.includes("json")
        ? result.headers.get("Content-Type")!
        : "application/json",
    );
    for (const cookieValue of result.headers.getSetCookie())
      responseHeaders.append("Set-Cookie", cookieValue);
    const retryAfter = result.headers.get("Retry-After");
    if (retryAfter) responseHeaders.set("Retry-After", retryAfter);
    const payload =
      result.status === 204 || !result.body
        ? null
        : await readBounded(result.body, 1_048_576, 10_000);
    return new Response(payload, { status: result.status, headers: responseHeaders });
  } catch {
    return reply(503, "The Forge API could not be reached. Check the backend service and retry.");
  }
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
