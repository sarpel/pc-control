# Action Plan

This action plan is based on the analysis of the codebase and the `docs/UI_LAYER_FIX_SUMMARY.md` document. It targets logical and not-deprecated tasks to improve the application.

## 1. Complete Repository Implementations

### PairingRepository
- **Implement `clearAllPairings`**: The `ConnectionStatusViewModel` currently clears the UI list but notes that it should ideally call `pairingRepository.clearAllPairings()`.
  - *File*: `android/app/src/main/java/com/pccontrol/voice/data/repository/PairingRepository.kt`
  - *Task*: Add a method to remove all paired devices from the database and secure storage.

### PCDiscovery
- **Improve JSON Parsing**: The `parsePCInfo` method currently uses simple string parsing.
  - *File*: `android/app/src/main/java/com/pccontrol/voice/network/PCDiscovery.kt`
  - *Task*: Replace manual string parsing with `kotlinx.serialization` or `JSONObject` for robust handling of API responses.

## 2. Address "Future (Other Layers)" Tasks

These tasks were identified in `docs/UI_LAYER_FIX_SUMMARY.md` as necessary fixes outside the UI layer.

### Domain Layer
- **Fix `VoiceAssistantService.kt` compilation errors**: Address domain layer issues.
  - *Status*: Pending investigation of specific errors.

### Network Layer
- **Fix `AudioStreamer.kt` compilation errors**.
- **Fix `WebSocketClient.kt` compilation errors**.
- **Refine `PCDiscovery.kt`**: While it compiles, ensure it fully integrates with the rest of the network layer fixes.

### Service Layer
- **Fix `QuickSettingsTileService.kt` compilation errors**.

### UI Components
- **Fix missing imports in UI components**: Identify and resolve any remaining compilation errors in UI components not covered by the recent UI layer fix.

## 3. Testing Strategy

Implement the testing recommendations to ensure stability.

### Unit Tests
- **SetupWizardViewModel**: Test step navigation and state transitions.
- **DevicePairingViewModel**: Test code validation and generation logic.
- **ConnectionStatusViewModel**: Test device management operations and state updates.

### Integration Tests
- **Setup Wizard Flow**: Verify the complete flow from welcome to success.
- **Device Pairing**: Test with actual or mocked PC agent interactions.
- **Connection Status**: Verify refresh logic and real-time updates.

### UI Tests
- **Navigation**: Verify screen transitions in Setup Wizard.
- **Input Validation**: Test pairing code entry fields.
- **Interactions**: Verify buttons and list items in Connection Status screen.
