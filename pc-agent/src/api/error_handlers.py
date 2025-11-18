"""
Error handling middleware and custom exception handlers for FastAPI.

This module provides:
- Custom exception classes
- Global exception handlers
- Turkish error message translations
- Structured error responses
"""

import logging
import traceback
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# Turkish error messages dictionary
TURKISH_ERROR_MESSAGES = {
    # Connection errors
    "connection_failed": "Bağlantı başarısız oldu",
    "connection_timeout": "Bağlantı zaman aşımına uğradı",
    "connection_refused": "Bağlantı reddedildi",
    "connection_lost": "Bağlantı kesildi",

    # Authentication errors
    "authentication_required": "Kimlik doğrulama gerekli",
    "authentication_failed": "Kimlik doğrulama başarısız",
    "token_expired": "Oturum süresi doldu",
    "invalid_token": "Geçersiz oturum bilgisi",
    "invalid_credentials": "Geçersiz kimlik bilgileri",

    # Authorization errors
    "access_denied": "Erişim reddedildi",
    "insufficient_permissions": "Yetersiz yetkiler",
    "device_not_authorized": "Cihaz yetkili değil",

    # Command errors
    "command_failed": "Komut çalıştırılamadı",
    "command_timeout": "Komut zaman aşımına uğradı",
    "invalid_command": "Geçersiz komut",
    "command_not_understood": "Komut anlaşılamadı",

    # Audio errors
    "audio_processing_failed": "Ses işleme başarısız",
    "audio_quality_low": "Ses kalitesi düşük",
    "transcription_failed": "Ses metne dönüştürülemedi",

    # System errors
    "system_error": "Sistem hatası",
    "internal_server_error": "Sunucu hatası",
    "service_unavailable": "Hizmet kullanılamıyor",
    "resource_not_found": "Kaynak bulunamadı",
    "resource_conflict": "Kaynak çakışması",

    # Validation errors
    "validation_error": "Doğrulama hatası",
    "invalid_input": "Geçersiz girdi",
    "missing_parameter": "Eksik parametre",
    "invalid_format": "Geçersiz format",

    # Network errors
    "network_error": "Ağ hatası",
    "pc_offline": "Bilgisayar çevrimdışı",
    "pc_not_responding": "Bilgisayar yanıt vermiyor",

    # General
    "unknown_error": "Bilinmeyen hata",
    "operation_failed": "İşlem başarısız",
    "try_again": "Lütfen tekrar deneyin",
}


class PCControlException(Exception):
    """Base exception for PC Control Agent."""

    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
        turkish_message: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.turkish_message = turkish_message or TURKISH_ERROR_MESSAGES.get(
            error_code,
            "Bir hata oluştu"
        )
        super().__init__(message)


class AuthenticationException(PCControlException):
    """Authentication related errors."""

    def __init__(self, message: str, error_code: str = "authentication_failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details
        )


class AuthorizationException(PCControlException):
    """Authorization related errors."""

    def __init__(self, message: str, error_code: str = "access_denied", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details
        )


class CommandException(PCControlException):
    """Command execution errors."""

    def __init__(self, message: str, error_code: str = "command_failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )


class AudioProcessingException(PCControlException):
    """Audio processing errors."""

    def __init__(self, message: str, error_code: str = "audio_processing_failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details
        )


class ResourceNotFoundException(PCControlException):
    """Resource not found errors."""

    def __init__(self, message: str, error_code: str = "resource_not_found", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details
        )


class ConnectionException(PCControlException):
    """Connection related errors."""

    def __init__(self, message: str, error_code: str = "connection_failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details
        )


def create_error_response(
    error_code: str,
    message: str,
    turkish_message: str,
    status_code: int,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response.

    Args:
        error_code: Machine-readable error code
        message: English error message
        turkish_message: Turkish error message for user display
        status_code: HTTP status code
        details: Additional error details
        request_id: Request ID for tracking

    Returns:
        Dictionary with error response structure
    """
    return {
        "error": {
            "code": error_code,
            "message": message,
            "turkish_message": turkish_message,
            "status_code": status_code,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id
        }
    }


async def pc_control_exception_handler(request: Request, exc: PCControlException) -> JSONResponse:
    """Handle custom PC Control exceptions."""
    logger.error(
        f"PCControlException: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path
        }
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            error_code=exc.error_code,
            message=exc.message,
            turkish_message=exc.turkish_message,
            status_code=exc.status_code,
            details=exc.details,
            request_id=request.headers.get("X-Request-ID")
        )
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle HTTP exceptions."""
    logger.warning(
        f"HTTPException: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path
        }
    )

    turkish_message = TURKISH_ERROR_MESSAGES.get("unknown_error", "Bir hata oluştu")

    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(
            error_code=f"http_{exc.status_code}",
            message=str(exc.detail),
            turkish_message=turkish_message,
            status_code=exc.status_code,
            request_id=request.headers.get("X-Request-ID")
        )
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors."""
    logger.warning(
        f"ValidationError: {exc.errors()}",
        extra={
            "errors": exc.errors(),
            "body": exc.body,
            "path": request.url.path
        }
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=create_error_response(
            error_code="validation_error",
            message="Request validation failed",
            turkish_message=TURKISH_ERROR_MESSAGES["validation_error"],
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"validation_errors": exc.errors()},
            request_id=request.headers.get("X-Request-ID")
        )
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.error(
        f"Unexpected error: {str(exc)}",
        exc_info=True,
        extra={
            "exception_type": type(exc).__name__,
            "path": request.url.path,
            "traceback": traceback.format_exc()
        }
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=create_error_response(
            error_code="internal_server_error",
            message="An unexpected error occurred",
            turkish_message=TURKISH_ERROR_MESSAGES["internal_server_error"],
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"exception_type": type(exc).__name__} if logger.isEnabledFor(logging.DEBUG) else {},
            request_id=request.headers.get("X-Request-ID")
        )
    )


def configure_error_handlers(app: FastAPI) -> None:
    """
    Configure error handlers for the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # Custom exception handlers
    app.add_exception_handler(PCControlException, pc_control_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("Error handlers configured successfully")
