# Collector design and operations

## Design goals

The collector separates cheap discovery from expensive historical hydration. A candidate can be
ranked with search metadata and compact public-event facts before the application spends the core
GitHub REST budget. This lets the candidate universe grow into the thousands while the deeply
hydrated cohort stays bounded.

## Storage model

| Layer | Retained data | Bound |
| --- | --- | --- |
| GitHub Search | one mutable candidate row per GitHub repository ID | collection candidate ceiling |
| GH Archive | hourly repository counters only | hours × top repositories/hour |
| Raw GH Archive JSON | never retained | zero |
| Active repository entities | commits, issues, PRs, releases, contributors | time and item ceilings |
| Repository snapshots | one updated point per UTC day | recurring historical series |
| Jobs | status, lease, attempts, payload, timestamps, errors | operational ledger |

Hourly archive projections are versioned. When the selection formula changes, the configured
hours replay and replace their old compact rows atomically. This prevents stale rows from mixing
two algorithms.

## Default hard bounds

- Commit bootstrap: 180 days and 5,000 items per repository.
- Issues: 3,000 most recently updated items.
- Pull requests: 3,000 most recently updated items.
- Releases: 730 days and 500 items.
- Contributors: 200.
- External activity: 500 repositories per hour, retained for 90 days.

These are safety ceilings, not target volumes. Most repositories stop at their time watermark long
before an item ceiling. If a ceiling is reached, analytics should be interpreted as a recent
bounded view rather than complete repository history.

## Queue behavior

Jobs have a unique deduplication key, priority, schedule time, attempt count, and worker lease.
Workers claim one due row using `FOR UPDATE SKIP LOCKED`. A failed job is isolated from the batch;
transient errors use exponential backoff and terminal errors remain visible in the work ledger.
If a process dies, the scheduler requeues work after the lease expires.

Priorities are deliberately asymmetric:

1. manual pinned repositories;
2. GitHub Search discovery;
3. GH Archive discovery;
4. collection reconciliation and metadata probes;
5. hydration ordered by the latest trend score;
6. maintenance.

The GitHub client serializes requests within a worker, observes primary and secondary limits, keeps
a proportional reserve for small search buckets, and reschedules work after the reported reset.

## Scaling

PostgreSQL is the coordination layer, so multiple collector processes can safely share one queue.
Start with one process; add workers only after observing the GitHub rate budget and database write
latency. More workers improve parsing and database concurrency but do not create more GitHub quota.

For materially larger deployments:

- separate discovery and hydration workers by accepted job types;
- partition `commits`, `issues`, `pull_requests`, and external activity by time;
- move analytics recalculation to its own low-priority queue;
- use PgBouncer if worker counts exceed the configured connection pool;
- monitor queue age, failed jobs, database size, API request latency, and GitHub reset time.

## Recovery

All sources are replayable. GitHub entities use conflict-safe upserts, archive hours use replaceable
projections, snapshots deduplicate within a UTC day, and queue keys prevent duplicate scheduled
work. Restarting the collector is therefore the normal recovery action; deleting data or resetting
the queue should not be necessary.
