# Action Plan for Active Pull Request

This action plan addresses the suggestions and issues identified in the active pull request "Refactor imports and enhance database cleanup functionality".

## 📱 Android Application

### 🔴 Critical Fixes (Compilation & Logic)

1.  **Fix DataStore Usage (`QuickSettingsConfig.kt`)**
    *   **Issue**: Uses deprecated `createDataStore` API.
    *   **Action**: Migrate to `preferencesDataStore` delegate pattern defined at file scope.

2.  **Fix Auth Token Persistence (`PairingRepository.kt`)**
    *   **Issue**: `encryptSensitiveData` is called, but the result is never stored in SharedPreferences. Decryption attempts fail because the data is missing.
    *   **Action**:
        *   Store the result of `encryptSensitiveData` into SharedPreferences immediately.
        *   Retrieve from SharedPreferences before calling `decryptSensitiveData`.

3.  **Fix Database Migration (`AppDatabase.kt`)**
    *   **Issue**: `fallbackToDestructiveMigration()` is used while a new migration `MIGRATION_3_4` is defined but not added. This risks silent data loss.
    *   **Action**: Explicitly add migrations via `.addMigrations(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4)` and `.addCallback(DatabaseCallback(context))`.

4.  **Fix WebSocketManager Injection (`VoiceCommandViewModel.kt`)**
    *   **Issue**: `WebSocketManager` is missing Hilt injection, causing the ViewModel to use a placeholder `val success = true`.
    *   **Action**: Add `@Inject` to `WebSocketManager` constructor or provide it via a Hilt module, then inject it into `VoiceCommandViewModel`.

5.  **Fix Undefined Variable in Python Service (`pairing_validator.py`)**
    *   **Issue**: Variable `client_cert` is used but not defined (parameter is `client_certificate`).
    *   **Action**: Rename usage to `client_certificate` and add expiration check.

### 🟠 Major Improvements (Performance & Quality)

6.  **Optimize Command Clearing (`VoiceCommandRepository.kt`)**
    *   **Issue**: `clearAllCommands` fetches all commands and deletes them one by one in a loop.
    *   **Action**: Replace loop with a single `dao.deleteExpiredCommands(Long.MAX_VALUE)` call.

7.  **Remove Duplicate DAO Methods (`OfflineCommandDao.kt`)**
    *   **Issue**: `deleteOldCommands` and `deleteCompletedOlderThan` are identical.
    *   **Action**: Remove the duplicate, keeping the more descriptive name (`deleteCompletedOlderThan`).

8.  **Secure Connection ID Generation (`ConnectionQueueModels.kt`)**
    *   **Issue**: Uses `Math.random()` which is not cryptographically secure or guaranteed unique.
    *   **Action**: Replace with `java.util.UUID.randomUUID()`.

9.  **Refactor Enums (`VoiceAssistantServiceManager.kt`)**
    *   **Issue**: `ConnectionState` and `ServiceState` are duplicated in `domain` and `presentation` layers with inconsistent structures.
    *   **Action**: Move these enums to a `common` or `shared` package to be used by both layers.

10. **Improve WebSocket Connection Wait (`PairingRepository.kt`)**
    *   **Issue**: Uses a fixed `delay(2000)` which is unreliable.
    *   **Action**: Observe `webSocketClient.connectionState` flow to wait for `CONNECTED` state.

## 🐍 PC Agent (Python)

### 🔴 Critical Fixes

11. **Fix Import Paths (`websocket_server.py`)**
    *   **Issue**: Absolute imports without `src.` prefix fail when running as a module.
    *   **Action**: Restore `src.` prefix to imports (e.g., `from src.config.settings import ...`).

12. **Fix Settings Attribute Mismatch (`main.py`)**
    *   **Issue**: Code uses `settings.debug_mode` but the model defines `settings.debug`.
    *   **Action**: Update usage to `settings.debug`.

13. **Handle Anthropic Breaking Changes (`requirements.txt`)**
    *   **Issue**: `anthropic>=0.39.0` removes `client.count_tokens`.
    *   **Action**: Update code to use `client.beta.messages.count_tokens()` or pin a compatible version if immediate migration isn't possible.

### 🟡 Minor Fixes

14. **Remove Unused Imports (`voice_command_processor.py`)**
    *   **Action**: Remove unused `FileType` import.

## 📝 Execution Order

1.  **Phase 1**: Fix compilation errors (Android imports, DataStore, Python imports).
2.  **Phase 2**: Fix critical logic bugs (Auth token storage, DB migration, Variable names).
3.  **Phase 3**: Apply architectural improvements (Enums, Hilt injection).
4.  **Phase 4**: Apply optimizations and security fixes (UUID, DAO optimization).
