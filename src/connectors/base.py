from abc import ABC, abstractmethod
from typing import List, Optional
import re
from src.common.models import PaperMetadata, SearchQuery


def generate_bibtex_key(author_name: str, year: Optional[int], title: str) -> str:
    """Generate standardized academic BibTeX key: [FirstAuthorLastname][Year][FirstKeyword]."""
    clean_author = "Anonymous"
    if author_name:
        parts = author_name.strip().split()
        clean_author = parts[-1] if parts else "Anonymous"
    clean_author = re.sub(r"[^a-zA-Z]", "", clean_author)

    clean_year = str(year) if year else "2024"

    clean_title_word = "Paper"
    if title:
        words = [w for w in re.sub(r"[^a-zA-Z0-9\s]", "", title).split() if len(w) > 3]
        if words:
            clean_title_word = words[0].capitalize()

    return f"{clean_author}{clean_year}{clean_title_word}"


class BaseConnector(ABC):
    """Abstract base class for academic literature connectors."""

    name: str = "base"

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> List[PaperMetadata]:
        """Search literature repository and return standardized paper metadata."""
        pass

    @abstractmethod
    async def get_by_id(self, identifier: str) -> Optional[PaperMetadata]:
        """Fetch full paper metadata by repository-specific identifier (arXiv ID, DOI, PMID)."""
        pass
