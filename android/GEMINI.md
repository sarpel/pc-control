# PC Voice Assistant - Project Context

## Project Overview

**PC Voice Assistant** is an Android application designed to control a PC via voice commands. It acts as a client, communicating with a PC server (likely running a counterpart application) over a local network connection using HTTP and WebSockets.

**Key Functionality:**
*   **Voice Command Processing:** Captures audio, processes it, and sends commands to the PC.
*   **Real-time Communication:** Uses WebSockets for low-latency control and feedback.
*   **Background Operation:** Runs as a Foreground Service (`VoiceAssistantService`) to ensure continuous operation even when the app is minimized.
*   **Quick Access:** Includes a Quick Settings Tile for easy toggling.
*   **Secure Connection:** Implements certificate pinning and security crypto features.
*   **Auto-Start:** Capable of starting on boot.

## Technical Architecture

The project follows a **Clean Architecture** approach, structured by layers:

*   **Presentation Layer (`presentation/`)**:
    *   Built with **Jetpack Compose** (Material3) for the UI.
    *   Uses **ViewModels** (Hilt-injected) for state management.
    *   `MainActivity` is the entry point.
    *   `QuickSettingsTileService` provides system-level access.
*   **Domain Layer (`domain/`)**:
    *   Contains business logic and service definitions (`VoiceAssistantService`, `AudioCaptureService`).
    *   Defines Use Cases (implied).
*   **Data Layer (`data/`)**:
    *   Handles data persistence using **Room** (database) and **DataStore** (preferences).
    *   Manages repositories.
*   **Network Layer (`network/`)**:
    *   Handles HTTP requests via **OkHttp**.
    *   Manages WebSocket connections using **Java-WebSocket**.
*   **Infrastructure:**
    *   `workers/`: Background tasks using **WorkManager**.
    *   `security/`: Cryptographic utilities.
    *   `audio/`: Audio recording and processing logic.

## Tech Stack & Libraries

*   **Language:** Kotlin (1.9.20)
*   **UI Framework:** Jetpack Compose (BOM 2023.10.01)
*   **Dependency Injection:** Dagger Hilt (2.47)
*   **Asynchronous Programming:** Kotlin Coroutines & Flow
*   **Networking:**
    *   OkHttp (REST)
    *   Java-WebSocket (Real-time)
    *   Kotlinx Serialization (JSON parsing)
*   **Persistence:**
    *   Room (SQLite abstraction)
    *   DataStore (Preferences)
*   **Code Quality:** Detekt (Static analysis)
*   **Testing:** JUnit 4, Mockito, Robolectric, Espresso

## Build & Development

### Prerequisites
*   JDK 17 (Java 11 compatibility target)
*   Android SDK (compileSdk 34)

### Key Commands

*   **Build Debug APK:**
    ```bash
    ./gradlew assembleDebug
    ```
*   **Run Unit Tests:**
    ```bash
    ./gradlew test
    ```
*   **Run Instrumented Tests:**
    ```bash
    ./gradlew connectedAndroidTest
    ```
*   **Run Static Analysis (Detekt):**
    ```bash
    ./gradlew detekt
    ```
*   **Clean Build:**
    ```bash
    ./gradlew clean
    ```

## Configuration

*   **Application ID:** `com.pccontrol.voice`
*   **Min SDK:** 30 (Android 11)
*   **Target SDK:** 34 (Android 14)
*   **API Configuration:**
    *   Base URLs are defined in `app/build.gradle.kts` under `buildConfigField`.
    *   Debug: `http://10.0.2.2:8765` (Android Emulator loopback)
    *   Release: `https://pc.local:8765`

## Development Conventions

*   **Dependency Injection:** Use `@HiltViewModel` for ViewModels and `@AndroidEntryPoint` for Activities/Fragments/Services.
*   **Concurrency:** Use `suspend` functions and `Flow` for data streams. Avoid blocking the main thread.
*   **UI:** All new UI should be written in Jetpack Compose.
*   **Permissions:** Runtime permissions (especially Microphone and Notification) must be handled carefully due to Android 14+ requirements.
