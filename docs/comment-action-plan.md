# Comment-Derived Action Plan

This plan tracks open follow-ups called out directly in code comments. Each item captures a logical, non-deprecated task that still needs implementation.

## Quick Settings Tile Service
- Implement haptic feedback in `provideHapticFeedback()` so tile interactions give tactile confirmation.
- Add real status monitoring teardown inside `stopStatusMonitoring()` by keeping references to launched coroutines and cancelling them when the tile stops listening.
- Replace the placeholder connection flow in `VoiceAssistantServiceConnection.connect()` with actual service binding and connection status propagation; update `isConnected` accordingly.

## Voice Command Pipeline
- Wire `VoiceCommandViewModel.initialize()` to collect and expose real-time results from `AudioProcessingService`, rather than leaving the collector unimplemented.
- Persist command execution results in `WebSocketManager.handleCommandResult()` using the app’s storage/repository layer instead of only printing them.

## Connection & Pairing Management
- Implement repository-backed device cleanup in `ConnectionStatusViewModel.clearAllDevices()` (e.g., a `PairingRepository` method) so paired devices are removed from storage as well as UI state.

## PC Discovery
- Replace the heuristic string parsing in `PCDiscovery.parsePCInfo()` with proper JSON parsing of the API response and populate MAC addresses from ARP/NS lookups when available.
