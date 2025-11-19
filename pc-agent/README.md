# PC Control Agent - Python Backend

Voice-controlled PC assistant backend service providing secure WebSocket API for Android voice command processing.

## 🚀 Quick Start

### Prerequisites

- **Python**: 3.10 or higher
- **Operating System**: Windows 10/11 (64-bit)
- **Hardware**: 8GB+ RAM, Intel i5 equivalent (last 5 years)
- **Network**: WiFi connectivity on same network as Android device
- **API Key**: Claude API key from [Anthropic Console](https://console.anthropic.com/)

### Installation

#### 1. Clone and Navigate

```bash
git clone <repository-url>
cd pc-control/pc-agent
```

#### 2. Create Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/macOS:**
```bash
python -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Or install in development mode:

```bash
pip install -e .
```

For development tools (linting, testing):

```bash
pip install -e ".[dev]"
```

#### 4. Configure Environment

Create a `.env` file in the `pc-agent/` directory:

```bash
# Server Configuration
PC_AGENT_HOST=0.0.0.0
PC_AGENT_PORT=8765
PC_AGENT_USE_SSL=true

# Security
PC_AGENT_SECRET_KEY=your-secret-key-change-this-in-production
PC_AGENT_SESSION_TIMEOUT=86400

# Claude API Configuration (REQUIRED)
PC_AGENT_CLAUDE_API_KEY=your-claude-api-key-here

# Logging
PC_AGENT_LOG_LEVEL=INFO
PC_AGENT_ENVIRONMENT=development

# Database
PC_AGENT_DATABASE_URL=sqlite:///./pc_agent.db

# Performance
PC_AGENT_MAX_CONCURRENT_CONNECTIONS=10
PC_AGENT_COMMAND_TIMEOUT=30
```

**Important:** Replace `your-claude-api-key-here` with your actual Claude API key.

#### 5. Generate SSL Certificates (Required for mTLS)

**Option A:** Use OpenSSL (recommended for development)

```bash
# Create certificates directory
mkdir -p config/certificates

# Generate CA key and certificate
openssl genrsa -out config/certificates/ca.key 4096
openssl req -new -x509 -days 365 -key config/certificates/ca.key -out config/certificates/ca.crt -subj "/CN=PC Control CA"

# Generate server key and certificate
openssl genrsa -out config/certificates/server.key 4096
openssl req -new -key config/certificates/server.key -out config/certificates/server.csr -subj "/CN=localhost"
openssl x509 -req -days 365 -in config/certificates/server.csr -CA config/certificates/ca.crt -CAkey config/certificates/ca.key -set_serial 01 -out config/certificates/server.crt
```

**Option B:** Use built-in certificate service

```python
from src.services.certificate_service import CertificateService

service = CertificateService()
service.generate_ca_certificate()
service.generate_server_certificate()
```

#### 6. Run the Application

**Standard launch:**

```bash
python src/main.py
```

**Using uvicorn directly:**

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8765 --ssl-keyfile config/certificates/server.key --ssl-certfile config/certificates/server.crt
```

**Development mode (auto-reload):**

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8765
```

The server will start at:
- **HTTPS**: `https://0.0.0.0:8765` (production)
- **HTTP**: `http://0.0.0.0:8765` (development, if SSL disabled)

### Verify Installation

```bash
# Check server is running
curl -k https://localhost:8765/health

# Expected output:
# {"status": "healthy", "version": "1.0.0"}
```

## 📁 Project Structure

```
pc-agent/
├── src/                      # Source code
│   ├── api/                  # FastAPI application
│   │   ├── main.py          # Main FastAPI app
│   │   ├── websocket_server.py  # WebSocket endpoints
│   │   ├── rest_endpoints.py    # REST API routes
│   │   ├── middleware.py    # Authentication & rate limiting
│   │   └── error_handlers.py    # Error handling
│   ├── services/             # Business logic
│   │   ├── voice_command_processor.py  # Voice command handling
│   │   ├── command_interpreter.py      # Claude API integration
│   │   ├── system_controller.py        # System operations
│   │   ├── browser_control.py          # Browser automation
│   │   ├── audio_processor.py          # Audio processing
│   │   ├── certificate_service.py      # mTLS certificate management
│   │   ├── connection_manager.py       # WebSocket connections
│   │   └── pairing_service.py          # Device pairing
│   ├── models/               # Data models
│   │   ├── voice_command.py
│   │   ├── device_pairing.py
│   │   └── message.py
│   ├── database/             # Database layer
│   │   ├── connection.py    # Database connection manager
│   │   └── schema.py        # Database schema
│   ├── config/               # Configuration
│   │   └── settings.py      # Pydantic settings
│   └── main.py              # Application entry point
├── tests/                    # Test suite
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── contract/            # Contract tests
├── config/                   # Configuration files
│   └── certificates/        # SSL certificates (generated)
├── pyproject.toml           # Project metadata & dependencies
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## 🔧 Configuration

### Environment Variables

All configuration uses the `PC_AGENT_` prefix. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `PC_AGENT_HOST` | `0.0.0.0` | Server bind address |
| `PC_AGENT_PORT` | `8765` | Server port |
| `PC_AGENT_USE_SSL` | `true` | Enable SSL/TLS |
| `PC_AGENT_CLAUDE_API_KEY` | None | **Required:** Claude API key |
| `PC_AGENT_SECRET_KEY` | (insecure default) | JWT signing key |
| `PC_AGENT_LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `PC_AGENT_ENVIRONMENT` | `development` | Environment mode |
| `PC_AGENT_DATABASE_URL` | `sqlite:///./pc_agent.db` | Database connection |
| `PC_AGENT_MAX_CONCURRENT_CONNECTIONS` | `10` | Max WebSocket connections |
| `PC_AGENT_COMMAND_TIMEOUT` | `30` | Command timeout (seconds) |

### Certificate Locations

Default paths (configurable via environment):

- **CA Certificate**: `config/certificates/ca.crt`
- **Server Certificate**: `config/certificates/server.crt`
- **Server Private Key**: `config/certificates/server.key`

## 🎯 Usage

### Starting the Service

**Production:**

```bash
# With virtual environment activated
python src/main.py
```

**Development with auto-reload:**

```bash
uvicorn src.api.main:app --reload
```

**Custom configuration:**

```bash
PC_AGENT_PORT=9000 PC_AGENT_LOG_LEVEL=DEBUG python src/main.py
```

### API Endpoints

#### Health Check

```bash
GET /health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "development"
}
```

#### Device Pairing

```bash
POST /api/pairing/initiate
Content-Type: application/json

{
  "device_name": "My Android Phone",
  "device_fingerprint": "android_device_fingerprint"
}
```

#### WebSocket Connection

```
wss://localhost:8765/ws
```

Send JSON messages:
```json
{
  "type": "voice_command",
  "audio_data": "base64_encoded_audio",
  "metadata": {
    "sample_rate": 16000,
    "channels": 1,
    "encoding": "opus"
  }
}
```

### Voice Command Processing Flow

1. **Android captures voice** → Opus encoding
2. **Audio streamed** → WebSocket connection
3. **Speech-to-text** → Local processing (future: Whisper integration)
4. **Command interpretation** → Claude API analyzes command
5. **System execution** → Browser/system operations
6. **Response sent** → WebSocket message back to Android

## 🧪 Testing

### Run All Tests

```bash
pytest
```

### Unit Tests Only

```bash
pytest tests/unit/
```

### Integration Tests

```bash
pytest tests/integration/
```

### Contract Tests

```bash
pytest tests/contract/
```

### With Coverage

```bash
pytest --cov=src --cov-report=html
```

Coverage report: `htmlcov/index.html`

### Test Categories

Use markers to run specific test types:

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Security tests
pytest -m security

# Slow tests excluded
pytest -m "not slow"
```

## 🔍 Development Tools

### Code Quality

**Linting with Ruff:**

```bash
ruff check src/
```

**Auto-fix issues:**

```bash
ruff check --fix src/
```

**Code formatting with Black:**

```bash
black src/
```

**Type checking with Mypy:**

```bash
mypy src/
```

**Run all quality checks:**

```bash
ruff check src/ && mypy src/ && pytest --cov=src
```

### Database Management

**Initialize database:**

```python
from src.database.connection import initialize_database
import asyncio

asyncio.run(initialize_database())
```

**Database location:** `pc_agent.db` (configurable via `PC_AGENT_DATABASE_URL`)

## 🐛 Troubleshooting

### Common Issues

#### 1. SSL Certificate Errors

**Problem:** `SSL: CERTIFICATE_VERIFY_FAILED`

**Solution:**
```bash
# Regenerate certificates
rm -rf config/certificates/*
# Follow certificate generation steps above
```

#### 2. Port Already in Use

**Problem:** `Address already in use: 8765`

**Solution:**
```bash
# Find process using port
netstat -ano | findstr :8765

# Kill process or use different port
PC_AGENT_PORT=9000 python src/main.py
```

#### 3. Import Errors

**Problem:** `ModuleNotFoundError: No module named 'src'`

**Solution:**
```bash
# Install in editable mode
pip install -e .

# Or run from correct directory
cd pc-agent
python src/main.py
```

#### 4. Claude API Errors

**Problem:** `anthropic.AuthenticationError`

**Solution:**
- Verify API key in `.env` file
- Check API key at https://console.anthropic.com/
- Ensure environment variable loaded: `echo $PC_AGENT_CLAUDE_API_KEY`

#### 5. Database Locked

**Problem:** `sqlite3.OperationalError: database is locked`

**Solution:**
```bash
# Close all connections
# Delete database and reinitialize
rm pc_agent.db
python src/main.py
```

### Logging

Enable debug logging:

```bash
PC_AGENT_LOG_LEVEL=DEBUG python src/main.py
```

Log output includes:
- Server startup/shutdown events
- WebSocket connections
- Voice command processing
- System operation execution
- Error stack traces

## 📊 Performance

### System Requirements

**Minimum:**
- Python 3.10+
- 4GB RAM
- 2 CPU cores
- 500MB disk space

**Recommended:**
- Python 3.11+
- 8GB RAM
- 4 CPU cores
- 1GB disk space

### Resource Usage

- **Memory**: ~200MB average
- **CPU**: 10-15% average (spikes during voice processing)
- **Network**: 24kbps for voice streaming
- **Disk**: Minimal (audit logs only)

### Optimization Tips

1. **Reduce logging** in production: `PC_AGENT_LOG_LEVEL=WARNING`
2. **Limit connections**: `PC_AGENT_MAX_CONCURRENT_CONNECTIONS=5`
3. **Use production mode**: `PC_AGENT_ENVIRONMENT=production`
4. **Enable connection pooling**: Already configured

## 🔒 Security

### Production Checklist

- [ ] Change `PC_AGENT_SECRET_KEY` to strong random value
- [ ] Use production SSL certificates (not self-signed)
- [ ] Enable firewall rules (port 8765 limited to local network)
- [ ] Set `PC_AGENT_ENVIRONMENT=production`
- [ ] Review audit logs regularly
- [ ] Rotate certificates every 90 days
- [ ] Never commit `.env` file to version control

### Security Features

- **mTLS**: Mutual authentication with client certificates
- **Rate Limiting**: 10 requests/second per IP
- **Session Timeout**: 24-hour auth tokens
- **Audit Logging**: All security events logged
- **Input Validation**: Pydantic models for all inputs
- **CORS Protection**: Configurable allowed origins

## 📝 API Documentation

Interactive API docs available when server is running:

- **Swagger UI**: `https://localhost:8765/docs`
- **ReDoc**: `https://localhost:8765/redoc`
- **OpenAPI JSON**: `https://localhost:8765/openapi.json`

## 🤝 Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) in the project root.

## 📄 License

MIT License - see [LICENSE](../LICENSE) file.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/your-org/pc-control/issues)
- **Docs**: See `../docs/` directory
- **Security**: Report security issues to security@example.com

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [Anthropic Claude](https://www.anthropic.com/) - AI command interpretation
- [Pydantic](https://pydantic.dev/) - Data validation
- [uvicorn](https://www.uvicorn.org/) - ASGI server

---

**Last Updated**: 2025-11-19
**Version**: 1.0.0
