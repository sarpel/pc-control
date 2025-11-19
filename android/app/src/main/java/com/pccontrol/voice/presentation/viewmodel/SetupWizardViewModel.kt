package com.pccontrol.voice.presentation.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import android.content.Context
import com.pccontrol.voice.data.repository.PairingRepository
import com.pccontrol.voice.network.PCDiscovery
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.android.lifecycle.HiltViewModel
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
    val pairingId: String? = null,
    val isPairing: Boolean = false,
    val isVerifying: Boolean = false,
    val errorMessage: String? = null
)

/**
 * ViewModel for the setup wizard
 */
@HiltViewModel
class SetupWizardViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
    private val pcDiscovery: PCDiscovery,
    private val pairingRepository: PairingRepository
) : ViewModel() {

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
                val pcs = pcDiscovery.discoverPCs()
                val mappedPCs = pcs.map { 
                    DiscoveredPC(it.id, it.name, it.ipAddress, it.isAvailable) 
                }

                _uiState.value = _uiState.value.copy(
                    isDiscovering = false,
                    discoveredPCs = mappedPCs
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isDiscovering = false,
                    errorMessage = "Discovery failed: ${e.message}"
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
                val selectedPC = _uiState.value.selectedPC
                val manualIP = _uiState.value.manualPCAddress
                val ip = selectedPC?.ipAddress ?: manualIP.takeIf { it.isNotBlank() }
                
                if (ip == null) {
                    throw Exception("No PC selected or IP entered")
                }

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
                        isPairing = false,
                        isVerifying = true,
                        pairingCode = response?.pairing_code,
                        pairingId = response?.pairing_id
                    )
                    // Start polling for status
                    startVerificationPolling()
                } else {
                    throw result.exceptionOrNull() ?: Exception("Pairing initiation failed")
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isPairing = false,
                    errorMessage = "Pairing failed: ${e.message}"
                )
            }
        }
    }

    fun retryVerification() {
        startVerificationPolling()
    }

    private fun startVerificationPolling() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isVerifying = true,
                errorMessage = null
            )

            val pairingId = _uiState.value.pairingId
            val ip = _uiState.value.selectedPC?.ipAddress ?: _uiState.value.manualPCAddress

            if (pairingId == null || ip.isBlank()) {
                _uiState.value = _uiState.value.copy(
                    isVerifying = false,
                    errorMessage = "Missing pairing information"
                )
                return@launch
            }

            var attempts = 0
            while (attempts < 30) { // 1 minute timeout
                delay(2000)
                val result = pairingRepository.checkPairingStatus(pairingId, ip)

                if (result.isSuccess) {
                    val status = result.getOrNull()?.status
                    if (status == "paired" || status == "confirmed") {
                        finishSetup()
                        return@launch
                    } else if (status == "failed" || status == "rejected") {
                        _uiState.value = _uiState.value.copy(
                            isVerifying = false,
                            errorMessage = "Pairing rejected or failed"
                        )
                        return@launch
                    }
                }
                attempts++
            }

            _uiState.value = _uiState.value.copy(
                isVerifying = false,
                errorMessage = "Verification timed out. Please try again."
            )
        }
    }

    fun finishSetup() {
        viewModelScope.launch {
            // Save setup completion state
            val sharedPrefs = context.getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
            sharedPrefs.edit().putBoolean("setup_completed", true).apply()

            _uiState.value = _uiState.value.copy(
                currentStep = SetupStep.SUCCESS,
                isVerifying = false
            )
        }
    }
}
