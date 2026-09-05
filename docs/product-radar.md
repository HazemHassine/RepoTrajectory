# Developer radar beta

The product connects discovery, deterministic briefs, contextual comparison and browser-local
watch reasons. Eight initial topic rules focus on AI infrastructure; the evidence schema is generic.
Existing repository analytics remain available through progressive disclosure.

## Architecture and identity

GitHub numeric IDs own external links, evidence, shared source state, daily snapshots and changes.
The existing PostgreSQL job queue schedules up to 200 deep repositories daily. Public reads never
fetch external data or enqueue work. No additional service or paid source is required.

Package candidates come from explicit npm/PyPI README URLs. Registry repository metadata must
resolve through GitHub to the same numeric ID. Conflicting project links and name-only matches
are rejected. A match confidence of 1 means deterministic identity verification, not package quality.
Renames resolve through GitHub redirects. Packages without explicit links may be missed.

## Sources and bounds

| Source | Evidence | Refresh/cache | Bound |
| --- | --- | --- | --- |
| GitHub | Existing releases/issues and README | Daily; README weekly | 20 releases, 5 sampled open issues, 20,000 README characters |
| npm | Latest package metadata | 24 hours | Four package targets per repository |
| npm downloads | Last-week downloads | Seven days | Downloads are not people |
| PyPI | Metadata, Python requirements, publication | 24 hours | Identity-verified packages only |
| pypistats | Last-week downloads | Seven days | No ecosystem crawl |
| deps.dev v3 | Version license/deprecation context | Seven days | No full dependency graph |
| OSV v1/query | Exact package-version advisories | 24 hours | 30 findings; truncation disclosed |
| HN public search | Stories linking directly to repository | 72 hours | 20 hits; no complete threads |

Adapters use fixed HTTPS hosts, 12-second timeouts, three attempts with exponential backoff,
rate-limit retry scheduling and a 2 MB response ceiling. Normalized source state is the shared
cache. Last success, errors and next refresh remain inspectable. Failed sources retain their
previous successful observations and show degraded status.

References: [npm downloads](https://github.com/npm/registry/blob/main/docs/download-counts.md),
[PyPI JSON](https://docs.pypi.org/api/json/), [pypistats](https://pypistats.org/api/),
[deps.dev](https://docs.deps.dev/api/v3/), [OSV](https://google.github.io/osv.dev/api/),
[HN search](https://hn.algolia.com/api).

## Evidence, changes and retention

Descriptions/README excerpts are attributed project statements. GitHub attention, package
downloads, maintenance and discussions remain separate. Empty OSV results mean no known findings
returned for the checked version, not that a project is secure. HN submissions are attributed,
not independently verified experiences or sentiment judgments.

Events cover releases, newly observed vulnerabilities, relevant submissions, license transitions,
dormancy/resumption and material download changes. Downloads require both 50% movement and 1,000
absolute downloads by default. Dormancy means no recorded push for 180 days. First observations
are baselines. Missing licenses never become license changes. Release/discussion time uses
publication; vulnerability discovery uses observation. No semantic blocker-resolution claim is made.

Evidence, snapshots, changes and inactive source state have 180-day retention. Evidence and changes
also have a 200-row per-repository cap. Catalog deletion cascades; change references tolerate
evidence expiry. AI usage/artifacts expire after 60 days. Raw GH Archive payloads, complete HN
threads and full articles are never stored. Existing historical analytics retain their old policy.

## Watchlists and comparison

Up to 100 local watches retain GitHub ID, name, reason, blocker, tags and original timestamp.
Editing preserves the timestamp. Reasons never leave localStorage. Clearing browser storage
loses watches. Changes use numeric ID and disclose retention limits. Local watches do not trigger
additional collection; collection coverage may be incomplete for cold projects.

The comparison API accepts 2–4 IDs; the UI presents two projects. Explicit language, license,
package ecosystem and push freshness constraints are evaluated. Deployment stays unknown.
Free-text context is displayed, not automatically interpreted. Briefs and comparisons remain
deterministic even with hosted AI configured and never manufacture a winner.

## Optional AI

AI requires AI_ENABLED=true and a key. Offline providers return no vectors. The semantic-v2
namespace bypasses old hash vectors and query caches without deleting historical data.
Search reports semantic retrieval only after matching model/version vectors are queried successfully.

Hosted calls reserve PostgreSQL budgets under an advisory lock: one concurrent call, 100 requests
per day and 300,000 conservatively reserved tokens per month by default. Failed calls retain
reservations; unavailable ledger access denies AI without blocking reads. Scout artifacts cache
by evidence/request fingerprint, model, provider and prompt version. Actual usage and optional
configured price estimates are recorded; missing cost remains unknown.

## Operations, limits and next work

The target remains one 4–8 GB RAM VPS with 2–4 shared vCPU. Budget €10–18 for hosting and keep total
hosting/backup spend below €20; these are planning assumptions, not a vendor quote or measured
capacity guarantee. No managed database, search service, queue or paid AI is required.

Redis had no runtime consumer and was removed from Compose. Existing volumes are preserved.
Restore now uses an error-stopping transaction and checks schema revision plus every public table.
Failed rehearsal databases remain available for diagnosis. The original initial migration was
frozen into SQL because importing current ORM models broke fresh installation before pgvector setup.

Deferred to keep this delivery bounded: curated RSS, manifest-based package discovery, complete
dependency graphs, fixed-vulnerability reconciliation, richer deployment facts, AI brief/compare
synthesis, accounts/notifications and watch-driven adaptive collection.

Next five improvements: verified manifest package discovery; grounded deployment/capability facts;
vulnerability lifecycle tracking; bounded anonymous watch-interest scheduling; curated official feeds.
