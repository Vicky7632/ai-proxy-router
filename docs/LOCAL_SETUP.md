# Local development setup

These instructions are for local development. They are separate from the
Docker Desktop Kubernetes workflow in [KUBERNETES.md](KUBERNETES.md).

## Prerequisites

- Docker Desktop with Docker Compose.
- Python 3.12 for running the backend outside its container.
- Node.js 20 and npm for the frontend.
- A Groq API credential for provider completions.
- A Gemini API credential for semantic prompt embeddings. The code treats
  Gemini and OpenRouter chat credentials as optional configuration, but the
  provider must have a credential to answer requests.

## Configuration and secrets

There is no checked-in `.env.example`. The repository has local `.env` files;
their values are intentionally not reproduced here. The backend loads
`Backend/.env` and requires:

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Yes | SQLAlchemy database connection. Compose overrides this with its internal PostgreSQL service URL. |
| `GROQ_API_KEY` | Yes | Groq provider credential. |
| `JWT_SECRET_KEY` | Yes | Signs dashboard access and refresh tokens. |
| `GEMINI_API_KEY` | No at startup | Gemini chat integration and semantic-cache embedding generation. |
| `OPENROUTER_API_KEY` | No at startup | OpenRouter chat integration. |
| `REDIS_URL` | No | Optional complete Redis connection URL. |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_USERNAME`, `REDIS_PASSWORD`, `REDIS_SSL`, `REDIS_DB` | No | Redis connection settings used when `REDIS_URL` is not set. Defaults are in `Backend/app/config.py`. |
| `FRONTEND_ORIGIN` | No | Single CORS-allowed origin; default is `http://localhost:3000`. For a Vite dev server, set it to `http://localhost:5173`. |
| `COOKIE_SECURE`, `COOKIE_SAMESITE` | No | Dashboard cookie options; see `Backend/app/config.py`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `JWT_ALGORITHM` | No | Dashboard token configuration. |
| `SEMANTIC_CACHE_SIMILARITY_THRESHOLD`, `SEMANTIC_CACHE_TTL_SECONDS`, `SEMANTIC_CACHE_CLEANUP_INTERVAL_SECONDS` | No | Semantic-cache threshold, TTL, and cleanup interval. |
| `PROVIDER_HEALTH_FAILURE_THRESHOLD`, `PROVIDER_HEALTH_COOLDOWN_SECONDS` | No | Provider health/cooldown settings. |

The backend setting defaults and validation are the source of truth. Do not
commit real credentials. If the local `.env` files are missing, create them
locally with your own values; do not copy secrets from another environment.

## Option A: run the full stack with Docker Compose

From the repository root, make sure `Backend/.env` has the required values.
Compose supplies PostgreSQL and Redis and passes the backend's connection
settings to the backend container.

```powershell
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose ps
```

Published local endpoints:

| Service | Local address |
| --- | --- |
| Frontend | `http://localhost:3000` |
| Backend | `http://localhost:8000` |
| PostgreSQL | `localhost:5433` (container port 5432) |
| Redis | `localhost:6379` |

Compose defines named volumes `postgres_data` and `redis_data`. Do not remove
them when stopping or updating the application if you need to preserve data.

Useful non-destructive commands:

```powershell
docker compose ps
docker compose logs --tail 100 backend
docker compose logs --tail 100 frontend
docker compose exec backend alembic current
```

Stop the services without removing volumes:

```powershell
docker compose down
```

Do not append `-v` if the database and Redis data must be retained.

## Option B: run frontend/backend source with local data services

Start only the Compose data services:

```powershell
docker compose up -d postgres redis
```

Configure a backend environment for the host-run API. Use the local mapped
PostgreSQL port `5433`, Redis at `localhost:6379`, and the required secrets
from the table above. Set `FRONTEND_ORIGIN=http://localhost:5173` so the API
allows the Vite development server's origin with credentials.

The dependency files in this repository are UTF-16 encoded. The backend
Dockerfile normalizes its requirements file for container installation. For
a host Python environment, convert to a temporary UTF-8 requirements file
without changing the checked-in file:

```powershell
python -m venv .venv
$requirements = [System.IO.File]::ReadAllText(
  (Resolve-Path .\Backend\requirements.txt),
  [System.Text.Encoding]::Unicode
)
$requirementsPath = Join-Path $env:TEMP "ai-proxy-router-requirements.txt"
[System.IO.File]::WriteAllText(
  $requirementsPath,
  $requirements,
  [System.Text.UTF8Encoding]::new($false)
)
.\.venv\Scripts\python.exe -m pip install -r $requirementsPath
```

Then run the backend from its directory so its `app` package and Alembic
configuration resolve correctly:

```powershell
Set-Location .\Backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

In another PowerShell terminal:

```powershell
Set-Location .\Frontend
npm ci
$env:VITE_API_BASE_URL = "http://localhost:8000"
npm run dev
```

Vite serves the development frontend at `http://localhost:5173` by default.
The API's `FRONTEND_ORIGIN` must match that exact origin for CORS.

## Test commands

Frontend:

```powershell
Set-Location .\Frontend
npm test
npm run build
```

Backend:

```powershell
Set-Location .
.\.venv\Scripts\python.exe -m pytest Backend\tests -q
```

Some tests use mocks or SQLite. Tests that exercise PostgreSQL/pgvector,
Redis-backed caching, embeddings, or providers can need local services or
configured test doubles. Do not run tests against production resources.

## Troubleshooting

- **Backend configuration validation fails:** check the required variable
  names in `Backend/app/config.py`; do not print `.env` values into logs or
  support requests.
- **CORS error from Vite:** set `FRONTEND_ORIGIN` to the actual UI origin,
  normally `http://localhost:5173`, then restart the local backend.
- **Frontend calls the wrong API:** `VITE_API_BASE_URL` is read by the Vite
  client at build/dev-server startup. Set it before `npm run dev` or before
  building the Docker image.
- **PostgreSQL/Redis unavailable:** inspect `docker compose ps` and the
  relevant service logs. Preserve named volumes when troubleshooting.
- **Provider failure:** verify the required provider credential is available
  without printing it, and check backend status/error logs for the provider
  name and error category.
