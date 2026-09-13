from typing import Optional
import httpx
from src.common.exceptions import IngestionError
from src.common.logging import setup_logger
from src.storage.object_store import ObjectStore

logger = setup_logger("hermes.ingestion.downloader")


class PDFDownloader:
    """Downloads academic paper PDFs and persists them into object storage."""

    def __init__(self, object_store: Optional[ObjectStore] = None) -> None:
        self.object_store = object_store or ObjectStore()

    async def download_and_store(self, pdf_url: str, bibtex_key: str) -> str:
        """Download PDF from public URL and store in MinIO/local storage."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/pdf,*/*",
        }
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                res = await client.get(pdf_url, headers=headers)
                if res.status_code != 200:
                    raise IngestionError(f"Failed to download PDF from {pdf_url}: Status {res.status_code}")

                data = res.content
                if len(data) < 1000 or not data.startswith(b"%PDF"):
                    raise IngestionError(f"Downloaded content from {pdf_url} is not a valid PDF file")

                storage_path = await self.object_store.save_pdf(bibtex_key, data)
                logger.info(f"Persisted PDF for {bibtex_key} at {storage_path}")
                return storage_path
        except Exception as e:
            logger.error(f"Error downloading PDF for {bibtex_key}: {e}")
            raise IngestionError(f"PDF download failed: {e}") from e
