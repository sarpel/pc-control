package com.pccontrol.voice.data.database

import androidx.room.*

/**
 * Data Access Object for offline commands.
 */
@Dao
interface OfflineCommandDao {

    @Query("SELECT * FROM offline_commands ORDER BY created_at DESC")
    suspend fun getAllCommands(): List<OfflineCommandEntity>

    @Query("SELECT * FROM offline_commands WHERE status = :status ORDER BY created_at")
    suspend fun getCommandsByStatus(status: String): List<OfflineCommandEntity>

    @Query("SELECT * FROM offline_commands WHERE command_type = :commandType ORDER BY created_at")
    suspend fun getCommandsByType(commandType: String): List<OfflineCommandEntity>

    @Query("SELECT * FROM offline_commands WHERE device_name = :deviceName ORDER BY created_at")
    suspend fun getCommandsByDevice(deviceName: String): List<OfflineCommandEntity>

    @Query("SELECT * FROM offline_commands WHERE status = 'pending' ORDER BY created_at ASC LIMIT :limit")
    suspend fun getPendingCommands(limit: Int = 10): List<OfflineCommandEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertCommand(command: OfflineCommandEntity)

    @Update
    suspend fun updateCommand(command: OfflineCommandEntity)

    @Delete
    suspend fun deleteCommand(command: OfflineCommandEntity)

    @Query("DELETE FROM offline_commands WHERE command_id = :commandId")
    suspend fun deleteCommandById(commandId: String)

    @Query("UPDATE offline_commands SET status = :status, executed_at = strftime('%s', 'now') WHERE command_id = :commandId")
    suspend fun updateCommandStatus(commandId: String, status: String)

    @Query("UPDATE offline_commands SET status = 'failed', error_message = :errorMessage WHERE command_id = :commandId")
    suspend fun markCommandFailed(commandId: String, errorMessage: String)

    @Query("DELETE FROM offline_commands WHERE status IN ('completed', 'failed') AND created_at < :timestamp")
    suspend fun deleteCompletedOlderThan(timestamp: Long)
}