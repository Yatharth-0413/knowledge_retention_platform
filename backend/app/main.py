from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401  (registers all ORM models with the mapper)
from app.analytics.router import router as analytics_router
from app.auth.router import router as auth_router
from app.chat.router import router as chat_router
from app.config import settings
from app.database import Base, engine
from app.documents.router import router as documents_router
from app.graph.router import router as graph_router
from app.knowledge.router import router as knowledge_router
from app.teams.router import router as teams_router
from app.users.router import router as users_router

app = FastAPI(title="Knowledge Retention Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(teams_router)
app.include_router(users_router)
app.include_router(documents_router)
app.include_router(knowledge_router)
app.include_router(analytics_router)
app.include_router(chat_router)
app.include_router(graph_router)
