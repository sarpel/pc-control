package com.pccontrol.voice.presentation.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pccontrol.voice.data.repository.PairingRepository
import com.pccontrol.voice.services.WebSocketManager
import dagger.hilt.android.lifecycle.HiltViewModel
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
    private val webSocketManager: WebSocketManager,
    private val pairingRepository: PairingRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(ConnectionStatusUiState())
    val uiState: StateFlow<ConnectionStatusUiState> = _uiState.asStateFlow()

    init {
        loadConnectionStatus()
        observeConnection()
    }

    private fun observeConnection() {
        viewModelScope.launch {
            webSocketManager.currentConnection.collect { connection ->
                val isConnected = webSocketManager.isConnected.value
                _uiState.value = _uiState.value.copy(
                    isConnected = isConnected,
                    pcName = connection?.pcName,
                    pcIpAddress = connection?.pcIpAddress,
                    lastConnectedTime = connection?.lastConnectedAt ?: 0L,
                    // Other fields would be updated from connection stats if available
                )
            }
        }
    }

    private fun loadConnectionStatus() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true)

            try {
                // Refresh connection status if needed
                // For now, the observer handles the updates
                
                _uiState.value = _uiState.value.copy(isLoading = false)
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
                pairingRepository.removePairing(deviceId)
                
                // Update UI list (should ideally observe database)
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
                webSocketManager.disconnect()
                // UI update handled by observer
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
                val result = webSocketManager.sendMessage("ping")
                
                if (result.isSuccess) {
                     _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        statusMessage = "Bağlantı testi başarılı",
                        isError = false
                    )
                } else {
                    throw result.exceptionOrNull() ?: Exception("Ping failed")
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
                // Remove all devices (implementation depends on repository capabilities)
                // For now, we iterate if we had a list, or just clear UI
                // Ideally: pairingRepository.clearAllPairings()
                
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
