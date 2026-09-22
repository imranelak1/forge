import { describe, expect, it } from "vitest";
import {
  authorizationDestination,
  oauthErrorMessage,
  validOAuthCallbackRedirect,
} from "@/lib/oauth";

describe("OAuth navigation boundaries", () => {
  it("accepts only the selected provider's pinned HTTPS authorization endpoint", () => {
    expect(
      authorizationDestination("github", "https://github.com/login/oauth/authorize?state=opaque"),
    ).toBe("https://github.com/login/oauth/authorize?state=opaque");
    expect(
      authorizationDestination(
        "google",
        "https://accounts.google.com/o/oauth2/v2/auth?state=opaque",
      ),
    ).toContain("accounts.google.com");
    for (const target of [
      "https://github.com.attacker.example/login/oauth/authorize",
      "http://github.com/login/oauth/authorize",
      "https://attacker@github.com/login/oauth/authorize",
      "https://github.com/login/oauth/authorize#secret",
      "javascript:alert(1)",
      "https://github.com/login/oauth/authorize/elsewhere",
      "https://accounts.google.com/o/oauth2/v2/auth",
    ])
      expect(() => authorizationDestination("github", target)).toThrow();
  });

  it.each([
    "/app?oauth=signed-in",
    "/app/account?oauth=linked",
    "/app/settings?tab=members&oauth=signed-in",
    "/login?oauth_error=invalid_state",
  ])("accepts the local callback destination %s", (value) => {
    expect(validOAuthCallbackRedirect(value)).toBe(true);
  });

  it.each([
    "https://attacker.example/app",
    "//attacker.example/app",
    "/\\attacker.example",
    "/app/../../evil",
    "/app%2f..%2f..%2fevil",
    "/app#token",
    "/login?returnTo=https://attacker.example",
    "/login?oauth_error=unknown",
    "/login?oauth_error=denied&oauth_error=invalid_state",
    "/application?oauth=signed-in",
    "/app\nLocation:https://attacker.example",
  ])("rejects unsafe callback destination %s", (value) => {
    expect(validOAuthCallbackRedirect(value)).toBe(false);
  });

  it("uses fixed recoverable error messages without reflecting supplied query text", () => {
    expect(oauthErrorMessage("account_exists")).toContain("existing method");
    expect(oauthErrorMessage("link_unavailable")).toContain("verify");
    expect(oauthErrorMessage("<script>alert(1)</script>")).toBe("");
    expect(oauthErrorMessage("toString")).toBe("");
  });
});
