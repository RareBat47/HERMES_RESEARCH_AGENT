class HermesException(Exception):
    """Base exception class for Hermes Research Agent."""
    pass


class ConnectorError(HermesException):
    """Raised when an academic literature connector fails."""
    pass


class IngestionError(HermesException):
    """Raised when PDF downloading or parsing fails."""
    pass


class GrobidServiceError(IngestionError):
    """Raised when GROBID service is unreachable or returns error."""
    pass


class StorageError(HermesException):
    """Raised when database or object storage operations fail."""
    pass


class VectorStoreError(HermesException):
    """Raised when Qdrant vector index operations fail."""
    pass


class AgentError(HermesException):
    """Raised when agent execution or tool invocation fails."""
    pass


class CitationVerificationError(AgentError):
    """Raised when claim citation verification fails."""
    pass
