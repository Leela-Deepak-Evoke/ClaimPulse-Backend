# ClaimPulse — Backend

FastAPI monolith backed by PostgreSQL. Python 3.12+, managed with [uv](https://docs.astral.sh/uv/).

## Setup

```powershell
uv sync
copy .env.example .env   # then fill in real values (never commit .env)
```

## Commands

| Task | Command |
|---|---|
| Run API (dev) | `uv run uvicorn claimpulse.main:app --reload` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Type check | `uv run mypy` |
| Test (80% coverage gate) | `uv run pytest` |

## API docs

With the server running: Swagger UI at http://localhost:8000/docs, ReDoc at http://localhost:8000/redoc, health check at http://localhost:8000/health.

## Layout

```
src/claimpulse/   application package (feature-oriented)
  main.py         FastAPI app factory
  config.py       settings from env (.env, .env.local)
  api/            routers (auth, users, payers, patients, claims, dashboard, lookups, health)
  schemas/        Pydantic request/response models
  services/       business rules (claim status lifecycle, dashboard queries)
  models.py       SQLAlchemy models for the existing tables
  errors.py       single error envelope {error: {code, message, requestId}}
tests/            pytest suite
```
