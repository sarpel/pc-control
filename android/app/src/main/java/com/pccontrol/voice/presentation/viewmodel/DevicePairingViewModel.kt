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
                // Get IP and PairingID from navigation arguments
                val ip = savedStateHandle.get<String>("ipAddress")
                val pairingId = savedStateHandle.get<String>("pairingId")
                
                if (ip == null || pairingId == null) {
                    throw Exception("Missing pairing information")
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
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        statusMessage = "Eşleştirme başarılı! PC'ye bağlandı.",
                        isError = false
                    )
                    // Navigation should be handled by the screen composable observing this state
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
