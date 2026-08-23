# Metric methodology

Scores are explainable heuristics, not scientific ground truth. Each stored `metric_snapshot` contains the score, window, calculation time, and every component used to produce it. All components are constrained to 0–100 before weighting.

## Momentum score

**Question:** Is development and community activity accelerating?

For a selected window (30 days by default), the model uses observed star and contributor growth rates, human commit and PR change versus the immediately preceding equal window, and stable releases per month. Growth and acceleration use a hyperbolic tangent centered at 50; zero change is neutral, decline scores below 50, and acceleration scores above 50. Release cadence uses `100 × (1 − exp(−x/2))`, which rewards consistency with diminishing returns. Until snapshot history spans the window, unavailable growth components are excluded and the remaining weights are renormalized.

| Component | Weight |
|---|---:|
| Star growth | 25% |
| Contributor growth | 20% |
| Commit acceleration | 25% |
| PR acceleration | 20% |
| Release cadence | 10% |

Limitations: snapshot growth requires observations spanning the window. A first ingestion therefore reports growth as unavailable. Known bot accounts are excluded from human commit signals and exposed as automation share, but bot identification is heuristic. Monorepos, rebases, and release conventions can still distort inputs.

## Community health score

**Question:** Is the community active, responsive, and able to ship?

Active human contributors, recent human commits, and stable releases use diminishing-return transforms so large projects do not win merely through scale. Issue-close and PR-merge cycles use events resolved during the window, avoiding the strongest recent-open cohort bias. Missing response evidence scores zero and remains visibly marked. PR acceptance is merged divided by all resolved PRs in the window.

| Component | Weight |
|---|---:|
| Active contributors | 20% |
| Issue resolution time | 15% |
| PR merge time | 15% |
| PR merge rate | 20% |
| Release cadence | 10% |
| Recent commits | 20% |

Limitations: close time is not first-response time, and low merge rates may reflect intentionally strict governance. Issue-heavy support repositories and projects using external trackers need contextual interpretation.

## Contribution concentration / maintainer-dependency proxy

**Question:** How concentrated is recorded contribution activity?

The model reports top-one share, top-three share, and Herfindahl–Hirschman Index (`Σ share²`). Risk is `100 × (45% top-one + 25% top-three + 30% HHI)`. Higher means more concentrated. It uses recent human commits when available and falls back to cumulative GitHub contributions only when the window has no recent commits. It is not a literal bus factor because GitHub API evidence does not reveal maintainer permissions, tacit knowledge, or succession readiness.

## Development velocity

The API returns human commits, merged PRs, closed issues, and stable releases in weekly buckets. Metric components also preserve current and previous equal-window counts, automation volume/share, issue intake/closure, net issue flow, per-week activity, and per-month release cadence. Percent change is `(current − previous) / previous`; positive activity following a zero baseline is capped at +100% for presentation.

## Evidence confidence

Confidence summarizes event volume and snapshot coverage. It does not turn a small cycle-time sample into strong evidence: the API separately returns resolved PR, merged PR, and closed issue sample sizes. The UI displays baseline-pending states rather than silently substituting zero growth.

## Repository growth

Stars, forks, open issues, watchers, and contributor count are observed at ingestion time. Growth compares actual snapshots rather than reconstructing history from current values. Sparse capture cadence can hide short-lived changes, so production scheduling should collect at least daily.
