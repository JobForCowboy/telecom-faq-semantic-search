from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import admin, public
from .config import get_settings
from .db import SessionLocal, init_db
from .embeddings import EmbedderManager, EmbedderUnavailableError
from .schemas import HealthResponse
from .services.conversations import InMemoryConversationStore
from .seed import bootstrap_faqs, load_seed_dataset


settings = get_settings()
embedder_manager = EmbedderManager(settings)
conversation_store = InMemoryConversationStore(max_messages=settings.conversation_max_messages)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    embedder_manager.warmup()
    if embedder_manager.state.ready:
        with SessionLocal() as session:
            bootstrap_faqs(session, embedder_manager, load_seed_dataset())
    app.state.embedder_manager = embedder_manager
    app.state.conversation_store = conversation_store
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
