package com.pccontrol.voice.data.database

import androidx.room.*

/**
 * Data Access Object for device pairing information.
 */
@Dao
interface DevicePairingDao {

    @Query("SELECT * FROM device_pairing ORDER BY created_at DESC")
    suspend fun getAllPairings(): List<DevicePairingEntity>

    @Query("SELECT * FROM device_pairing WHERE pairing_id = :pairingId")
    suspend fun getPairingById(pairingId: String): DevicePairingEntity?

    @Query("SELECT * FROM device_pairing WHERE android_device_id = :androidDeviceId")
    suspend fun getPairingsByAndroidDevice(androidDeviceId: String): List<DevicePairingEntity>

    @Query("SELECT * FROM device_pairing WHERE android_fingerprint = :fingerprint")
    suspend fun getPairingByAndroidFingerprint(fingerprint: String): DevicePairingEntity?

    @Query("SELECT * FROM device_pairing WHERE pc_fingerprint = :fingerprint")
    suspend fun getPairingByPcFingerprint(fingerprint: String): DevicePairingEntity?

    @Query("SELECT * FROM device_pairing WHERE pairing_code = :pairingCode")
    suspend fun getPairingByCode(pairingCode: String): DevicePairingEntity?

    @Query("SELECT * FROM device_pairing WHERE status = :status ORDER BY created_at DESC")
    suspend fun getPairingsByStatus(status: String): List<DevicePairingEntity>

    @Query("SELECT * FROM device_pairing WHERE expires_at > :timestamp AND status IN ('initiated', 'awaiting_confirmation')")
    suspend fun getActivePairings(timestamp: Long): List<DevicePairingEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertPairing(pairing: DevicePairingEntity)

    @Update
    suspend fun updatePairing(pairing: DevicePairingEntity)

    @Delete
    suspend fun deletePairing(pairing: DevicePairingEntity)

    @Query("DELETE FROM device_pairing WHERE pairing_id = :pairingId")
    suspend fun deletePairingById(pairingId: String)

    @Query("UPDATE device_pairing SET status = :status, completed_at = strftime('%s', 'now') WHERE pairing_id = :pairingId")
    suspend fun updatePairingStatus(pairingId: String, status: String)

    @Query("UPDATE device_pairing SET expires_at = :expiresAt WHERE pairing_id = :pairingId")
    suspend fun updatePairingExpiry(pairingId: String, expiresAt: Long)

    @Query("DELETE FROM device_pairing")
    suspend fun deleteAllPairings()

    @Query("DELETE FROM device_pairing WHERE expires_at < :timestamp AND status != 'completed'")
    suspend fun deleteExpiredPairings(timestamp: Long)
}