# AI Proxy Router

A unified API gateway for chat completion requests across multiple LLM providers, with authentication, API-key management, multi-layer caching, semantic search, provider routing, health tracking, analytics, and streaming.

## Overview

AI Proxy Router is a backend-focused AI infrastructure project designed to sit between applications and multiple LLM providers.

Instead of every application integrating directly with individual providers, the router provides a unified API and handles:

* Authentication and API-key management
* Exact response caching with Redis
* Semantic caching with PostgreSQL + pgvector
* Multi-provider routing
* Provider health tracking and cooldowns
* Request and cache analytics
* Streaming chat completions
* PostgreSQL persistence
* Dockerized local deployment
* React dashboard for monitoring and testing

The goal was to understand how an AI gateway works internally rather than simply calling an LLM API.

---

## Architecture

```text
                         ┌──────────────────────┐
                         │    React Dashboard   │
                         │  React + Tailwind    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      FastAPI         │
                         │     API Gateway      │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼────────────────┐
                    │               │                │
                    ▼               ▼                ▼
              ┌──────────┐   ┌────────────┐   ┌──────────────┐
              │  Redis   │   │ PostgreSQL │   │   Provider   │
              │          │   │ + pgvector │   │   Router     │
              │ Exact    │   │ Semantic   │   │              │
              │ Cache    │   │ Cache      │   │ Groq         │
              │ Sessions │   │ Analytics  │   │ Gemini       │
              │ Health   │   │            │   │ OpenRouter   │
              └──────────┘   └────────────┘   └──────────────┘
```

---

## Request Flow

The router uses a multi-layer cache before making a provider request.

### 1. Exact Cache Hit

```text
Request
   ↓
Redis lookup
   ↓
HIT
   ↓
Return cached response
```

No embedding generation, semantic search, or provider call is required.

### 2. Semantic Cache Hit

```text
Request
   ↓
Redis MISS
   ↓
Generate embedding
   ↓
pgvector semantic search
   ↓
Semantic HIT
   ↓
Return existing response
```

This allows similar requests with different wording to reuse an existing response.

### 3. Cache Miss

```text
Request
   ↓
Redis MISS
   ↓
Semantic Cache MISS
   ↓
Provider Router
   ↓
LLM Provider
   ↓
Store response
   ↓
Return response
```

### Complete Flow

```text
Client
  ↓
Authentication
  ↓
API Key Validation
  ↓
Redis Exact Cache
  ↓
Semantic Cache
  ↓
Provider Selection
  ↓
LLM Provider
  ↓
Response Storage
  ↓
Analytics
  ↓
Client
```

---

## Key Features

### Authentication

* JWT-based authentication
* HTTP-only access and refresh-token cookies
* Refresh-token rotation
* Redis-backed refresh sessions
* Access-token blacklist on logout
* Protected dashboard routes

### API Key Management

* Generate proxy API keys
* List active keys
* Revoke keys
* Raw API key returned only once
* SHA-256 hash stored in the database
* Separate API credentials from dashboard authentication

Example:

```http
Authorization: Bearer sk-...
```

---

### Multi-Layer Caching

#### Exact Cache

Redis is used for fast exact-match response caching.

```text
Same request
    ↓
Redis HIT
    ↓
Cached response
```

#### Semantic Cache

PostgreSQL + pgvector is used for similarity-based cache lookup.

```text
Similar request
    ↓
Generate embedding
    ↓
pgvector search
    ↓
Semantic HIT / MISS
```

The semantic cache also supports:

* Similarity threshold
* TTL
* Automatic cleanup
* Time-based expiration

---

### Provider Routing

The router supports multiple LLM providers:

* Groq
* Google Gemini
* OpenRouter

The provider layer abstracts provider-specific APIs behind a common interface.

This allows the application to send requests through a single gateway instead of implementing separate integrations for every provider.

---

### Provider Health Tracking

Provider failures are tracked using Redis.

The router records:

* Request count
* Failure count
* Last successful request
* Last failure
* Provider health state

Unhealthy providers can enter a cooldown period and the router can select another available provider.

---

### Streaming

The chat completion endpoint supports streaming responses using Server-Sent Events (SSE).

```text
Client
  ↓
FastAPI
  ↓
Provider
  ↓
SSE chunks
  ↓
Client
```

Streaming requests bypass the normal response-cache lookup and forward provider chunks incrementally to the client.

---

### Cache Analytics

The system records cache and provider activity in PostgreSQL.

Tracked metrics include:

* Total requests
* Cache hits
* Cache hit rate
* Redis hits
* Redis misses
* Semantic hits
* Semantic misses
* Provider calls
* Time-window based analytics

Example:

```text
Total Requests      → 51
Cache Hits          → 6
Redis Hits          → 3
Semantic Hits       → 3
Provider Calls      → 11
Cache Hit Rate      → 11.8%
```

---

## Tech Stack

### Backend

* FastAPI
* Python
* SQLAlchemy
* Alembic
* Pydantic

### Database

* PostgreSQL
* pgvector

### Caching / State

* Redis
* Redis Cloud support

### LLM Providers

* Groq
* Google Gemini
* OpenRouter

### Frontend

* React
* Vite
* React Router
* Tailwind CSS
* Axios

### Infrastructure

* Docker
* Docker Compose
* Nginx

---

## Project Structure

```text
AI Proxy Router
│
├── Backend
│   ├── app
│   │   ├── api
│   │   ├── core
│   │   ├── db
│   │   ├── models
│   │   ├── services
│   │   └── main.py
│   │
│   ├── alembic
│   ├── tests
│   ├── DockerFile
│   ├── requirements.txt
|
│
├── Frontend
│   ├── src
│   │   ├── components
│   │   ├── pages
│   │   ├── services
│   │   └── ...
│   ├── Dockerfile
│   └── package.json
│
├── docker-compose.yml
└── README.md
```

---

## Running with Docker

The project can be started as a complete local stack using Docker Compose.

### Services

| Service    |   Port |
| ---------- | -----: |
| Frontend   | `3000` |
| Backend    | `8000` |
| PostgreSQL | `5433` |
| Redis      | `6379` |

### Start

```bash
docker compose up --build -d
```

Run database migrations:

```bash
docker compose exec backend alembic upgrade head
```

Check running services:

```bash
docker compose ps
```

### Application

Frontend:

```text
http://localhost:3000
```

Swagger API documentation:

```text
http://localhost:8000/docs
```

PostgreSQL is exposed on:

```text
localhost:5433
```

Redis is exposed on:

```text
localhost:6379
```

Inside Docker, the backend connects to PostgreSQL and Redis using their Compose service names.

---

## Local Development

### Backend

```powershell
cd Backend

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

Create:

```text
Backend/.env
```

Example:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/ai_proxy_router

GROQ_API_KEY=your-groq-api-key
GEMINI_API_KEY=your-gemini-api-key
OPENROUTER_API_KEY=your-openrouter-api-key

JWT_SECRET_KEY=replace-with-a-random-secret

ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_USERNAME=
REDIS_PASSWORD=
REDIS_SSL=false
REDIS_DB=0

SEMANTIC_CACHE_TTL_SECONDS=3600
SEMANTIC_CACHE_CLEANUP_INTERVAL_SECONDS=3600
PROVIDER_HEALTH_COOLDOWN_SECONDS=60
```

Run migrations:

```powershell
alembic upgrade head
```

Start the API:

```powershell
python -m uvicorn app.main:app --reload
```

API documentation:

```text
http://localhost:8000/docs
```

---

### Frontend

```powershell
cd Frontend

npm install
npm run dev
```

The development frontend runs on:

```text
http://localhost:3000
```

Configure the API URL in:

```text
Frontend/.env
```

Example:

```env
VITE_API_BASE_URL=http://localhost:8000
```

---

## Authentication Flow

Dashboard authentication uses HTTP-only cookies.

```text
Register
   ↓
Login
   ↓
Access Token + Refresh Token
   ↓
HTTP-only Cookies
   ↓
Protected Dashboard
```

Important authentication endpoints:

```text
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
GET  /auth/me
```

Proxy API keys are separate from dashboard authentication:

```text
POST /keys
GET  /keys
DELETE /keys/{key_id}

POST /v1/chat/completions
```

The raw API key is shown only when it is created. Only its SHA-256 hash is persisted.

---

## Chat Completion

The main gateway endpoint is:

```http
POST /v1/chat/completions
```

with:

```http
Authorization: Bearer sk-...
Content-Type: application/json
```

Example request:

```json
{
  "model": "openai/gpt-oss-20b",
  "messages": [
    {
      "role": "user",
      "content": "Explain Redis caching in simple terms."
    }
  ]
}
```

The router handles authentication, caching, provider selection, provider execution, response storage, and analytics.

---

## Database Migrations

Alembic is used for database schema management.

Run:

```bash
alembic upgrade head
```

Create a new migration when required:

```bash
alembic revision --autogenerate -m "describe change"
```

---

## Testing
124 tests passed

The backend includes automated tests covering core functionality.

The project also includes manual end-to-end verification for:

* Authentication
* API-key creation and revocation
* Exact Redis cache hits
* Semantic cache hits
* Provider fallback
* Provider health
* Cache analytics
* Streaming responses
* Dockerized application flow
* Mobile frontend responsiveness

---

## Design Goals

The project was built around a few practical backend engineering goals:

1. **Single API interface** for multiple LLM providers.
2. **Avoid unnecessary provider calls** through exact and semantic caching.
3. **Handle provider failures** using health tracking and routing.
4. **Separate dashboard authentication from proxy API credentials.**
5. **Observe the system** through request, cache, and provider analytics.
6. **Support streaming** instead of only returning complete responses.
7. **Make the complete system reproducible** with Docker Compose.

---

## What I Learned

This project started as a way to understand how an AI API gateway works internally.

The implementation involved working through:

* FastAPI backend architecture
* PostgreSQL data modeling
* Redis caching and state management
* pgvector semantic search
* LLM provider abstraction
* Provider health and fallback
* JWT authentication
* Streaming with SSE
* Docker and multi-container networking
* Frontend-backend integration
* Observability and analytics

The most important part was not just implementing individual features, but understanding how they interact inside a real request lifecycle.

---

## Author

**Vicky Kumar**

* GitHub: [Vicky7632](https://github.com/Vicky7632)
* LinkedIn: [Vicky Kumar](https://www.linkedin.com/in/vicky-kumar-b390a1354/)
