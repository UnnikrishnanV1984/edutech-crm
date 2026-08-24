# Load testing

`FEATURES_AND_PLAN.md` Phase 5 exit criterion: "load test with simulated
multi-tenant traffic (skewed tenant sizes)". `scenarios/mixed-traffic.js`
runs two [k6](https://k6.io) scenarios concurrently — a "large tenant" at
4x the VU count of a "small tenant" — against the real BFF -> FastAPI ->
Postgres chain, using real Keycloak-issued tokens for the two dev-seeded
tenants (`backend/app/db/seed.py`).

## Prerequisites

- `docker compose up` already running (the script hits the live stack,
  not a mock).
- A k6 binary on the host. **Run it natively — do not run it via
  `docker run grafana/k6`.** Keycloak's dev-mode stamps a token's `iss`
  claim from the Host header of whatever request fetched it, and the BFF
  validates `iss` against the browser-facing `KEYCLOAK_ISSUER_URL`
  (`http://localhost:8080/...`). A token fetched from inside a container
  — via the compose network's `keycloak` hostname or Docker Desktop's
  `host.docker.internal` — gets a different `iss` and the BFF rejects it
  with 401. A native k6 process naturally requests through `localhost`,
  matching what a browser (and `tests/test_tenant_isolation.py`) already
  do, so this doesn't come up.
  - Install: see [k6.io/docs/get-started/installation](https://k6.io/docs/get-started/installation/)
    (Windows: `choco install k6`, `winget install k6`, or download the
    zip release directly — whichever your environment allows).

## Run

```
k6 run loadtest/scenarios/mixed-traffic.js
```

Configurable via env vars (all optional, shown with their defaults):

```
KEYCLOAK_ISSUER_URL=http://localhost:8080/realms/edutech-crm \
KEYCLOAK_CLIENT_ID=web \
BFF_BASE_URL=http://localhost:4000 \
LARGE_TENANT_VUS=20 \
SMALL_TENANT_VUS=5 \
DURATION=30s \
k6 run loadtest/scenarios/mixed-traffic.js
```

The script authenticates as `counselor.a` (tenant A, the "large tenant"
scenario) and `counselor.b` (tenant B, "small tenant") — the same dev
users `backend/app/db/seed.py` provisions from
`keycloak/realm-export.json`, password `password`. Each VU repeatedly
hits a random one of `/api/v1/contacts`, `/api/v1/deals`, `/api/v1/tasks`
through the BFF, sleeping 1s between iterations.

## Baseline (2026-08-24)

`LARGE_TENANT_VUS=10 SMALL_TENANT_VUS=3 DURATION=15s`, run natively
against a local `docker compose up` stack (dev-seeded data only, not a
production-scale dataset):

```
checks_succeeded...: 100.00% 152 out of 152
http_req_failed....: 0.00%   0 out of 154
http_req_duration..: avg=325.11ms min=52.34ms med=265.55ms max=996.27ms p(90)=594.78ms p(95)=786.16ms
http_reqs..........: 154    9.372052/s
```

No SLO is defined yet (`GAP_FIXES_PLAN.md` item 5 scope), so this is a
reference point for future comparisons, not a pass/fail gate — the
`thresholds` block in the script (`http_req_failed rate<1%`,
`http_req_duration p(95)<1000ms`) is a starting sanity check, not a
tuned target. The p(95) here (786ms) is worth keeping an eye on if this
baseline is revisited at a larger VU count or against non-trivial data
volumes — 13 concurrent VUs against a handful of dev-seeded rows is a
long way from a real multi-tenant production load.
