import asyncio
from celery import Celery
from src.config.settings import get_settings
from src.worker.tasks import PaperIngestionService

settings = get_settings()

celery_app = Celery(
    "hermes_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="tasks.ingest_paper")
def ingest_paper_task(identifier: str, project_id: int = None) -> dict:
    service = PaperIngestionService()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        paper = loop.run_until_complete(service.ingest(identifier, project_id))
        return {
            "status": "success",
            "paper_id": paper.id,
            "bibtex_key": paper.bibtex_key,
            "title": paper.title,
        }
    finally:
        loop.close()
