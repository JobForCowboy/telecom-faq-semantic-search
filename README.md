# Telecom FAQ Semantic Search

End-to-end MVP for telecom support where the user asks a question in a chat UI and the system returns the closest prepared FAQ answer using semantic search over embeddings.

## Stack

- `Next.js 15` frontend with a chat page and a local FAQ admin page.
- `FastAPI` backend for embedding, similarity search, thresholding, and query logging.
- `Postgres + pgvector` for FAQ storage, vector search, and fallback history.
- `EuroBERT/EuroBERT-210m` configured as the target embedding model. For local Docker demo the compose file defaults to `hash` embeddings so the stack can start without downloading model weights.

## Architecture

1. The user sends a question from the chat page.
2. FastAPI normalizes the text and turns it into an embedding.
3. The backend finds the closest FAQ using cosine similarity in `pgvector`.
4. If the best match is above the configured threshold, the prepared FAQ answer is returned.
5. If confidence is too low, the backend stores the request as an escalation and returns a fallback message.

## Project Layout

- [backend/app/main.py](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/backend/app/main.py)
- [frontend/app/page.tsx](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/frontend/app/page.tsx)
- [frontend/app/admin/page.tsx](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/frontend/app/admin/page.tsx)
- [docker-compose.yml](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/docker-compose.yml)

## Local Run

### Docker Compose demo

```bash
cp .env.example .env
docker compose up --build
```

This starts:

- frontend at `http://localhost:3000`
- backend at `http://localhost:8000`
- postgres at `localhost:5432`

Compose uses `EMBEDDING_BACKEND=hash` by default so the demo works without model downloads. To switch to the actual model, replace the backend environment with:

```env
EMBEDDING_BACKEND=transformers
EMBEDDING_MODEL_NAME=EuroBERT/EuroBERT-210m
EMBEDDING_DIM=768
```

### Manual backend run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
uvicorn app.main:app --app-dir backend --reload
```

If you want the actual `EuroBERT/EuroBERT-210m` backend locally instead of the lightweight hash demo mode, install the ML extras as well:

```bash
pip install -r backend/requirements-ml.txt
```

### Manual frontend run

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

## Configuration Hygiene

- Copy [`.env.example`](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/.env.example) to `.env` before running `docker compose`.
- Copy [`backend/.env.example`](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/backend/.env.example) to `backend/.env` for manual backend runs.
- Example files contain non-secret placeholders only. Real credentials must come from untracked `.env` files or CI/CD secrets.

## Seed Data

Sample FAQ and evaluation data live in:

- [data/faqs.json](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/data/faqs.json)
- [data/eval_queries.json](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/data/eval_queries.json)

To seed FAQ rows manually after the backend dependencies are installed:

```bash
python3 -m app.seed
```

Run it from the `backend` directory or set `--app-dir backend` in your command.

## API Surface

- `POST /api/chat/query`
- `GET /api/admin/faqs`
- `POST /api/admin/faqs`
- `PUT /api/admin/faqs/{faq_id}`
- `DELETE /api/admin/faqs/{faq_id}`
- `GET /api/admin/escalations`
- `GET /health`

## Tests

Basic unit tests cover deterministic hash embeddings and match/fallback threshold behavior:

```bash
pytest backend/tests
```
