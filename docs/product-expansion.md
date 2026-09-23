# Planned product expansion

Status: six product directions accepted for planning; none is implemented or enabled by this document. Phases 0–13 retain their order and approval gates in the [roadmap](roadmap.md). **Phase 6, test intelligence, is the current milestone; Phase 7 Sentry integration is next after its gate.** The milestones below identify prerequisites and possible small pilots, not permission to start them, change integration scopes, publish customer data or send messages.

Forge can become useful to open-source users and individual developers before they need a team workspace. Start with evidence people can inspect and share, then offer personal reflection and small-project monitoring. A public repository page is a discovery surface and a useful product in its own right; team adoption is optional.

## Priority and dependency milestones

| Priority | Planned track                | Smallest useful milestone                                                                                | Prerequisites and gate                                                                                                                                                                                     |
| -------- | ---------------------------- | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1        | Public repository health     | A shareable page showing PR wait and CI outcomes with source coverage                                    | Phase 4 PR evidence, Phase 5 CI evidence; Phase 6 for test signals. Propose the public-data pilot after Phase 6, with its own scope decision.                                                              |
| 1        | Contributor guidance         | A first-contribution guide alongside the same repository page                                            | Phase 4 history plus reliable contributor identity, longer-history coverage and a maintainer-policy source. Shares the public-data pilot.                                                                  |
| 1        | Free maintainer tools        | Private drafts for a stale-PR digest and release notes; potential-flakiness evidence where reports exist | Phases 4–6 for evidence; Phase 9 for any enabled outbound nudges. Read-only drafts can be proposed with the public-data pilot.                                                                             |
| 2        | Personal engineering profile | A private year-in-review for one consenting individual                                                   | Phases 2–5, an independently reviewed personal-data authorization boundary and sufficient annual history. Propose a separate pilot after the public-data foundation.                                       |
| 3        | Free side-project monitoring | A post-deployment watch for one or two connected projects                                                | Phases 5, 7, 8 and 9 for deployments, errors, explicit associations and alerts. Propose after Phase 9.                                                                                                     |
| 4        | Opt-in public benchmarks     | A few adequately sized language/team-size cohorts                                                        | Stable Phase 4–6 metric definitions, explicit contributor consent, sufficient adoption and aggregation/privacy validation. Phase 10 may help recomputation; it is not a reason to add orchestration early. |

Public production launches additionally depend on Phase 13 hosting, abuse controls, operational budgets and deletion runbooks. Phases 11 and 12 keep their measured-need gates; none of these tracks requires Kafka or ClickHouse by default. At each existing gate, choose whether to scope a pilot separately. Do not silently add these features to Phase 6 or reorder the approved phases.

## Shared data and privacy architecture

- **Separate public and tenant data.** A shared public catalog has its own records, source identifiers, refresh jobs, access rules and serving views. Fetch permitted public provider metadata through that path. Never make a tenant row public by removing its organization filter, and never use a public endpoint to join private tenant facts. Cross-linking the same provider repository is an identity mapping, not a grant to read tenant data.
- **Treat publication as a separate purpose.** A public repository or an installed GitHub App does not authorize publishing uploaded JUnit reports, private workflows, personal profiles or benchmark contributions. A maintainer must explicitly choose any additional public evidence. Store that publication decision independently from provider installation and benchmark consent.
- **Preserve coverage.** Display the observed window, sample counts, excluded records, last successful refresh and available sources. Public repository visibility does not establish that workflow jobs, artifacts or test reports are available. Missing reports cannot mean zero failures; absence of a review cannot prove a maintainer ignored a contributor. Never replace unknown values with healthy scores.
- **Make revocation effective.** Recheck source visibility and entitlement during refresh. On loss of access or a public-to-private change, stop collection and withdraw the public page, derived previews and cache entries. Design purge and backup-expiry rules before the pilot; this plan does not claim those mechanisms exist. Explicitly withdrawn optional evidence must stop serving even if core repository metadata remains public.
- **Bound collection and exposure.** Apply repository quotas, bounded histories, provider rate limits and refresh budgets. Do not publish emails, secrets, raw logs or identifiable error samples. Public pages provide repository evidence, not individual contributor rankings. Any shared page carries the same limitations as its underlying data.
- **Test boundaries before release.** Prove that public requests cannot enumerate private repositories, tenant records or individual profiles; private-to-public changes require the appropriate explicit choice; revocation removes serving access; and cached pages cannot retain withdrawn evidence.

## 1. Public repository health pages

**Audience and value.** Developers evaluating an open-source dependency, contributors deciding where to help and maintainers explaining repository conditions. A stable, shareable page should answer practical questions before installation and serve as a live Forge demonstration.

**Evidence and limits.** Show observed PR review/merge waiting distributions, the current open queue, CI red/green history and potential flaky tests only when eligible reports exist. A distinct maintainer-response measure requires timestamped human responses and reliable evidence that the responder was a maintainer at that time; current membership alone is insufficient. Until that source exists, label the available measure “first substantive review,” with its exclusions. Workflow success is not proof of a successful deployment, complete testing or dependency security. Avoid a single health grade that hides missing sources or suggests a maintenance guarantee.

**Small MVP.** An allowlisted set of public repositories with a read-only overview, a chosen observation window, source links, per-section coverage and a copyable page URL. Keep public provider facts separate from any owner-published test summaries. Add test signals only after Phase 6 report handling and publication controls are ready.

**Acceptance and success signals.** Each displayed aggregate matches its eligible evidence; missing CI or JUnit access is visibly unavailable; page removal and private-repository denial pass tests. In an opt-in pilot, track whether dependency evaluators can explain the page's limits, follow evidence links and return or share it. Measure discovery without exposing identifiable visitor or contributor activity.

## 2. Contributor guidance

**Audience and value.** First-time contributors who want realistic expectations and maintainers who repeatedly explain contribution practices. Help a contributor choose an area and prepare a reviewable change.

**Evidence and limits.** Observed first-time PR merge expectations require a stable provider account ID, bot exclusions and enough repository history to establish whether an earlier PR exists. A 90-day import alone cannot establish a first-ever contribution. Where older history is incomplete, label the cohort “first observed in this window” or omit the first-time comparison. Show merged outcomes alongside closed-unmerged and still-open PRs; a merge-time distribution alone would hide unsuccessful or unfinished contributions. Never promise acceptance or a deadline.

**Small MVP.** A repository guide containing observed contribution outcomes and waiting ranges, active areas derived from covered file/label history, and links to current contribution instructions. Describe smaller PRs as an observed association with clear sample sizes, not a maintainer preference unless the maintainer explicitly states that preference. Do not infer skill, availability or intent from a person's activity.

**Acceptance and success signals.** Reopened PRs, account renames, bots and incomplete historical identity fixtures produce the documented cohorts. Small or missing samples suppress comparisons. Maintainers can correct policy text without changing historical facts. Pilot contributors should be able to identify a suitable area and distinguish written policy from measured tendencies; track useful guide visits and voluntary feedback, not pressure on maintainers to meet a target.

## 3. Personal engineering profile

**Audience and value.** An individual developer reflecting on their own review turnaround, PR-size habits, changes over a year and a year-in-review. The individual controls this product and its data. It must never become employer surveillance or employee ranking.

**Evidence and limits.** Link identities through authenticated provider accounts, not guessed emails or display names. Let the individual select sources and observation windows. Distinguish reviews they submitted from reviews received on their PRs, and use only covered timestamps and file statistics. Annual comparisons require comparable coverage; partial years and changed repository selection must remain visible. Activity is not a measure of productivity, competence or hours worked.

**Small MVP.** A private profile and private year-in-review with evidence drill-down, source selection, export and deletion. Separate personal authorization from organization membership: an employer's administrator, billing owner or manager has no profile access, including after inviting that person into a workspace. No team ranking, manager lookup, bulk employee export or automatic profile publication. Any later sharing is separately chosen by the individual, limited in scope and revocable.

**Acceptance and success signals.** Consent is specific and revocable; source revocation stops collection and removes access to affected evidence according to the disclosed deletion policy. An individual's consent does not bypass authorization to an employer's private repository or permit publishing its contents. Prove those boundaries, including organization-admin denial, before a pilot. Success is voluntary repeat reflection and useful self-reported insights, not employer purchases, higher activity counts or comparative scores.

## 4. Free monitoring for one or two side projects

**Audience and value.** Independent developers operating a small service who want to know whether errors changed after a deployment. Keep one or two projects useful for free, with an optional team workspace later.

**Evidence and limits.** Requires authorized deployment history and Sentry error data with explicit service, environment and release mappings. A passing workflow cannot start an invented deployment watch. Without a known mapping, show the missing association; a time-adjacent error rise is evidence to investigate, not proof that the deployment caused it. No traffic denominator means no claimed error rate.

**Small MVP.** Connect up to two projects, choose a production environment and notification destination, preview a bounded post-deployment watch, then explicitly enable it. Show new/error-count changes against a declared baseline, freshness and the exact observations behind each alert. Define free refresh, event and retention quotas at the pilot gate and disclose them before connection; never silently turn a limit into reassuring zeroes. Team adoption must preserve separate access and be optional.

**Acceptance and success signals.** Duplicate statuses and overlapping polls do not double-alert; stale or missing data yields an unavailable watch; destination disablement and credential revocation stop unsent work. Pilot success means developers connect a project, understand a real alert and continue using monitoring with tolerable noise and predictable collection cost. No automatic rollback or deployment halt is included.

## 5. Opt-in public benchmarks

**Audience and value.** Maintainers and teams seeking context for repository-level PR, CI or test patterns across comparable languages and team sizes. Publish aggregated distributions with their coverage, not a leaderboard or an individual score.

**Evidence and limits.** Require explicit benchmark-purpose opt-in from an authorized repository/organization owner; public visibility, a public health page and ordinary integration consent do not count. Use disclosed language grouping and owner-supplied coarse team-size bands rather than inferring employment or team membership from commits. Avoid counting one owner with many repositories as many independent organizations. Metrics, windows, exclusions and collection methods must be comparable before combining sources.

**Small MVP.** A few fixed cohorts and time windows for stable repository-level metrics. Initial publication floor: at least 20 eligible repositories from at least 10 independently consenting owners, after all filters, with bounded contribution per owner. This floor is a suppression rule, not an anonymity guarantee. Show eligible/total sample counts and missing-data coverage; suppress a cohort if ownership concentration, sensitive outliers or combinations of releases could reveal a contributor. No named examples, raw records, participant lists, arbitrary filters or drill-through.

**Acceptance and success signals.** Validate contribution bounds, small-cohort suppression, repeat-publication/differencing risks and metric parity. Withdrawal excludes future contributions and triggers recomputation or withdrawal of affected Forge-hosted releases; disclose that downloaded public aggregates cannot be recalled. Review aggregation privacy before publishing rather than claiming that removal of names is sufficient. Success is enough sustained opt-in participation to publish useful, stable cohorts and readers correctly interpreting their limits; empty cohorts remain unpublished.

## 6. Free tools for public-repository maintainers

**Audience and value.** Maintainers who want quiet, practical help with repetitive work: potential flaky-test detection, stale-PR nudges and release-note drafts. Keep useful tooling free for public repositories within disclosed quotas.

**Evidence and limits.** Potential flakiness needs actual test executions with the Phase 6 sample/transition rules and branch/environment context; CI failure alone cannot identify a flaky test. Stale-PR suggestions need covered activity timestamps and exclusions for drafts, blocked work and maintainer-set labels. Release-note drafts must use explicit merged-PR/release associations and expose missing links. Generated text remains a draft backed by source links.

**Small MVP.** An in-app, reviewable digest containing potential flaky tests and stale PR candidates, plus a release-note draft for a selected range. Begin without repository writes. After Phase 9, a maintainer may explicitly authorize a repository-specific nudge destination and cadence; default to a weekly digest, suppress repeated items and provide pause/disable controls. Publishing a draft requires a separate authorized action. No auto-merge, auto-close, unsolicited contributor messages or automatic release publication.

**Acceptance and success signals.** Missing reports suppress flakiness claims; excluded PRs stay excluded; replay cannot duplicate messages; disabling a rule cancels unsent nudges. Permissions and author identity are checked at dispatch. Pilot success is maintained use of useful drafts, maintainer-reported time saved and low dismissal/mute rates, rather than maximizing bot messages or contributor activity.

## Decisions to resolve at each pilot gate

Record the specific scope, public/tenant/personal data boundary, source permissions, refresh and retention budgets, publication or notification controls, abuse handling and validation fixtures before implementation. Set measurable pilot targets with participants rather than inventing market validation. The initial priorities may change with evidence, but any change must preserve the current roadmap gates and the privacy commitments above.
