import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SystemStatus } from "@/features/system/system-status";

function renderStatus() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <SystemStatus />
    </QueryClientProvider>,
  );
}

describe("system health", () => {
  it("shows actual readiness and reruns both checks on request", async () => {
    const fetchMock = vi.fn((url: string) =>
      Promise.resolve(
        new Response(
          JSON.stringify(
            url.endsWith("live")
              ? { status: "ok" }
              : { status: "ready", checks: { database: "up", migrations: "current" } },
          ),
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderStatus();
    await waitFor(() => expect(screen.getAllByText("Healthy")).toHaveLength(3));
    fireEvent.click(screen.getByRole("button", { name: "Run checks" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
  });

  it("does not present an unreachable API as a healthy database", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network unavailable")));
    renderStatus();
    expect(await screen.findByText("Some services need attention")).toBeInTheDocument();
    expect(screen.queryByText("Healthy")).not.toBeInTheDocument();
    expect(screen.getAllByText("Not verified")).toHaveLength(2);
    expect(
      screen.getByText("Checks database connectivity using the API’s runtime credentials."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open troubleshooting" })).toHaveAttribute(
      "href",
      "/guide#troubleshooting",
    );
  });

  it("distinguishes a stale schema from a database outage", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              url.endsWith("live")
                ? { status: "ok" }
                : { code: "not_ready", checks: { database: "up", migrations: "pending" } },
            ),
            { status: url.endsWith("live") ? 200 : 503 },
          ),
        ),
      ),
    );
    renderStatus();
    expect(await screen.findByText("Migration required")).toBeInTheDocument();
    expect(screen.getAllByText("Healthy")).toHaveLength(2);
  });
});
