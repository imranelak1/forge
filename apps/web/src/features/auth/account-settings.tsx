"use client";

import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useState } from "react";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/auth-client";
import type { PageResult, Session } from "@/lib/auth-types";
import { useAuth } from "./auth-provider";
import { FormMessage } from "./form-parts";
import { RequestEmailForm } from "./auth-pages";
import { ConnectedAccounts } from "./social-auth";

const date = (value: string) =>
  new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

export function AccountSettings() {
  const { identity, logout } = useAuth();
  const client = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const sessions = useInfiniteQuery({
    queryKey: ["sessions", identity?.user.id],
    enabled: !!identity,
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) =>
      api<PageResult<Session>>(
        `/auth/sessions?limit=25${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`,
        { signal },
      ),
    getNextPageParam: (page) =>
      page.page.has_more ? (page.page.next_cursor ?? undefined) : undefined,
  });
  async function endSession(id: string) {
    setBusy(id);
    setError("");
    setSuccess("");
    try {
      await api(`/auth/sessions/${id}`, { method: "DELETE" });
      await client.invalidateQueries({ queryKey: ["sessions"] });
      setSuccess("Session revoked. That browser must sign in again.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }
  async function signOut() {
    setBusy("logout");
    setError("");
    setSuccess("");
    try {
      await logout();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(null);
    }
  }
  if (!identity) return null;
  return (
    <div className="settings-content">
      <div className="page-heading">
        <div>
          <h1>Account settings</h1>
          <p>Manage your sign-in methods, email verification and active sessions.</p>
        </div>
        <Button variant="outline" disabled={!!busy} onClick={() => void signOut()}>
          {busy === "logout" ? "Signing out..." : "Sign out"}
        </Button>
      </div>
      <section className="settings-section" aria-labelledby="profile-title">
        <div className="settings-section-heading">
          <h2 id="profile-title">Your account</h2>
        </div>
        <dl className="account-details">
          <div>
            <dt>Name</dt>
            <dd>{identity.user.name}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{identity.user.email}</dd>
          </div>
          <div>
            <dt>Email status</dt>
            <dd className={identity.user.email_verified ? "state-success" : "state-warning"}>
              {identity.user.email_verified ? "Verified" : "Not verified"}
            </dd>
          </div>
        </dl>
        {!identity.user.email_verified && (
          <div className="verification-form">
            <p>Verify your email to accept team invitations.</p>
            <RequestEmailForm kind="verify-email" email={identity.user.email} />
          </div>
        )}
      </section>
      <Suspense fallback={<p role="status">Loading connected accounts...</p>}>
        <ConnectedAccounts />
      </Suspense>
      <section className="settings-section" aria-labelledby="sessions-title">
        <div className="settings-section-heading">
          <h2 id="sessions-title">Active sessions</h2>
          <p>Revoke a session to end access in that browser. Sign out ends this session.</p>
        </div>
        <FormMessage error={error} success={success} />
        {sessions.isPending ? (
          <p role="status">Loading sessions...</p>
        ) : sessions.isError ? (
          <div className="account-form">
            <FormMessage error={errorMessage(sessions.error)} />
            <Button variant="outline" onClick={() => void sessions.refetch()}>
              Retry sessions
            </Button>
          </div>
        ) : (
          <>
            <ul className="session-list">
              {sessions.data.pages
                .flatMap((page) => page.data)
                .map((session) => (
                  <li className="session-row" key={session.id}>
                    <div>
                      <strong>{session.current ? "This browser" : "Other browser session"}</strong>
                      <p>
                        Started{" "}
                        <time dateTime={session.created_at}>{date(session.created_at)}</time>
                      </p>
                      <p>
                        Expires{" "}
                        <time dateTime={session.expires_at}>{date(session.expires_at)}</time>
                      </p>
                      <span className="session-reference">Session {session.id.slice(0, 8)}</span>
                    </div>
                    {session.current ? (
                      <span className="member-role">Current session</span>
                    ) : (
                      <Button
                        variant="outline"
                        disabled={!!busy}
                        onClick={() => void endSession(session.id)}
                      >
                        {busy === session.id ? "Revoking..." : "Revoke session"}
                      </Button>
                    )}
                  </li>
                ))}
            </ul>
            {sessions.hasNextPage && (
              <Button
                variant="outline"
                disabled={sessions.isFetchingNextPage}
                onClick={() => void sessions.fetchNextPage()}
              >
                {sessions.isFetchingNextPage ? "Loading..." : "Load more sessions"}
              </Button>
            )}
          </>
        )}
      </section>
    </div>
  );
}
