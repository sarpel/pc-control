package com.pccontrol.voice.data.database

import androidx.room.*

/**
 * Data Access Object for command history.
 */
@Dao
interface CommandHistoryDao {

    @Query("SELECT * FROM command_history ORDER BY timestamp DESC LIMIT :limit")
    suspend fun getRecentCommands(limit: Int = 10): List<CommandHistoryEntity>

    @Query("SELECT * FROM command_history WHERE device_name = :deviceName ORDER BY timestamp DESC LIMIT :limit")
    suspend fun getRecentCommandsByDevice(deviceName: String, limit: Int = 10): List<CommandHistoryEntity>

    @Query("SELECT * FROM command_history WHERE success = :success ORDER BY timestamp DESC LIMIT :limit")
    suspend fun getCommandsBySuccess(success: Boolean, limit: Int = 10): List<CommandHistoryEntity>

    @Query("SELECT * FROM command_history WHERE timestamp > :timestamp ORDER BY timestamp DESC")
    suspend fun getCommandsAfter(timestamp: Long): List<CommandHistoryEntity>

    @Query("SELECT * FROM command_history WHERE expires_at < :timestamp")
    suspend fun getExpiredCommands(timestamp: Long): List<CommandHistoryEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertCommand(command: CommandHistoryEntity)

    @Delete
    suspend fun deleteCommand(command: CommandHistoryEntity)

    @Query("DELETE FROM command_history WHERE expires_at < :timestamp")
    suspend fun deleteExpiredCommands(timestamp: Long)

    @Query("DELETE FROM command_history WHERE history_id = :historyId")
    suspend fun deleteCommandById(historyId: String)

    @Query("DELETE FROM command_history")
    suspend fun deleteAllCommands()
}