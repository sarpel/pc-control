"""
Credential Cleanup Service

Provides secure cleanup and removal of sensitive credentials from Windows
Credential Manager and application storage. Implements secure deletion
patterns to prevent credential recovery.

Task: T087 [P] Implement secure credential cleanup in both platforms
"""

import logging
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logging.warning("keyring module not available - Windows Credential Manager integration disabled")

logger = logging.getLogger(__name__)


class CredentialCleanupService:
    """
    Handles secure cleanup of sensitive credentials from various storage locations.
    """

    # Service name for Windows Credential Manager
    SERVICE_NAME = "PCVoiceControl"

    # Known credential keys
    CREDENTIAL_KEYS = [
        "claude_api_key",
        "auth_token",
        "certificate_password",
        "session_key",
        "device_token"
    ]

    # Sensitive database tables
    SENSITIVE_TABLES = [
        "device_pairings",
        "auth_tokens",
        "session_keys"
    ]

    # Sensitive file patterns
    SENSITIVE_FILES = [
        "*.key",
        "*.pem",
        "auth_token.txt",
        "session.dat",
        ".env"
    ]

    def __init__(self, db_path: Optional[str] = None, config_dir: Optional[Path] = None):
        """
        Initialize the credential cleanup service.

        Args:
            db_path: Path to the SQLite database (optional)
            config_dir: Path to the configuration directory (optional)
        """
        self.db_path = db_path
        self.config_dir = config_dir or Path.home() / ".pc-voice-control"
        self.cleanup_results: List[str] = []
        self.cleanup_errors: List[str] = []

    def perform_complete_cleanup(self) -> Dict[str, any]:
        """
        Perform complete secure cleanup of all credentials.
        Should be called when uninstalling or resetting the service.

        Returns:
            Dictionary with cleanup results and errors
        """
        logger.info("Starting complete credential cleanup")

        self.cleanup_results = []
        self.cleanup_errors = []

        try:
            # 1. Clean Windows Credential Manager
            cred_manager_count = self._cleanup_credential_manager()
            self.cleanup_results.append(f"Credential Manager: {cred_manager_count} credentials deleted")

            # 2. Clean database credentials
            db_count = self._cleanup_database_credentials()
            self.cleanup_results.append(f"Database: {db_count} records cleared")

            # 3. Clean sensitive files
            file_count = self._cleanup_sensitive_files()
            self.cleanup_results.append(f"Files: {file_count} files securely deleted")

            # 4. Clean environment variables (in-memory only)
            env_count = self._cleanup_environment_variables()
            self.cleanup_results.append(f"Environment: {env_count} variables cleared")

            # 5. Secure memory cleanup (best effort)
            self._secure_memory_cleanup()
            self.cleanup_results.append("Memory: Cleanup triggered")

            success = len(self.cleanup_errors) == 0
            logger.info(f"Credential cleanup completed: {len(self.cleanup_results)} operations, {len(self.cleanup_errors)} errors")

            return {
                "success": success,
                "results": self.cleanup_results,
                "errors": self.cleanup_errors
            }

        except Exception as e:
            error_msg = f"Critical error during cleanup: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.cleanup_errors.append(error_msg)
            return {
                "success": False,
                "results": self.cleanup_results,
                "errors": self.cleanup_errors
            }

    def _cleanup_credential_manager(self) -> int:
        """
        Clean up credentials from Windows Credential Manager.

        Returns:
            Number of credentials deleted
        """
        deleted_count = 0

        if not KEYRING_AVAILABLE:
            self.cleanup_errors.append("Keyring not available - skipping Credential Manager cleanup")
            return deleted_count

        try:
            for key in self.CREDENTIAL_KEYS:
                try:
                    # Check if credential exists
                    credential = keyring.get_password(self.SERVICE_NAME, key)
                    if credential:
                        keyring.delete_password(self.SERVICE_NAME, key)
                        deleted_count += 1
                        logger.debug(f"Deleted credential: {key}")
                except keyring.errors.PasswordDeleteError:
                    logger.debug(f"Credential not found: {key}")
                except Exception as e:
                    error_msg = f"Failed to delete credential {key}: {str(e)}"
                    logger.warning(error_msg)
                    self.cleanup_errors.append(error_msg)

        except Exception as e:
            error_msg = f"Credential Manager cleanup error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.cleanup_errors.append(error_msg)

        return deleted_count

    def _cleanup_database_credentials(self) -> int:
        """
        Clean up sensitive data from SQLite database.

        Returns:
            Number of records cleared
        """
        deleted_count = 0

        if not self.db_path or not os.path.exists(self.db_path):
            logger.debug("Database path not provided or doesn't exist - skipping DB cleanup")
            return deleted_count

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            for table in self.SENSITIVE_TABLES:
                try:
                    # Check if table exists
                    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
                    if cursor.fetchone():
                        # Delete all records from sensitive tables
                        cursor.execute(f"DELETE FROM {table}")
                        deleted_count += cursor.rowcount
                        logger.debug(f"Cleared {cursor.rowcount} records from {table}")
                except sqlite3.OperationalError as e:
                    logger.debug(f"Table {table} not found or error: {e}")

            # Clear auth tokens from other tables (if they have token columns)
            try:
                cursor.execute("UPDATE connections SET auth_token = NULL WHERE auth_token IS NOT NULL")
                deleted_count += cursor.rowcount
            except sqlite3.OperationalError:
                pass  # Column might not exist

            conn.commit()
            conn.close()

        except Exception as e:
            error_msg = f"Database cleanup error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.cleanup_errors.append(error_msg)

        return deleted_count

    def _cleanup_sensitive_files(self) -> int:
        """
        Securely delete sensitive files.

        Returns:
            Number of files deleted
        """
        deleted_count = 0

        if not self.config_dir.exists():
            logger.debug("Config directory doesn't exist - skipping file cleanup")
            return deleted_count

        try:
            for pattern in self.SENSITIVE_FILES:
                for file_path in self.config_dir.rglob(pattern):
                    try:
                        if file_path.is_file():
                            # Overwrite file before deletion (simple secure delete)
                            file_size = file_path.stat().st_size
                            with open(file_path, 'wb') as f:
                                f.write(b'\x00' * file_size)  # Overwrite with zeros
                                f.flush()
                                os.fsync(f.fileno())

                            # Delete the file
                            file_path.unlink()
                            deleted_count += 1
                            logger.debug(f"Securely deleted file: {file_path}")
                    except Exception as e:
                        error_msg = f"Failed to delete file {file_path}: {str(e)}"
                        logger.warning(error_msg)
                        self.cleanup_errors.append(error_msg)

        except Exception as e:
            error_msg = f"File cleanup error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.cleanup_errors.append(error_msg)

        return deleted_count

    def _cleanup_environment_variables(self) -> int:
        """
        Clear sensitive environment variables (in current process only).

        Returns:
            Number of variables cleared
        """
        cleared_count = 0

        sensitive_env_vars = [
            "CLAUDE_API_KEY",
            "AUTH_TOKEN",
            "SESSION_KEY",
            "DEVICE_TOKEN"
        ]

        try:
            for var in sensitive_env_vars:
                if var in os.environ:
                    del os.environ[var]
                    cleared_count += 1
                    logger.debug(f"Cleared environment variable: {var}")
        except Exception as e:
            error_msg = f"Environment variable cleanup error: {str(e)}"
            logger.warning(error_msg)
            self.cleanup_errors.append(error_msg)

        return cleared_count

    def _secure_memory_cleanup(self):
        """
        Attempt to clear sensitive data from memory.
        This is best-effort and not guaranteed due to Python's memory management.
        """
        try:
            import gc
            gc.collect()
            logger.debug("Triggered garbage collection for memory cleanup")
        except Exception as e:
            logger.warning(f"Memory cleanup warning: {str(e)}")

    def cleanup_specific_credential(self, key: str) -> bool:
        """
        Clean up a specific credential by key.

        Args:
            key: The credential key to remove

        Returns:
            True if successful, False otherwise
        """
        if not KEYRING_AVAILABLE:
            logger.warning("Keyring not available - cannot cleanup credential")
            return False

        try:
            credential = keyring.get_password(self.SERVICE_NAME, key)
            if credential:
                keyring.delete_password(self.SERVICE_NAME, key)
                logger.info(f"Deleted specific credential: {key}")
                return True
            else:
                logger.warning(f"Credential not found: {key}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete credential {key}: {str(e)}", exc_info=True)
            return False

    def verify_cleanup(self) -> Dict[str, any]:
        """
        Verify that credentials have been properly cleaned up.

        Returns:
            Dictionary with verification results
        """
        remaining_credentials = []
        remaining_files = []

        # Check Credential Manager
        if KEYRING_AVAILABLE:
            for key in self.CREDENTIAL_KEYS:
                try:
                    if keyring.get_password(self.SERVICE_NAME, key):
                        remaining_credentials.append(key)
                except Exception:
                    pass  # Credential doesn't exist or error accessing

        # Check sensitive files
        if self.config_dir.exists():
            for pattern in self.SENSITIVE_FILES:
                for file_path in self.config_dir.rglob(pattern):
                    if file_path.is_file():
                        remaining_files.append(str(file_path))

        is_clean = len(remaining_credentials) == 0 and len(remaining_files) == 0

        return {
            "is_clean": is_clean,
            "remaining_credentials": remaining_credentials,
            "remaining_files": remaining_files
        }


def get_cleanup_summary(cleanup_result: Dict[str, any]) -> str:
    """
    Generate a human-readable summary of cleanup results.

    Args:
        cleanup_result: The cleanup result dictionary

    Returns:
        Formatted summary string
    """
    summary = []

    if cleanup_result["success"]:
        summary.append("✓ Cleanup completed successfully")
    else:
        summary.append("✗ Cleanup completed with errors")

    if cleanup_result.get("results"):
        summary.append("\nResults:")
        for result in cleanup_result["results"]:
            summary.append(f"  ✓ {result}")

    if cleanup_result.get("errors"):
        summary.append("\nErrors:")
        for error in cleanup_result["errors"]:
            summary.append(f"  ✗ {error}")

    return "\n".join(summary)


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.DEBUG)

    service = CredentialCleanupService()
    result = service.perform_complete_cleanup()

    print(get_cleanup_summary(result))
    print("\nVerification:")
    verification = service.verify_cleanup()
    print(f"Is clean: {verification['is_clean']}")
    if not verification['is_clean']:
        print(f"Remaining credentials: {verification['remaining_credentials']}")
        print(f"Remaining files: {verification['remaining_files']}")
