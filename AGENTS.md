# AGENTS.md — rules for every coding agent in this repo

This repo is built mostly by AI agents (Google Jules) and merged by a human.
Every change must leave `main` deployable.

## Layout
- `backend/` FastAPI app (Python 3.12). Entry: `backend/app/main.py`. Tests: `backend/tests/`.
- `backend/migrations/` plain, numbered SQL files (`0001_init.sql`, `0002_...sql`). Never edit an applied migration; add a new one.
- `frontend/` Next.js (App Router, TypeScript). Pages under `frontend/app/`.
- MySQL 8 is the only database. Redis may be added later for caching/queues.

## Commands
```bash
# backend
cd backend && pip install -r requirements.txt && pytest -q
# frontend
cd frontend && npm ci && npm run lint && npm run build
# everything locally
docker compose up --build
```

## Conventions
- Backend: routers in `backend/app/routers/<area>.py`, mounted under `/api`. Pydantic models for every request and response.
- Use parameterized SQL only (no string-formatted queries). Read `DATABASE_URL` from the environment.
- Frontend calls the backend through `NEXT_PUBLIC_API_URL`. No secrets in frontend code.
- Every new endpoint gets at least one test for success and one for a validation error.
- Keep PRs small and focused on the issue you were given. No drive-by refactors.
- Never commit secrets, `.env` files, or generated build output.
- Write the PR description as: what changed, why, how it was tested, and the issue id.

## Definition of done
CI is green (backend tests, frontend lint and build), the AI review has no blocking findings, and the change matches the issue's acceptance criteria.
