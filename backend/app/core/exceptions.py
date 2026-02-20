from typing import Optional


class BaseAppException(Exception):
    """Base exception for the application."""

    def __init__(self, message: str, details: Optional[str] = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


class PrimeTagAPIError(BaseAppException):
    """Exception raised when PrimeTag API calls fail."""

    def __init__(
        self,
        message: str,
        response_body: Optional[str] = None,
        status_code: Optional[int] = None,
        is_timeout: bool = False,
        retry_after: Optional[float] = None,
    ):
        super().__init__(message, response_body)
        self.response_body = response_body
        self.status_code = status_code
        self.is_timeout = is_timeout
        # Retry-After delay in seconds (populated from HTTP header on 429 responses)
        self.retry_after = retry_after

    @property
    def is_retryable(self) -> bool:
        """
        Determine if this error is retryable.
        Retryable errors: timeouts, rate limits (429), server errors (5xx).
        """
        if self.is_timeout:
            return True
        if self.status_code is not None:
            # 429 = rate limited, 5xx = server errors
            return self.status_code == 429 or self.status_code >= 500
        return False


class LLMParsingError(BaseAppException):
    """Exception raised when LLM fails to parse a query."""

    def __init__(self, message: str, original_query: Optional[str] = None):
        super().__init__(message, original_query)
        self.original_query = original_query


class SearchError(BaseAppException):
    """Exception raised during search operations."""
    pass


class ExportError(BaseAppException):
    """Exception raised during export operations."""
    pass


class CacheError(BaseAppException):
    """Exception raised during cache operations."""
    pass
