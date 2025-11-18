"""
Database connection and migration framework for PC Control Agent.

This module provides:
- Database connection management
- Migration system
- Connection pooling
- Transaction management
- Database health monitoring
"""

import asyncio
import logging
import sqlite3
import sqlite3.dbapi2 as sqlite
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Any, Callable, Union
import aiosqlite

from src.config.settings import get_settings
from src.database.schema import DATABASE_SCHEMA

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    Asynchronous database connection manager.

    This class provides a high-level interface for database operations
    with connection pooling, transaction management, and health monitoring.
    """

    def __init__(self):
        """Initialize database connection manager."""
        self.settings = get_settings()
        self.db_path = Path(self.settings.database_url.replace("sqlite:///", ""))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Connection management
        self._connection_pool: List[aiosqlite.Connection] = []
        self._pool_lock = asyncio.Lock()
        self._max_connections = 10

        # Migration management
        self._migrations: List[Migration] = []
        self._migration_table = "schema_migrations"

        # Statistics
        self._stats = {
            "total_connections": 0,
            "active_connections": 0,
            "total_queries": 0,
            "failed_queries": 0,
            "last_activity": None
        }

    async def initialize(self) -> None:
        """
        Initialize database with schema and migrations.

        This method creates the database if it doesn't exist,
        applies the schema, and runs any pending migrations.
        """
        try:
            logger.info(f"Initializing database at: {self.db_path}")

            # Create initial database with schema
            await self._create_database_with_schema()

            # Initialize migration system
            await self._initialize_migrations()

            # Run migrations
            await self._run_migrations()

            logger.info("Database initialization completed successfully")

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    async def _create_database_with_schema(self) -> None:
        """Create database with initial schema."""
        # Use synchronous SQLite for initial setup
        conn = sqlite3.connect(self.db_path)
        try:
            # Enable foreign key constraints
            conn.execute("PRAGMA foreign_keys = ON")

            # Execute schema
            conn.executescript(DATABASE_SCHEMA)

            # Commit changes
            conn.commit()

            logger.debug("Database schema created successfully")

        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    async def _initialize_migrations(self) -> None:
        """Initialize migration system."""
        # Register migrations here in order
        self._migrations = [
            Migration(
                version=1,
                description="Initial database schema",
                sql="""
                -- This migration is applied by the initial schema creation
                -- No additional SQL needed
                """
            ),
            Migration(
                version=2,
                description="Add performance indexes",
                sql="""
                -- Add additional indexes for performance
                CREATE INDEX IF NOT EXISTS idx_voice_commands_transcription ON voice_commands (transcription);
                CREATE INDEX IF NOT EXISTS idx_actions_created_at_desc ON actions (created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_audit_log_severity_timestamp ON audit_log (severity, timestamp);
                """
            ),
        ]

    async def _run_migrations(self) -> None:
        """Run pending migrations."""
        async with self.get_connection() as conn:
            # Create migrations table if not exists
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._migration_table} (
                    version INTEGER PRIMARY KEY,
                    description TEXT NOT NULL,
                    applied_at DATETIME NOT NULL,
                    checksum TEXT
                )
            """)

            # Get applied migrations
            applied_migrations = await self._get_applied_migrations(conn)
            applied_versions = {m["version"] for m in applied_migrations}

            # Run pending migrations
            for migration in self._migrations:
                if migration.version not in applied_versions:
                    logger.info(f"Running migration {migration.version}: {migration.description}")
                    await self._run_migration(conn, migration)

            logger.info("All migrations completed successfully")

    async def _get_applied_migrations(self, conn: aiosqlite.Connection) -> List[Dict[str, Any]]:
        """Get list of applied migrations from database."""
        cursor = await conn.execute(f"""
            SELECT version, description, applied_at, checksum
            FROM {self._migration_table}
            ORDER BY version
        """)
        return await cursor.fetchall()

    async def _run_migration(self, conn: aiosqlite.Connection, migration: "Migration") -> None:
        """Run a single migration within a transaction."""
        async with conn.transaction():
            # Execute migration SQL
            if migration.sql.strip():
                await conn.executescript(migration.sql)

            # Record migration
            checksum = self._calculate_checksum(migration.sql)
            await conn.execute(f"""
                INSERT INTO {self._migration_table} (version, description, applied_at, checksum)
                VALUES (?, ?, ?, ?)
            """, (migration.version, migration.description, datetime.utcnow(), checksum))

    def _calculate_checksum(self, sql: str) -> str:
        """Calculate checksum for migration SQL."""
        import hashlib
        return hashlib.sha256(sql.encode()).hexdigest()

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """
        Get database connection from pool or create new one.

        This method implements a simple connection pool and provides
        a connection ready for use.
        """
        conn = None
        try:
            conn = await self._get_connection_from_pool()
            self._stats["active_connections"] += 1
            self._stats["last_activity"] = datetime.utcnow()
            yield conn
        except Exception as e:
            self._stats["failed_queries"] += 1
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                await self._return_connection_to_pool(conn)
                self._stats["active_connections"] -= 1

    async def _get_connection_from_pool(self) -> aiosqlite.Connection:
        """Get connection from pool or create new one."""
        async with self._pool_lock:
            if self._connection_pool:
                conn = self._connection_pool.pop()
                logger.debug("Reusing connection from pool")
            else:
                # Create new connection
                conn = await aiosqlite.connect(self.db_path)
                # Enable WAL mode for better concurrency
                await conn.execute("PRAGMA journal_mode=WAL")
                # Enable foreign key constraints
                await conn.execute("PRAGMA foreign_keys=ON")
                # Optimize for performance
                await conn.execute("PRAGMA synchronous=NORMAL")
                await conn.execute("PRAGMA cache_size=10000")
                logger.debug("Created new database connection")
                self._stats["total_connections"] += 1

            return conn

    async def _return_connection_to_pool(self, conn: aiosqlite.Connection) -> None:
        """Return connection to pool if not at capacity."""
        async with self._pool_lock:
            if len(self._connection_pool) < self._max_connections:
                try:
                    # Test connection is still valid
                    await conn.execute("SELECT 1")
                    self._connection_pool.append(conn)
                    logger.debug("Returned connection to pool")
                except Exception as e:
                    # Connection is broken, close it
                    await conn.close()
                    logger.debug("Closed broken connection")
            else:
                # Pool is full, close connection
                await conn.close()
                logger.debug("Pool full, closed connection")

    async def execute_query(
        self,
        query: str,
        params: Optional[tuple] = None,
        fetch_one: bool = False,
        fetch_all: bool = False
    ) -> Optional[Union[sqlite.Row, List[sqlite.Row]]]:
        """
        Execute a database query.

        Args:
            query: SQL query string
            params: Query parameters
            fetch_one: Return single row if True
            fetch_all: Return all rows if True

        Returns:
            Query results
        """
        async with self.get_connection() as conn:
            cursor = await conn.execute(query, params or ())
            self._stats["total_queries"] += 1

            if fetch_one:
                result = await cursor.fetchone()
                return dict(result) if result else None
            elif fetch_all:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
            else:
                # For INSERT/UPDATE/DELETE operations
                return None

    async def execute_transaction(
        self,
        queries: List[tuple[str, Optional[tuple]]]
    ) -> None:
        """
        Execute multiple queries within a transaction.

        Args:
            queries: List of (query, params) tuples
        """
        async with self.get_connection() as conn:
            async with conn.transaction():
                for query, params in queries:
                    await conn.execute(query, params or ())
                    self._stats["total_queries"] += 1

    async def execute_script(self, script: str) -> None:
        """
        Execute multiple SQL statements.

        Args:
            script: SQL script with multiple statements
        """
        async with self.get_connection() as conn:
            await conn.executescript(script)
            self._stats["total_queries"] += 1

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform database health check.

        Returns:
            Health check results
        """
        try:
            async with self.get_connection() as conn:
                # Test basic connectivity
                await conn.execute("SELECT 1")

                # Get database info
                cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in await cursor.fetchall()]

                # Check table counts
                table_counts = {}
                for table in ["voice_commands", "actions", "device_pairing", "pc_connections"]:
                    try:
                        cursor = await conn.execute(f"SELECT COUNT(*) FROM {table}")
                        count = (await cursor.fetchone())[0]
                        table_counts[table] = count
                    except Exception:
                        table_counts[table] = 0

                return {
                    "status": "healthy",
                    "database_path": str(self.db_path),
                    "tables": tables,
                    "table_counts": table_counts,
                    "connection_pool_size": len(self._connection_pool),
                    "active_connections": self._stats["active_connections"],
                    "total_connections": self._stats["total_connections"],
                    "total_queries": self._stats["total_queries"],
                    "failed_queries": self._stats["failed_queries"],
                    "last_activity": self._stats["last_activity"].isoformat() if self._stats["last_activity"] else None,
                    "timestamp": datetime.utcnow().isoformat()
                }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def cleanup_expired_data(self) -> Dict[str, int]:
        """
        Clean up expired data from database.

        Returns:
            Dictionary with cleanup results
        """
        cleanup_results = {}

        try:
            async with self.get_connection() as conn:
                # Clean up expired command history (older than 10 minutes)
                ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
                cursor = await conn.execute(
                    "DELETE FROM command_history WHERE expires_at < ?",
                    (ten_minutes_ago.isoformat(),)
                )
                cleanup_results["command_history"] = cursor.rowcount

                # Clean up old audit logs (older than 90 days)
                ninety_days_ago = datetime.utcnow() - timedelta(days=90)
                cursor = await conn.execute(
                    "DELETE FROM audit_log WHERE timestamp < ?",
                    (ninety_days_ago.isoformat(),)
                )
                cleanup_results["audit_log"] = cursor.rowcount

                # Clean up old performance metrics (older than 30 days)
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                cursor = await conn.execute(
                    "DELETE FROM performance_metrics WHERE timestamp < ?",
                    (thirty_days_ago.isoformat(),)
                )
                cleanup_results["performance_metrics"] = cursor.rowcount

                # Clean up old error logs (older than 30 days)
                cursor = await conn.execute(
                    "DELETE FROM error_log WHERE timestamp < ? AND resolved = 1",
                    (thirty_days_ago.isoformat(),)
                )
                cleanup_results["error_log"] = cursor.rowcount

                logger.info(f"Database cleanup completed: {cleanup_results}")
                return cleanup_results

        except Exception as e:
            logger.error(f"Database cleanup failed: {e}")
            raise

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Database statistics
        """
        try:
            stats = self._stats.copy()

            # Add real-time statistics
            async with self.get_connection() as conn:
                # Get total table sizes
                table_sizes = {}
                for table in ["voice_commands", "actions", "device_pairing", "pc_connections"]:
                    try:
                        cursor = await conn.execute(f"SELECT COUNT(*) FROM {table}")
                        count = (await cursor.fetchone())[0]
                        table_sizes[table] = count
                    except Exception:
                        table_sizes[table] = 0

                # Get database file size
                try:
                    file_size = self.db_path.stat().st_size if self.db_path.exists() else 0
                except Exception:
                    file_size = 0

                stats.update({
                    "table_counts": table_sizes,
                    "database_file_size_bytes": file_size,
                    "database_file_size_mb": round(file_size / (1024 * 1024), 2),
                    "timestamp": datetime.utcnow().isoformat()
                })

                return stats

        except Exception as e:
            logger.error(f"Failed to get database statistics: {e}")
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

    async def close(self) -> None:
        """Close all connections and cleanup resources."""
        async with self._pool_lock:
            # Close all connections in pool
            for conn in self._connection_pool:
                await conn.close()
            self._connection_pool.clear()

            # Cancel migration job if running
            if hasattr(self, '_migration_job') and self._migration_job:
                self._migration_job.cancel()

        logger.info("Database connection manager closed")

    def __del__(self):
        """Cleanup when object is destroyed."""
        # Note: Can't use await in __del__, so this is best-effort
        try:
            # Close remaining connections synchronously
            for conn in self._connection_pool:
                conn.close()
            self._connection_pool.clear()
        except Exception:
            pass


class Migration:
    """Database migration definition."""

    def __init__(self, version: int, description: str, sql: str):
        self.version = version
        self.description = description
        self.sql = sql


# Global database connection instance
_db_connection: Optional[DatabaseConnection] = None


def get_database_connection() -> DatabaseConnection:
    """Get global database connection instance."""
    global _db_connection
    if _db_connection is None:
        _db_connection = DatabaseConnection()
    return _db_connection


async def initialize_database() -> None:
    """Initialize the global database connection."""
    db = get_database_connection()
    await db.initialize()


async def close_database() -> None:
    """Close the global database connection."""
    global _db_connection
    if _db_connection:
        await _db_connection.close()
        _db_connection = None


# Alias for backward compatibility
Database = DatabaseConnection