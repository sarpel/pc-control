# GitHub Copilot Instructions for PC Control Voice Assistant

## Project Overview

This is a **Voice-Controlled PC Assistant** that enables hands-free Windows PC control using Turkish voice commands from an Android device. The system consists of:

- **Android App** (Kotlin + Jetpack Compose): Voice capture, UI, device pairing
- **PC Agent** (Python 3.10+ + FastAPI): STT processing with Whisper.cpp, command execution via Claude API, system control

Key technologies:
- Android: Kotlin 1.9+, Jetpack Compose, OkHttp WebSocket, Room database
- Python: FastAPI, Whisper.cpp, Anthropic Claude API, aiosqlite
- Communication: WebSocket over mTLS with Opus audio compression
- Security: mTLS authentication, certificate-based pairing

## Project Structure

```
pc-control/
├── android/              # Android app (Kotlin)
│   ├── app/
│   │   └── src/
│   │       ├── main/     # Production code
│   │       └── test/     # Unit tests
│   └── tests/            # Instrumentation tests
├── pc-agent/             # Python PC agent
│   ├── src/              # Source code
│   │   ├── audio/        # Whisper.cpp STT
│   │   ├── llm/          # Claude API integration
│   │   ├── services/     # Business logic
│   │   └── api/          # FastAPI server
│   ├── tests/            # Test suite (unit, integration, contract)
│   ├── requirements.txt  # Production dependencies
│   ├── requirements-dev.txt  # Development dependencies
│   └── pyproject.toml    # Python project configuration
├── specs/                # Feature specifications
├── docs/                 # Documentation
└── Makefile             # Development convenience commands
```

## Build & Run

### Prerequisites
- Python 3.10+ (for PC agent)
- Android Studio (for Android app)
- Same WiFi network for both devices
- Claude API key

### Python PC Agent

```bash
# Setup
cd pc-agent
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v --cov=src

# Lint
ruff check .
mypy src/

# Format
ruff format .
# Note: black is also available but redundant with ruff format

# Run development server
python -m uvicorn src.api.websocket_server:app --host 0.0.0.0 --port 8765 --reload
```

### Android App

```bash
# Setup
cd android
./gradlew wrapper --gradle-version=8.4

# Build debug APK
./gradlew assembleDebug

# Run tests
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
# Setup everything
make setup

# Run all tests
make test

# Run all linting
make lint

# Format all code
make format

# Clean build artifacts
make clean
```

## Coding Standards

### Python (PC Agent)

**Style:**
- Line length: 100 characters
- Use Ruff for linting and formatting (Black is also configured but redundant with ruff format)
- Use mypy for type checking
- Follow PEP 8 conventions

**Type Hints:**
- All functions must have type hints
- Use `from __future__ import annotations` for forward references
- Prefer specific types over `Any`

**Testing:**
- Minimum test coverage: 80%
- Use pytest with async support (`pytest-asyncio`)
- Organize tests: `tests/unit/`, `tests/integration/`, `tests/contract/`
- Mark tests appropriately: `@pytest.mark.unit`, `@pytest.mark.integration`

**Imports:**
- Use absolute imports
- Group imports: standard library, third-party, local
- Ruff/isort handles import ordering

**Security:**
- Never commit API keys or secrets
- Use environment variables via `.env` files
- Validate all inputs
- Use parameterized queries for database operations

### Kotlin (Android)

**Style:**
- Follow official Kotlin coding conventions
- Use detekt for static analysis
- Use ktlint for formatting
- Minimum SDK: 30 (Android 11+)
- Target SDK: 34

**Architecture:**
- Use MVVM pattern
- Repository pattern for data access
- Dependency injection with Hilt
- Jetpack Compose for UI

**Testing:**
- Write unit tests for ViewModels and repositories
- Use instrumentation tests for UI components
- Mock dependencies appropriately

**Imports:**
- Group imports: Android, third-party, local
- Remove unused imports

## Common Tasks

### Adding a New Voice Command

1. Update MCP tools schema in `specs/001-voice-pc-control/contracts/mcp-tools-schema.json`
2. Implement command handler in `pc-agent/src/services/`
3. Add tests in `pc-agent/tests/integration/`
4. Update API documentation in `docs/api/`

### Adding a New Android Feature

1. Create ViewModels in appropriate package
2. Implement UI with Jetpack Compose
3. Add navigation if needed
4. Write unit and instrumentation tests
5. Update user documentation

### Fixing a Bug

1. Write a failing test that reproduces the bug
2. Fix the issue with minimal changes
3. Ensure all tests pass
4. Update documentation if needed

### Updating Dependencies

Python:
```bash
cd pc-agent
pip install --upgrade <package>
# Then manually update the specific version in requirements.txt or requirements-dev.txt
# Run tests to ensure compatibility
```

Android:
```bash
cd android
# Update version in build.gradle.kts
./gradlew dependencies  # Check dependency tree
```

## Important Conventions

### File Naming
- Python: `snake_case.py`
- Kotlin: `PascalCase.kt`
- Tests: `test_*.py` or `*Test.kt`

### Git Commits
- Use conventional commits format: `type(scope): description`
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- Keep commits focused and atomic

### Configuration Files
- Never commit `.env` files (use `.env.template` as example)
- Keep secrets in environment variables
- Use `.gitignore` to exclude build artifacts and credentials

### Documentation
- Update README.md for user-facing changes
- Update API documentation for endpoint changes
- Add inline comments for complex logic only
- Keep docstrings concise and accurate

## Test Coverage Requirements

- Overall: 80%+ (enforced by pytest)
- Critical paths: 95%+
- Contract tests: 100% coverage of API contracts

## Security Guidelines

- All communication uses mTLS
- Voice data never persisted
- Audit logging for security events (90-day retention)
- Use Android KeyStore for credential storage
- Validate certificates with pinning
- Rate limiting on all API endpoints

## Performance Targets

- Voice capture latency: <100ms
- Audio streaming: <200ms buffering
- STT processing: 300-800ms
- Command execution: 100-1000ms
- Total end-to-end: <2 seconds (simple commands)

## When Making Changes

1. **Read existing code** - Follow patterns used in the codebase
2. **Write tests first** - TDD when possible
3. **Make minimal changes** - Don't refactor unrelated code
4. **Run tests frequently** - Validate changes early
5. **Update documentation** - Keep docs in sync with code
6. **Check security** - Run security scans before committing
7. **Review coverage** - Maintain or improve test coverage

## Quick Reference Commands

```bash
# Full setup
make setup

# Development workflow
make test          # Run all tests
make lint          # Run all linting
make format        # Format all code
make clean         # Clean artifacts

# Python specific
cd pc-agent && pytest tests/ -v
cd pc-agent && ruff check .

# Android specific
cd android && ./gradlew test
cd android && ./gradlew detekt
```

## Additional Notes

- Project uses Turkish for UI and voice commands
- Supports Windows 10/11 only (PC agent)
- Android 11+ required (SDK 30+)
- Same WiFi network required for both devices
- Claude API key required for command interpretation
