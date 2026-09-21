# AI Proxy Router

A unified API gateway for chat completion requests across multiple LLM
providers, with authentication, routing, caching, rate limiting, and cost
tracking.

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy, Alembic
- **Database**: PostgreSQL
- **Authentication**: JWT access and refresh tokens
- **Session storage**: Redis / Redis Cloud
- **Frontend**: React, Tailwind CSS

## Setup

### Backend

```bash
cd Backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in `Backend/`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/ai_proxy_router
GROQ_API_KEY=your-groq-api-key
JWT_SECRET_KEY=replace-with-a-random-secret-at-least-32-characters
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Redis Cloud
REDIS_HOST=redis-12967.c83.us-east-1-2.ec2.cloud.redislabs.com
REDIS_PORT=12967
REDIS_USERNAME=default
REDIS_PASSWORD=your-rotated-redis-cloud-password
REDIS_SSL=true
REDIS_DB=0
```

Run the server:

```bash
python -m uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/docs` for the API docs.

## Authentication

The backend uses JWT authentication with a short-lived access token and a
long-lived refresh token:

- `POST /auth/register` with `{ "email": "...", "password": "..." }`
- `POST /auth/login` with the same fields
- `POST /auth/refresh` with `{ "refresh_token": "..." }`
- `POST /auth/logout` with `Authorization: Bearer <access_token>` and
  `{ "refresh_token": "..." }`
- `GET /auth/me` with `Authorization: Bearer <access_token>`

The chat completion endpoint also requires a valid access token. Refresh
tokens are signed JWTs and tracked in Redis with an expiry. Refresh-token
rotation and logout revoke refresh sessions immediately.
The access token is also blacklisted in Redis until its expiry, so previously
issued access tokens cannot be used after logout.

The Redis client uses `redis.Redis` with TLS for the Redis Cloud configuration.
`REDIS_URL` remains supported and takes precedence when provided.

## Author

Vicky Kumar
