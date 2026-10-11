# API reference

The routes below are registered by the FastAPI application. The interactive
OpenAPI UI is available at `/docs` while the backend is running; `/openapi.json`
is FastAPI's generated schema endpoint.

Examples use placeholders only. Do not place real API keys, JWTs, passwords,
cookies, or provider credentials in documentation or screenshots.

## Authentication conventions

- **Dashboard routes:** require the HTTP-only `access_token` cookie created by
  `/auth/login` (or `/auth/refresh`). The browser sends credentials.
- **Proxy routes:** require `Authorization: Bearer <proxy-api-key>`. The key
  must be active and not revoked.
- A proxy key's raw value is returned only when it is created. `GET /keys`
  returns metadata only.

## Endpoints

### `GET /`

Health/root response from the FastAPI application. No authentication.

**Response `200`:**

```json
{"message": "AI proxy router running"}
```

### `POST /auth/register`

Create a dashboard user. No authentication. Email is normalized to lowercase;
first and last names must be 1-100 characters, password 8-72 characters, and
email must be valid.

**Request:**

```json
{
  "first_name": "Example",
  "last_name": "User",
  "email": "user@example.invalid",
  "password": "<choose-a-local-password>"
}
```

**Response `201`:**

```json
{
  "id": "00000000-0000-0000-0000-000000000000",
  "first_name": "Example",
  "last_name": "User",
  "email": "user@example.invalid"
}
```

**Other implemented response:** `409` if the normalized email already exists;
`422` for request validation errors.

### `POST /auth/login`

Sign in with email/password. No prior authentication. On success, the server
sets HTTP-only `access_token` and `refresh_token` cookies; the response body
does not contain tokens.

**Request:**

```json
{"email": "user@example.invalid", "password": "<local-password>"}
```

**Response `200`:**

```json
{"message": "Login successful"}
```

**Other implemented responses:** `401` for invalid credentials, `503` if
refresh-session storage cannot be used, and `422` for validation errors.

### `POST /auth/refresh`

Rotate a refresh session and set new HTTP-only cookies. Requires the
`refresh_token` cookie.

**Request body:** none.

**Response `200`:**

```json
{"message": "Token refreshed"}
```

**Other implemented responses:** `401` for missing, expired, invalid, reused,
or revoked refresh session; `503` if Redis-backed auth session storage is
unavailable.

### `POST /auth/logout`

Invalidate the signed-in session and delete both cookies. Requires a valid
dashboard access cookie and the refresh cookie.

**Request body:** none.

**Response:** `204 No Content`.

**Other implemented responses:** `401` for absent or invalid authentication
cookies; `503` if Redis-backed revocation storage is unavailable.

### `GET /auth/me`

Return the signed-in dashboard user's profile. Requires the access cookie.

**Response `200`:**

```json
{
  "id": "00000000-0000-0000-0000-000000000000",
  "first_name": "Example",
  "last_name": "User",
  "email": "user@example.invalid"
}
```

**Other implemented response:** `401` if the user is not authenticated.

### `POST /keys`

Create a proxy key owned by the signed-in dashboard user. Requires the access
cookie. The `api_key` value is returned once; the database stores its hash.

**Request:**

```json
{"name": "Local development"}
```

**Response `201` (illustrative metadata and placeholder secret):**

```json
{
  "id": "00000000-0000-0000-0000-000000000000",
  "name": "Local development",
  "created_at": "2026-01-01T00:00:00",
  "revoked_at": null,
  "api_key": "<returned-once-proxy-key>"
}
```

**Other implemented responses:** `401` if the dashboard user is not
authenticated; `422` for an empty or over-255-character name or other
validation errors.

### `GET /keys`

List the signed-in user's proxy-key metadata. Requires the access cookie. This
endpoint deliberately does not return raw API keys or their hashes.

**Response `200`:**

```json
[
  {
    "id": "00000000-0000-0000-0000-000000000000",
    "name": "Local development",
    "created_at": "2026-01-01T00:00:00",
    "revoked_at": null
  }
]
```

**Other implemented response:** `401` if the user is not authenticated.

### `DELETE /keys/{key_id}`

Revoke a key belonging to the signed-in dashboard user. Requires the access
cookie. `key_id` must be a UUID. Revocation is permanent.

**Request body:** none.

**Response:** `204 No Content`.

**Other implemented responses:** `401` if the dashboard user is not
authenticated; `404` if the key does not belong to the user or has already
been revoked; `422` for an invalid UUID.

### `POST /v1/chat/completions`

Create a chat completion. Requires an active proxy API key in the Bearer
Authorization header. Request fields are defined by `ChatCompletionRequest`:
`model` defaults to `openai/gpt-oss-20b`, `messages` is required, `stream`
defaults to `false`, and `temperature` defaults to `0.7`. A message has string
`role` and `content` fields.

**Request (non-streaming):**

```http
POST /v1/chat/completions
Authorization: Bearer <proxy-api-key>
Content-Type: application/json
```

```json
{
  "model": "openai/gpt-oss-20b",
  "messages": [{"role": "user", "content": "Explain a design trade-off."}],
  "stream": false,
  "temperature": 0.7
}
```

**Response `200`:** JSON returned by the selected provider in its
OpenAI-compatible completion format. The exact payload fields are provider
dependent; the backend does not declare a response model. A typical successful
shape is:

```json
{
  "id": "chatcmpl-example",
  "object": "chat.completion",
  "created": 1760000000,
  "model": "openai/gpt-oss-20b",
  "choices": [
    {
      "index": 0,
      "message": {"role": "assistant", "content": "<completion-text>"},
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

When returned, `X-Cache` indicates `HIT` or `MISS`; `X-Remaining-Budget` is
included when a budget is configured.

**Streaming:** set `"stream": true`. The response uses `text/event-stream`,
containing OpenAI-style `data: { ... }` frames and a final `data: [DONE]`.
Chunks are forwarded as they arrive. Streaming support depends on the selected
provider adapter; the base adapter returns `501` for providers without a stream
implementation.

**Models mapped by the current router:**

| Request model | Provider |
| --- | --- |
| `openai/gpt-oss-20b` | Groq |
| `gemini-3.6-flash` | Google Gemini |
| `qwen/qwen-2.5-72b-instruct` | OpenRouter |
| `google/gemma-3-27b-it:free` | OpenRouter |
| `auto` | Ranks healthy providers by consecutive failures, with Groq, Gemini, then OpenRouter as the tie-break order |

**Other implemented responses:** `400` for an unsupported model; `401` for a
missing/invalid/revoked proxy key; `403` when the monthly budget is exceeded;
`429` when the Redis-backed rate limit is exceeded; `422` for request
validation; `500` if a required provider credential is missing; `501` where
the chosen adapter does not implement streaming; `502` for provider/routing
failures; `503` if rate-limit storage is unavailable. Provider HTTP errors may
also be propagated by the provider adapter.

### `GET /v1/analytics/cache`

Return cache and request totals for the authenticated proxy API key. Requires
Bearer authentication.

**Optional query parameters:**

- `from`: ISO 8601 date-time, inclusive.
- `to`: ISO 8601 date-time, exclusive.
- When both are provided, `from` must be earlier than `to`.

**Request example:**

```http
GET /v1/analytics/cache?from=2026-01-01T00:00:00Z&to=2026-02-01T00:00:00Z
Authorization: Bearer <proxy-api-key>
```

**Response `200`:**

```json
{
  "total_requests": 12,
  "redis_hits": 3,
  "redis_misses": 9,
  "semantic_hits": 2,
  "semantic_misses": 7,
  "redis_errors": 0,
  "semantic_errors": 0,
  "provider_calls": 7,
  "cache_hits": 5,
  "cache_hit_rate": 41.666666666666664
}
```

The example values are illustrative. **Other implemented responses:** `400`
when `from` is not earlier than `to`; `401` for invalid/missing proxy key;
`422` for malformed date-time parameters.

`provider_calls` counts request-log rows where at least one provider attempt
was made. Multiple retries or fallback attempts within a single request still
count as one provider-called request.

### `GET /v1/providers/health`

Return health counters for the provider names exposed by this endpoint
(`groq`, `gemini`, `openrouter`). Requires Bearer authentication.

**Request example:**

```http
GET /v1/providers/health
Authorization: Bearer <proxy-api-key>
```

**Response `200`:**

```json
{
  "providers": {
    "groq": {
      "total_requests": 0,
      "total_failures": 0,
      "consecutive_failures": 0,
      "last_success_at": null,
      "last_failure_at": null
    },
    "gemini": {
      "total_requests": 0,
      "total_failures": 0,
      "consecutive_failures": 0,
      "last_success_at": null,
      "last_failure_at": null
    },
    "openrouter": {
      "total_requests": 0,
      "total_failures": 0,
      "consecutive_failures": 0,
      "last_success_at": null,
      "last_failure_at": null
    }
  }
}
```

Counters are backed by Redis and are not an availability guarantee. **Other
implemented response:** `401` for invalid/missing proxy key.
