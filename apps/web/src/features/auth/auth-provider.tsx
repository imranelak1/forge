"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, getIdentity } from "@/lib/auth-client";
import type { Identity, Organization, PageResult } from "@/lib/auth-types";

const identityKey = ["auth", "me"] as const;
type AuthContextValue = {
  identity: Identity | null | undefined;
  loading: boolean;
  error: Error | null;
  organization: Organization | undefined;
  selectOrganization: (id: string) => Promise<void>;
  loadMoreOrganizations: () => Promise<void>;
  reload: () => Promise<void>;
  authenticated: () => Promise<void>;
  clearSession: () => Promise<void>;
  logout: () => Promise<void>;
};
const AuthContext = createContext<AuthContextValue | null>(null);
const authPaths = [
  "/login",
  "/register",
  "/verify-email",
  "/invite",
  "/forgot-password",
  "/reset-password",
];

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const client = useQueryClient();
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [synchronizing, setSynchronizing] = useState(false);
  const channelRef = useRef<BroadcastChannel | null>(null);
  const enabled = pathname.startsWith("/app") || authPaths.includes(pathname);
  const identity = useQuery<Identity | null>({
    queryKey: identityKey,
    queryFn: async ({ signal }) => {
      try {
        const result = await getIdentity(signal);
        // Keep a selected organization beyond the first page available after refetch,
        // while asking the API to recheck its current membership and role.
        if (selectedId && !result.organizations.some((item) => item.id === selectedId)) {
          try {
            result.organizations.push(
              await api<Organization>(`/organizations/${selectedId}`, { signal }),
            );
          } catch (error) {
            if (!(error instanceof ApiError && [403, 404].includes(error.status))) throw error;
          }
        }
        return result;
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    enabled,
    retry: false,
    staleTime: 15_000,
  });
  const clearOrganizationQueries = useCallback(async () => {
    await client.cancelQueries({ predicate: (query) => query.queryKey[0] === "organization" });
    client.removeQueries({ predicate: (query) => query.queryKey[0] === "organization" });
  }, [client]);
  const reload = useCallback(async () => {
    await client.invalidateQueries({ queryKey: identityKey });
  }, [client]);
  const authenticated = useCallback(async () => {
    await client.cancelQueries();
    client.clear();
    client.setQueryData(identityKey, await getIdentity());
    setSelectedId(null);
    // A channel does not receive its own messages. Reuse the listening channel
    // instead of creating a second channel which would notify this same tab.
    channelRef.current?.postMessage({ type: "changed" });
  }, [client]);
  const selectOrganization = useCallback(
    async (id: string) => {
      if (!client.getQueryData<Identity>(identityKey)?.organizations.some((item) => item.id === id))
        return;
      await clearOrganizationQueries();
      setSelectedId(id);
    },
    [client, clearOrganizationQueries],
  );
  const loadMoreOrganizations = useCallback(async () => {
    const current = client.getQueryData<Identity>(identityKey);
    const cursor = current?.organizations_page?.next_cursor;
    if (!current || !cursor) return;
    const page = await client.fetchQuery({
      queryKey: ["organization-list", current.user.id, cursor],
      queryFn: ({ signal }) =>
        api<PageResult<Organization>>(
          `/organizations?limit=100&cursor=${encodeURIComponent(cursor)}`,
          { signal },
        ),
    });
    client.setQueryData<Identity | null>(identityKey, (previous) => {
      if (!previous || previous.session_id !== current.session_id) return previous;
      return {
        ...previous,
        organizations: Array.from(
          new Map(
            [...previous.organizations, ...page.data].map((item) => [item.id, item]),
          ).values(),
        ),
        organizations_page: page.page,
      };
    });
  }, [client]);
  const clearSession = useCallback(async () => {
    await client.cancelQueries();
    client.clear();
    client.setQueryData(identityKey, null);
    setSelectedId(null);
    channelRef.current?.postMessage({ type: "signed-out" });
  }, [client]);
  const logout = useCallback(async () => {
    await api("/auth/logout", { method: "POST" });
    await clearSession();
    router.replace("/login");
  }, [clearSession, router]);

  useEffect(() => {
    const ended = () => {
      void client.cancelQueries({ predicate: (query) => query.queryKey[0] === "organization" });
      client.removeQueries({
        predicate: (query) =>
          query.queryKey[0] === "organization" || query.queryKey[0] === "sessions",
      });
      client.setQueryData(identityKey, null);
    };
    window.addEventListener("forge:session-ended", ended);
    const channel =
      typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel("forge-auth");
    channelRef.current = channel;
    if (channel)
      channel.onmessage = (event: MessageEvent<unknown>) => {
        if (!event.data || typeof event.data !== "object" || !("type" in event.data)) return;
        const type = event.data.type;
        if (type !== "changed" && type !== "signed-out") return;
        setSynchronizing(true);
        void client
          .cancelQueries()
          .then(async () => {
            client.removeQueries({ predicate: (query) => query.queryKey[0] !== "auth" });
            setSelectedId(null);
            if (type === "signed-out") {
              client.setQueryData(identityKey, null);
              return;
            }
            // Hide the previous account while checking the new cookie session.
            // Do not publish a transient signed-out state and redirect a valid tab.
            await client.fetchQuery<Identity | null>({
              queryKey: identityKey,
              queryFn: async ({ signal }) => {
                try {
                  return await getIdentity(signal);
                } catch (error) {
                  if (error instanceof ApiError && error.status === 401) return null;
                  throw error;
                }
              },
              staleTime: 0,
              retry: false,
            });
          })
          .catch(() => {
            // Query state exposes the transport error and the workspace recovery action.
          })
          .finally(() => setSynchronizing(false));
      };
    return () => {
      channel?.close();
      channelRef.current = null;
      window.removeEventListener("forge:session-ended", ended);
    };
  }, [client]);

  const organization =
    identity.data?.organizations.find((item) => item.id === selectedId) ??
    identity.data?.organizations[0];
  const value = useMemo(
    () => ({
      identity: synchronizing ? undefined : identity.data,
      loading:
        enabled &&
        (identity.isPending || synchronizing || (identity.data === null && identity.isFetching)),
      error: identity.error,
      organization,
      selectOrganization,
      loadMoreOrganizations,
      reload,
      authenticated,
      clearSession,
      logout,
    }),
    [
      identity.data,
      identity.error,
      identity.isPending,
      identity.isFetching,
      synchronizing,
      enabled,
      organization,
      selectOrganization,
      loadMoreOrganizations,
      reload,
      authenticated,
      clearSession,
      logout,
    ],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider is required.");
  return value;
}
