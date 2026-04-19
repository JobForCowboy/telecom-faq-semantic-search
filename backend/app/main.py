from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from .api import admin, public
from .config import get_settings
from .db import SessionLocal, init_db
from .embeddings import EmbedderManager, EmbedderUnavailableError
from .models import FAQ
from .schemas import HealthResponse
from .seed import load_seed_dataset


settings = get_settings()
embedder_manager = EmbedderManager(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    embedder_manager.warmup()
    if embedder_manager.state.ready:
        with SessionLocal() as session:
            has_rows = session.scalar(select(FAQ.id).limit(1)) is not None
            if not has_rows:
                for entry in load_seed_dataset():
                    question = entry["question"].strip()
                    session.add(
                        FAQ(
                            question=question,
                            answer=entry["answer"].strip(),
                            embedding=embedder_manager.embed(question),
                            is_active=True,
                        )
                    )
                session.commit()
    app.state.embedder_manager = embedder_manager
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(public.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    ready = embedder_manager.state.ready
    return HealthResponse(
        status="ok" if ready else "degraded",
        embedding_backend=settings.embedding_backend,
        model_name=settings.embedding_model_name,
        model_ready=ready,
        detail=embedder_manager.state.detail,
    )


@app.exception_handler(EmbedderUnavailableError)
async def embedder_error_handler(_, exc: EmbedderUnavailableError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})
