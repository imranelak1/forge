"use client";

import Link from "next/link";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/auth-client";
import type { AuditEvent, Member, Organization, PageResult, Role } from "@/lib/auth-types";
import { useAuth } from "@/features/auth/auth-provider";
import { Field, FormMessage } from "@/features/auth/form-parts";

const roles: Role[] = ["viewer", "member", "admin", "owner"];
const roleLabels: Record<Role, string> = {
  viewer: "Viewer",
  member: "Member",
  admin: "Admin",
  owner: "Owner",
};
const date = (value: string) =>
  new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

export function OrganizationSettings() {
  const { organization } = useAuth();
  if (!organization) return null;
  return <SettingsContent key={organization.id} organization={organization} />;
}

function SettingsContent({ organization }: { organization: Organization }) {
  const { identity, reload } = useAuth();
  const client = useQueryClient();
  const router = useRouter();
  const manager = organization.role === "admin" || organization.role === "owner";
  const owner = organization.role === "owner";
  const base = `/organizations/${organization.id}`;
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<{ section: string; message: string } | null>(null);
  const [success, setSuccess] = useState<{ section: string; message: string } | null>(null);
  const [removeId, setRemoveId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const members = useInfiniteQuery({
    queryKey: ["organization", organization.id, "members"],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) =>
      api<PageResult<Member>>(
        `${base}/members?limit=25${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`,
        { signal },
      ),
    getNextPageParam: (page) =>
      page.page.has_more ? (page.page.next_cursor ?? undefined) : undefined,
  });
  const audit = useInfiniteQuery({
    queryKey: ["organization", organization.id, "audit"],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) =>
      api<PageResult<AuditEvent>>(
        `${base}/audit?limit=15${pageParam ? `&cursor=${encodeURIComponent(pageParam)}` : ""}`,
        { signal },
      ),
    getNextPageParam: (page) =>
      page.page.has_more ? (page.page.next_cursor ?? undefined) : undefined,
    enabled: manager,
  });

  async function change(section: string, action: () => Promise<void>) {
    setBusy(section);
    setError(null);
    setSuccess(null);
    try {
      await action();
      await client.invalidateQueries({ queryKey: ["organization", organization.id] });
      await reload();
    } catch (err) {
      setError({ section, message: errorMessage(err) });
    } finally {
      setBusy(null);
    }
  }
  const message = (section: string) => (
    <FormMessage
      error={error?.section === section ? error.message : undefined}
      success={success?.section === section ? success.message : undefined}
    />
  );

  return (
    <div className="settings-content">
      <div className="page-heading">
        <div>
          <h1>Organization settings</h1>
          <p>
            {organization.name} · {roleLabels[organization.role]}
          </p>
        </div>
        <Button asChild variant="outline">
          <Link href="/app/organizations/new">New organization</Link>
        </Button>
      </div>
      {organization.is_demo && (
        <p className="phase-notice">This organization contains demonstration data.</p>
      )}
      <section className="settings-section" aria-labelledby="organization-details-title">
        <div className="settings-section-heading">
          <h2 id="organization-details-title">Organization details</h2>
          <p>The name your team sees in Forge.</p>
        </div>
        <form
          className="account-form"
          method="post"
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            void change("details", async () => {
              await api(base, { method: "PATCH", body: { name: String(data.get("name")).trim() } });
              setSuccess({ section: "details", message: "Organization name saved." });
            });
          }}
          aria-busy={busy === "details"}
        >
          <Field
            label="Organization name"
            name="name"
            defaultValue={organization.name}
            required
            minLength={2}
            maxLength={100}
            autoComplete="organization"
            disabled={!manager || !!busy}
          />
          <div className="setting-value">
            <span>Slug</span>
            <code>{organization.slug}</code>
          </div>
          {message("details")}
          {manager ? (
            <Button type="submit" disabled={!!busy}>
              {busy === "details" ? "Saving..." : "Save organization"}
            </Button>
          ) : (
            <p className="field-hint">An owner or admin can update organization details.</p>
          )}
        </form>
      </section>
      <section className="settings-section" aria-labelledby="members-title">
        <div className="settings-section-heading">
          <h2 id="members-title">Members</h2>
          <p>
            Owners manage the organization. Admins manage members. Members contribute; viewers have
            read access.
          </p>
        </div>
        {members.isPending ? (
          <p role="status">Loading members...</p>
        ) : members.isError ? (
          <div className="account-form">
            <FormMessage error={errorMessage(members.error)} />
            <Button variant="outline" onClick={() => void members.refetch()}>
              Retry members
            </Button>
          </div>
        ) : (
          <>
            <ul className="member-list">
              {members.data.pages
                .flatMap((page) => page.data)
                .map((member) => {
                  const editable = manager && (member.role !== "owner" || owner);
                  const section = `member-${member.id}`;
                  return (
                    <li className="member-row" key={member.id}>
                      <div className="member-identity">
                        <strong>
                          {member.name}
                          {member.user_id === identity?.user.id ? " (you)" : ""}
                        </strong>
                        <span>{member.email}</span>
                      </div>
                      {editable ? (
                        <div className="member-actions">
                          <select
                            aria-label={`Role for ${member.email}`}
                            value={member.role}
                            disabled={!!busy}
                            onChange={(event) => {
                              const role = event.target.value;
                              void change(section, async () => {
                                await api(`${base}/members/${member.id}`, {
                                  method: "PATCH",
                                  body: { role },
                                });
                                setSuccess({
                                  section,
                                  message: `Role updated for ${member.name}.`,
                                });
                              });
                            }}
                          >
                            {roles
                              .filter((role) => owner || role !== "owner")
                              .map((role) => (
                                <option value={role} key={role}>
                                  {roleLabels[role]}
                                </option>
                              ))}
                          </select>
                          <Button
                            variant="ghost"
                            disabled={!!busy}
                            aria-label={`Remove ${member.email}`}
                            onClick={() => {
                              setRemoveId(member.id);
                              setError(null);
                            }}
                          >
                            Remove
                          </Button>
                        </div>
                      ) : (
                        <span className="member-role">{roleLabels[member.role]}</span>
                      )}
                      {removeId === member.id && (
                        <div className="member-confirm">
                          <p>
                            Remove {member.name} from {organization.name}? They will lose access to
                            this organization.
                          </p>
                          <div className="form-actions">
                            <Button
                              variant="outline"
                              disabled={!!busy}
                              onClick={() =>
                                void change(section, async () => {
                                  await api(`${base}/members/${member.id}`, { method: "DELETE" });
                                  setRemoveId(null);
                                })
                              }
                            >
                              {busy === section ? "Removing..." : "Confirm removal"}
                            </Button>
                            <Button
                              variant="ghost"
                              disabled={!!busy}
                              onClick={() => setRemoveId(null)}
                            >
                              Cancel
                            </Button>
                          </div>
                        </div>
                      )}
                      <div className="member-feedback">{message(section)}</div>
                    </li>
                  );
                })}
            </ul>
            {members.hasNextPage && (
              <Button
                variant="outline"
                disabled={members.isFetchingNextPage}
                onClick={() => void members.fetchNextPage()}
              >
                {members.isFetchingNextPage ? "Loading..." : "Load more members"}
              </Button>
            )}
            {owner && (
              <p className="field-hint">
                Keep at least one owner. To transfer ownership, make another member an owner before
                changing your own role.
              </p>
            )}
          </>
        )}
      </section>
      {manager && (
        <section className="settings-section" aria-labelledby="invite-title">
          <div className="settings-section-heading">
            <h2 id="invite-title">Invite a teammate</h2>
            <p>The recipient must sign in with a verified email matching the invitation.</p>
          </div>
          <form
            className="account-form"
            method="post"
            onSubmit={(event) => {
              event.preventDefault();
              const form = event.currentTarget;
              const data = new FormData(form);
              void change("invite", async () => {
                const invitation = await api<{ email: string; expires_at: string }>(
                  `${base}/invitations`,
                  {
                    method: "POST",
                    body: { email: String(data.get("email")).trim(), role: data.get("role") },
                  },
                );
                setSuccess({
                  section: "invite",
                  message: `Invitation sent to ${invitation.email}. It expires ${date(invitation.expires_at)}.`,
                });
                form.reset();
              });
            }}
            aria-busy={busy === "invite"}
          >
            <Field
              label="Teammate email"
              name="email"
              type="email"
              autoComplete="off"
              maxLength={254}
              required
              disabled={!!busy}
            />
            <div className="form-field">
              <label htmlFor="invite-role">Invitation role</label>
              <select id="invite-role" name="role" defaultValue="member" disabled={!!busy}>
                {roles
                  .filter((role) => owner || role !== "owner")
                  .map((role) => (
                    <option value={role} key={role}>
                      {roleLabels[role]}
                    </option>
                  ))}
              </select>
            </div>
            {message("invite")}
            <Button type="submit" disabled={!!busy}>
              {busy === "invite" ? "Sending invitation..." : "Send invitation"}
            </Button>
          </form>
        </section>
      )}
      {manager && (
        <section className="settings-section" aria-labelledby="audit-title">
          <div className="settings-section-heading">
            <h2 id="audit-title">Organization activity</h2>
            <p>Recorded changes to this organization and its membership.</p>
          </div>
          {audit.isPending ? (
            <p role="status">Loading activity...</p>
          ) : audit.isError ? (
            <div className="account-form">
              <FormMessage error={errorMessage(audit.error)} />
              <Button variant="outline" onClick={() => void audit.refetch()}>
                Retry activity
              </Button>
            </div>
          ) : (
            <>
              {audit.data.pages.every((page) => !page.data.length) ? (
                <p>No organization changes have been recorded.</p>
              ) : (
                <ol className="audit-list">
                  {audit.data.pages
                    .flatMap((page) => page.data)
                    .map((item) => (
                      <li key={item.id}>
                        <span>{item.action.replace(/[._]/g, " ")}</span>
                        <time dateTime={item.created_at}>{date(item.created_at)}</time>
                      </li>
                    ))}
                </ol>
              )}
              {audit.hasNextPage && (
                <Button
                  variant="outline"
                  disabled={audit.isFetchingNextPage}
                  onClick={() => void audit.fetchNextPage()}
                >
                  {audit.isFetchingNextPage ? "Loading..." : "Load more activity"}
                </Button>
              )}
            </>
          )}
        </section>
      )}
      {owner && (
        <section className="settings-section" aria-labelledby="deactivate-title">
          <div className="settings-section-heading">
            <h2 id="deactivate-title">Deactivate organization</h2>
            <p>Members will lose access to this organization. Its data is retained.</p>
          </div>
          {!deleting ? (
            <Button variant="outline" onClick={() => setDeleting(true)}>
              Deactivate organization
            </Button>
          ) : (
            <form
              className="account-form"
              method="post"
              onSubmit={(event) => {
                event.preventDefault();
                const form = new FormData(event.currentTarget);
                if (form.get("confirmation") !== organization.slug) {
                  setError({
                    section: "deactivate",
                    message: "Enter the exact organization slug to confirm.",
                  });
                  return;
                }
                void change("deactivate", async () => {
                  await api(base, { method: "DELETE" });
                  await client.cancelQueries({ queryKey: ["organization", organization.id] });
                  client.removeQueries({ queryKey: ["organization", organization.id] });
                  router.replace("/app");
                });
              }}
              aria-busy={busy === "deactivate"}
            >
              <Field
                label={`Type ${organization.slug} to confirm`}
                name="confirmation"
                autoComplete="off"
                required
                disabled={!!busy}
              />
              {message("deactivate")}
              <div className="form-actions">
                <Button variant="outline" type="submit" disabled={!!busy}>
                  {busy === "deactivate" ? "Deactivating..." : "Confirm deactivation"}
                </Button>
                <Button
                  variant="ghost"
                  type="button"
                  onClick={() => setDeleting(false)}
                  disabled={!!busy}
                >
                  Cancel
                </Button>
              </div>
            </form>
          )}
        </section>
      )}
    </div>
  );
}
