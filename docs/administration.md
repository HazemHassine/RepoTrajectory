# Administration

RepoTrajectory separates public research views from its privileged control plane. The collection
page remains read-only; `/admin` is the only browser workspace that can enqueue ingestion, run
collection policy operations, retry or cancel jobs, and inspect detailed queue or audit records.

## Configure or rotate the password

Run the password setup from the repository root:

```bash
./run.sh admin-password
```

The prompt does not echo input. It writes only a salted PBKDF2-HMAC-SHA256 hash and a new random
session-signing secret to `.env`. The file is mode `0600`, excluded by `.gitignore`, absent from
both Docker build contexts, and used only as runtime configuration. The plaintext password is
never written or printed. Rotating the password also rotates the signing secret, invalidating all
previous sessions.

After startup, the launcher prints the administration URL. The default username is `admin`.

## Security boundary

- Passwords use PBKDF2-HMAC-SHA256 with 600,000 iterations and a random 128-bit salt.
- Successful login creates an eight-hour HMAC-signed session in an `HttpOnly`, `SameSite=Strict`
  cookie. The browser never stores the session or password in local storage.
- Every state-changing request requires a random session-bound CSRF token in a custom header, an
  explicitly allowed Origin or Referer, and a non-cross-site Fetch Metadata context.
- Five rejected logins from the API's observed client address trigger a 15-minute rolling lockout.
- The API exposes a fixed allowlist of operations. It does not provide arbitrary shell, SQL, or
  Docker-socket access.
- Job retry and cancellation use conditional database updates so a concurrent worker claim cannot
  be overwritten.
- Sign-ins, rejected attempts, commands, ingestion requests, retries, cancellations, and sign-outs
  enter an append-only administrative audit table. Passwords, session tokens, CSRF tokens, GitHub
  tokens, and signing secrets are never included in audit details.
- Admin responses are marked `Cache-Control: no-store`; the API also emits frame, MIME-sniffing,
  referrer, permissions, and content-security headers.

The default launcher publishes only loopback HTTP, so `ADMIN_SECURE_COOKIES=false` is necessary for
local use. When placing the app behind HTTPS, set `ADMIN_SECURE_COOKIES=true` and replace
`ADMIN_ALLOWED_ORIGINS` with the exact HTTPS origin. Never expose the app publicly with the local
development defaults.

## Available operations

- Run scheduler: enqueue all due discovery, GH Archive, reconciliation, refresh, and maintenance
  work.
- Reconcile cohort: re-rank eligible candidates and promote the current active set.
- Reclassify candidates: reapply the current transparent software eligibility rules.
- Run maintenance: enqueue retention cleanup for compact external-activity records.
- Queue repository: add an explicit `owner/repository` to bounded ingestion.
- Retry job: reset only a failed or cancelled job.
- Cancel job: cancel only queued or failed work; running and completed jobs are immutable from the
  panel.

Long-running collection never executes in the HTTP request. Commands enqueue durable PostgreSQL
work for the private collector process, preserving leases, retry policy, rate-limit handling, and
restart recovery.
