# Telecom FAQ Semantic Search

End-to-end MVP for telecom support where the user asks a question in a chat UI and the system returns the closest prepared FAQ answer using semantic retrieval over local embeddings.

The current version also supports short dialogue mode without changing the retrieval-first core:

- short in-memory conversation context keyed by `conversation_id`
- retrieval-aware follow-up handling for brief turns like `домашний`
- lightweight clarification questions for ambiguous retrieval results
- explicit reset flow in the UI and API

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
- a short-context dialogue layer for clarification and follow-up resolution
- retrieval-aware domain and out-of-domain policy layers
- an escalation review loop that feeds missed queries back into the KB

### How retrieval works

1. The user sends a raw question from the chat UI.
2. FastAPI loads recent dialogue context for `conversation_id`.
3. For short follow-up turns, the backend builds a contextualized retrieval query.
4. FastAPI normalizes the contextualized query.
5. The backend creates an embedding from the normalized text.
6. The query is matched against `faq_variants` in `pgvector`.
7. If the top candidates are ambiguous, the backend can return a clarification question.
8. Otherwise the best variant resolves to one canonical FAQ entry.
9. If the score is above the configured threshold, the canonical answer is returned.
10. Otherwise, the query is stored as an escalation with both raw and normalized contextualized text.

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

## ML Backend Policy

`transformers` is the real/default embedding backend for this project. The intended semantic retrieval model is `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`; it is not an incidental implementation detail, because retrieval quality depends on multilingual sentence embeddings rather than lexical hashes.

The domain filter, out-of-domain policy, normalization, soft-match handling, and clarification logic are retrieval-aware policy layers. They make semantic retrieval safer and more explainable, but they are not replacements for ML retrieval and should not be used to weaken the retrieval-first architecture.

`hash` is only a degraded offline fallback for explicit smoke checks, demos, or diagnostics when the transformer model cannot be loaded. It is not production-quality retrieval and should not be treated as an equivalent mode. Do not silently switch `.env`, `.env.example`, or `backend/.env.example` to `EMBEDDING_BACKEND=hash`; if `transformers` fails because HuggingFace, DNS, network access, or the local model cache is unavailable, report that as an environment/model availability problem.

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

The default backend is `EMBEDDING_BACKEND=transformers`. On first startup, the backend may need HuggingFace/network access to download `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, or a pre-populated local model cache. If that model cannot be loaded, fix the environment or cache instead of changing the project default. Use `EMBEDDING_BACKEND=hash` only for intentional offline smoke/debug runs.

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

Without the ML extras and model availability, `transformers` cannot provide semantic retrieval. That is an environment setup issue; `hash` remains only an explicit degraded fallback for offline diagnostics.

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
- `POST /api/chat/query` for smoke, single-turn, and dialogue checks
- `POST /api/chat/reset` for dialogue eval setup
- `POST /api/admin/retrieval-debug` for optional fail-case analysis

Datasets:

- [data/eval/main.json](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/data/eval/main.json)
- [data/eval/hard_cases.json](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/data/eval/hard_cases.json)
- [data/eval/dialogue.json](/home/kia/Documents/work-7rl/AILAB/telecom-faq-semantic-search/data/eval/dialogue.json)

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

Dialogue dataset shape:

```json
{
  "conversation": [
    { "role": "user", "text": "не работает интернет" },
    { "role": "assistant", "text": "Уточните, домашний или мобильный интернет?" },
    { "role": "user", "text": "домашний" }
  ],
  "expected_status": "matched",
  "expected_canonical_question": "Почему не работает домашний интернет?",
  "case_type": "dialogue"
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
- short dialogue flows with clarification + follow-up resolution
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
- `dialogue_accuracy`
- `clarification_success_rate`
- `followup_resolution_rate`
- `false_clarifications`
- `false_escalations`
- `false_matches`
- `top_3_hit_rate`
- `normalization_sensitive_accuracy`

The CLI exits with a non-zero status when smoke fails or when any eval case fails, which makes it usable in a repeatable regression loop.

## Admin Workflow

### Retrieval debug

`/admin/debug` shows:

- conversation id
- recent messages
- original query
- contextualized query
- normalized contextualized query
- threshold
- top-3 matches
- matched variant
- canonical FAQ
- score
- domain decision
- out-of-domain decision trace
- follow-up detection
- clarification trigger
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
- `POST /api/chat/reset`
- `GET /api/admin/faqs`
- `POST /api/admin/faqs`
- `PUT /api/admin/faqs/{faq_id}`
- `DELETE /api/admin/faqs/{faq_id}`
- `POST /api/admin/retrieval-debug`
- `GET /api/admin/escalations`
- `GET /health`

`POST /api/admin/retrieval-debug` returns debug-only retrieval metadata including recent messages, raw query, contextualized query, normalized contextualized query, threshold, top matches, and the domain/out-of-domain decision trace.

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
