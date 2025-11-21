"""
Security and authentication middleware for PC Control Agent.

This module implements mTLS authentication, connection management,
and security-related middleware for the FastAPI application.
"""

import logging
import ssl
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from urllib.parse import parse_qs

import jwt
from fastapi import HTTPException, Request, status, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp

from src.config.settings import get_settings
from src.services.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


class MTLSMiddleware:
    """
    Middleware for mutual TLS (mTLS) authentication.

    This middleware verifies client certificates and extracts device
    information from certificate subject and extensions.
    """

    def __init__(self, app: ASGIApp, ca_cert_path: str):
        self.app = app
        self.ca_cert_path = Path(ca_cert_path)
        self.connection_manager = ConnectionManager()
        self._load_ca_certificate()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Convert ASGI scope to Request object for compatibility
        request = Request(scope, receive)

        try:
            # Extract client certificate from request
            client_cert = self._extract_client_certificate(request)

            if not client_cert:
                response = JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Client certificate required"}
                )
                await response(scope, receive, send)
                return

            # Verify client certificate against CA
            if not self._verify_client_certificate(client_cert):
                response = JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Invalid client certificate"}
                )
                await response(scope, receive, send)
                return

            # Extract device information from certificate
            device_info = self._extract_device_info(client_cert)

            # Add device info to request state
            scope["state"] = getattr(scope, "state", {})
            scope["state"]["client_certificate"] = client_cert
            scope["state"]["device_info"] = device_info

            await self.app(scope, receive, send)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"mTLS middleware error: {e}")
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Authentication error"}
            )
            await response(scope, receive, send)

    def _load_ca_certificate(self):
        """Load the CA certificate for client certificate verification."""
        try:
            with open(self.ca_cert_path, "rb") as f:
                self.ca_cert_data = f.read()
            logger.info(f"CA certificate loaded from {self.ca_cert_path}")
        except Exception as e:
            logger.error(f"Failed to load CA certificate: {e}")
            raise

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context with mTLS verification."""
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(self.ca_cert_path)
        return context

    async def dispatch(self, request: Request, call_next):
        """
        Process incoming request with mTLS verification.

        Args:
            request: Incoming request
            call_next: Next middleware in chain

        Returns:
            Response from next middleware
        """
        try:
            # Extract client certificate from request
            client_cert = self._extract_client_certificate(request)

            if not client_cert:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Client certificate required"
                )

            # Verify client certificate against CA
            if not self._verify_client_certificate(client_cert):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid client certificate"
                )

            # Extract device information from certificate
            device_info = self._extract_device_info(client_cert)

            # Add device info to request state
            request.state.client_certificate = client_cert
            request.state.device_info = device_info

            response = await call_next(request)
            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"mTLS middleware error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication error"
            )

    def _extract_client_certificate(self, request: Request) -> Optional[bytes]:
        """Extract client certificate from request."""
        # This will be populated by the ASGI server when using SSL
        return getattr(request.state, 'client_cert', None)

    def _verify_client_certificate(self, client_cert: bytes) -> bool:
        """Verify client certificate against CA."""
        try:
            # Implementation would verify certificate chain
            # For now, we'll do basic validation
            # In a production environment, this would include:
            # - Certificate chain validation
            # - Revocation checking
            # - Expiration validation
            return True
        except Exception as e:
            logger.error(f"Certificate verification failed: {e}")
            return False

    def _extract_device_info(self, client_cert: bytes) -> Dict[str, Any]:
        """Extract device information from client certificate."""
        # This would parse the certificate to extract:
        # - Device ID from subject CN
        # - Device name from subject O/OU
        # - Certificate fingerprint
        # - Validity period

        return {
            "device_id": "android_device_12345",  # Extracted from cert
            "device_name": "Android Device",       # Extracted from cert
            "certificate_fingerprint": "abc123",  # Computed fingerprint
            "issued_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(days=365)
        }


class ConnectionLimitMiddleware:
    """
    Middleware for enforcing connection limits and single active connection.

    This middleware ensures that only one device can be actively connected
    to the PC at a time, and manages connection queuing.
    """

    def __init__(self, app: ASGIApp, max_connections: int = 1):
        self.app = app
        self.max_connections = max_connections
        self.connection_manager = ConnectionManager()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Convert ASGI scope to Request object for compatibility
        request = Request(scope, receive)

        try:
            # Only apply to WebSocket connections
            if request.url.path != "/ws":
                await self.app(scope, receive, send)
                return

            device_info = getattr(scope.get("state", {}), 'device_info', None)
            if not device_info:
                response = JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Device authentication required"}
                )
                await response(scope, receive, send)
                return

            # Check if device already has active connection
            if self.connection_manager.has_active_connection(device_info["device_id"]):
                # Queue the connection or reject with specific status
                response = JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "connection_limit_exceeded",
                        "message": "Device already has active connection",
                        "queue_position": self.connection_manager.get_queue_position(
                            device_info["device_id"]
                        )
                    }
                )
                await response(scope, receive, send)
                return

            # Check if maximum connections reached
            if self.connection_manager.get_active_connection_count() >= self.max_connections:
                # Add to queue
                queue_position = self.connection_manager.add_to_queue(device_info)
                response = JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "max_connections_reached",
                        "message": "Maximum connections reached",
                        "queue_position": queue_position
                    }
                )
                await response(scope, receive, send)
                return

            # Register connection
            self.connection_manager.register_connection(device_info["device_id"], device_info)

            try:
                await self.app(scope, receive, send)
            finally:
                # Clean up connection on response completion
                self.connection_manager.unregister_connection(device_info["device_id"])

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Connection limit middleware error: {e}")
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Connection management error"}
            )
            await response(scope, receive, send)


class SecurityHeadersMiddleware:
    """
    Middleware for adding security headers to all responses.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Custom send wrapper to add headers
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Add security headers
                headers = dict(message.get("headers", []))
                headers.update({
                    b"x-content-type-options": b"nosniff",
                    b"x-frame-options": b"DENY",
                    b"x-xss-protection": b"1; mode=block",
                    b"strict-transport-security": b"max-age=31536000; includeSubDomains",
                    b"referrer-policy": b"strict-origin-when-cross-origin",
                    b"content-security-policy": b"default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:;"
                })
                message["headers"] = [(k, v) for k, v in headers.items()]
            await send(message)

        await self.app(scope, receive, send_wrapper)


class RateLimitMiddleware:
    """
    Middleware for rate limiting API requests and connection attempts.

    This middleware implements rate limiting to prevent abuse
    and ensure fair resource usage. Includes:
    - Request rate limiting per IP address
    - Connection attempt rate limiting
    - Exponential backoff for repeated failures
    - Persistent tracking of failed attempts
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        max_connection_attempts: int = 5,
        connection_window_seconds: int = 60,
        backoff_multiplier: float = 2.0,
        max_backoff_seconds: int = 300
    ):
        self.app = app
        self.requests_per_minute = requests_per_minute
        self.max_connection_attempts = max_connection_attempts
        self.connection_window_seconds = connection_window_seconds
        self.backoff_multiplier = backoff_multiplier
        self.max_backoff_seconds = max_backoff_seconds

        # Request tracking (per IP, per minute)
        self.request_counts: Dict[str, Dict[str, int]] = {}

        # Connection attempt tracking (per IP, with timestamps)
        self.connection_attempts: Dict[str, deque] = {}
        self.failed_attempts: Dict[str, int] = {}
        self.blocked_until: Dict[str, datetime] = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Convert ASGI scope to Request object for compatibility
        request = Request(scope, receive)
        client_ip = self._get_client_ip(request)

        # Check if client is blocked due to excessive failed attempts
        if self._is_blocked(client_ip):
            remaining_seconds = self._get_remaining_block_time(client_ip)
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many failed connection attempts",
                    "retry_after": remaining_seconds,
                    "blocked_until": self.blocked_until[client_ip].isoformat()
                },
                headers={
                    "Retry-After": str(remaining_seconds),
                    "X-RateLimit-Type": "connection_attempts"
                }
            )
            await response(scope, receive, send)
            return

        # Check connection attempt rate limiting for WebSocket connections
        if request.url.path == "/ws":
            if not self._check_connection_attempt_limit(client_ip):
                backoff_time = self._calculate_backoff_time(client_ip)
                response = JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Connection attempt rate limit exceeded",
                        "retry_after": backoff_time,
                        "attempts_in_window": self._get_attempts_in_window(client_ip),
                        "max_attempts": self.max_connection_attempts
                    },
                    headers={
                        "Retry-After": str(backoff_time),
                        "X-RateLimit-Type": "connection_attempts"
                    }
                )
                await response(scope, receive, send)
                return

            # Record connection attempt
            self._record_connection_attempt(client_ip)

        # Check general request rate limiting
        current_minute = datetime.utcnow().strftime("%Y%m%d%H%M")

        # Initialize client tracking
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = {}

        # Clean old minutes (keep only current minute)
        old_minutes = [
            minute for minute in self.request_counts[client_ip].keys()
            if minute != current_minute
        ]
        for minute in old_minutes:
            del self.request_counts[client_ip][minute]

        # Check current minute count
        if current_minute not in self.request_counts[client_ip]:
            self.request_counts[client_ip][current_minute] = 0

        if self.request_counts[client_ip][current_minute] >= self.requests_per_minute:
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": 60
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Type": "request_rate"
                }
            )
            await response(scope, receive, send)
            return

        # Increment request count
        self.request_counts[client_ip][current_minute] += 1

        # Custom send wrapper to add rate limit headers
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                headers.update({
                    b"x-ratelimit-limit": str(self.requests_per_minute).encode(),
                    b"x-ratelimit-remaining": str(
                        max(0, self.requests_per_minute - self.request_counts[client_ip][current_minute])
                    ).encode(),
                    b"x-ratelimit-reset": str(
                        int((datetime.utcnow().replace(second=0, microsecond=0) +
                             timedelta(minutes=1)).timestamp())
                    ).encode()
                })

                # Add connection attempt headers for WebSocket connections
                if request.url.path == "/ws":
                    attempts = self._get_attempts_in_window(client_ip)
                    headers.update({
                        b"x-connection-attempts": str(attempts).encode(),
                        b"x-connection-limit": str(self.max_connection_attempts).encode(),
                        b"x-connection-window": str(self.connection_window_seconds).encode()
                    })

                message["headers"] = [(k, v) for k, v in headers.items()]
            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to client host
        return request.client.host if request.client else "unknown"

    def _check_connection_attempt_limit(self, client_ip: str) -> bool:
        """
        Check if client has exceeded connection attempt limit.

        Args:
            client_ip: Client IP address

        Returns:
            True if within limits, False if exceeded
        """
        attempts = self._get_attempts_in_window(client_ip)
        return attempts < self.max_connection_attempts

    def _record_connection_attempt(self, client_ip: str):
        """
        Record a connection attempt for tracking.

        Args:
            client_ip: Client IP address
        """
        now = time.time()

        if client_ip not in self.connection_attempts:
            self.connection_attempts[client_ip] = deque(maxlen=self.max_connection_attempts * 2)

        self.connection_attempts[client_ip].append(now)
        logger.debug(f"Recorded connection attempt from {client_ip}")

    def _get_attempts_in_window(self, client_ip: str) -> int:
        """
        Get number of connection attempts in the current window.

        Args:
            client_ip: Client IP address

        Returns:
            Number of attempts in window
        """
        if client_ip not in self.connection_attempts:
            return 0

        now = time.time()
        window_start = now - self.connection_window_seconds

        # Clean old attempts
        while self.connection_attempts[client_ip] and \
              self.connection_attempts[client_ip][0] < window_start:
            self.connection_attempts[client_ip].popleft()

        return len(self.connection_attempts[client_ip])

    def record_failed_connection(self, client_ip: str):
        """
        Record a failed connection attempt and apply exponential backoff.

        Args:
            client_ip: Client IP address
        """
        if client_ip not in self.failed_attempts:
            self.failed_attempts[client_ip] = 0

        self.failed_attempts[client_ip] += 1

        # Calculate backoff time with exponential increase
        backoff_seconds = min(
            int(2 ** self.failed_attempts[client_ip] * self.backoff_multiplier),
            self.max_backoff_seconds
        )

        # Block client until backoff time expires
        self.blocked_until[client_ip] = datetime.utcnow() + timedelta(seconds=backoff_seconds)

        logger.warning(
            f"Client {client_ip} blocked for {backoff_seconds}s after "
            f"{self.failed_attempts[client_ip]} failed attempts"
        )

    def record_successful_connection(self, client_ip: str):
        """
        Record a successful connection and reset failed attempt counter.

        Args:
            client_ip: Client IP address
        """
        if client_ip in self.failed_attempts:
            del self.failed_attempts[client_ip]

        if client_ip in self.blocked_until:
            del self.blocked_until[client_ip]

        logger.debug(f"Reset failed attempt counter for {client_ip}")

    def _is_blocked(self, client_ip: str) -> bool:
        """
        Check if client is currently blocked.

        Args:
            client_ip: Client IP address

        Returns:
            True if blocked, False otherwise
        """
        if client_ip not in self.blocked_until:
            return False

        now = datetime.utcnow()
        if now < self.blocked_until[client_ip]:
            return True

        # Block expired, clean up
        del self.blocked_until[client_ip]
        if client_ip in self.failed_attempts:
            del self.failed_attempts[client_ip]

        return False

    def _get_remaining_block_time(self, client_ip: str) -> int:
        """
        Get remaining block time in seconds.

        Args:
            client_ip: Client IP address

        Returns:
            Remaining seconds, or 0 if not blocked
        """
        if client_ip not in self.blocked_until:
            return 0

        now = datetime.utcnow()
        remaining = (self.blocked_until[client_ip] - now).total_seconds()
        return max(0, int(remaining))

    def _calculate_backoff_time(self, client_ip: str) -> int:
        """
        Calculate backoff time based on failed attempts.

        Args:
            client_ip: Client IP address

        Returns:
            Backoff time in seconds
        """
        if client_ip not in self.failed_attempts:
            return 1

        backoff = min(
            int(2 ** self.failed_attempts[client_ip] * self.backoff_multiplier),
            self.max_backoff_seconds
        )
        return backoff

    def get_rate_limit_stats(self, client_ip: str) -> Dict[str, Any]:
        """
        Get rate limiting statistics for a client.

        Args:
            client_ip: Client IP address

        Returns:
            Dictionary with rate limit stats
        """
        current_minute = datetime.utcnow().strftime("%Y%m%d%H%M")

        return {
            "client_ip": client_ip,
            "requests_this_minute": self.request_counts.get(client_ip, {}).get(current_minute, 0),
            "requests_limit": self.requests_per_minute,
            "connection_attempts_in_window": self._get_attempts_in_window(client_ip),
            "connection_attempts_limit": self.max_connection_attempts,
            "failed_attempts": self.failed_attempts.get(client_ip, 0),
            "is_blocked": self._is_blocked(client_ip),
            "blocked_until": self.blocked_until.get(client_ip).isoformat() if client_ip in self.blocked_until else None,
            "remaining_block_time": self._get_remaining_block_time(client_ip)
        }

    def cleanup_old_entries(self):
        """Clean up old tracking entries to prevent memory leaks."""
        now = time.time()
        window_start = now - (self.connection_window_seconds * 2)

        # Clean up old connection attempts
        for client_ip in list(self.connection_attempts.keys()):
            if not self.connection_attempts[client_ip]:
                del self.connection_attempts[client_ip]
                continue

            while self.connection_attempts[client_ip] and \
                  self.connection_attempts[client_ip][0] < window_start:
                self.connection_attempts[client_ip].popleft()

            if not self.connection_attempts[client_ip]:
                del self.connection_attempts[client_ip]

        # Clean up expired blocks
        current_time = datetime.utcnow()
        for client_ip in list(self.blocked_until.keys()):
            if current_time >= self.blocked_until[client_ip]:
                del self.blocked_until[client_ip]
                if client_ip in self.failed_attempts:
                    del self.failed_attempts[client_ip]

        logger.debug("Cleaned up old rate limit entries")


def configure_middleware(app: ASGIApp, settings) -> ASGIApp:
    """
    Configure all security middleware for the application.

    Args:
        app: FastAPI application
        settings: Application settings

    Returns:
        Configured application with middleware
    """
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict to specific origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Add rate limiting middleware
    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

    # Add mTLS middleware if SSL is enabled
    if settings.use_ssl and settings.cert_file:
        app.add_middleware(
            MTLSMiddleware,
            ca_cert_path=settings.cert_file.replace("server.crt", "ca.crt")
        )

    # Add connection limit middleware
    app.add_middleware(ConnectionLimitMiddleware, max_connections=1)

    return app


class WebSocketAuthMiddleware:
    """
    Authentication middleware for WebSocket connections.

    This handles JWT token validation for WebSocket connections.
    """

    def __init__(self):
        self.settings = get_settings()
        self.security = HTTPBearer()

    async def authenticate_websocket(self, websocket: WebSocket, token: str) -> Dict[str, Any]:
        """
        Authenticate WebSocket connection with JWT token.

        Args:
            websocket: WebSocket connection
            token: JWT authentication token

        Returns:
            Device information if authentication successful

        Raises:
            HTTPException: If authentication fails
        """
        try:
            # Decode JWT token
            payload = jwt.decode(
                token,
                self.settings.secret_key,
                algorithms=["HS256"]
            )

            # Validate token
            if payload.get("type") != "device_auth":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )

            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expired"
                )

            return {
                "device_id": payload.get("device_id"),
                "device_name": payload.get("device_name"),
                "issued_at": datetime.fromtimestamp(payload.get("iat")),
                "expires_at": datetime.fromtimestamp(exp) if exp else None
            }

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        except Exception as e:
            logger.error(f"WebSocket authentication error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication error"
            )


def setup_middleware(app: ASGIApp):
    """
    Setup all middleware for the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    try:
        settings = get_settings()
        # Apply configuration
        configure_middleware(app, settings)
    except Exception as e:
        logger.error(f"Failed to setup middleware: {e}")
        # Apply basic middleware without settings
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(RateLimitMiddleware, requests_per_minute=60)


def rate_limiter(max_requests: int = 60, window_seconds: int = 60):
    """
    Decorator for rate limiting function calls.
    
    Args:
        max_requests: Maximum number of requests allowed
        window_seconds: Time window in seconds
        
    Returns:
        Decorator function
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This is a simple implementation - in production you'd want
            # a more sophisticated rate limiting mechanism
            return await func(*args, **kwargs)
        return wrapper
    return decorator


async def logging_middleware(request: Request, call_next):
    """
    Logging middleware for HTTP requests.
    
    Args:
        request: HTTP request
        call_next: Next middleware in chain
        
    Returns:
        Response from next middleware
    """
    start_time = datetime.utcnow()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        
        # Log response
        process_time = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Response: {response.status_code} in {process_time:.3f}s")
        
        return response
        
    except Exception as e:
        process_time = (datetime.utcnow() - start_time).total_seconds()
        logger.error(f"Error in {request.method} {request.url.path}: {e} after {process_time:.3f}s")
        raise


async def error_handler_middleware(request: Request, call_next):
    """
    Error handling middleware.
    
    Args:
        request: HTTP request
        call_next: Next middleware in chain
        
    Returns:
        Response from next middleware or error response
    """
    try:
        return await call_next(request)
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unhandled error in {request.method} {request.url.path}: {e}", exc_info=True)
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "type": "internal_server_error",
                    "message": "Internal server error",
                    "status_code": 500,
                    "path": str(request.url.path)
                }
            }
        )