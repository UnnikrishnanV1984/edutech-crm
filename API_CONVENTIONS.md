# API conventions

Applies to both the BFF -> FastAPI contract and the React -> BFF contract,
unless noted otherwise.

## 1. Auth & tenant resolution

- React authenticates directly against Keycloak (Authorization Code flow +
  PKCE), receiving an access token (JWT) + refresh token.
- The Keycloak access token carries `sub` (user id), `tenant_id` (custom
  attribute or claim), and role claims.
- React sends the Keycloak access token to the BFF on every call. The BFF
  validates it against Keycloak's JWKS endpoint (not a local secret), then
  forwards to FastAPI:
  - `X-Tenant-Id` — resolved tenant UUID (from the validated token)
  - `X-User-Id` — acting user UUID
  - `X-Request-Id` — generated per request, for tracing across logs
- FastAPI never talks to Keycloak directly — it trusts the BFF's forwarded,
  already-validated headers, and rejects any request missing `X-Tenant-Id`
  with `401` before touching the database.

## 2. URL structure

```
/api/v1/<resource>              collection
/api/v1/<resource>/{id}         single resource
/api/v1/<resource>/{id}/<sub>   nested resource
```

Tenant is never part of the URL path — it comes from the header/JWT, never
from a user-editable request field.

## 3. Response envelope

```json
{
  "data": { },
  "meta": { "request_id": "..." }
}
```

Collections:

```json
{
  "data": [ ],
  "meta": {
    "request_id": "...",
    "page": 1,
    "page_size": 25,
    "total": 132
  }
}
```

## 4. Error format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable summary",
    "details": [ { "field": "email", "issue": "invalid format" } ]
  },
  "meta": { "request_id": "..." }
}
```

Standard `code` values: `VALIDATION_ERROR`, `NOT_FOUND`, `UNAUTHORIZED`,
`FORBIDDEN`, `CONFLICT`, `RATE_LIMITED`, `INTERNAL_ERROR`.

## 5. Pagination, filtering, sorting

- Pagination: `?page=1&page_size=25` (default 25, max 100).
- Filtering: `?stage=demo_scheduled&lead_source=meta_ads`.
- Sorting: `?sort=-updated_at` (`-` prefix = descending).

## 6. Versioning

- Path-based: `/api/v1/...`. Breaking changes get a new version prefix;
  additive changes (new optional fields) do not require a version bump.

## 7. Idempotency (webhooks and integrations)

- Inbound webhooks (Meta, Google, WhatsApp) must include an idempotency key
  in the request (platform event ID). FastAPI checks Redis for that key
  before processing; if seen, return `200` without reprocessing.
- Outbound calls that trigger side effects (sending an email/WhatsApp
  message) should be queued as a background job, not executed inline in the
  request/response cycle.

## 8. Rate limiting

- Enforced at the BFF layer, keyed by `tenant_id`, backed by Redis.
- FastAPI returns `429` with `RATE_LIMITED` if it independently detects
  abuse (defense in depth), but primary enforcement lives in the BFF.
