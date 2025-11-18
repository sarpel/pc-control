package com.pccontrol.voice.presentation.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
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
    val isPairing: Boolean = false,
    val isVerifying: Boolean = false,
    val errorMessage: String? = null
)

/**
 * ViewModel for the setup wizard
 */
@HiltViewModel
class SetupWizardViewModel @Inject constructor() : ViewModel() {

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

            // TODO: Implement actual PC discovery logic
            // Simulating discovery for now
            kotlinx.coroutines.delay(2000)

            // Mock discovered PCs
            val mockPCs = listOf(
                DiscoveredPC(
                    id = "pc1",
                    name = "Windows PC",
                    ipAddress = "192.168.1.100",
                    isAvailable = true
                )
            )

            _uiState.value = _uiState.value.copy(
                isDiscovering = false,
                discoveredPCs = mockPCs
            )
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

            // TODO: Implement actual pairing logic
            kotlinx.coroutines.delay(1500)

            _uiState.value = _uiState.value.copy(
                isPairing = false,
                isVerifying = true
            )

            // Auto-advance to verification
            kotlinx.coroutines.delay(1000)
            _uiState.value = _uiState.value.copy(isVerifying = false)
        }
    }

    fun retryVerification() {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(
                isVerifying = true,
                errorMessage = null
            )

            // TODO: Implement actual verification logic
            kotlinx.coroutines.delay(1500)

            _uiState.value = _uiState.value.copy(isVerifying = false)
        }
    }

    fun finishSetup() {
        // TODO: Save setup completion and navigate to main screen
        viewModelScope.launch {
            // Save pairing information
            // Navigate to main activity
        }
    }
}
