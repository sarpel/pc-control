package com.pccontrol.voice.presentation.viewmodel

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pccontrol.voice.data.repository.PairingRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import kotlin.random.Random

/**
 * UI state for device pairing screen
 */
data class DevicePairingUiState(
    val ipAddress: String = "",
    val pairingId: String? = null,
    val isInitiated: Boolean = false,
    val pairingCode: String = "",
    val pairingCodeError: String? = null,
    val generatedPairingCode: String? = null,
    val showPairingCode: Boolean = false,
    val isLoading: Boolean = false,
    val statusMessage: String = "",
    val isError: Boolean = false
)

/**
 * ViewModel for device pairing screen
 */
@HiltViewModel
class DevicePairingViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
    private val pairingRepository: PairingRepository,
    private val savedStateHandle: SavedStateHandle
) : ViewModel() {

    private val _uiState = MutableStateFlow(DevicePairingUiState())
    val uiState: StateFlow<DevicePairingUiState> = _uiState.asStateFlow()

    fun updateIpAddress(ip: String) {
        _uiState.value = _uiState.value.copy(
            ipAddress = ip,
            statusMessage = "",
            isError = false
        )
    }

    fun initiatePairing() {
        val ip = _uiState.value.ipAddress
        if (ip.isBlank()) {
            _uiState.value = _uiState.value.copy(
                statusMessage = "Lütfen IP adresi girin",
                isError = true
            )
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isLoading = true,
                statusMessage = "PC'ye bağlanılıyor...",
                isError = false
            )

            try {
                val deviceId = android.provider.Settings.Secure.getString(
                    context.contentResolver, 
                    android.provider.Settings.Secure.ANDROID_ID
                )

                val result = pairingRepository.initiatePairing(
                    deviceName = android.os.Build.MODEL,
                    deviceId = deviceId,
                    pcIpAddress = ip
                )

                if (result.isSuccess) {
                    val response = result.getOrNull()
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        isInitiated = true,
                        pairingId = response?.pairing_id,
                        statusMessage = "Bağlantı başarılı. Lütfen PC loglarında görünen kodu girin.",
                        isError = false
                    )
                } else {
                    throw result.exceptionOrNull() ?: Exception("Bağlantı başarısız")
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    statusMessage = "Bağlantı hatası: ${e.message}",
                    isError = true
                )
            }
        }
    }

    fun updatePairingCode(code: String) {
        // Only allow digits, max 6 characters
        val filteredCode = code.filter { it.isDigit() }.take(6)

        _uiState.value = _uiState.value.copy(
            pairingCode = filteredCode,
            pairingCodeError = when {
                filteredCode.isEmpty() -> null
                filteredCode.length < 6 -> "Kod 6 haneli olmalıdır"
                else -> null
            }
        )
    }

    fun generatePairingCode() {
        // Deprecated/Unused in new flow but kept for compatibility if needed
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isLoading = true,
                statusMessage = "Kod oluşturuluyor...",
                isError = false
            )

            try {
                // Generate a random 6-digit code
                val code = Random.nextInt(100000, 999999).toString()

                _uiState.value = _uiState.value.copy(
                    generatedPairingCode = code,
                    showPairingCode = true,
                    isLoading = false,
                    statusMessage = "Kod başarıyla oluşturuldu. PC'ye girilen kodu yazın.",
                    isError = false
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    statusMessage = "Kod oluşturulamadı: ${e.message}",
                    isError = true
                )
            }
        }
    }

    fun copyPairingCode() {
        val code = _uiState.value.generatedPairingCode ?: return

        try {
            val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            val clip = ClipData.newPlainText("Pairing Code", code)
            clipboard.setPrimaryClip(clip)

            _uiState.value = _uiState.value.copy(
                statusMessage = "Kod kopyalandı",
                isError = false
            )
        } catch (e: Exception) {
            _uiState.value = _uiState.value.copy(
                statusMessage = "Kod kopyalanamadı: ${e.message}",
                isError = true
            )
        }
    }

    fun startPairing() {
        val code = _uiState.value.pairingCode

        if (code.length != 6) {
            _uiState.value = _uiState.value.copy(
                pairingCodeError = "Lütfen 6 haneli kodu girin",
                isError = true
            )
            return
        }

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isLoading = true,
                statusMessage = "Eşleştiriliyor...",
                isError = false,
                pairingCodeError = null
            )

            try {
                val ip = _uiState.value.ipAddress
                val pairingId = _uiState.value.pairingId
                
                if (ip.isBlank() || pairingId == null) {
                    throw Exception("Eşleştirme bilgileri eksik. Lütfen önce bağlanın.")
                }

                val deviceId = android.provider.Settings.Secure.getString(
                    context.contentResolver, 
                    android.provider.Settings.Secure.ANDROID_ID
                )

                val result = pairingRepository.verifyPairing(
                    pairingId = pairingId,
                    pairingCode = code,
                    deviceId = deviceId,
                    pcIpAddress = ip
                )

                if (result.isSuccess) {
                    // Establish secure connection immediately after pairing
                    val connectionResult = pairingRepository.establishSecureConnection(
                        deviceId = deviceId,
                        pcIpAddress = ip
                    )

                    if (connectionResult.isSuccess) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            statusMessage = "Eşleştirme başarılı! PC'ye bağlandı.",
                            isError = false
                        )
                        // Navigation should be handled by the screen composable observing this state
                    } else {
                        throw connectionResult.exceptionOrNull() ?: Exception("Bağlantı kurulamadı")
                    }
                } else {
                    throw result.exceptionOrNull() ?: Exception("Pairing failed")
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    statusMessage = "Eşleştirme başarısız: ${e.message}",
                    isError = true,
                    pairingCodeError = "Geçersiz kod veya bağlantı hatası"
                )
            }
        }
    }
}
