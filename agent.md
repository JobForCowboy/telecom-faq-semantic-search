# Agent Notes

## Project Invariant

This project is retrieval-first. Preserve the semantic retrieval architecture and keep `transformers` as the default, high-significance ML backend.

The intended embedding model is `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. It is architecturally significant because the product behavior depends on multilingual sentence embeddings over FAQ variants stored in `pgvector`.

## Backend Rule

Do not silently switch `.env`, `.env.example`, or `backend/.env.example` to `EMBEDDING_BACKEND=hash`. The `hash` backend is allowed only for explicit offline diagnostics, smoke checks, or demos when the transformer model cannot be loaded.

If `transformers` fails because HuggingFace, DNS, network access, package installation, or the local model cache is unavailable, report that as an environment/model availability problem. Do not weaken the project architecture by making `hash` the default or documenting it as production-quality retrieval.

## Policy Layers

Out-of-domain filtering, domain rules, soft-match handling, normalization, clarification, and escalation review must remain explainable retrieval-aware policy layers. They may gate, contextualize, debug, or improve semantic retrieval, but they must not replace semantic ML retrieval.
