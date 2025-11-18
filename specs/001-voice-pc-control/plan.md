# Implementation Plan: Voice-Controlled PC Assistant

**Branch**: `001-voice-pc-control` | **Date**: 2025-11-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-voice-pc-control/spec.md`

## Summary

Voice-controlled PC assistant system enabling hands-free Windows PC control from Android device using Turkish voice commands with English technical terms. System uses WebSocket for real-time audio streaming, Whisper.cpp for local STT processing, Claude API with MCP tool routing for command interpretation, and mTLS encryption for secure communication. Supports PC wake-from-sleep via Wake-on-LAN, system operations (app launch, volume control, file search), and browser automation (navigation, search, content extraction).

## Technical Context

**Language/Version**: Kotlin (Android 11+ SDK 30+), Python 3.10+ (Windows)
**Primary Dependencies**: OkHttp (WebSocket), Jetpack Compose (UI), FastAPI (WebSocket server), Whisper.cpp (STT), Claude API (NLU), MCP servers (system/browser automation)
**Storage**: Android KeyStore (credentials), SharedPreferences (config), SQLite (audit/command logs), Windows Credential Manager (API keys)
**Testing**: JUnit5 + Compose testing (Android), pytest + pytest-asyncio (Python), contract tests, integration tests
**Target Platform**: Android 11+ (SDK 30, Target 34+), Windows 10/11 (64-bit)
**Project Type**: Mobile + API (Android client + Python Windows service)
**Performance Goals**: <2s end-to-end latency (simple commands), <10s PC wake-up, 16kHz audio streaming <200ms buffer, <100ms VAD detection, 95% command success rate
**Constraints**: <5% battery/hour, local STT (no cloud), same local network only, Turkish language primary, mTLS encryption required, 80% test coverage, TDD workflow mandatory
**Scale/Scope**: MVP - single user per PC, ~20-30 command types, 5 command history context window

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**✅ PASSED** - All constitution principles satisfied:

- **Security-First Development**: mTLS + certificate pinning, Android KeyStore encryption, TLS 1.3, input validation, no plain-text secrets
- **Test-Driven Development**: Comprehensive acceptance scenarios defined, test strategy documented, 80% coverage target, TDD workflow required
- **Performance & Reliability**: <2s latency (FR-008), 16kHz/<200ms audio, <10s wake, 95% success rate (SC-004)
- **Component Independence**: Android/Python independently deployable, WebSocket contract boundaries, version negotiation capability
- **Graceful Degradation**: 30s LLM retry queue, auto-reconnect, clear Turkish error messages (FR-018)
- **Observability**: Structured logging, performance metrics, network/audio diagnostics, debug mode
- **Simplicity & YAGNI**: Multi-component architecture **JUSTIFIED** by physical separation requirement (Android device + Windows PC) and constitution Principle IV mandate for component independence

## Project Structure

### Documentation (this feature)

```text
specs/001-voice-pc-control/
├── spec.md              # Feature specification (completed)
├── plan.md              # This file (Phase 0-1 complete)
├── research.md          # Technical decisions (Phase 0 complete)
├── data-model.md        # Entity definitions (Phase 1 complete)
├── quickstart.md        # Developer setup (Phase 1 complete)
├── contracts/           # API contracts (Phase 1 complete)
│   ├── websocket-protocol.md
│   └── mcp-tools-schema.json
└── tasks.md             # NOT YET CREATED - Next: run /speckit.tasks
```

### Source Code (repository root)

```text
pc-control/
├── android/                    # Android app (Kotlin)
│   ├── app/
│   │   ├── src/
│   │   │   ├── main/
│   │   │   │   ├── kotlin/
│   │   │   │   │   └── com/pccontrol/voice/
│   │   │   │   │       ├── audio/          # Opus encoding, audio capture
│   │   │   │   │       ├── network/        # WebSocket client, mTLS
│   │   │   │   │       ├── ui/             # Jetpack Compose screens
│   │   │   │   │       ├── security/       # KeyStore, pairing
│   │   │   │   │       └── MainActivity.kt
│   │   │   │   ├── res/
│   │   │   │   └── AndroidManifest.xml
│   │   │   └── test/           # Unit tests (JUnit5)
│   │   └── build.gradle.kts
│   ├── gradle/
│   └── settings.gradle.kts
├── pc-agent/                   # Python Windows service
│   ├── src/
│   │   ├── audio/              # Whisper.cpp STT, VAD
│   │   ├── llm/                # Claude API integration
│   │   ├── mcp/                # MCP tool routing (system/browser)
│   │   ├── websocket/          # FastAPI WebSocket server
│   │   ├── security/           # mTLS, certificate management
│   │   ├── models/             # Data models (SQLAlchemy)
│   │   └── main.py
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── e2e/
│   │   └── contract/
│   ├── requirements.txt
│   └── pyproject.toml
├── specs/                      # Feature documentation (this directory)
├── scripts/                    # Build and deployment automation
│   ├── generate_certs.py
│   ├── download_whisper_model.py
│   └── test_wol.py
└── .github/
    └── workflows/              # CI/CD pipelines
```

**Structure Decision**: Mobile + API architecture chosen due to physical separation requirement (Android device as voice input, Windows PC as execution target). Android app handles audio capture, UI, and security. Python service provides STT processing, LLM integration, and command execution. This aligns with constitution Principle IV (Component Independence) and enables independent deployment, version management, and testing of each component.

## Complexity Tracking

**No violations requiring justification** - Multi-component architecture is necessary, not speculative:

| Aspect | Justification | Simpler Alternative Rejected |
|--------|---------------|------------------------------|
| Android + Python components | Physical separation required (phone ≠ PC), cannot achieve requirements with single component | Cloud-only architecture rejected (privacy requirement FR-017) |
| Mobile + API pattern | Constitution Principle IV mandates component independence for distributed systems | Monolithic approach rejected (impossible to run on both Android and Windows from single codebase) |

---

## Phase 0: Research (✅ COMPLETE)

**Output**: `research.md` - All technical unknowns resolved through specification analysis

**Key Decisions Documented**:
1. Mobile + API architecture (Android + Python WebSocket)
2. Audio pipeline: 16kHz PCM → Opus compression → WebSocket streaming
3. Command interpretation: Claude API with MCP tool routing
4. Security: mTLS with self-signed certificates + Android KeyStore
5. PC wake: Wake-on-LAN UDP with 15s service startup timeout
6. Browser automation: Chrome DevTools MCP server
7. Testing: JUnit5 (Android) + pytest (Python) + contract tests
8. Error handling: Turkish messages + retry queues + graceful degradation

---

## Phase 1: Design & Contracts (✅ COMPLETE)

**Output**: `data-model.md`, `contracts/`, `quickstart.md`

**Artifacts Generated**:

### 1. Data Model (`data-model.md`)
- **Voice Command**: Audio data (transient), transcribed text, confidence, status state machine
- **PC Connection**: Connection state, latency metrics, authentication, health checks
- **Action**: Operation type (system/browser/query), parameters, execution status, confirmation logic
- **Command History**: Recent commands (5 max, 10-minute retention) for context
- **Device Pairing**: mTLS certificates, auth tokens, pairing status, security constraints

### 2. API Contracts (`contracts/`)
- **WebSocket Protocol** (`websocket-protocol.md`):
  - Authentication handshake (mTLS + bearer token)
  - Binary audio streaming (Opus frames with sequence numbers)
  - Command processing pipeline (transcription → interpretation → execution)
  - Confirmation prompts for destructive operations
  - Connection management (ping/pong, health checks, reconnection)
  - Wake-on-LAN integration
  - Comprehensive error codes (1xxx-5xxx) with Turkish messages

- **MCP Tools Schema** (`mcp-tools-schema.json`):
  - System tools: launch_application, adjust_volume, find_files, delete_file, query_system_info
  - Browser tools: browser_navigate, browser_search, browser_extract_content, browser_interact
  - Security constraints (confirmation for system directory deletions)
  - Performance constraints (timeouts per tool, max 3 concurrent)
  - Error handling (retryable vs non-retryable errors, backoff strategy)

### 3. Developer Quickstart (`quickstart.md`)
- Android Studio setup with dependencies (OkHttp, Jetpack Compose, Opus encoding)
- Python environment setup (FastAPI, Whisper.cpp, Claude API)
- Certificate generation for mTLS testing
- Development workflow (running both components, debugging, testing)
- Common issues and solutions

---

## Phase 2: Task Generation (⏳ PENDING)

**Command**: Run `/speckit.tasks` to generate `tasks.md`

**Expected Output**: Dependency-ordered implementation tasks based on:
- Constitution-mandated TDD workflow (tests before implementation)
- Component independence (Android and Python can be developed in parallel after contracts defined)
- Security-first approach (mTLS and certificate infrastructure before feature development)
- Performance SLA validation (latency benchmarks integrated into CI pipeline)

**Next Steps**:
1. Execute `/speckit.tasks` command to generate detailed task breakdown
2. Review and approve task order with stakeholders
3. Begin implementation following TDD workflow (test → implement → refactor)
4. Maintain 80% test coverage throughout development

---

## Agent Context Update

**Status**: ✅ COMPLETE

The `/update-agent-context.ps1` script has been executed to update `CLAUDE.md` with the technology stack:
- **Languages**: Kotlin (Android 11+), Python 3.10+ (Windows)
- **Frameworks**: OkHttp, Jetpack Compose, FastAPI, Whisper.cpp, Claude API, MCP servers

This enables Claude Code to provide context-aware assistance for subsequent implementation tasks.

---

## Summary

**Planning Phase Complete** ✅

All Phase 0 and Phase 1 deliverables have been generated:
- ✅ Technical research and decisions documented
- ✅ Constitution gates evaluated and passed
- ✅ Data model with 5 core entities defined
- ✅ WebSocket protocol contract (mTLS, binary audio, command pipeline)
- ✅ MCP tools schema (9 tools: 5 system + 4 browser)
- ✅ Developer quickstart guide
- ✅ Agent context updated

**Ready for Phase 2**: Execute `/speckit.tasks` to generate implementation task breakdown.
