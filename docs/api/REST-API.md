# REST API Documentation
## Voice-Controlled PC Assistant

**Version**: 1.0.0
**Base URL**: `https://<pc-ip>:8443`
**Protocol**: HTTPS with mTLS

---

## Table of Contents

1. [Authentication](#authentication)
2. [Device Pairing](#device-pairing)
3. [Connection Management](#connection-management)
4. [Error Codes](#error-codes)
5. [Rate Limiting](#rate-limiting)
6. [Examples](#examples)

---

## Authentication

All requests require mTLS client certificate authentication. The client certificate must be obtained through the device pairing flow.

### Headers

```http
Content-Type: application/json
X-Device-ID: <device-identifier>
X-Client-Version: <app-version>
```

---

## Device Pairing

### Initialize Pairing

Start a new device pairing session.

**Endpoint**: `POST /api/v1/pairing/init`

**Request Body**:
```json
{
  "device_name": "string",
  "device_type": "android",
  "os_version": "string"
}
```

**Response** (200 OK):
```json
{
  "pairing_id": "uuid",
  "pairing_code": "123456",
  "expires_at": "2025-11-18T15:30:00Z",
  "qr_code": "base64-encoded-image"
}
```

**Response** (429 Too Many Requests):
```json
{
  "error": "rate_limit_exceeded",
  "message": "Maximum pairing attempts exceeded. Try again in 60 seconds.",
  "retry_after": 60
}
```

### Complete Pairing

Complete the pairing process and receive certificates.

**Endpoint**: `POST /api/v1/pairing/complete`

**Request Body**:
```json
{
  "pairing_id": "uuid",
  "pairing_code": "123456",
  "public_key": "base64-encoded-public-key"
}
```

**Response** (200 OK):
```json
{
  "device_id": "uuid",
  "client_certificate": "base64-pem-certificate",
  "ca_certificate": "base64-pem-certificate",
  "auth_token": "jwt-token",
  "expires_at": "2025-11-19T15:30:00Z"
}
```

**Response** (400 Bad Request):
```json
{
  "error": "invalid_pairing_code",
  "message": "The pairing code is invalid or has expired."
}
```

### Revoke Pairing

Revoke a device pairing.

**Endpoint**: `DELETE /api/v1/pairing/{device_id}`

**Headers**:
```http
Authorization: Bearer <auth-token>
```

**Response** (204 No Content)

**Response** (404 Not Found):
```json
{
  "error": "device_not_found",
  "message": "Device not found or already revoked."
}
```

---

## Connection Management

### Get Connection Status

Get the current connection status and health metrics.

**Endpoint**: `GET /api/v1/connection/status`

**Headers**:
```http
Authorization: Bearer <auth-token>
```

**Response** (200 OK):
```json
{
  "status": "connected",
  "latency_ms": 45,
  "last_heartbeat": "2025-11-18T15:30:45Z",
  "connection_quality": "excellent",
  "active_sessions": 1,
  "connection_id": "uuid"
}
```

### Send Heartbeat

Send a heartbeat to maintain connection.

**Endpoint**: `POST /api/v1/connection/heartbeat`

**Headers**:
```http
Authorization: Bearer <auth-token>
```

**Request Body**:
```json
{
  "connection_id": "uuid",
  "timestamp": "2025-11-18T15:30:45Z"
}
```

**Response** (200 OK):
```json
{
  "acknowledged": true,
  "server_time": "2025-11-18T15:30:45.123Z",
  "latency_ms": 45
}
```

### Disconnect

Gracefully disconnect from the server.

**Endpoint**: `POST /api/v1/connection/disconnect`

**Headers**:
```http
Authorization: Bearer <auth-token>
```

**Response** (200 OK):
```json
{
  "disconnected": true,
  "message": "Connection closed successfully"
}
```

---

## Error Codes

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 204 | No Content | Request succeeded with no response body |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource conflict (e.g., already paired) |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error occurred |
| 503 | Service Unavailable | Service temporarily unavailable |

### Application Error Codes

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `invalid_pairing_code` | 400 | Pairing code is invalid or expired |
| `device_not_found` | 404 | Device ID not found |
| `already_paired` | 409 | Device is already paired |
| `max_devices_reached` | 403 | Maximum devices limit reached (3) |
| `rate_limit_exceeded` | 429 | Too many requests in time window |
| `certificate_invalid` | 401 | Client certificate is invalid |
| `certificate_expired` | 401 | Client certificate has expired |
| `auth_token_expired` | 401 | Authentication token has expired |
| `connection_unavailable` | 503 | PC is sleeping or disconnected |

---

## Rate Limiting

Rate limits are applied per device and IP address:

### Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/api/v1/pairing/init` | 5 requests | 5 minutes |
| `/api/v1/pairing/complete` | 10 requests | 5 minutes |
| `/api/v1/connection/*` | 100 requests | 1 minute |
| All endpoints | 1000 requests | 1 hour |

### Rate Limit Headers

All responses include rate limit information:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1700000000
```

### Rate Limit Response

When rate limit is exceeded:

```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded. Try again in 42 seconds.",
  "retry_after": 42,
  "limit": 100,
  "window": "1 minute"
}
```

---

## Examples

### Complete Pairing Flow

```bash
# 1. Initialize pairing
curl -X POST https://192.168.1.100:8443/api/v1/pairing/init \
  -H "Content-Type: application/json" \
  -d '{
    "device_name": "My Android Phone",
    "device_type": "android",
    "os_version": "Android 13"
  }'

# Response:
# {
#   "pairing_id": "abc123",
#   "pairing_code": "654321",
#   "expires_at": "2025-11-18T16:00:00Z"
# }

# 2. Complete pairing (with code entered on PC)
curl -X POST https://192.168.1.100:8443/api/v1/pairing/complete \
  -H "Content-Type: application/json" \
  -d '{
    "pairing_id": "abc123",
    "pairing_code": "654321",
    "public_key": "base64-encoded-key"
  }'

# Response:
# {
#   "device_id": "device-uuid",
#   "client_certificate": "base64-pem",
#   "ca_certificate": "base64-pem",
#   "auth_token": "jwt-token",
#   "expires_at": "2025-11-19T15:30:00Z"
# }
```

### Check Connection Status

```bash
curl -X GET https://192.168.1.100:8443/api/v1/connection/status \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  --cert client.crt \
  --key client.key \
  --cacert ca.crt

# Response:
# {
#   "status": "connected",
#   "latency_ms": 45,
#   "connection_quality": "excellent"
# }
```

### Handle Rate Limiting

```python
import requests
import time

def make_request_with_retry(url, headers, max_retries=3):
    for attempt in range(max_retries):
        response = requests.post(url, headers=headers)

        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            continue

        return response

    raise Exception("Max retries exceeded")
```

---

## Security Considerations

### mTLS Configuration

All API endpoints require mutual TLS (mTLS) authentication:

1. **Client Certificate**: Obtained through device pairing
2. **CA Certificate**: Self-signed CA provided by PC agent
3. **Certificate Validation**: Both server and client validate certificates

### Token Management

Authentication tokens:
- **Lifetime**: 24 hours
- **Renewal**: Automatic renewal 1 hour before expiration
- **Revocation**: Tokens are revoked on device unpairing
- **Storage**: Must be stored securely (Android KeyStore)

### Best Practices

1. **Certificate Storage**: Store certificates in Android KeyStore
2. **Token Refresh**: Implement automatic token refresh
3. **Error Handling**: Handle certificate expiration gracefully
4. **Retry Logic**: Implement exponential backoff for retries
5. **Rate Limits**: Respect rate limits and implement backoff
6. **Audit Logging**: All API calls are logged for security audit

---

## Versioning

The API uses URL-based versioning (`/api/v1/`). Breaking changes will increment the major version number.

### Current Version

**Version**: 1.0.0
**Release Date**: 2025-11-18
**Stability**: Production

### Deprecation Policy

- Deprecated endpoints will be supported for 6 months
- Deprecation notices will be included in response headers:
  ```http
  X-API-Deprecated: true
  X-API-Sunset: 2026-05-18
  ```

---

## Support

For API support:
- **Documentation**: See full documentation in `/docs`
- **Issues**: Report issues on GitHub
- **Security**: Report security issues privately

---

**Last Updated**: 2025-11-18
**API Version**: 1.0.0
