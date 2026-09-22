import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "@/features/auth/auth-provider";
import { ApiError, getIdentity } from "@/lib/auth-client";
import type { Identity } from "@/lib/auth-types";

vi.mock("next/navigation", () => ({
  usePathname: () => "/app",
  useRouter: () => ({ replace: vi.fn() }),
}));
vi.mock("@/lib/auth-client", async () => ({
  ...(await vi.importActual<typeof import("@/lib/auth-client")>("@/lib/auth-client")),
  getIdentity: vi.fn(),
}));

const owner: Identity = {
  user: { id: "owner", name: "Owner", email: "owner@example.test", email_verified: true },
  session_id: "session",
  organizations: [],
};
const teammate: Identity = {
  ...owner,
  user: { ...owner.user, id: "teammate", name: "Teammate" },
  session_id: "another-session",
};

class FakeBroadcastChannel {
  static instances = new Set<FakeBroadcastChannel>();
  onmessage: ((event: MessageEvent) => void) | null = null;
  constructor(public name: string) {
    FakeBroadcastChannel.instances.add(this);
  }
  postMessage(data: unknown) {
    for (const channel of FakeBroadcastChannel.instances) {
      if (channel !== this && channel.name === this.name)
        channel.onmessage?.({ data } as MessageEvent);
    }
  }
  close() {
    FakeBroadcastChannel.instances.delete(this);
  }
}

function Probe() {
  const auth = useAuth();
  return (
    <>
      <p>{auth.loading ? "Checking" : (auth.identity?.user.name ?? "Signed out")}</p>
      <button onClick={() => void auth.authenticated()}>Complete sign in</button>
    </>
  );
}
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  );
  return client;
}

beforeEach(() => {
  vi.mocked(getIdentity).mockReset();
  FakeBroadcastChannel.instances.clear();
  vi.stubGlobal("BroadcastChannel", FakeBroadcastChannel);
  window.history.replaceState({}, "", "/app");
});

describe("cross-tab authentication changes", () => {
  it("announces completed OAuth only after identity is checked and removes the callback marker", async () => {
    window.history.replaceState({}, "", "/app/settings?tab=members&oauth=signed-in");
    let completeIdentity: (identity: Identity) => void = () => undefined;
    vi.mocked(getIdentity).mockImplementation(
      () =>
        new Promise((resolve) => {
          completeIdentity = resolve;
        }),
    );
    const otherTab = new FakeBroadcastChannel("forge-auth");
    const received = vi.fn();
    otherTab.onmessage = received;
    mount();
    await screen.findByText("Checking");
    expect(received).not.toHaveBeenCalled();
    await act(async () => {
      completeIdentity(owner);
    });
    await screen.findByText("Owner");
    expect(received).toHaveBeenCalledTimes(1);
    expect(window.location.pathname + window.location.search).toBe("/app/settings?tab=members");
    otherTab.close();
  });

  it("keeps this tab signed in after publishing its own completed sign-in", async () => {
    vi.mocked(getIdentity).mockRejectedValueOnce(new ApiError(401, "Sign in"));
    mount();
    await screen.findByText("Signed out");
    vi.mocked(getIdentity).mockResolvedValue(owner);
    fireEvent.click(screen.getByRole("button", { name: "Complete sign in" }));
    await screen.findByText("Owner");
    await waitFor(() => expect(FakeBroadcastChannel.instances.size).toBe(1));
    expect(screen.queryByText("Signed out")).not.toBeInTheDocument();
  });

  it("rechecks another tab's sign-in without exposing a signed-out redirect state", async () => {
    vi.mocked(getIdentity).mockResolvedValue(owner);
    mount();
    await screen.findByText("Owner");
    let resolveIdentity: (identity: Identity) => void = () => undefined;
    vi.mocked(getIdentity).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveIdentity = resolve;
        }),
    );
    const otherTab = new FakeBroadcastChannel("forge-auth");
    act(() => {
      otherTab.postMessage({ type: "changed" });
    });
    await screen.findByText("Checking");
    expect(screen.queryByText("Signed out")).not.toBeInTheDocument();
    await act(async () => {
      resolveIdentity(teammate);
    });
    await screen.findByText("Teammate");
    otherTab.close();
  });

  it("clears tenant data and ends the local session when another tab signs out", async () => {
    vi.mocked(getIdentity).mockResolvedValue(owner);
    const client = mount();
    await screen.findByText("Owner");
    client.setQueryData(["organization", "private", "members"], { private: true });
    const otherTab = new FakeBroadcastChannel("forge-auth");
    act(() => {
      otherTab.postMessage({ type: "signed-out" });
    });
    await screen.findByText("Signed out");
    expect(client.getQueryData(["organization", "private", "members"])).toBeUndefined();
    otherTab.close();
  });
});
