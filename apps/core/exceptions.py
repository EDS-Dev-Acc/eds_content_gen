"""
Standardized error handling for EMCIP API.

Provides consistent error codes, exception classes, and response formatting.
"""

import logging
import traceback
import uuid
from enum import Enum
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


# =============================================================================
# Error Codes
# =============================================================================

class ErrorCode(str, Enum):
    """Standardized error codes for API responses."""
    
    # Validation errors (400)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_URL = "INVALID_URL"
    INVALID_FORMAT = "INVALID_FORMAT"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_VALUE = "INVALID_VALUE"
    
    # Authentication/Authorization (401/403)
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RATE_LIMITED = "RATE_LIMITED"
    
    # Resource errors (404/409)
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    DUPLICATE = "DUPLICATE"
    CONFLICT = "CONFLICT"
    
    # External service errors
    NETWORK_ERROR = "NETWORK_ERROR"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    DNS_ERROR = "DNS_ERROR"
    SSL_ERROR = "SSL_ERROR"
    CONNECTION_REFUSED = "CONNECTION_REFUSED"
    
    # Security errors
    SSRF_BLOCKED = "SSRF_BLOCKED"
    UNSAFE_URL = "UNSAFE_URL"
    CONTENT_TOO_LARGE = "CONTENT_TOO_LARGE"
    INVALID_CONTENT_TYPE = "INVALID_CONTENT_TYPE"
    
    # Processing errors
    PROCESSING_ERROR = "PROCESSING_ERROR"
    EXTRACTION_ERROR = "EXTRACTION_ERROR"
    LLM_ERROR = "LLM_ERROR"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    CRAWL_ERROR = "CRAWL_ERROR"
    
    # Task/Queue errors
    TASK_ERROR = "TASK_ERROR"
    TASK_TIMEOUT = "TASK_TIMEOUT"
    TASK_CANCELLED = "TASK_CANCELLED"
    
    # Database errors
    DATABASE_ERROR = "DATABASE_ERROR"
    INTEGRITY_ERROR = "INTEGRITY_ERROR"
    
    # Server errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


# =============================================================================
# Error Response Schema
# =============================================================================

@dataclass
class ErrorDetail:
    """Detailed error information."""
    code: ErrorCode
    message: str
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "code": self.code.value if isinstance(self.code, ErrorCode) else self.code,
            "message": self.message,
        }
        if self.field:
            result["field"] = self.field
        if self.details:
            result["details"] = self.details
        return result


@dataclass
class ErrorResponse:
    """Standardized error response."""
    error: ErrorDetail
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.error.to_dict(),
            "request_id": self.request_id,
        }
    
    def to_response(self, status_code: int = 400) -> Response:
        return Response(self.to_dict(), status=status_code)


# =============================================================================
# Custom Exceptions
# =============================================================================

class EMCIPException(APIException):
    """Base exception for EMCIP API errors."""
    
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = ErrorCode.INTERNAL_ERROR
    default_detail = "An error occurred"
    
    def __init__(
        self,
        message: Optional[str] = None,
        code: Optional[ErrorCode] = None,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
    ):
        self.message = message or self.default_detail
        self.error_code = code or self.error_code
        self.field = field
        self.error_details = details or {}
        
        if status_code:
            self.status_code = status_code
        
        super().__init__(detail=self.message)
    
    def get_error_response(self, request_id: Optional[str] = None) -> ErrorResponse:
        return ErrorResponse(
            error=ErrorDetail(
                code=self.error_code,
                message=self.message,
                field=self.field,
                details=self.error_details if self.error_details else None,
            ),
            request_id=request_id or str(uuid.uuid4()),
        )


class ValidationError(EMCIPException):
    """Validation error."""
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = ErrorCode.VALIDATION_ERROR
    default_detail = "Validation failed"


class NotFoundError(EMCIPException):
    """Resource not found."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = ErrorCode.NOT_FOUND
    default_detail = "Resource not found"


class DuplicateError(EMCIPException):
    """Duplicate resource."""
    status_code = status.HTTP_409_CONFLICT
    error_code = ErrorCode.DUPLICATE
    default_detail = "Resource already exists"


class PermissionDeniedError(EMCIPException):
    """Permission denied."""
    status_code = status.HTTP_403_FORBIDDEN
    error_code = ErrorCode.PERMISSION_DENIED
    default_detail = "Permission denied"


class SSRFBlockedError(EMCIPException):
    """SSRF protection blocked request."""
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = ErrorCode.SSRF_BLOCKED
    default_detail = "URL blocked for security reasons"


class NetworkError(EMCIPException):
    """Network/external service error."""
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = ErrorCode.NETWORK_ERROR
    default_detail = "Network error occurred"


class TimeoutError(EMCIPException):
    """Timeout error."""
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    error_code = ErrorCode.NETWORK_TIMEOUT
    default_detail = "Request timed out"


class BudgetExceededError(EMCIPException):
    """LLM budget exceeded."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = ErrorCode.BUDGET_EXCEEDED
    default_detail = "LLM budget exceeded"


class ProcessingError(EMCIPException):
    """Processing/extraction error."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = ErrorCode.PROCESSING_ERROR
    default_detail = "Processing failed"


# =============================================================================
# Exception Handler
# =============================================================================

def get_request_id(request) -> str:
    """Get or generate request ID from request."""
    if hasattr(request, 'request_id'):
        return request.request_id
    return str(uuid.uuid4())


def emcip_exception_handler(exc, context):
    """
    Custom exception handler for EMCIP API.
    
    Converts all exceptions to standardized error response format.
    """
    request = context.get('request')
    request_id = get_request_id(request) if request else str(uuid.uuid4())
    
    # Handle our custom exceptions
    if isinstance(exc, EMCIPException):
        error_response = exc.get_error_response(request_id)
        logger.warning(
            f"API Error: {exc.error_code.value}",
            extra={
                "request_id": request_id,
                "error_code": exc.error_code.value,
                "message": exc.message,
                "field": exc.field,
                "status_code": exc.status_code,
            }
        )
        return error_response.to_response(exc.status_code)
    
    # Handle Django validation errors
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, 'message_dict'):
            details = exc.message_dict
            message = "Validation failed"
        else:
            details = {"errors": exc.messages}
            message = exc.messages[0] if exc.messages else "Validation failed"
        
        error_response = ErrorResponse(
            error=ErrorDetail(
                code=ErrorCode.VALIDATION_ERROR,
                message=message,
                details=details,
            ),
            request_id=request_id,
        )
        return error_response.to_response(status.HTTP_400_BAD_REQUEST)
    
    # Handle 404
    if isinstance(exc, Http404):
        error_response = ErrorResponse(
            error=ErrorDetail(
                code=ErrorCode.NOT_FOUND,
                message=str(exc) if str(exc) else "Resource not found",
            ),
            request_id=request_id,
        )
        return error_response.to_response(status.HTTP_404_NOT_FOUND)
    
    # Handle requests library exceptions
    import requests as req_lib
    if isinstance(exc, req_lib.exceptions.Timeout):
        error_response = ErrorResponse(
            error=ErrorDetail(
                code=ErrorCode.NETWORK_TIMEOUT,
                message="Request timed out",
            ),
            request_id=request_id,
        )
        return error_response.to_response(status.HTTP_504_GATEWAY_TIMEOUT)
    
    if isinstance(exc, req_lib.exceptions.ConnectionError):
        error_response = ErrorResponse(
            error=ErrorDetail(
                code=ErrorCode.CONNECTION_REFUSED,
                message="Could not connect to remote server",
            ),
            request_id=request_id,
        )
        return error_response.to_response(status.HTTP_502_BAD_GATEWAY)
    
    if isinstance(exc, req_lib.exceptions.SSLError):
        error_response = ErrorResponse(
            error=ErrorDetail(
                code=ErrorCode.SSL_ERROR,
                message="SSL certificate verification failed",
            ),
            request_id=request_id,
        )
        return error_response.to_response(status.HTTP_502_BAD_GATEWAY)
    
    # Handle SSRF errors
    from apps.core.security import SSRFError
    if isinstance(exc, SSRFError):
        error_response = ErrorResponse(
            error=ErrorDetail(
                code=ErrorCode.SSRF_BLOCKED,
                message=str(exc),
            ),
            request_id=request_id,
        )
        return error_response.to_response(status.HTTP_400_BAD_REQUEST)
    
    # Use DRF's default handler for standard exceptions
    response = drf_exception_handler(exc, context)
    
    if response is not None:
        # Wrap DRF response in our format
        error_code = ErrorCode.VALIDATION_ERROR
        if response.status_code == 401:
            error_code = ErrorCode.AUTHENTICATION_REQUIRED
        elif response.status_code == 403:
            error_code = ErrorCode.PERMISSION_DENIED
        elif response.status_code == 404:
            error_code = ErrorCode.NOT_FOUND
        elif response.status_code == 429:
            error_code = ErrorCode.RATE_LIMITED
        elif response.status_code >= 500:
            error_code = ErrorCode.INTERNAL_ERROR
        
        # Extract message from DRF response
        if isinstance(response.data, dict):
            if 'detail' in response.data:
                message = str(response.data['detail'])
                details = None
            else:
                message = "Validation failed"
                details = response.data
        elif isinstance(response.data, list):
            message = response.data[0] if response.data else "Error"
            details = {"errors": response.data}
        else:
            message = str(response.data)
            details = None
        
        error_response = ErrorResponse(
            error=ErrorDetail(
                code=error_code,
                message=message,
                details=details,
            ),
            request_id=request_id,
        )
        return error_response.to_response(response.status_code)
    
    # Unhandled exception - log and return generic error
    logger.exception(
        f"Unhandled exception: {type(exc).__name__}",
        extra={
            "request_id": request_id,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "traceback": traceback.format_exc(),
        }
    )
    
    error_response = ErrorResponse(
        error=ErrorDetail(
            code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred",
        ),
        request_id=request_id,
    )
    return error_response.to_response(status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# Response Helpers
# =============================================================================

def error_response(
    code: ErrorCode,
    message: str,
    status_code: int = 400,
    field: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> Response:
    """
    Create a standardized error response.
    
    Use this helper for manual error returns in views to maintain consistency
    with the exception handler's response format.
    
    Args:
        code: ErrorCode enum value
        message: Human-readable error message
        status_code: HTTP status code (default 400)
        field: Optional field name for field-specific errors
        details: Optional additional error details
        request_id: Optional request ID (auto-generated if not provided)
    
    Returns:
        Response with standardized error format
    """
    from apps.core.middleware import get_request_id
    
    if request_id is None:
        request_id = get_request_id() or str(uuid.uuid4())
    
    response = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            field=field,
            details=details,
        ),
        request_id=request_id,
    )
    return response.to_response(status_code)


def success_response(
    data: Any = None,
    message: Optional[str] = None,
    status_code: int = 200,
) -> Response:
    """Create a standardized success response."""
    response_data = {}
    
    if data is not None:
        if isinstance(data, dict):
            response_data.update(data)
        else:
            response_data['data'] = data
    
    if message:
        response_data['message'] = message
    
    return Response(response_data, status=status_code)


def created_response(
    data: Any = None,
    message: str = "Created successfully",
) -> Response:
    """Create a 201 Created response."""
    return success_response(data=data, message=message, status_code=201)


def bulk_response(
    succeeded: List[Dict],
    failed: List[Dict],
    message: Optional[str] = None,
) -> Response:
    """Create a bulk operation response with partial success breakdown."""
    total = len(succeeded) + len(failed)
    
    response_data = {
        "total": total,
        "succeeded_count": len(succeeded),
        "failed_count": len(failed),
        "succeeded": succeeded,
        "failed": failed,
    }
    
    if message:
        response_data["message"] = message
    else:
        response_data["message"] = f"{len(succeeded)} of {total} operations succeeded"
    
    # Use 200 for all success, 207 for partial success
    status_code = 200 if not failed else 207
    
    return Response(response_data, status=status_code)
