"use client";
import Link from "next/link";
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/auth-provider";
import { api, errorMessage } from "@/lib/auth-client";
import type { Organization } from "@/lib/auth-types";
import { canManage, type Repository } from "@/features/github/types";
import {
  AnalyticsError,
  AnalyticsLoading,
  DemoNotice,
  PageMore,
  RefreshData,
  useEvidencePage,
} from "@/features/analytics/analytics-ui";
import { utcDate, validId } from "@/features/analytics/types";
import type { CIToken, RepositoryTestPolicy } from "./types";
import { TestFiltersForm, testKeys, useTestPage } from "./tests-ui";

export function TestSettingsPage() {
  const { organization, identity } = useAuth(),
    search = useSearchParams();
  if (!organization) return null;
  const value = search.get("repository"),
    repository = value && validId(value) ? value : undefined;
  return (
    <SettingsContent
      key={`${organization.id}:${repository}`}
      organization={organization}
      repository={repository}
      verified={!!identity?.user.email_verified}
    />
  );
}
function SettingsContent({
  organization,
  repository,
  verified,
}: {
  organization: Organization;
  repository?: string;
  verified: boolean;
}) {
  const router = useRouter(),
    manager = canManage(organization.role) && verified;
  return (
    <div className="analytics-content">
      <Link
        className="analytics-back text-link"
        href={`/app/tests${repository ? `?repository=${repository}` : ""}`}
      >
        Test intelligence
      </Link>
      <div className="page-heading">
        <div>
          <h1>Report uploads and policy</h1>
          <p>
            {organization.name} · Repository-scoped CI credentials and potential-flakiness
            thresholds.
          </p>
        </div>
        <RefreshData organization={organization.id} />
      </div>
      <DemoNotice demo={organization.is_demo} />
      <TestFiltersForm
        organization={organization.id}
        kind="settings"
        filters={{ repository }}
        apply={(next) =>
          router.replace(
            `/app/tests/settings${next.repository ? `?repository=${next.repository}` : ""}`,
          )
        }
      />
      {!manager && (
        <p className="analytics-note">
          A verified organization owner or admin can change policy and manage upload tokens. All
          members can inspect the repository settings.
        </p>
      )}
      {repository ? (
        <>
          <PolicySettings
            organization={organization.id}
            repository={repository}
            manager={manager}
          />
          <TokenSettings organization={organization.id} repository={repository} manager={manager} />
        </>
      ) : (
        <p className="analytics-empty">
          Choose a repository to inspect its policy and CI upload tokens.
        </p>
      )}
    </div>
  );
}
function PolicySettings({
  organization,
  repository,
  manager,
}: {
  organization: string;
  repository: string;
  manager: boolean;
}) {
  const [saved, setSaved] = useState(false);
  const query = useQuery({
    queryKey: [...testKeys(organization), "policy", repository],
    queryFn: ({ signal }) =>
      api<RepositoryTestPolicy>(
        `/organizations/${organization}/repositories/${repository}/test-policy`,
        { signal },
      ),
    retry: false,
  });
  return (
    <section className="analytics-section">
      <h2>Potential-flakiness policy</h2>
      <p className="analytics-note">
        Thresholds describe evidence worth investigating, not a diagnosis. Outcomes are evaluated
        separately by test, branch and environment. Excluded branches are exact names.
      </p>
      {query.isPending ? (
        <AnalyticsLoading label="Loading test policy" />
      ) : query.isError ? (
        <AnalyticsError error={query.error} retry={query.refetch} />
      ) : (
        <PolicyForm
          key={query.data.version ?? query.data.updated_at ?? "default"}
          organization={organization}
          repository={repository}
          policy={query.data}
          manager={manager}
          onSaved={() => setSaved(true)}
          onEdit={() => setSaved(false)}
        />
      )}
      {saved && (
        <p className="form-success" role="status">
          Test policy saved.
        </p>
      )}
    </section>
  );
}
function PolicyForm({
  organization,
  repository,
  policy,
  manager,
  onSaved,
  onEdit,
}: {
  organization: string;
  repository: string;
  policy: RepositoryTestPolicy;
  manager: boolean;
  onSaved: () => void;
  onEdit: () => void;
}) {
  const client = useQueryClient(),
    [values, setValues] = useState(policy),
    [branches, setBranches] = useState(policy.excluded_branches.join("\n")),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const change = (key: keyof RepositoryTestPolicy, value: number) => {
    onEdit();
    setValues({ ...values, [key]: value });
  };
  const fields: [keyof RepositoryTestPolicy, string, number, number, number][] = [
    ["window_days", "Lookback days", 2, 90, 1],
    ["min_executions", "Minimum executions", 2, 1000, 1],
    ["failure_rate_low", "Minimum failure fraction", 0.001, 0.999, 0.001],
    ["failure_rate_high", "Maximum failure fraction", 0.001, 0.999, 0.001],
    ["min_transitions", "Minimum outcome flips", 1, 100, 1],
  ];
  return (
    <form
      className="tests-policy-form"
      onSubmit={async (event) => {
        event.preventDefault();
        setError("");
        onEdit();
        const excluded = branches
          .split(/\r?\n/)
          .map((s) => s.trim())
          .filter(Boolean);
        if (values.failure_rate_low >= values.failure_rate_high) {
          setError("Maximum failure fraction must be greater than the minimum.");
          return;
        }
        if (excluded.length > 50 || excluded.some((s) => s.length > 255)) {
          setError("Use at most 50 branch names, each up to 255 characters.");
          return;
        }
        setBusy(true);
        try {
          await api(`/organizations/${organization}/repositories/${repository}/test-policy`, {
            method: "PATCH",
            body: {
              window_days: values.window_days,
              min_executions: values.min_executions,
              failure_rate_low: values.failure_rate_low,
              failure_rate_high: values.failure_rate_high,
              min_transitions: values.min_transitions,
              excluded_branches: excluded,
            },
          });
          onSaved();
          await client.invalidateQueries({ queryKey: testKeys(organization) });
        } catch (e) {
          setError(errorMessage(e));
        } finally {
          setBusy(false);
        }
      }}
    >
      <div className="tests-policy-fields">
        {fields.map(([key, label, min, max, step]) => (
          <label key={key}>
            {label}
            <input
              type="number"
              required
              min={min}
              max={max}
              step={step}
              value={values[key] as number}
              disabled={!manager || busy}
              onChange={(e) => change(key, e.target.valueAsNumber)}
            />
          </label>
        ))}
        <label className="tests-branches">
          Excluded branches
          <textarea
            rows={3}
            value={branches}
            disabled={!manager || busy}
            onChange={(e) => {
              setBranches(e.target.value);
              onEdit();
            }}
            placeholder="One exact branch name per line"
            maxLength={12800}
          />
        </label>
      </div>
      <p className="analytics-note">
        Failure fractions use values between 0 and 1; 0.05 means 5%. Current policy updated:{" "}
        {utcDate(policy.updated_at)}.
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <Button type="submit" variant="outline" disabled={!manager || busy}>
        {busy ? "Saving policy…" : "Save test policy"}
      </Button>
    </form>
  );
}
function TokenSettings({
  organization,
  repository,
  manager,
}: {
  organization: string;
  repository: string;
  manager: boolean;
}) {
  const client = useQueryClient(),
    tokens = useTestPage<CIToken>(organization, `repositories/${repository}/service-tokens`),
    repositories = useEvidencePage<Repository>(organization, "repositories");
  const items = tokens.data?.pages.flatMap((p) => p.items) ?? [],
    source = repositories.data?.pages.flatMap((p) => p.items).find((r) => r.id === repository);
  const unavailable = !!source && (source.is_demo || !source.selected || !source.authorized),
    [name, setName] = useState(""),
    [days, setDays] = useState(30),
    [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [issued, setIssued] = useState<{ id: string; credential: string } | null>(null),
    [confirm, setConfirm] = useState<string | null>(null);
  const enabled = manager && !unavailable;
  async function revoke(token: CIToken) {
    setBusy(token.id);
    setError("");
    setNotice("");
    try {
      await api(`/organizations/${organization}/service-tokens/${token.id}`, { method: "DELETE" });
      if (issued?.id === token.id) setIssued(null);
      setConfirm(null);
      await client.invalidateQueries({
        queryKey: [...testKeys(organization), `repositories/${repository}/service-tokens`],
      });
      setNotice(`Revoked ${token.name}. Pending reports using this token may be canceled.`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy("");
    }
  }
  return (
    <section className="analytics-section">
      <h2>CI upload tokens</h2>
      <p className="analytics-note">
        Tokens can only upload test reports to this repository. They cannot read reports or act as a
        member. Store a new credential in your CI secret store; Forge displays it once.
      </p>
      <p className="analytics-note">
        Upload directly to the backend API after its workflow attempt has been imported.{" "}
        <Link className="text-link" href="/guide#test-reports">
          Read the JUnit upload guide
        </Link>
        .
      </p>
      {unavailable && (
        <p className="analytics-note">
          {source?.is_demo
            ? "Generated demo repositories cannot receive live uploads."
            : "New tokens require a selected repository with current GitHub access."}{" "}
          You can still inspect the policy and retained token history.
        </p>
      )}
      {issued && (
        <div className="tests-issued" role="region" aria-label="New CI upload credential">
          <h3>Copy this credential now</h3>
          <p className="analytics-note">
            It will not be shown again after you dismiss it or leave this page.
          </p>
          <label htmlFor="issued-ci-credential">CI upload credential</label>
          <textarea
            id="issued-ci-credential"
            readOnly
            autoComplete="off"
            spellCheck={false}
            rows={3}
            value={issued.credential}
          />
          <div className="analytics-filter-actions">
            <Button
              type="button"
              variant="outline"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(issued.credential);
                  setNotice("Credential copied. Store it in your CI secret store.");
                } catch {
                  setError("Clipboard access failed. Select and copy the credential above.");
                }
              }}
            >
              Copy credential
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setIssued(null);
                setNotice("Credential dismissed. Create a new token if it was not saved.");
              }}
            >
              Dismiss credential
            </Button>
          </div>
        </div>
      )}
      <form
        className="tests-token-form"
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy("create");
          setError("");
          setNotice("");
          try {
            const result = await api<{ token: CIToken; credential: string }>(
              `/organizations/${organization}/repositories/${repository}/service-tokens`,
              { method: "POST", body: { name: name.trim(), expires_in_days: days } },
            );
            setIssued({ id: result.token.id, credential: result.credential });
            setName("");
            await client.invalidateQueries({
              queryKey: [...testKeys(organization), `repositories/${repository}/service-tokens`],
            });
          } catch (e) {
            setError(errorMessage(e));
          } finally {
            setBusy("");
          }
        }}
      >
        <label>
          Token name
          <input
            required
            minLength={1}
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={!enabled || !!busy || !!issued}
            placeholder="CI report uploader"
            autoComplete="off"
          />
        </label>
        <label>
          Expires in days
          <input
            type="number"
            min={1}
            max={90}
            step={1}
            required
            value={days}
            onChange={(e) => setDays(e.target.valueAsNumber)}
            disabled={!enabled || !!busy || !!issued}
          />
        </label>
        <Button
          type="submit"
          variant="outline"
          disabled={!enabled || !!busy || !!issued || !name.trim()}
        >
          {busy === "create" ? "Issuing token…" : "Issue upload token"}
        </Button>
      </form>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="form-success" role="status">
          {notice}
        </p>
      )}
      {tokens.isPending ? (
        <AnalyticsLoading label="Loading upload tokens" />
      ) : tokens.isError && !items.length ? (
        <AnalyticsError error={tokens.error} retry={tokens.refetch} />
      ) : (
        <>
          {items.length ? (
            <div className="analytics-table-wrap">
              <table className="analytics-table">
                <thead>
                  <tr>
                    <th scope="col">Token</th>
                    <th scope="col">Status</th>
                    <th scope="col">Usage</th>
                    <th scope="col">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((token) => {
                    const expired = Date.parse(token.expires_at) <= tokens.dataUpdatedAt;
                    return (
                      <tr key={token.id}>
                        <th scope="row">
                          {token.name}
                          <span className="analytics-meta mono">{token.token_prefix}…</span>
                          <span className="analytics-meta">{token.scope}</span>
                        </th>
                        <td data-label="Status">
                          {token.revoked_at ? "Revoked" : expired ? "Expired" : "Active"}
                          <span className="analytics-meta">
                            Expires {utcDate(token.expires_at)}
                          </span>
                        </td>
                        <td data-label="Usage">
                          Last used {utcDate(token.last_used_at)}
                          <span className="analytics-meta">
                            Created {utcDate(token.created_at)}
                          </span>
                        </td>
                        <td data-label="Action">
                          {token.revoked_at ? (
                            "Revoked"
                          ) : confirm === token.id ? (
                            <div className="tests-confirm">
                              <p>Revoke {token.name}?</p>
                              <Button
                                variant="outline"
                                disabled={!!busy || !manager}
                                onClick={() => void revoke(token)}
                              >
                                {busy === token.id ? "Revoking…" : "Confirm revoke"}
                              </Button>
                              <button
                                className="text-link"
                                disabled={!!busy}
                                onClick={() => setConfirm(null)}
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <Button
                              variant="outline"
                              disabled={!manager || !!busy}
                              onClick={() => setConfirm(token.id)}
                            >
                              Revoke {token.name}
                            </Button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="analytics-empty">
              No CI upload tokens have been issued for this repository.
            </p>
          )}
          <PageMore result={tokens} count={items.length} />
        </>
      )}
    </section>
  );
}
