import { safeReturn } from "./auth-client";

export const oauthProviders = ["github", "google"] as const;
export type OAuthProvider = (typeof oauthProviders)[number];
export const providerNames: Record<OAuthProvider, string> = { github: "GitHub", google: "Google" };
export interface ProviderAvailability {
  providers: { id: OAuthProvider; enabled: boolean }[];
}
export interface Connection {
  provider: OAuthProvider;
  email: string;
  created_at: string;
}

const oauthErrors: Record<string, string> = {
  denied: "Sign-in was cancelled. Choose a sign-in method to try again.",
  invalid_state:
    "This sign-in attempt expired or could not be verified. Start again in this browser.",
  provider_unavailable:
    "The sign-in provider is unavailable. Please try again shortly or use your email and password.",
  invalid_identity:
    "The provider could not verify your account. Try again or use another sign-in method.",
  email_unverified:
    "Use a verified primary email, or create a Forge account with email and connect this provider from Account settings.",
  account_exists:
    "An account already uses this email. Sign in using your existing method, then connect GitHub or Google in Account settings.",
  identity_in_use:
    "This provider account is already connected to another Forge account. Choose a different account.",
  link_unavailable:
    "Sign in and verify your Forge email before connecting a provider in Account settings.",
};

export function oauthErrorMessage(code: string | null) {
  return code && Object.hasOwn(oauthErrors, code) ? oauthErrors[code] : "";
}

export function authorizationDestination(provider: OAuthProvider, value: string): string {
  const expected =
    provider === "github"
      ? "https://github.com/login/oauth/authorize"
      : "https://accounts.google.com/o/oauth2/v2/auth";
  const url = new URL(value);
  if (`${url.origin}${url.pathname}` !== expected || url.username || url.password || url.hash)
    throw new Error("The provider sign-in address could not be verified. Please retry.");
  return url.href;
}

export function validOAuthCallbackRedirect(value: string | null): value is string {
  if (!value || value.length > 4096 || /[%\\\u0000-\u0020]/.test(value.split("?", 1)[0]))
    return false;
  if (/[\\\u0000-\u0020]/.test(value) || !value.startsWith("/") || value.startsWith("//"))
    return false;
  const url = new URL(value, "https://forge.invalid");
  if (url.origin !== "https://forge.invalid" || url.hash) return false;
  if (url.pathname === "/login") {
    return url.searchParams.size === 1 && !!oauthErrorMessage(url.searchParams.get("oauth_error"));
  }
  return /^\/app(?:\/|$)/.test(url.pathname) && safeReturn(value) === value;
}
