from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes.agent import router as agent_router
from src.api.routes.papers import router as papers_router
from src.api.routes.projects import router as projects_router
from src.common.logging import setup_logger
from src.config.settings import get_settings
from src.storage.database import init_db

logger = setup_logger("hermes.api")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Hermes Research Agent database and services...")
    await init_db()
    yield
    logger.info("Shutting down Hermes API...")


app = FastAPI(
    title="Hermes Research Agent API",
    description="Academic-first research assistant API with multi-engine literature search, GROBID parsing, vector retrieval, and LangGraph multi-agent orchestration.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(papers_router)
app.include_router(projects_router)
app.include_router(agent_router)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "hermes-research-agent",
        "environment": settings.ENVIRONMENT,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
