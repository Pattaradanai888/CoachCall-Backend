# CoachCall Backend

FastAPI backend for CoachCall: coaches manage athletes, groups, courses and sessions, track skill progression, and get performance reports and analytics.

## Stack

- Python 3.11.13, FastAPI, SQLAlchemy 2 (async, asyncpg), Alembic
- PostgreSQL
- JWT auth (access + refresh tokens), bcrypt
- Azure Blob Storage (profile images), Azure Communication Services (password-reset email)
- uv for dependency management, Ruff for linting, pytest for tests

## API

All routers are mounted in `src/api.py`:

| Prefix | Purpose |
|---|---|
| `/auth` | Register, login, refresh, logout |
| `/profile` | View and update profile, change password, upload image |
| `/athlete` | Athletes, groups, positions, skill progression |
| `/course` | Skills, courses, sessions, task completions, reports |
| `/analytics` | Dashboards, trends, leaderboard |
| `/rubrics` | Skill rubrics and indicators |
| `/password-reset` | OTP request, verify, reset |

`GET /health-check` returns service health. Interactive docs are at `/docs` when the server runs.

## Setup

1. Install [uv](https://docs.astral.sh/uv/), then install dependencies:

   ```bash
   uv sync
   ```

2. Create a `.env` file in the project root with these keys:

   ```
   PROJECT_NAME=
   ENVIRONMENT=
   DATABASE_URL=
   TEST_DATABASE_URL=
   DEPLOYMENT_DATABASE_URL=
   JWT_SECRET=
   JWT_ALGORITHM=
   TOKEN_TYPE=
   ACCESS_TOKEN_EXPIRE_MINUTES=
   REFRESH_TOKEN_EXPIRE_MINUTES=
   AZURE_STORAGE_ACCOUNT=
   AZURE_STORAGE_KEY=
   AZURE_CONTAINER_NAME=
   COMMUNICATION_SERVICES_CONNECTION_STRING=
   SENDER_ADDRESS=
   CORS_ORIGINS=
   OTP_EXPIRE_MINUTES=10
   ```

3. Run migrations:

   ```bash
   uv run alembic upgrade head
   ```

4. Start the dev server:

   ```bash
   uv run fastapi dev src/main.py
   ```

## Tests and linting

```bash
uv run pytest
uv run pytest --cov=src
uv run ruff check .
```

## Docker

```bash
docker build -t coachcall-backend .
docker compose up -d
```

`docker-compose.yml` reads its environment from `.env`. Production uses `docker-compose.prod.yml` and `deploy.sh`, deployed to Azure by the GitHub Actions workflow in `.github/workflows/automate-deploy-on-azure.yml`.
