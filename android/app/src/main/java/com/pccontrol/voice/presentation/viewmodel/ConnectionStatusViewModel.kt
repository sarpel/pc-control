package com.pccontrol.voice.presentation.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pccontrol.voice.data.database.AppDatabase
import com.pccontrol.voice.services.WebSocketManager
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * Paired device data class
 */
data class PairedDevice(
    val id: String,
    val name: String,
    val model: String,
    val lastConnected: Long
)

/**
 * UI state for connection status screen
 */
data class ConnectionStatusUiState(
    val isConnected: Boolean = false,
    val pcName: String? = null,
    val pcIpAddress: String? = null,
    val lastConnectedTime: Long = 0L,
    val latencyMs: Int = 0,
    val connectionCount: Int = 0,
    val pairedDevices: List<PairedDevice> = emptyList(),
    val wifiNetworkName: String? = null,
    val signalStrength: Int? = null,
    val pairingMethod: String? = null,
    val isLoading: Boolean = false,
    val statusMessage: String = "",
    val isError: Boolean = false
)

/**
 * ViewModel for connection status screen
 */
@HiltViewModel
class ConnectionStatusViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
    private val webSocketManager: WebSocketManager
) : ViewModel() {

    private val database = AppDatabase.getDatabase(context)
    private val _uiState = MutableStateFlow(ConnectionStatusUiState())
    val uiState: StateFlow<ConnectionStatusUiState> = _uiState.asStateFlow()

    init {
        loadConnectionStatus()
        observeConnectionState()
    }

    private fun observeConnectionState() {
        viewModelScope.launch {
            webSocketManager.isConnected.collect { isConnected ->
                _uiState.value = _uiState.value.copy(isConnected = isConnected)
            }
        }

        viewModelScope.launch {
            webSocketManager.currentConnection.collect { connection ->
                connection?.let {
                    _uiState.value = _uiState.value.copy(
                        pcName = it.pcName,
                        pcIpAddress = it.pcIpAddress,
                        lastConnectedTime = it.lastConnectedAt ?: 0L,
                        latencyMs = it.latencyMs ?: 0,
                        connectionCount = it.connectionCount ?: 0
                    )
                }
            }
        }
    }

    private fun loadConnectionStatus() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)

            try {
                // Load paired devices from database
                val connections = database.pcConnectionDao().getActiveConnections()
                val pairedDevices = connections.map { conn ->
                    PairedDevice(
                        id = conn.connectionId,
                        name = conn.pcName,
                        model = "Windows PC",
                        lastConnected = conn.lastConnectedAt ?: 0L
                    )
                }

                _uiState.value = _uiState.value.copy(
                    pairedDevices = pairedDevices,
                    isLoading = false
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    statusMessage = "Durum yüklenemedi: ${e.message}",
                    isError = true
                )
            }
        }
    }

    fun refreshStatus() {
        loadConnectionStatus()
    }

    fun removeDevice(deviceId: String) {
        viewModelScope.launch {
            try {
                // Remove device from database
                database.pcConnectionDao().deleteConnectionById(deviceId)
                
                val updatedDevices = _uiState.value.pairedDevices.filter { it.id != deviceId }
                _uiState.value = _uiState.value.copy(
                    pairedDevices = updatedDevices,
                    statusMessage = "Cihaz kaldırıldı",
                    isError = false
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    statusMessage = "Cihaz kaldırılamadı: ${e.message}",
                    isError = true
                )
            }
        }
    }

    fun disconnect() {
        viewModelScope.launch {
            try {
                // Disconnect from PC
                webSocketManager.disconnect()
                
                _uiState.value = _uiState.value.copy(
                    isConnected = false,
                    pcName = null,
                    pcIpAddress = null,
                    latencyMs = 0,
                    statusMessage = "Bağlantı kesildi",
                    isError = false
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    statusMessage = "Bağlantı kesilemedi: ${e.message}",
                    isError = true
                )
            }
        }
    }

    fun testConnection() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isLoading = true,
                statusMessage = "Bağlantı test ediliyor...",
                isError = false
            )

            try {
                // Send ping message to test connection
                val currentConnection = webSocketManager.currentConnection.value
                if (currentConnection != null && webSocketManager.isConnected.value) {
                    // Measure latency by sending a ping
                    val startTime = System.currentTimeMillis()
                    val result = webSocketManager.sendMessage("""{"type":"ping"}""")
                    val endTime = System.currentTimeMillis()
                    
                    if (result.isSuccess) {
                        val latency = (endTime - startTime).toInt()
                        
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            latencyMs = latency,
                            statusMessage = "Bağlantı testi başarılı (${latency}ms)",
                            isError = false
                        )
                    } else {
                        throw Exception("Ping başarısız")
                    }
                } else {
                    throw Exception("Bağlantı yok")
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    statusMessage = "Bağlantı testi başarısız: ${e.message}",
                    isError = true
                )
            }
        }
    }

    fun clearAllDevices() {
        viewModelScope.launch {
            try {
                // Clear all paired devices from database
                val allDevices = _uiState.value.pairedDevices
                for (device in allDevices) {
                    database.pcConnectionDao().deleteConnectionById(device.id)
                }
                
                _uiState.value = _uiState.value.copy(
                    pairedDevices = emptyList(),
                    statusMessage = "Tüm cihazlar temizlendi",
                    isError = false
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    statusMessage = "Cihazlar temizlenemedi: ${e.message}",
                    isError = true
                )
            }
        }
    }
}
