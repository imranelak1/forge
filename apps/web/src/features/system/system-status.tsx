"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ArrowRight, CheckCircle2, CircleDashed, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { fetchSystemHealth, type CheckState } from "@/lib/health";

function State({ value, loading }: { value?: CheckState; loading: boolean }) {
  if (loading)
    return (
      <span className="state-neutral">
        <CircleDashed size={14} aria-hidden="true" />
        Checking
      </span>
    );
  if (value === "healthy")
    return (
      <span className="state-success">
        <CheckCircle2 size={14} aria-hidden="true" />
        Healthy
      </span>
    );
  if (value === "unavailable")
    return (
      <span className="state-warning">
        <AlertCircle size={14} aria-hidden="true" />
        Unavailable
      </span>
    );
  if (value === "pending")
    return (
      <span className="state-warning">
        <AlertCircle size={14} aria-hidden="true" />
        Migration required
      </span>
    );
  return (
    <span className="state-neutral">
      <CircleDashed size={14} aria-hidden="true" />
      Not verified
    </span>
  );
}

export function SystemStatus({ compact = false }: { compact?: boolean }) {
  const query = useQuery({
    queryKey: ["installation", "health"],
    queryFn: ({ signal }) => fetchSystemHealth(signal),
    refetchInterval: 30_000,
    retry: false,
  });
  const checks = [
    {
      key: "api" as const,
      label: "API",
      detail: "Checks whether the application service responds to requests.",
    },
    {
      key: "database" as const,
      label: "PostgreSQL",
      detail: "Checks database connectivity using the API’s runtime credentials.",
    },
    {
      key: "migrations" as const,
      label: "Schema",
      detail: "Checks whether applied migrations match this build.",
    },
  ];
  const healthy =
    query.data?.api === "healthy" &&
    query.data?.database === "healthy" &&
    query.data?.migrations === "healthy";
  if (compact) {
    return (
      <section className="health-strip" aria-label="Installation health">
        <div className="health-strip-checks" aria-live="polite">
          {checks.map((check) => (
            <div key={check.key}>
              <span>{check.label}</span>
              <State value={query.data?.[check.key]} loading={query.isPending} />
            </div>
          ))}
        </div>
        <Link href="/system" className="text-link">
          System status
          <ArrowRight size={14} aria-hidden="true" />
        </Link>
      </section>
    );
  }
  return (
    <section aria-label="Service health" className="system-section">
      <div className="section-toolbar">
        <div>
          <h2>Service checks</h2>
          <p>Checked every 30 seconds while this page is open.</p>
        </div>
        <Button variant="outline" onClick={() => void query.refetch()} disabled={query.isFetching}>
          <RefreshCw size={16} aria-hidden="true" />
          {query.isFetching ? "Checking…" : "Run checks"}
        </Button>
      </div>
      <div className="service-list" aria-live="polite" aria-busy={query.isFetching}>
        {checks.map((check) => (
          <div className="service-row" key={check.key}>
            <div>
              <h3>{check.label}</h3>
              <p>{check.detail}</p>
            </div>
            <State value={query.data?.[check.key]} loading={query.isPending} />
          </div>
        ))}
      </div>
      <div className="check-footer" aria-live="polite">
        <span>
          {query.data
            ? `Last checked at ${new Date(query.data.checkedAt).toLocaleTimeString()}`
            : "Waiting for the first check."}
        </span>
        <span>Responses are never cached.</span>
      </div>
      {!query.isPending && !healthy && (
        <div className="recovery-message" role="status">
          <AlertCircle size={18} aria-hidden="true" />
          <div>
            <h3>Some services need attention</h3>
            <p>
              Check your running containers and database configuration, then run the checks again.{" "}
              <Link href="/guide#troubleshooting">Open troubleshooting</Link>.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}
