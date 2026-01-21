from typing import Optional


class BaseAppException(Exception):
    """Base exception for the application."""

    def __init__(self, message: str, details: Optional[str] = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


class PrimeTagAPIError(BaseAppException):
    """Exception raised when PrimeTag API calls fail."""

    def __init__(self, message: str, response_body: Optional[str] = None):
        super().__init__(message, response_body)
        self.response_body = response_body


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
