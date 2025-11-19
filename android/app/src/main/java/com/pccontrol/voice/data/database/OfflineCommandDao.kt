package com.pccontrol.voice.data.database

import androidx.room.*

/**
 * Data Access Object for offline commands.
 */
@Dao
interface OfflineCommandDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(command: OfflineCommandEntity)

    @Query("SELECT * FROM offline_commands WHERE status = 'PENDING' ORDER BY created_at ASC")
    suspend fun getPendingCommands(): List<OfflineCommandEntity>

    @Query("UPDATE offline_commands SET status = :status, executed_at = :timestamp WHERE command_id = :commandId")
    suspend fun updateStatus(commandId: String, status: String, timestamp: Long)

    @Query("DELETE FROM offline_commands WHERE status IN ('COMPLETED', 'FAILED') AND created_at < :timestamp")
    suspend fun deleteCompletedOlderThan(timestamp: Long)

    @Query("DELETE FROM offline_commands")
    suspend fun clearAll()
}