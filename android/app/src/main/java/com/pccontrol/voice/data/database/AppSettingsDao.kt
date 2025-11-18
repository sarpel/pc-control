package com.pccontrol.voice.data.database

import androidx.room.*
import kotlinx.coroutines.flow.Flow

/**
 * Data Access Object for application settings.
 */
@Dao
interface AppSettingsDao {

    @Query("SELECT * FROM app_settings ORDER BY category, key")
    fun getAllSettings(): Flow<List<AppSettingsEntity>>

    @Query("SELECT * FROM app_settings WHERE key = :key")
    suspend fun getSettingByKey(key: String): AppSettingsEntity?

    @Query("SELECT * FROM app_settings WHERE category = :category ORDER BY key")
    suspend fun getSettingsByCategory(category: String): List<AppSettingsEntity>

    @Query("SELECT value FROM app_settings WHERE key = :key")
    suspend fun getSettingValue(key: String): String?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertSetting(setting: AppSettingsEntity)

    @Update
    suspend fun updateSetting(setting: AppSettingsEntity)

    @Delete
    suspend fun deleteSetting(setting: AppSettingsEntity)

    @Query("DELETE FROM app_settings WHERE key = :key")
    suspend fun deleteSettingByKey(key: String)

    @Query("UPDATE app_settings SET value = :value, updated_at = strftime('%s', 'now') WHERE key = :key")
    suspend fun updateSettingValue(key: String, value: String)
}