from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Author(BaseModel):
    name: str
    affiliation: Optional[str] = None
    email: Optional[str] = None


class PaperMetadata(BaseModel):
    bibtex_key: str
    title: str
    authors: List[Author] = Field(default_factory=list)
    abstract: str = ""
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    pmid: Optional[str] = None
    citation_count: int = 0
    pdf_url: Optional[str] = None
    source: str = "unknown"  # arxiv, semanticscholar, pubmed, crossref


class SearchQuery(BaseModel):
    query: str
    sources: List[str] = Field(default_factory=lambda: ["arxiv", "semanticscholar"])
    max_results_per_source: int = 5
    year_start: Optional[int] = None
    year_end: Optional[int] = None


class PaperSectionContent(BaseModel):
    section_name: str
    heading: str
    text_content: str
    page_number: Optional[int] = 1
    token_count: Optional[int] = 0


class StructuredPaperNote(BaseModel):
    paper_bibtex_key: str
    problem: str = Field(description="The central scientific question or problem addressed")
    key_idea: str = Field(description="Core intuition or methodological insight")
    method_details: str = Field(description="Detailed algorithm, architecture, or workflow")
    datasets: List[str] = Field(default_factory=list, description="Benchmarks or datasets used")
    metrics: List[str] = Field(default_factory=list, description="Evaluation metrics")
    results: str = Field(description="Key numerical or qualitative findings against baselines")
    limitations: str = Field(description="Explicit or implicit weaknesses and caveats")
    reproducibility_notes: str = Field(description="Code availability, hyperparameters, hardware")
    important_quotes: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Exact quotes with section and page number"
    )


class CitationVerificationResult(BaseModel):
    claim: str
    bibtex_key: str
    grounding_passage: str
    similarity_score: float = 0.0
    confidence_score: float = 0.0
    is_verified: bool
    critique: str
