"""
Configuration settings for PC Control Agent

This module defines all configuration settings using Pydantic for validation
and environment variable loading.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="PC_AGENT_"
    )

    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host address")
    port: int = Field(default=8765, description="Server port")
    use_ssl: bool = Field(default=True, description="Enable SSL/TLS")
    cert_file: Optional[str] = Field(
        default=None, description="Path to SSL certificate file"
    )
    key_file: Optional[str] = Field(
        default=None, description="Path to SSL private key file"
    )
    cors_origins: list[str] = Field(
        default=["*"], description="Allowed CORS origins"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(
        default=None, description="Log file path"
    )

    # Security
    secret_key: str = Field(
        default="your-secret-key-change-in-production",
        description="JWT secret key"
    )
    session_timeout: int = Field(
        default=86400, description="Session timeout in seconds"
    )
    max_connection_attempts: int = Field(
        default=5, description="Maximum connection attempts"
    )

    # API Configuration
    claude_api_key: Optional[str] = Field(
        default=None, description="Claude API key"
    )
    claude_api_url: str = Field(
        default="https://api.anthropic.com",
        description="Claude API URL"
    )

    # Audio Processing
    audio_sample_rate: int = Field(
        default=16000, description="Audio sample rate"
    )
    audio_channels: int = Field(
        default=1, description="Audio channels"
    )
    audio_buffer_size: int = Field(
        default=1024, description="Audio buffer size"
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./pc_agent.db",
        description="Database connection URL"
    )

    # Performance
    max_concurrent_connections: int = Field(
        default=10, description="Maximum concurrent connections"
    )
    command_timeout: int = Field(
        default=30, description="Command timeout in seconds"
    )

    # File paths
    certificates_dir: Path = Field(
        default=Path("config/certificates"),
        description="Certificates directory"
    )

    # Application metadata
    version: str = Field(default="1.0.0", description="Application version")
    environment: str = Field(
        default="development", description="Environment (development/staging/production)"
    )

    # Development
    debug: bool = Field(default=False, description="Enable debug mode")
    validate_api_keys: bool = Field(default=True, description="Validate API keys")
    validate_certificates: bool = Field(default=True, description="Validate certificates")

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"

    def model_post_init(self, __context) -> None:
        """Post-initialization setup."""
        # Create certificates directory if it doesn't exist
        self.certificates_dir.mkdir(parents=True, exist_ok=True)

        # Set default SSL paths if not provided
        if self.use_ssl and not self.cert_file:
            self.cert_file = str(self.certificates_dir / "server.crt")
        if self.use_ssl and not self.key_file:
            self.key_file = str(self.certificates_dir / "server.key")


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment."""
    global _settings
    _settings = Settings()
    return _settings