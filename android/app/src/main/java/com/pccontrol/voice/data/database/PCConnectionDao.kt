package com.pccontrol.voice.data.database

import androidx.room.*
import kotlinx.coroutines.flow.Flow

/**
 * Data Access Object for PC connections.
 */
@Dao
interface PCConnectionDao {

    @Query("SELECT * FROM pc_connections ORDER BY last_connected_at DESC")
    fun getAllConnections(): Flow<List<PCConnectionEntity>>

    @Query("SELECT * FROM pc_connections WHERE connection_id = :connectionId")
    suspend fun getConnectionById(connectionId: String): PCConnectionEntity?

    @Query("SELECT * FROM pc_connections WHERE status = :status")
    suspend fun getConnectionsByStatus(status: String): List<PCConnectionEntity>

    @Query("SELECT * FROM pc_connections WHERE pc_ip_address = :ipAddress")
    suspend fun getConnectionByIpAddress(ipAddress: String): PCConnectionEntity?

    @Query("SELECT * FROM pc_connections WHERE device_pairing_id = :pairingId")
    suspend fun getConnectionByPairingId(pairingId: String): PCConnectionEntity?

    @Query("SELECT * FROM pc_connections WHERE status IN ('connected', 'authenticated') ORDER BY last_heartbeat DESC")
    suspend fun getActiveConnections(): List<PCConnectionEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertConnection(connection: PCConnectionEntity)

    @Update
    suspend fun updateConnection(connection: PCConnectionEntity)

    @Delete
    suspend fun deleteConnection(connection: PCConnectionEntity)

    @Query("DELETE FROM pc_connections WHERE connection_id = :connectionId")
    suspend fun deleteConnectionById(connectionId: String)

    @Query("UPDATE pc_connections SET status = :status, updated_at = strftime('%s', 'now') WHERE connection_id = :connectionId")
    suspend fun updateConnectionStatus(connectionId: String, status: String)

    @Query("UPDATE pc_connections SET latency_ms = :latency, last_heartbeat = strftime('%s', 'now') WHERE connection_id = :connectionId")
    suspend fun updateConnectionLatency(connectionId: String, latency: Int)

    @Query("UPDATE pc_connections SET connection_count = connection_count + 1, total_connection_time_ms = total_connection_time_ms + :additionalTime, last_connected_at = strftime('%s', 'now') WHERE connection_id = :connectionId")
    suspend fun updateConnectionStats(connectionId: String, additionalTime: Long)

    @Query("DELETE FROM pc_connections WHERE status = 'disconnected' AND last_heartbeat < strftime('%s', 'now', '-7 days')")
    suspend fun cleanupOldConnections()
}