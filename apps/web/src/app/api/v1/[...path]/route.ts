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
        : undefined;
    if (
      request.method !== "GET" ||
      !maximum ||
      value.length > maximum ||
      upstream.searchParams.has(key)
    )
      return reply(400, "Unsupported query parameters.");
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

export { proxy as GET, proxy as POST, proxy as PATCH, proxy as DELETE };
