#!/usr/bin/env python3
"""
Main entry point for the PC Control Agent

This module starts the FastAPI server with WebSocket support for voice command processing.
"""

import asyncio
import logging
import ssl
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from src.api.websocket_server import app
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point for the PC Control Agent."""
    settings = get_settings()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("Starting PC Control Agent v%s", settings.version)

    # SSL configuration for production
    ssl_context = None
    if settings.use_ssl:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(
            settings.cert_file,
            settings.key_file
        )
        logger.info("SSL/TLS enabled")

    # Start server
    config = uvicorn.Config(
        app=app,
        host=settings.host,
        port=settings.port,
        ssl_certfile=settings.cert_file if settings.use_ssl else None,
        ssl_keyfile=settings.key_file if settings.use_ssl else None,
        log_level=settings.log_level.lower(),
        access_log=True,
    )

    server = uvicorn.Server(config)

    try:
        logger.info("Server starting on %s://%s:%d",
                   "https" if settings.use_ssl else "http",
                   settings.host, settings.port)
        await server.serve()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error("Server error: %s", e)
        raise
    finally:
        logger.info("Server stopped")


if __name__ == "__main__":
    asyncio.run(main())