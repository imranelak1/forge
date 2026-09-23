# Upload JUnit reports

Phase 6 accepts direct XML uploads and shows stored suites, executions, test history, pass rates and potential-flakiness evidence. It does not download GitHub artifacts. A passing workflow without an uploaded report does not establish passing tests.

## Prepare the repository and token

1. Connect the [GitHub App](github-setup.md), select a repository and enable its Actions read permission. The organization, installation and repository must remain active and authorized. Demo or disconnected repositories cannot receive upload tokens.
2. Synchronize the exact workflow run and attempt that produced the report. Phase 6 requires this parent to be already imported. The provider run ID is the numeric GitHub ID, while Forge's report response contains the internal workflow UUID. Reruns require their own positive attempt number.
3. As a verified owner/admin, open the repository's test settings and create an upload token, or call `POST /api/v1/organizations/{organization}/repositories/{repository}/service-tokens` with `{ "name": "CI reports", "expires_in_days": 30 }` using normal session/CSRF protection. Expiry is 1–90 days; at most 20 active tokens are allowed per repository.
4. Copy the credential once into your CI secret store. Forge retains its hash and a display prefix; it cannot reveal the credential again. The token only grants `test_reports:write` for that repository. It cannot read test evidence, manage settings or authenticate a human session.

Do not put the credential into source files, report XML, command output or shell tracing. The selected XML can contain source-authored names and failure messages; restrict who can upload it and who belongs to the organization.

## Send uncompressed XML

Use the backend/API origin directly, such as `http://localhost:8000` locally or your configured HTTPS API endpoint. The Next.js browser proxy does not forward XML uploads. A remote CI runner cannot reach your machine's localhost; deploying a reachable API remains a separate operational step.

The existing local GitHub webhook tunnel/helper accepts only GitHub webhook deliveries. Its URL cannot accept JUnit uploads, and GitHub sign-in does not grant a CI credential. Local `curl` can use port 8000; hosted CI needs separately configured HTTPS API ingress or authorized service connectivity. Phase 6 does not provision that external infrastructure.

Set the following environment variables in your shell or CI configuration: `FORGE_API_ORIGIN`, `FORGE_ORGANIZATION` and `FORGE_REPOSITORY` (Forge UUIDs), `FORGE_WORKFLOW_RUN_ID` (GitHub numeric ID), `FORGE_RUN_ATTEMPT`, `FORGE_WORKFLOW_HEAD_SHA` (the full lowercase head SHA stored for that attempt) and the secret `FORGE_CI_TOKEN`.

```sh
curl --fail-with-body --request POST \
  --header "Authorization: Bearer ${FORGE_CI_TOKEN}" \
  --header "Content-Type: application/xml" \
  --data-binary @report.xml \
  "${FORGE_API_ORIGIN}/api/v1/organizations/${FORGE_ORGANIZATION}/repositories/${FORGE_REPOSITORY}/test-reports?workflow_run_id=${FORGE_WORKFLOW_RUN_ID}&run_attempt=${FORGE_RUN_ATTEMPT}&report_key=unit-tests&shard=default&framework=junit&environment=ci&commit_sha=${FORGE_WORKFLOW_HEAD_SHA}"
```

This example uses fixed URL-safe report metadata. URL-encode custom query values. Keep `report_key` stable for the same report producer and use a distinct `shard` for each independently produced shard. `framework` and optional `environment` participate in evidence interpretation. The supplied SHA is optional but, when supplied, must match the imported workflow. In pull-request workflows, a runner's checkout/merge SHA may differ from the recorded head SHA; do not substitute it without checking.

Success returns HTTP 202 with a receipt ID, status and `duplicate` flag. Parsing runs asynchronously. Inspect **Test runs** in the signed-in workspace, or use authenticated `GET /api/v1/organizations/{organization}/test-runs/{receipt}`. Machine upload credentials intentionally cannot poll read APIs. A workflow can be imported while still running; its reports remain outside completion-based metrics until completion evidence is available.

If the parent is not imported, `workflow_not_imported` returns 422. Synchronize it through Forge, retain the report in your own CI storage and resend when that exact attempt is available. Forge does not hold an unverified report waiting for a future parent. This ordering is an explicit first-version limitation.

## Replay, corrections and revocation

Resending the same bytes for the same repository/workflow attempt/report key/shard returns the original receipt without duplicate cases. Changing framework or environment on an identical replay returns `report_metadata_conflict`.

Changed report content requires `supersedes=<current-receipt-UUID>` on the same upload URL. Only successful processing marks the previous receipt superseded and removes its executions from current metrics. Earlier reports remain inspectable. An in-progress correction must finish before another correction is accepted; a failed correction does not replace a valid report.

Revoke a token in repository test settings or with `DELETE /api/v1/organizations/{organization}/service-tokens/{token}` using a verified owner/admin session and CSRF. Revocation blocks new uploads and cancels pending ingestion; retained completed evidence is still tenant-readable. A canceled report is represented as `status=failed` with a fixed reason such as `token_revoked`, `ingestion_canceled` or `payload_expired`, not as a successful zero-test report.

## Supported evidence and limits

| Input or behavior | Phase 6 contract                                                                                                                                                                   |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Body              | `application/xml` or `text/xml`, direct uncompressed XML, at most 10 MiB; 15-second upload read deadline                                                                           |
| Collections       | `testsuite` and `testsuites` roots, nested suites, at most 100,000 normalized executions including explicit retries                                                                |
| Structural limits | Depth 64, 10,000 suites, 500,000 XML elements, at most 64 attributes and 65,536 attribute characters per element                                                                   |
| XML security      | DTD/custom/external entities rejected, no network/file resolution; archives, multipart and compressed bodies unsupported                                                           |
| Identity          | Framework/file/class/name/explicit parameters; full parameterized names preserved; suite-path fallback when file/class absent                                                      |
| Duplicate names   | Separate ambiguous occurrences, never silently collapsed into retries or used for historical flakiness attribution                                                                 |
| Retries           | Surefire `flakyFailure`, `flakyError`, `rerunFailure`, `rerunError`; other retry metadata is flagged, not guessed                                                                  |
| Outcomes          | Passed, failed, error and skipped; contradictory outcome evidence generates warnings; unsupported attribute-only outcome dialects are rejected                                     |
| Durations         | Nonnegative finite seconds, at most 365 days; invalid values become null with a warning                                                                                            |
| Messages          | At most 2,048 characters per execution; failure text is stored as untrusted tenant evidence, while stdout/stderr/properties are discarded                                          |
| Identity text     | At most 2,048 characters per identity field; oversized fields are rejected rather than truncated into colliding identities                                                         |
| Queue limits      | At most 20 pending reports per repository and 120 new uploads per token per 15-minute window; exact replays do not add work                                                        |
| Retention         | Pending XML encrypted with a key derived from the application authentication secret, cleared on terminal handling, with one-day expiry cleanup; normalized evidence remains stored |

Parsing reports count discrepancies, missing/fallback identities, ambiguous duplicates, unsupported elements/retry metadata and invalid duration evidence as fixed warning codes. A report can complete with warnings. Its declared counts are compared with final leaf cases, not nested suite totals or every retry execution. Empty reports are visible and do not produce a nonempty passing sample. [Parser decision and dialect references](adr/014-test-intelligence.md)

## Understand the results

Pass rate uses final executions in accepted, non-superseded reports for the latest completed attempt: `passed / (passed + failed + error)`. Skipped counts are separate. Earlier retry attempts and their messages remain in report details. Workflow timing may be a labeled last-job-completion proxy; unknown completion is excluded from timed metrics.

Potential-flakiness evidence defaults to a 14-day window, at least 10 final observations, failure fraction 0.05–0.95 and at least two pass/fail changes. Grouping preserves repository, test identity, branch, environment, report key and shard. Ambiguous identities are excluded; fallback identity or missing branch/environment lowers confidence. Verified owners/admins may change the audited, versioned policy. The label means “investigate this evidence,” not a proven flaky defect.

The unstored default policy is version 1. The first custom policy is version 2, and later changes increment it; evidence responses identify the policy used to classify their retained observations.

Coverage describes uploaded reports only. Forge has no expected-shard manifest, cannot assume every CI job runs tests and cannot treat a missing report as zero failures. See [metric definitions](analytics.md) for cohort and source limitations.
