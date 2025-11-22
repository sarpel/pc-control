﻿# pc-control Development Guidelines

Voice-Controlled PC Assistant - Development guide for Claude Code and AI agents.

Last updated: 2025-11-21

## Project Overview

This is a voice-controlled Windows PC assistant that uses Turkish voice commands from an Android device. The system consists of two main components:

1. **Android App** (Kotlin): Voice capture, UI, device pairing
2. **PC Agent** (Python): Speech-to-text, command execution, system control

## Active Technologies

### Android App
- **Language**: Kotlin 1.9+
- **UI**: Jetpack Compose
- **Minimum SDK**: 30 (Android 11+)
- **Target SDK**: 34
- **Architecture**: MVVM with Hilt dependency injection
- **Key Libraries**: OkHttp (WebSocket), Room (database), Opus Android (audio)
- **Build**: Gradle 8.4, AGP 8.1+

### Python PC Agent
- **Language**: Python 3.10+
- **Web Framework**: FastAPI, Uvicorn
- **STT**: Whisper.cpp (local processing)
- **LLM**: Anthropic Claude API
- **Database**: aiosqlite (SQLite async)
- **Security**: cryptography, PyJWT, mTLS
- **Testing**: pytest, pytest-asyncio, pytest-cov

### Communication
- WebSocket over mTLS
- Opus audio compression
- Certificate-based authentication

## Project Structure

```text
pc-control/
├── android/              # Kotlin Android app
│   ├── app/src/main/     # Production code
│   ├── app/src/test/     # Unit tests
│   └── tests/            # Instrumentation tests
├── pc-agent/             # Python PC agent
│   ├── src/              # Source code
│   │   ├── audio/        # Whisper.cpp STT
│   │   ├── llm/          # Claude API
│   │   ├── services/     # Business logic
│   │   └── api/          # FastAPI server
│   └── tests/            # Unit, integration, contract tests
├── specs/                # Feature specifications
├── docs/                 # Documentation
└── Makefile             # Development commands
```

## Build & Test Commands

### Python (PC Agent)
```bash
cd pc-agent

# Setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt

# Test
pytest tests/ -v --cov=src

# Lint
ruff check .
mypy src/

# Format
ruff format .
# Note: black is redundant with ruff format
```

### Android
```bash
cd android

# Build
./gradlew assembleDebug

# Test
./gradlew test
./gradlew connectedAndroidTest

# Lint
./gradlew detekt
./gradlew ktlintCheck

# Format
./gradlew ktlintFormat
```

### Using Makefile
```bash
make setup          # Install all dependencies
make test           # Run all tests
make lint           # Run all linting
make format         # Format all code
make clean          # Clean build artifacts
```

## Code Style

### Python
- **Line length**: 100 characters
- **Formatter**: Ruff (use only Ruff; Black is also configured but should not be used)
- **Linter**: Ruff (pycodestyle, pyflakes, flake8-bugbear, etc.)
- **Type checker**: mypy (strict mode)
- **Type hints**: Required for all functions
- **Imports**: Absolute imports, sorted by ruff/isort
- **Test coverage**: Minimum 80%

### Kotlin
- **Style**: Official Kotlin conventions
- **Formatter**: ktlint
- **Linter**: detekt
- **Architecture**: MVVM pattern
- **DI**: Hilt/Dagger
- **Naming**: PascalCase for classes, camelCase for functions/variables

## Testing Requirements
- Python: 80%+ coverage (enforced by pytest)
- Organize tests: `tests/unit/`, `tests/integration/`, `tests/contract/`
- Use pytest markers: `@pytest.mark.unit`, `@pytest.mark.integration`
- Android: Unit tests for ViewModels, instrumentation tests for UI

## Security Guidelines
- Never commit secrets or API keys
- Use `.env` files for configuration (see `.env.template`)
- All communication uses mTLS
- Voice data never persisted
- Validate all inputs
- Run security scans before committing

## Recent Changes
- 2025-11-21: Updated CLAUDE.md with accurate project information
- 2025-11-18: Added Kotlin (Android 11+), Python 3.10+ (Windows) + OkHttp, Jetpack Compose, FastAPI, Whisper.cpp, Claude API, MCP servers

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
