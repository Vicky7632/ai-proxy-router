# AI Proxy Router

A unified API gateway that routes chat completion requests across multiple LLM providers (Groq, Gemini, OpenRouter, OpenAI, Anthropic) with automatic fallback, caching, rate limiting, and cost tracking.

## Status
In active development — currently building core backend + provider integrations.

## Tech Stack
- **Backend**: FastAPI, SQLAlchemy, Alembic
- **Database**: PostgreSQL (+ pgvector for semantic caching)
- **Cache / Rate limiting**: Redis
- **Frontend**: React, Tailwind CSS
- **Deployment**: Docker (planned)

## Features (planned/in progress)
- [x] FastAPI backend setup
- [x] PostgreSQL connection
- [ ] Unified `/v1/chat/completions` endpoint
- [ ] Multi-provider adapters (Groq, Gemini, OpenRouter, OpenAI, Anthropic)
- [ ] Automatic fallback on provider failure
- [ ] Redis caching (exact + semantic)
- [ ] Per-key rate limiting and budgets
- [ ] React analytics dashboard

## Setup

### Backend
\`\`\`bash
cd Backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
\`\`\`

Create a `.env` file in `Backend/`:
\`\`\`
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/ai_proxy_router
\`\`\`

Run the server:
\`\`\`bash
python -m uvicorn app.main:app --reload
\`\`\`

Visit `http://127.0.0.1:8000/docs` for the API docs.

## Project Structure
(link or paste a short version of your folder structure here)

### Authentication

The backend uses stateless JWT authentication with a short-lived access token
and a long-lived refresh token:

- `POST /auth/register` with `{ "email": "...", "password": "..." }`
- `POST /auth/login` with the same fields
- `POST /auth/refresh` with `{ "refresh_token": "..." }`
- `GET /auth/me` with `Authorization: Bearer <access_token>`

The chat completion endpoint also requires a valid access token. Refresh
tokens are signed JWTs and are tracked in Redis with an expiry. Refresh token
rotation and `POST /auth/logout` revoke refresh sessions immediately. Changing
`JWT_SECRET_KEY` invalidates all existing tokens.

For Redis Cloud, configure the client without putting credentials in source
code:

```env
REDIS_HOST=redis-12967.c83.us-east-1-2.ec2.cloud.redislabs.com
REDIS_PORT=12967
REDIS_USERNAME=default
REDIS_PASSWORD=your-rotated-redis-cloud-password
REDIS_SSL=true
REDIS_DB=0
```

The client uses `redis.Redis` with TLS for this configuration. `REDIS_URL`
remains supported and takes precedence when provided.

## Author
Vicky Kumar