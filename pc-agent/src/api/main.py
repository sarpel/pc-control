"""
Main API router for PC Voice Controller.

This module defines the main FastAPI application with all API routes,
middleware configuration, and startup/shutdown handlers.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from api.middleware import (
    setup_middleware,
    rate_limiter,
    logging_middleware,
    error_handler_middleware
)
from api.rest_endpoints import pairing_router, wol_router
from api.websocket_server import router as websocket_router
from database.connection import initialize_database, close_database
from services.certificate_service import CertificateService
from services.connection_manager import ConnectionManager
from config.settings import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Initialize services
certificate_service = CertificateService()
connection_manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting PC Voice Controller API...")

    try:
        # Initialize database
        await initialize_database()
        logger.info("Database initialized successfully")

        # Initialize certificates
        await certificate_service.initialize()
        logger.info("Certificate service initialized successfully")

        # Initialize connection manager
        await connection_manager.initialize()
        logger.info("Connection manager initialized successfully")

        logger.info("PC Voice Controller API started successfully")

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down PC Voice Controller API...")

    try:
        # Close connection manager
        await connection_manager.cleanup()

        # Close database
        await close_database()

        logger.info("PC Voice Controller API shut down successfully")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title="PC Voice Controller API",
    description="REST API for voice-controlled PC assistant with Android client support",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# Setup middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.middleware("http")(logging_middleware)
app.middleware("http")(error_handler_middleware)
setup_middleware(app)


# Include routers
app.include_router(pairing_router)
app.include_router(wol_router)
app.include_router(websocket_router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "PC Voice Controller API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "websocket": "/ws",
        "health": "/health"
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connection
        from database.connection import get_database_connection
        db = get_database_connection()
        health_info = await db.health_check()

        # Check certificate service
        cert_health = await certificate_service.health_check()

        # Check connection manager
        conn_health = connection_manager.get_health_status()

        overall_status = "healthy"
        if health_info["status"] != "healthy" or cert_health["status"] != "healthy":
            overall_status = "unhealthy"

        return {
            "status": overall_status,
            "timestamp": health_info["timestamp"],
            "database": health_info,
            "certificates": cert_health,
            "connections": conn_health,
            "version": "1.0.0"
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": "2025-01-01T00:00:00Z"
        }


# API info endpoint
@app.get("/api/v1/info")
async def get_api_info():
    """Get API information."""
    return {
        "name": "PC Voice Controller API",
        "version": "1.0.0",
        "description": "Voice-controlled PC assistant with Android client support",
        "endpoints": {
            "pairing": "/api/pairing",
            "wol": "/api/wol",
            "websocket": "/ws",
            "health": "/health",
            "docs": "/docs"
        },
        "features": [
            "mTLS authentication",
            "Device pairing",
            "Wake-on-LAN (WoL)",
            "WebSocket communication",
            "Voice command processing",
            "Certificate management"
        ],
        "supported_languages": ["tr", "en"],
        "protocols": ["HTTPS", "WSS"],
        "authentication": "mTLS + JWT"
    }


# System status endpoint
@app.get("/api/v1/status")
@rate_limiter(max_requests=10, window_seconds=60)
async def get_system_status():
    """Get detailed system status."""
    try:
        # Get database statistics
        db = get_database_connection()
        db_stats = await db.get_statistics()

        # Get connection statistics
        conn_stats = connection_manager.get_statistics()

        # Get certificate information
        cert_info = certificate_service.get_certificate_info()

        return {
            "status": "operational",
            "timestamp": "2025-01-01T00:00:00Z",
            "uptime_seconds": 3600,  # Would calculate actual uptime
            "database": {
                "status": "connected" if db_stats.get("table_counts") else "disconnected",
                "tables": db_stats.get("table_counts", {}),
                "file_size_mb": db_stats.get("database_file_size_mb", 0)
            },
            "connections": {
                "active": conn_stats.get("active_connections", 0),
                "total_today": conn_stats.get("total_connections_today", 0),
                "max_concurrent": conn_stats.get("max_concurrent_connections", 0)
            },
            "certificates": {
                "server_cert_valid": cert_info.get("server_certificate_valid", False),
                "ca_cert_valid": cert_info.get("ca_certificate_valid", False),
                "certificates_loaded": cert_info.get("certificates_loaded", 0)
            },
            "system": {
                "memory_usage_mb": 128,  # Would get actual memory usage
                "cpu_usage_percent": 15,  # Would get actual CPU usage
                "disk_usage_percent": 45   # Would get actual disk usage
            }
        }

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": "2025-01-01T00:00:00Z"
        }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "http_error",
                "message": exc.detail,
                "status_code": exc.status_code,
                "path": str(request.url.path)
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "type": "internal_server_error",
                "message": "Internal server error",
                "status_code": 500,
                "path": str(request.url.path)
            }
        }
    )


# Development server startup
if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host=settings.host,
        port=settings.port,
        ssl_keyfile=settings.ssl_key_file,
        ssl_certfile=settings.ssl_cert_file,
        reload=settings.debug,
        log_level="info"
    )