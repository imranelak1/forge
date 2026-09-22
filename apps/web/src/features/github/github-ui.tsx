"use client";

import { AlertCircle, CheckCircle2, CircleDashed, Clock3, PauseCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FormMessage } from "@/features/auth/form-parts";
import { errorMessage } from "@/lib/auth-client";
import { formatDate, type SyncRun } from "./types";

const labels = {
  queued: "Queued",
  running: "Syncing",
  retrying: "Retry scheduled",
  succeeded: "Up to date",
  partial: "Partial import",
  failed: "Sync failed",
  canceled: "Stopped",
};
export function SyncState({ run }: { run: SyncRun | null }) {
  if (!run)
    return (
      <span className="github-state state-neutral">
        <CircleDashed size={14} aria-hidden="true" />
        Not synced
      </span>
    );
  const Icon =
    run.status === "succeeded"
      ? CheckCircle2
      : ["failed", "partial"].includes(run.status)
        ? AlertCircle
        : run.status === "canceled"
          ? PauseCircle
          : Clock3;
  const color =
    run.status === "succeeded"
      ? "state-success"
      : ["failed", "partial", "retrying"].includes(run.status)
        ? "state-warning"
        : "state-neutral";
  return (
    <span className={`github-state ${color}`}>
      <Icon size={14} aria-hidden="true" />
      {labels[run.status]}
    </span>
  );
}

export function SyncDetails({ run }: { run: SyncRun }) {
  return (
    <div className="sync-details">
      <p>
        {run.kind === "catalog"
          ? `${run.repositories_processed.toLocaleString()} repositories found`
          : `${run.pull_requests_processed.toLocaleString()} pull requests and ${run.commits_processed.toLocaleString()} commits processed`}
      </p>
      {["running", "queued", "retrying"].includes(run.status) && (
        <p>Stage: {run.stage.replaceAll("_", " ")}</p>
      )}
      {run.next_retry_at && run.status === "retrying" && (
        <p>
          Next attempt <time dateTime={run.next_retry_at}>{formatDate(run.next_retry_at)}</time>.
        </p>
      )}
      {run.error_code && (
        <p className="sync-problem">
          {run.status === "retrying"
            ? "GitHub temporarily delayed this sync. Forge will retry automatically."
            : run.status === "partial"
              ? "Some history could not be imported. Retry the sync to continue."
              : "Sync could not finish. Check GitHub access in Integrations, then retry."}
        </p>
      )}
      {run.kind !== "catalog" && (
        <p>
          Import window: <time dateTime={run.since}>{formatDate(run.since)}</time> to{" "}
          <time dateTime={run.until}>{formatDate(run.until)}</time>.
        </p>
      )}
    </div>
  );
}

export function QueryFailure({
  error,
  retry,
  label,
}: {
  error: unknown;
  retry: () => void;
  label: string;
}) {
  return (
    <div className="github-recovery">
      <FormMessage error={errorMessage(error)} />
      <Button variant="outline" onClick={retry}>
        {label}
      </Button>
    </div>
  );
}
