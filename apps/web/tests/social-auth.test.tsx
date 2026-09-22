import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConnectedAccounts, SocialSignIn } from "@/features/auth/social-auth";
import { CredentialsPage } from "@/features/auth/auth-pages";
import { api } from "@/lib/auth-client";

const state = vi.hoisted(() => ({ verified: true }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(window.location.search),
  useRouter: () => ({ replace: vi.fn() }),
}));
vi.mock("@/features/auth/auth-provider", () => ({
  useAuth: () => ({ identity: { user: { id: "person", email_verified: state.verified } } }),
}));
vi.mock("@/lib/auth-client", async () => ({
  ...(await vi.importActual<typeof import("@/lib/auth-client")>("@/lib/auth-client")),
  api: vi.fn(),
}));

const configured = {
  providers: [
    { id: "github", enabled: true },
    { id: "google", enabled: true },
  ],
};
function mount(element: React.ReactNode = <SocialSignIn returnTo="/app/settings" />) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      {element}
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  state.verified = true;
  vi.mocked(api).mockReset();
  window.history.replaceState({}, "", "/login");
});

describe("provider sign-in controls", () => {
  it("prevents simultaneous password and social sign-in while authorization is starting", async () => {
    vi.mocked(api).mockImplementation((path) =>
      path === "/auth/providers" ? Promise.resolve(configured) : new Promise(() => {}),
    );
    mount(<CredentialsPage mode="login" />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Continue with GitHub" })).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Continue with GitHub" }));
    await screen.findByRole("button", { name: "Opening GitHub..." });
    expect(screen.getByLabelText("Password")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeDisabled();
  });

  it("keeps both choices visible and explains when deployment credentials are missing", async () => {
    vi.mocked(api).mockResolvedValue({
      providers: [
        { id: "github", enabled: false },
        { id: "google", enabled: false },
      ],
    });
    mount();
    await screen.findByText("Social sign-in is not configured yet.");
    expect(screen.getByRole("button", { name: "Continue with GitHub" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeDisabled();
  });

  it("enables the configured provider while identifying the unavailable provider", async () => {
    vi.mocked(api).mockResolvedValue({
      providers: [
        { id: "github", enabled: true },
        { id: "google", enabled: false },
      ],
    });
    mount();
    await screen.findByText("Google sign-in is not configured yet.");
    expect(screen.getByRole("button", { name: "Continue with GitHub" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeDisabled();
  });

  it("recovers provider discovery after a failed request", async () => {
    vi.mocked(api).mockRejectedValueOnce(new Error("offline")).mockResolvedValue(configured);
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Retry sign-in options" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Continue with Google" })).toBeEnabled(),
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("submits the login intent and refuses an untrusted authorization URL", async () => {
    vi.mocked(api).mockImplementation(async (path) =>
      path === "/auth/providers"
        ? configured
        : { authorization_url: "https://attacker.example/oauth" },
    );
    mount();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Continue with GitHub" })).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Continue with GitHub" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be verified");
    expect(api).toHaveBeenCalledWith("/auth/oauth/github/start", {
      method: "POST",
      refresh: false,
      body: { intent: "login", return_to: "/app/settings" },
    });
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeEnabled();
  });

  it("requires a verified Forge email before connecting an account", async () => {
    state.verified = false;
    vi.mocked(api).mockImplementation(async (path) =>
      path === "/auth/providers" ? configured : { connections: [] },
    );
    mount(<ConnectedAccounts />);
    expect(await screen.findByRole("button", { name: "Connect GitHub" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Connect Google" })).toBeDisabled();
    expect(screen.getByText("Verify your Forge email before connecting an account.")).toBeVisible();
  });

  it("shows the linked identity and sends an explicit linking intent for another provider", async () => {
    vi.mocked(api).mockImplementation(async (path) => {
      if (path === "/auth/providers") return configured;
      if (path === "/auth/connections")
        return {
          connections: [
            { provider: "github", email: "owner@example.com", created_at: "2026-01-01T00:00:00Z" },
          ],
        };
      throw new Error("Please sign in again before connecting an account.");
    });
    mount(<ConnectedAccounts />);
    await screen.findByText("owner@example.com");
    expect(screen.queryByRole("button", { name: "Connect GitHub" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Connect Google" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Please sign in again");
    expect(api).toHaveBeenCalledWith("/auth/oauth/google/start", {
      method: "POST",
      refresh: true,
      body: { intent: "link", return_to: "/app/account" },
    });
  });
});
