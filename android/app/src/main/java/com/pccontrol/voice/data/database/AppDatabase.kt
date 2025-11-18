package com.pccontrol.voice.data.database

import android.content.Context
import androidx.room.*
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import androidx.work.WorkManager
import com.pccontrol.voice.data.models.*
import com.pccontrol.voice.workers.DatabaseCleanupWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/**
 * Room database for PC Voice Assistant Android application.

 * This database stores:
 * - Local device connections
 * - Command history
 * - Application preferences
 * - Offline cached data
 */
@Database(
    entities = [
        PCConnectionEntity::class,
        CommandHistoryEntity::class,
        AppSettingsEntity::class,
        OfflineCommandEntity::class,
        DevicePairingEntity::class
    ],
    version = 4,
    exportSchema = false
)
@TypeConverters(Converters::class)
abstract class AppDatabase : RoomDatabase() {

    abstract fun pcConnectionDao(): PCConnectionDao
    abstract fun commandHistoryDao(): CommandHistoryDao
    abstract fun appSettingsDao(): AppSettingsDao
    abstract fun offlineCommandDao(): OfflineCommandDao
    abstract fun devicePairingDao(): DevicePairingDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getDatabase(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "pc_voice_assistant_database"
                )
                    .fallbackToDestructiveMigration()
                    .build()
                INSTANCE = instance
                instance
            }
        }
        
        fun getInstance(context: Context): AppDatabase = getDatabase(context)
    }

    /**
     * Database callback for initialization and cleanup.
     */
    private class DatabaseCallback(private val context: Context) : RoomDatabase.Callback() {
        override fun onCreate(db: SupportSQLiteDatabase) {
            super.onCreate(db)

            // Create initial settings
            createInitialSettings(db)

            // Schedule periodic cleanup
            schedulePeriodicCleanup()
        }

        override fun onOpen(db: SupportSQLiteDatabase) {
            super.onOpen(db)

            // Enable foreign key constraints
            db.execSQL("PRAGMA foreign_keys=ON")

            // Configure database for performance
            db.execSQL("PRAGMA journal_mode=WAL")
            db.execSQL("PRAGMA synchronous=NORMAL")
            db.execSQL("PRAGMA cache_size=10000")
        }

        private fun createInitialSettings(db: SupportSQLiteDatabase) {
            val currentTime = System.currentTimeMillis()
            // Insert default app settings
            db.execSQL("""
                INSERT INTO app_settings (key, value, category, description, is_encrypted, created_at, updated_at) VALUES
                ('max_command_history', '5', 'general', 'Maximum number of commands to keep in history', 0, $currentTime, $currentTime),
                ('enable_offline_mode', 'true', 'general', 'Enable offline command processing', 0, $currentTime, $currentTime),
                ('auto_reconnect', 'true', 'connection', 'Automatically reconnect to PC', 0, $currentTime, $currentTime),
                ('connection_timeout_ms', '10000', 'connection', 'Connection timeout in milliseconds', 0, $currentTime, $currentTime),
                ('audio_quality', 'high', 'audio', 'Audio recording quality setting', 0, $currentTime, $currentTime),
                ('enable_notifications', 'true', 'general', 'Enable push notifications', 0, $currentTime, $currentTime),
                ('dark_mode', 'false', 'appearance', 'Enable dark mode theme', 0, $currentTime, $currentTime),
                ('language', 'tr', 'general', 'Application language setting', 0, $currentTime, $currentTime)
            """.trimIndent())
        }

        private fun schedulePeriodicCleanup() {
            val workManager = WorkManager.getInstance(context)
            val cleanupRequest = DatabaseCleanupWorker.buildCleanupRequest()
            workManager.enqueue(cleanupRequest)
        }
    }

    /**
     * Migration from version 1 to 2.
     * Add DevicePairing table and update PCConnection.
     */
    object MIGRATION_1_2 : Migration(1, 2) {
        override fun migrate(database: SupportSQLiteDatabase) {
            // Create DevicePairing table
            database.execSQL("""
                CREATE TABLE IF NOT EXISTS device_pairing (
                    pairing_id TEXT PRIMARY KEY,
                    android_device_id TEXT NOT NULL,
                    android_fingerprint TEXT NOT NULL,
                    pc_fingerprint TEXT NOT NULL,
                    pairing_code TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'initiated',
                    created_at INTEGER NOT NULL,
                    completed_at INTEGER,
                    pc_name TEXT,
                    pc_ip_address TEXT,
                    expires_at INTEGER NOT NULL,
                    authentication_token TEXT,
                    device_name TEXT,
                    device_model TEXT,
                    os_version TEXT,
                    pairing_method TEXT DEFAULT 'manual'
                )
            """.trimIndent())

            // Update PCConnection table to add device_pairing_id foreign key
            database.execSQL("ALTER TABLE pc_connections ADD COLUMN device_pairing_id TEXT")
            database.execSQL("ALTER TABLE pc_connections ADD COLUMN device_name TEXT")
            database.execSQL("ALTER TABLE pc_connections ADD COLUMN device_model TEXT")
        }
    }

    /**
     * Migration from version 2 to 3.
     * Add OfflineCommand table and improve existing tables.
     */
    object MIGRATION_2_3 : Migration(2, 3) {
        override fun migrate(database: SupportSQLiteDatabase) {
            // Create OfflineCommand table
            database.execSQL("""
                CREATE TABLE IF NOT EXISTS offline_commands (
                    command_id TEXT PRIMARY KEY,
                    transcription TEXT NOT NULL,
                    command_type TEXT NOT NULL,
                    parameters TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at INTEGER NOT NULL,
                    executed_at INTEGER,
                    error_message TEXT,
                    device_name TEXT
                )
            """.trimIndent())

            // Add indexes for performance
            database.execSQL("CREATE INDEX IF NOT EXISTS index_pc_connections_status ON pc_connections(status)")
            database.execSQL("CREATE INDEX IF NOT EXISTS index_command_history_timestamp ON command_history(timestamp)")
            database.execSQL("CREATE INDEX IF NOT EXISTS index_offline_commands_status ON offline_commands(status)")
            database.execSQL("CREATE INDEX IF NOT EXISTS index_device_pairing_android_device_id ON device_pairing(android_device_id)")

            // Update existing data with timestamps if needed
            database.execSQL("UPDATE pc_connections SET last_connected_at = created_at WHERE last_connected_at IS NULL")
            database.execSQL("UPDATE pc_connections SET last_heartbeat = created_at WHERE last_heartbeat IS NULL")
        }
    }

    /**
     * Migration from version 3 to 4.
     * Add missing columns to AppSettings table.
     */
    object MIGRATION_3_4 : Migration(3, 4) {
        override fun migrate(database: SupportSQLiteDatabase) {
            // Add missing columns to app_settings table
            val currentTime = System.currentTimeMillis()
            
            database.execSQL("ALTER TABLE app_settings ADD COLUMN description TEXT")
            database.execSQL("ALTER TABLE app_settings ADD COLUMN is_encrypted INTEGER NOT NULL DEFAULT 0")
            database.execSQL("ALTER TABLE app_settings ADD COLUMN created_at INTEGER NOT NULL DEFAULT $currentTime")
            database.execSQL("ALTER TABLE app_settings ADD COLUMN updated_at INTEGER NOT NULL DEFAULT $currentTime")
        }
    }
}