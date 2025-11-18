# PC Control Voice Assistant - Makefile
# Convenience targets for development and testing

.PHONY: help install-dev setup test clean lint format security-check android-setup python-setup

# Default target
help:
	@echo "PC Control Voice Assistant - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  setup           - Install all dependencies and setup environment"
	@echo "  python-setup    - Setup Python development environment"
	@echo "  android-setup   - Setup Android development environment"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint            - Run all linting checks"
	@echo "  format          - Format all code"
	@echo "  security-check  - Run security scans"
	@echo ""
	@echo "Testing:"
	@echo "  test            - Run all tests"
	@echo "  test-python     - Run Python tests"
	@echo "  test-android    - Run Android tests"
	@echo ""
	@echo "Development:"
	@echo "  dev-python      - Start Python development server"
	@echo "  dev-android     - Build and install Android debug APK"
	@echo "  clean           - Clean build artifacts"

# Setup targets
setup: python-setup android-setup
	@echo "✅ Full setup complete!"

python-setup:
	@echo "🐍 Setting up Python development environment..."
	cd pc-agent && python -m venv venv
	cd pc-agent && . venv/bin/activate && pip install --upgrade pip
	cd pc-agent && . venv/bin/activate && pip install -r requirements-dev.txt
	cd pc-agent && . venv/bin/activate && pre-commit install
	@echo "✅ Python setup complete!"

android-setup:
	@echo "🤖 Setting up Android development environment..."
	cd android && ./gradlew wrapper --gradle-version=8.4
	@echo "✅ Android setup complete!"
	@echo "📱 Remember to open android/ in Android Studio for full setup"

# Code quality targets
lint:
	@echo "🔍 Running all linting checks..."
	$(MAKE) lint-python
	$(MAKE) lint-android

lint-python:
	@echo "🐍 Python linting..."
	cd pc-agent && ruff check .
	cd pc-agent && mypy src/

lint-android:
	@echo "🤖 Android linting..."
	cd android && ./gradlew detekt
	cd android && ./gradlew ktlintCheck

format:
	@echo "🎨 Formatting all code..."
	$(MAKE) format-python
	$(MAKE) format-android

format-python:
	@echo "🐍 Python formatting..."
	cd pc-agent && ruff format .
	cd pc-agent && black .

format-android:
	@echo "🤖 Android formatting..."
	cd android && ./gradlew ktlintFormat

security-check:
	@echo "🔒 Running security scans..."
	$(MAKE) security-python
	$(MAKE) security-android

security-python:
	@echo "🐍 Python security scan..."
	cd pc-agent && bandit -r src/ -f json -o security-report.json
	cd pc-agent && safety check -r requirements.txt

security-android:
	@echo "🤖 Android security scan..."
	cd android && ./gradlew lint

# Testing targets
test:
	@echo "🧪 Running all tests..."
	$(MAKE) test-python
	$(MAKE) test-android

test-python:
	@echo "🐍 Running Python tests..."
	cd pc-agent && python -m pytest tests/ -v --cov=src --cov-report=html

test-android:
	@echo "🤖 Running Android tests..."
	cd android && ./gradlew test
	cd android && ./gradlew connectedAndroidTest

# Development targets
dev-python:
	@echo "🚀 Starting Python development server..."
	cd pc-agent && . venv/bin/activate && python -m uvicorn src.api.websocket_server:app --host 0.0.0.0 --port 8765 --reload

dev-android:
	@echo "🚀 Building Android debug APK..."
	cd android && ./gradlew assembleDebug
	@echo "📱 APK built: android/app/build/outputs/apk/debug/app-debug.apk"

# Clean targets
clean:
	@echo "🧹 Cleaning all build artifacts..."
	$(MAKE) clean-python
	$(MAKE) clean-android

clean-python:
	@echo "🧹 Cleaning Python artifacts..."
	cd pc-agent && rm -rf venv/
	cd pc-agent && rm -rf build/
	cd pc-agent && rm -rf dist/
	cd pc-agent && rm -rf *.egg-info/
	cd pc-agent && find . -type d -name __pycache__ -delete
	cd pc-agent && find . -type f -name "*.pyc" -delete

clean-android:
	@echo "🧹 Cleaning Android artifacts..."
	cd android && ./gradlew clean

# Installation
install-dev:
	@echo "📦 Installing development dependencies..."
	pip install pre-commit
	cd pc-agent && python -m venv venv
	cd pc-agent && . venv/bin/activate && pip install -r requirements-dev.txt
	pre-commit install