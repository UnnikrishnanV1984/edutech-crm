# EdTech CRM — Features & Development Plan

## 1. Feature set

### Core CRM
- Contact & lead management (create, dedupe, merge, search, filter)
- Pipeline management (custom stages, drag-drop stage changes, per-stage SLAs)
- Task management (follow-ups, reminders, due dates, assignment)
- Document management (upload, tag, associate with a contact/deal)
- Reporting & analytics (pipeline funnel, source ROI, counselor performance)
- Forecasting & win-probability (stage-weighted at first pass; refine later)

### Lead capture & integrations
- Web form / landing page lead capture (embeddable form + API)
- Meta Lead Ads integration (webhook + Graph API fetch)
- Google Ads / GTM / GA4 integration (lead + behavioral events)
- Meta Conversions API + Google Ads offline conversions (send outcomes back)
- WhatsApp Business API integration (notifications, reminders, 2-way chat)
- Telephony/IVR integration (click-to-call, call logging) — later phase

### Workflow automation
- Trigger/condition/action rule builder (e.g., "no contact in 24h -> notify counselor")
- Scheduled reminders (demo reminders, fee due reminders)
- Auto-assignment (round robin / territory-based)

### EdTech-specific
- Course/program catalog linked to leads
- Admission funnel stages (Inquiry -> Contacted -> Demo scheduled -> Demo
  attended -> Application submitted -> Fee paid -> Enrolled -> Dropped)
- Fee/EMI tracking with payment gateway integration
- Duplicate lead detection across campaigns

### Platform
- Multi-tenant auth (JWT, tenant resolution)
- Role-based access control (admin, manager, counselor)
- Tenant admin console (users, roles, pipeline config)
- Audit log

## 2. Phased plan

### Phase 0 — Foundations (get a running skeleton)
- Repo scaffolding: React app, Express BFF, FastAPI service, each with its
  own Dockerfile, wired together in `docker-compose.yml` alongside `db`,
  `redis`, and `keycloak`
- Keycloak realm/client config checked in as `/keycloak/realm-export.json`,
  auto-imported so `docker compose up` gives a working login with no manual
  console setup
- Postgres schema: `tenants`, `users`, basic RLS pattern in place
- Auth: Keycloak login (Authorization Code + PKCE), BFF token validation via
  JWKS, tenant resolution end to end through to FastAPI
- CI: lint + test pipeline for all three services
- Skeleton Helm charts in `/deploy/helm` (even if not yet deployed) so the
  local-to-AWS module mapping is established early, not retrofitted later
- **Exit criteria**: a logged-in user in tenant A cannot see tenant B's data,
  proven with an automated test; `docker compose up` brings up the full
  stack from a clean checkout with no manual steps.

### Phase 1 — Core CRM
- Contacts/leads: CRUD, search, filters, dedupe on create
- Pipeline: stages (configurable per tenant), stage transitions, activity log
- Tasks: create, assign, due dates, list/board view
- Basic document upload (S3/MinIO)
- **Exit criteria**: a counselor can manually create a lead, move it through
  stages, attach a document, and complete a task.

### Phase 2 — Lead capture integrations
- Web form capture endpoint + embeddable form
- Meta Lead Ads webhook + Graph API fetch, mapped into `contacts`
- Google Ads/GTM lead capture, UTM parsing, source attribution
- Idempotent ingestion (dedupe via Redis, using platform event IDs)
- **Exit criteria**: a real Meta/Google test lead appears correctly attributed
  in the pipeline within seconds of submission.

### Phase 3 — Communication & automation
- WhatsApp Business API integration (templates, reminders)
- Email integration (transactional sends, tracking opens/clicks)
- Workflow engine: rule builder, trigger evaluation, background execution
- Auto-assignment logic
- **Exit criteria**: a configured rule ("no contact in 24h") actually fires
  and notifies the right counselor without manual intervention.

### Phase 4 — Reporting, forecasting, conversion feedback loop
- Pipeline funnel and source ROI dashboards
- Stage-weighted forecasting and win-probability
- Meta Conversions API + Google offline conversions (send enrollment/fee-paid
  events back to ad platforms)
- **Exit criteria**: marketing team can see cost-per-enrollment by channel,
  and ad platforms are receiving conversion signals.

### Phase 5 — Multi-tenancy hardening & single-tenant packaging
- Hash-partitioning for high-volume tables (activities, communication logs)
- Per-tenant rate limiting, per-tenant resource monitoring
- First real deployment to AWS EKS using the Helm charts from `/deploy/helm`
  (see `ARCHITECTURE.md` Section 6): `web`/`bff`/`backend`/`keycloak` images
  pushed to ECR, `db`/`redis` swapped to RDS/ElastiCache
- Single-tenant deployment path validated against a real client-style VPC
- Load test with simulated multi-tenant traffic (skewed tenant sizes)
- **Exit criteria**: the same Docker images built in Phase 0 deploy cleanly
  to EKS, and separately as an isolated single-tenant instance, with no code
  changes — only Helm `values.yaml` and environment config differ.

## 3. Suggested working agreement for Claude Code

- Work phase by phase; do not start Phase N+1 work until Phase N's exit
  criteria are met and tested.
- Every new table gets `tenant_id`, RLS policy, and a composite index leading
  with `tenant_id` — see `DATABASE_SCHEMA.md`.
- Every new FastAPI endpoint requires and validates tenant context — see
  `API_CONVENTIONS.md`.
- Prefer small, reviewable commits per feature slice over large batched changes.
