# Telecom FAQ Semantic Search

End-to-end MVP for telecom support where the user asks a question in a chat UI and the system returns the closest prepared FAQ answer using semantic retrieval over local embeddings.

## Stack

- `Next.js 15` frontend with chat, FAQ admin, retrieval debug, and escalation review pages.
- `FastAPI` backend for normalization, embeddings, cosine similarity search, thresholding, and query logging.
- `Postgres + pgvector` for FAQ storage, variant embeddings, and escalation history.
- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` as the default CPU-friendly local embedding model.

## Retrieval-First Design

This iteration improves ML value without fine-tuning and without changing the core architecture.

The system is strengthened through:

- a retrieval-friendly knowledge base with canonical FAQ entries and many user-like variants
- a shared normalization pipeline for query, seed, admin updates, and eval
- a larger eval set with abbreviations, typos, colloquial requests, short queries, and irrelevant prompts
- an escalation review loop that feeds missed queries back into the KB

### How retrieval works

1. The user sends a raw question from the chat UI.
2. FastAPI normalizes the text.
3. The backend creates an embedding from the normalized text.
4. The query is matched against `faq_variants` in `pgvector`.
5. The best variant resolves to one canonical FAQ entry.
6. If the score is above the configured threshold, the canonical answer is returned.
7. Otherwise, the query is stored as an escalation with both raw and normalized text.

### How normalization works

Normalization is lightweight and transparent. The same pipeline is used everywhere:

- lowercase
- `ё -> е`
- whitespace collapse
- soft punctuation cleanup
- dictionary-based abbreviation expansion
- dictionary-based typo and phrase correction

Rules live in:

- [data/normalization/abbreviations.json](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/data/normalization/abbreviations.json)
- [data/normalization/typos.json](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/data/normalization/typos.json)

Examples:

- `лк -> личный кабинет`
- `инет -> интернет`
- `мобила -> мобильная связь`
- `балансик -> баланс`
- `личная кабина -> личный кабинет`
- `интернета нету -> нет интернета`

### Why variants matter

The embedding model is kept local and unchanged. Retrieval quality is improved by designing the KB for matching real user language rather than only storing clean canonical phrasing.

Each FAQ keeps:

- one `canonical_question`
- one `answer`
- a retrieval-oriented list of `variants`

Variants are intentionally noisy and user-like:

- normal formulations
- short formulations
- colloquial forms
- abbreviations
- common typos
- slightly dirty support-chat wording

## Project Layout

- [backend/app/services/chat.py](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/backend/app/services/chat.py)
- [backend/app/services/admin.py](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/backend/app/services/admin.py)
- [backend/app/normalization.py](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/backend/app/normalization.py)
- [data/kb/faqs.json](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/data/kb/faqs.json)
- [data/eval/main.json](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/data/eval/main.json)
- [data/eval/hard_cases.json](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/data/eval/hard_cases.json)

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

### Manual backend run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
uvicorn app.main:app --app-dir backend --reload
```

If you want the actual embedding backend locally, install the ML extras as well:

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

## Seed Data

Seed assets are split by purpose:

- [data/kb/faqs.json](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/data/kb/faqs.json)
- [data/normalization/abbreviations.json](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/data/normalization/abbreviations.json)
- [data/normalization/typos.json](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/data/normalization/typos.json)

To seed FAQ rows manually after backend dependencies are installed:

```bash
python3 -m app.seed
```

Seed bootstrap is idempotent for canonical FAQs from the seed file:

- new seed FAQ entries are created
- existing seeded canonical FAQs are updated with the latest answer, active flag, and variants
- FAQ entries not present in the seed file are preserved

## Eval

Evaluation is API-based. The backend HTTP API is the single evaluation surface:

- `GET /health` for readiness
- `POST /api/chat/query` for smoke and pass/fail checks
- `POST /api/admin/retrieval-debug` for optional fail-case analysis

Datasets:

- [data/eval/main.json](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/data/eval/main.json)
- [data/eval/hard_cases.json](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/data/eval/hard_cases.json)

Target dataset shape:

```json
{
  "question": "У меня пропал домашний интернет",
  "expected_status": "matched",
  "expected_faq_id": 1,
  "case_type": "main",
  "notes": "baseline",
  "normalization_sensitive": false
}
```

The runner is backward-compatible with the older dataset fields:

- `query`
- `expected_canonical_question`
- `category`

Coverage includes:

- standard matched cases
- hard cases with abbreviations, typos, and colloquial phrasing
- irrelevant prompts that should escalate
- normalization-sensitive slices such as `лк -> личный кабинет` and `инет -> интернет`

Smoke check:

```bash
python3 -m app.eval smoke --base-url http://localhost:8000
```

Main eval:

```bash
python3 -m app.eval run --base-url http://localhost:8000 --dataset data/eval/main.json --mode summary
```

Hard cases with fail-case debug:

```bash
python3 -m app.eval run \
  --base-url http://localhost:8000 \
  --dataset data/eval/hard_cases.json \
  --mode detailed \
  --with-debug
```

Run both datasets together and save raw responses:

```bash
python3 -m app.eval run \
  --base-url http://localhost:8000 \
  --dataset data/eval/main.json \
  --dataset data/eval/hard_cases.json \
  --save-responses
```

The runner writes:

- `reports/eval_main_results.json`
- `reports/eval_hard_cases_results.json`
- `reports/eval_summary.json`
- `reports/eval_summary.md`

Reported metrics include:

- `total_cases`
- `passed_cases`
- `accuracy`
- `matched_accuracy`
- `escalation_accuracy`
- `false_escalations`
- `false_matches`
- `top_3_hit_rate`
- `normalization_sensitive_accuracy`

The CLI exits with a non-zero status when smoke fails or when any eval case fails, which makes it usable in a repeatable regression loop.

## Admin Workflow

### Retrieval debug

`/admin/debug` shows:

- original query
- normalized query
- threshold
- top-3 matches
- matched variant
- canonical FAQ
- score
- final threshold decision

This is intended as a data improvement tool, not just a demo screen.

### Escalation review loop

Escalations are not a dead end. They are the recommended maintenance loop for the KB:

1. Review escalated queries in `/admin/escalations`.
2. Open the query in retrieval debug.
3. If the intent belongs to an existing FAQ, add the query as a new variant.
4. If the intent is new, create a new canonical FAQ entry.
5. Re-seed or update the FAQ entry and rerun eval.

This project is intentionally improved through data and preprocessing, not through fine-tuning at this stage.

## API Surface

- `POST /api/chat/query`
- `GET /api/admin/faqs`
- `POST /api/admin/faqs`
- `PUT /api/admin/faqs/{faq_id}`
- `DELETE /api/admin/faqs/{faq_id}`
- `POST /api/admin/retrieval-debug`
- `GET /api/admin/escalations`
- `GET /health`

`POST /api/admin/retrieval-debug` returns debug-only retrieval metadata including raw query, normalized query, threshold, and top matches.

## Tests

Run the backend unit tests:

```bash
pytest backend/tests
```

Recommended retrieval regression workflow:

```bash
python3 -m app.eval smoke --base-url http://localhost:8000
python3 -m app.eval run --base-url http://localhost:8000 --dataset data/eval/main.json --mode summary
python3 -m app.eval run --base-url http://localhost:8000 --dataset data/eval/hard_cases.json --mode summary
python3 -m app.eval run --base-url http://localhost:8000 --dataset data/eval/hard_cases.json --mode detailed --with-debug
```
