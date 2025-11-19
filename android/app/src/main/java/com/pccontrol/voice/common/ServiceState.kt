package com.pccontrol.voice.common

import android.content.Context
import androidx.annotation.StringRes

enum class ConnectionState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    RECONNECTING,
    ERROR
}

enum class ServiceState {
    STOPPED,
    STARTING,
    RUNNING,
    LISTENING,
    ERROR
}

sealed class UiText {
    data class DynamicString(val value: String) : UiText()
    class StringResource(@StringRes val id: Int, vararg val args: Any) : UiText()

    fun asString(context: Context): String {
        return when (this) {
            is DynamicString -> value
            is StringResource -> context.getString(id, *args)
        }
    }
}
