package com.pccontrol.voice.presentation.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pccontrol.voice.network.PCDiscovery
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * Setup steps for the wizard flow
 */
enum class SetupStep {
    WELCOME,
    PC_DISCOVERY,
    PAIRING,
    VERIFICATION,
    SUCCESS
}

/**
 * Discovered PC data class
 */
data class DiscoveredPC(
    val id: String,
    val name: String,
    val ipAddress: String,
    val isAvailable: Boolean = true
)

/**
 * UI state for the setup wizard
 */
data class SetupWizardUiState(
    val currentStep: SetupStep = SetupStep.WELCOME,
    val isDiscovering: Boolean = false,
    val discoveredPCs: List<DiscoveredPC> = emptyList(),
    val selectedPC: DiscoveredPC? = null,
    val manualPCAddress: String = "",
    val pairingCode: String? = null,
    val isPairing: Boolean = false,
    val isVerifying: Boolean = false,
    val errorMessage: String? = null
)

/**
 * ViewModel for the setup wizard
 */
@HiltViewModel
class SetupWizardViewModel @Inject constructor(
    @ApplicationContext private val context: Context
) : ViewModel() {

    private val pcDiscovery = PCDiscovery(context)
    private val _uiState = MutableStateFlow(SetupWizardUiState())
    val uiState: StateFlow<SetupWizardUiState> = _uiState.asStateFlow()

    init {
        // Start PC discovery when entering PC_DISCOVERY step
        viewModelScope.launch {
            _uiState.collect { state ->
                if (state.currentStep == SetupStep.PC_DISCOVERY && !state.isDiscovering && state.discoveredPCs.isEmpty()) {
                    startPCDiscovery()
                }
            }
        }
    }

    fun nextStep() {
        val currentStep = _uiState.value.currentStep
        val nextStep = when (currentStep) {
            SetupStep.WELCOME -> SetupStep.PC_DISCOVERY
            SetupStep.PC_DISCOVERY -> SetupStep.PAIRING
            SetupStep.PAIRING -> {
                startPairing()
                SetupStep.VERIFICATION
            }
            SetupStep.VERIFICATION -> SetupStep.SUCCESS
            SetupStep.SUCCESS -> return
        }

        _uiState.value = _uiState.value.copy(currentStep = nextStep)
    }

    fun selectPC(pc: DiscoveredPC) {
        _uiState.value = _uiState.value.copy(selectedPC = pc)
    }

    fun retryDiscovery() {
        startPCDiscovery()
    }

    private fun startPCDiscovery() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isDiscovering = true,
                errorMessage = null
            )

            try {
                // Actual PC discovery logic using network scanning
                val discoveredPCList = pcDiscovery.discoverPCs()
                
                val discoveredPCs = discoveredPCList.map { pc ->
                    DiscoveredPC(
                        id = pc.id,
                        name = pc.name,
                        ipAddress = pc.ipAddress,
                        isAvailable = pc.isReachable
                    )
                }

                _uiState.value = _uiState.value.copy(
                    isDiscovering = false,
                    discoveredPCs = discoveredPCs,
                    errorMessage = if (discoveredPCs.isEmpty()) {
                        "PC bulunamadı. Manuel bağlantı deneyin."
                    } else {
                        null
                    }
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isDiscovering = false,
                    discoveredPCs = emptyList(),
                    errorMessage = "Keşif hatası: ${e.message}"
                )
            }
        }
    }

    fun enterPairingCode(code: String) {
        _uiState.value = _uiState.value.copy(pairingCode = code)
    }

    fun retryPairing() {
        _uiState.value = _uiState.value.copy(
            errorMessage = null,
            isPairing = false
        )
        startPairing()
    }

    private fun startPairing() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isPairing = true,
                errorMessage = null
            )

            try {
                // Actual pairing logic would involve:
                // 1. Establishing connection to selected PC
                // 2. Exchanging pairing code
                // 3. Certificate exchange
                // For now, we simulate the process
                kotlinx.coroutines.delay(1500)

                _uiState.value = _uiState.value.copy(
                    isPairing = false,
                    isVerifying = true
                )

                // Auto-advance to verification
                kotlinx.coroutines.delay(1000)
                _uiState.value = _uiState.value.copy(isVerifying = false)
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isPairing = false,
                    errorMessage = "Eşleştirme hatası: ${e.message}"
                )
            }
        }
    }

    fun retryVerification() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isVerifying = true,
                errorMessage = null
            )

            try {
                // Actual verification would check certificate validity
                // and ensure secure connection is established
                kotlinx.coroutines.delay(1500)

                _uiState.value = _uiState.value.copy(isVerifying = false)
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isVerifying = false,
                    errorMessage = "Doğrulama hatası: ${e.message}"
                )
            }
        }
    }

    fun finishSetup() {
        viewModelScope.launch {
            // Save setup completion status
            // In actual implementation, this would store pairing info to database
            // and navigate to main screen
        }
    }
}
