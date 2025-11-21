"""
Unit tests for configuration settings.

These tests verify that the configuration system works correctly
and handles various input scenarios.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config.settings import Settings, get_settings, reload_settings


class TestSettings:
    """Test cases for Settings class."""

    def test_default_settings(self):
        """Test that default settings are applied correctly."""
        # Clear environment variables that might interfere
        with patch.dict(os.environ, {}, clear=True):
            # Pass _env_file=None to ignore .env file
            settings = Settings(_env_file=None)

            assert settings.host == "0.0.0.0"
            assert settings.port == 8765
            assert settings.use_ssl is True
            assert settings.log_level == "INFO"
            assert settings.session_timeout == 86400
            assert settings.max_concurrent_connections == 10

    def test_environment_variable_override(self):
        """Test that environment variables override defaults."""
        with patch.dict(os.environ, {
            "PC_AGENT_HOST": "127.0.0.1",
            "PC_AGENT_PORT": "9999",
            "PC_AGENT_LOG_LEVEL": "DEBUG"
        }):
            settings = Settings()

            assert settings.host == "127.0.0.1"
            assert settings.port == 9999
            assert settings.log_level == "DEBUG"

    def test_env_file_loading(self):
        """Test loading settings from .env file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("""
PC_AGENT_HOST=192.168.1.100
PC_AGENT_PORT=8080
PC_AGENT_USE_SSL=false
""")

            # pydantic-settings loads from .env file in current dir or specified by _env_file
            # We need to instantiate Settings with _env_file argument
            settings = Settings(_env_file=str(env_file))

            assert settings.host == "192.168.1.100"
            assert settings.port == 8080
            assert settings.use_ssl is False

    def test_ssl_certificate_paths(self):
        """Test SSL certificate path configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cert_dir = Path(temp_dir)
            
            # Create dummy cert files
            (cert_dir / "server.crt").touch()
            (cert_dir / "server.key").touch()

            settings = Settings(
                use_ssl=True,
                cert_file=str(cert_dir / "server.crt"),
                key_file=str(cert_dir / "server.key")
            )

            assert Path(settings.cert_file).resolve() == (cert_dir / "server.crt").resolve()
            assert Path(settings.key_file).resolve() == (cert_dir / "server.key").resolve()

    def test_database_url_validation(self):
        """Test database URL configuration."""
        settings = Settings(database_url="postgresql://user:pass@localhost/db")
        assert settings.database_url == "postgresql://user:pass@localhost/db"

    def test_is_production_property(self):
        """Test the is_production property."""
        dev_settings = Settings(environment="development")
        assert dev_settings.is_production is False

        prod_settings = Settings(environment="production")
        assert prod_settings.is_production is True

    def test_certificates_dir_creation(self):
        """Test that certificates directory is created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cert_dir = Path(temp_dir) / "certs"

            Settings(certificates_dir=cert_dir)

            assert cert_dir.exists()
            assert cert_dir.is_dir()


class TestSettingsGlobals:
    """Test cases for global settings functions."""

    def test_get_settings_singleton(self):
        """Test that get_settings returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_reload_settings(self):
        """Test that reload_settings creates a new instance."""
        settings1 = get_settings()
        reloaded_settings = reload_settings()

        assert reloaded_settings is not settings1
        assert get_settings() is reloaded_settings

    @patch.dict(os.environ, {"PC_AGENT_HOST": "test-reload"})
    def test_reload_settings_uses_new_env(self):
        """Test that reload_settings picks up new environment variables."""
        original_settings = get_settings()
        original_host = original_settings.host

        # Change environment and reload
        reloaded_settings = reload_settings()

        # The reloaded settings should have the new environment value
        # but the original should remain unchanged
        assert reloaded_settings.host == "test-reload"
        assert original_settings.host != "test-reload"
        assert get_settings() is reloaded_settings