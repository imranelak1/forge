"use client";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/features/auth/auth-provider";
import {
  AnalyticsError,
  AnalyticsLoading,
  DemoNotice,
  RefreshData,
} from "@/features/analytics/analytics-ui";
import { validId } from "@/features/analytics/types";
import { api, errorMessage } from "@/lib/auth-client";
import { canManage } from "@/features/github/types";
import type { Organization } from "@/lib/auth-types";
import { DeliveryFiltersForm } from "./delivery-ui";
import type { EnvironmentPolicy } from "./types";

export function EnvironmentPage() {
  const { organization, identity } = useAuth();
  const search = useSearchParams();
  if (!organization) return null;
  const repository = search.get("repository");
  return (
    <EnvironmentContent
      key={`${organization.id}:${repository}`}
      organization={organization}
      repository={repository && validId(repository) ? repository : undefined}
      verified={!!identity?.user.email_verified}
    />
  );
}
function EnvironmentContent({
  organization,
  repository,
  verified,
}: {
  organization: Organization;
  repository?: string;
  verified: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const client = useQueryClient();
  const manager = canManage(organization.role) && verified;
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState({ error: "", success: "" });
  const query = useQuery({
    queryKey: [
      "organization",
      organization.id,
      "analytics",
      "delivery",
      "environments",
      repository,
    ],
    enabled: !!repository,
    queryFn: ({ signal }) =>
      api<{ items: EnvironmentPolicy[] }>(
        `/organizations/${organization.id}/repositories/${repository}/environments`,
        { signal },
      ),
    retry: false,
  });
  async function save(environment: string, classification: EnvironmentPolicy["override"]) {
    setBusy(environment);
    setNotice({ error: "", success: "" });
    try {
      await api(
        `/organizations/${organization.id}/repositories/${repository}/environments/classification`,
        { method: "PUT", body: { environment, classification } },
      );
      await client.invalidateQueries({
        queryKey: ["organization", organization.id, "analytics", "delivery"],
      });
      setNotice({
        error: "",
        success: `Classification saved for ${environment}. Analytics now use the stored policy.`,
      });
    } catch (error) {
      setNotice({ error: errorMessage(error), success: "" });
    } finally {
      setBusy(null);
    }
  }
  return (
    <div className="analytics-content">
      <Link className="analytics-back text-link" href="/app/deployments">
        Deployments
      </Link>
      <div className="page-heading">
        <div>
          <h1>Environment classification</h1>
          <p>
            {organization.name} · Explicit production policy for imported deployment environments.
          </p>
        </div>
      </div>
      <DemoNotice demo={organization.is_demo} />
      <div className="analytics-refresh">
        <RefreshData organization={organization.id} />
      </div>
      <p className="analytics-note">
        A Forge override applies to this repository and exact environment name. Removing it restores
        each deployment’s own provider flag. Missing flags remain unknown; names such as
        “production” do not classify deployments. These changes affect Forge analytics and do not
        change GitHub.
      </p>
      <DeliveryFiltersForm
        organization={organization.id}
        kind="environments"
        filters={{ repository }}
        apply={(next) =>
          router.replace(`${pathname}${next.repository ? `?repository=${next.repository}` : ""}`)
        }
      />
      {!manager && (
        <p className="analytics-note">
          A verified organization owner or admin can change classification. All members can inspect
          the policy.
        </p>
      )}
      {notice.error && (
        <p className="form-error" role="alert">
          {notice.error}
        </p>
      )}
      {notice.success && (
        <p className="form-success" role="status">
          {notice.success}
        </p>
      )}
      {!repository ? (
        <p className="analytics-empty">
          Choose a repository to inspect its observed deployment environments.
        </p>
      ) : query.isPending ? (
        <AnalyticsLoading label="Loading environment policy" />
      ) : query.isError ? (
        <AnalyticsError error={query.error} retry={query.refetch} />
      ) : query.data?.items.length ? (
        <>
          <p className="analytics-note">
            Counts cover all retained deployment records, independent of the metric date window.
          </p>
          <div className="delivery-environments">
            {query.data.items.map((item) => (
              <EnvironmentRow
                key={`${item.environment}:${item.override}`}
                item={item}
                enabled={manager && !busy}
                saving={busy === item.environment}
                save={save}
              />
            ))}
          </div>
        </>
      ) : (
        <p className="analytics-empty">
          No deployment environments have been imported for this repository. Check Deployments
          source coverage and repository sync progress.
        </p>
      )}
    </div>
  );
}
function EnvironmentRow({
  item,
  enabled,
  saving,
  save,
}: {
  item: EnvironmentPolicy;
  enabled: boolean;
  saving: boolean;
  save: (environment: string, classification: EnvironmentPolicy["override"]) => Promise<void>;
}) {
  const [value, setValue] = useState(item.override ?? "provider");
  return (
    <form
      className="delivery-environment"
      onSubmit={(event) => {
        event.preventDefault();
        void save(
          item.environment,
          value === "provider" ? null : (value as EnvironmentPolicy["override"]),
        );
      }}
    >
      <div>
        <h2>{item.environment}</h2>
        <p>
          {item.deployment_count} retained deployments · {item.production_count} production ·{" "}
          {item.nonproduction_count} non-production · {item.unknown_count} unknown
        </p>
      </div>
      <label>
        Classification for {item.environment}
        <select
          aria-label={`Classification for ${item.environment}`}
          value={value}
          disabled={!enabled}
          onChange={(event) => setValue(event.target.value)}
        >
          <option value="provider">Use each deployment’s provider flag</option>
          <option value="production">Production override</option>
          <option value="nonproduction">Non-production override</option>
        </select>
      </label>
      <Button disabled={!enabled || value === (item.override ?? "provider")}>
        {saving ? "Saving…" : "Save classification"}
      </Button>
    </form>
  );
}
