package com.pccontrol.voice.data.database

import androidx.room.TypeConverter
import java.util.*

/**
 * Type converters for Room database.
 */
class Converters {

    @TypeConverter
    fun fromTimestamp(value: Long?): Date? {
        return value?.let { Date(it) }
    }

    @TypeConverter
    fun dateToTimestamp(date: Date?): Long? {
        return date?.time
    }

    @TypeConverter
    fun fromUUID(uuid: String?): UUID? {
        return uuid?.let { UUID.fromString(it) }
    }

    @TypeConverter
    fun uuidToUUID(uuid: UUID?): String? {
        return uuid?.toString()
    }

    @TypeConverter
    fun fromStringList(value: String?): List<String>? {
        return value?.split(",")
    }

    @TypeConverter
    fun stringListToString(list: List<String>?): String? {
        return list?.joinToString(",")
    }
}