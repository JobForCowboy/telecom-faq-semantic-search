# Repository Guidelines

## Project Structure & Module Organization

This repository contains a retrieval-first telecom FAQ assistant. Backend source lives in `backend/app`, with API routers in `backend/app/api`, business logic in `backend/app/services`, and seed/eval utilities in `backend/app/seed.py` and `backend/app/eval.py`. Backend tests live in `backend/tests`.

The frontend is a Next.js app under `frontend`, with routes in `frontend/app`, shared UI in `frontend/components`, and API helpers in `frontend/lib`. Data assets live in `data`: FAQ seed content in `data/kb`, normalization dictionaries in `data/normalization`, domain rules in `data/domain`, and eval datasets in `data/eval`. Infrastructure files include `docker-compose.yml` and `infra/postgres`.

## Build, Test, and Development Commands

- `cp .env.example .env`: create local runtime configuration.
- `docker compose up --build`: build and run frontend, backend, and Postgres.
- `docker compose build backend`: rebuild the backend image after dependency or backend changes.
- `uvicorn app.main:app --app-dir backend --reload`: run the backend locally.
- `cd frontend && npm run dev`: run the frontend at `http://localhost:3000`.
- `pytest backend/tests`: run backend unit tests after installing `backend/requirements-dev.txt`.
- `python3 -m app.eval smoke --base-url http://localhost:8000`: run API smoke checks.

## Coding Style & Naming Conventions

Python code uses 4-space indentation, type hints, Pydantic schemas, and small service classes/functions. Keep FastAPI routers thin; put retrieval, dialogue, admin, and policy logic in `backend/app/services`.

Frontend code uses TypeScript React components with kebab-case filenames such as `admin-retrieval-debug.tsx`. Prefer clear prop names and keep API shapes centralized in `frontend/lib/api.ts`.

## Testing Guidelines

Backend tests use `pytest`; name files `test_*.py` and test functions `test_*`. Add focused tests when changing retrieval decisions, normalization, domain filtering, seeding, or eval behavior. For user-visible retrieval behavior, also update or run datasets in `data/eval`.

## Commit & Pull Request Guidelines

Recent commits use short imperative summaries, for example `add dialogue retrieval workflow and admin debug`. Keep commits scoped to one concern. Pull requests should include a concise description, test/eval commands run, linked issue if applicable, and screenshots for UI changes.

## Architecture & Configuration Notes

Preserve the retrieval-first architecture. `EMBEDDING_BACKEND=transformers` is the default, using `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. The `hash` backend is only for explicit offline smoke/debug runs and must not be documented or configured as production-quality retrieval. Treat model download/cache failures as environment issues.
