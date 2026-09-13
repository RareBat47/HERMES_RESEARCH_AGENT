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
    source: str = "unknown"  # arxiv, semanticscholar, pubmed, crossref, openalex


class SearchQuery(BaseModel):
    query: str
    sources: List[str] = Field(default_factory=lambda: ["arxiv", "semanticscholar", "pubmed", "openalex"])
    max_results_per_source: int = 5
    year_start: Optional[int] = None
    year_end: Optional[int] = None


class PaperSectionContent(BaseModel):
    section_name: str
    heading: str
    text_content: str
    page_number: Optional[int] = 1
    token_count: Optional[int] = 0


class PaperChunkModel(BaseModel):
    paper_id: int
    section_id: Optional[int] = None
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    page_number: int
    qdrant_point_id: str
    bibtex_key: str
    section_name: str
    heading: str


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


class CitationReference(BaseModel):
    bibtex_key: str
    chunk_id: Optional[int] = None
    qdrant_point_id: Optional[str] = None
    exact_quote: str
    section_hint: Optional[str] = None
    page_hint: Optional[int] = None
    confidence_score: float = 1.0


class GroundedAnswer(BaseModel):
    question: str
    answer: str
    is_grounded: bool
    citations: List[CitationReference] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    proposed_search_queries: List[str] = Field(default_factory=list)


class CitationVerificationResult(BaseModel):
    claim: str
    bibtex_key: str
    grounding_passage: str
    similarity_score: float = 0.0
    confidence_score: float = 0.0
    is_verified: bool
    critique: str
