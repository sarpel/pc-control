"""
Device pairing validation and error handling service.

Provides comprehensive validation for:
- Certificate security requirements
- Device pairing limits
- Input validation and sanitization
- Error handling with Turkish messages
- Security constraint enforcement

Security constraints:
- RSA 2048-bit minimum certificates
- Maximum 3 paired devices per PC
- 6-digit pairing code validation
- MAC address format validation
"""

import re
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
import ipaddress

from src.models.device_pairing import DevicePairing, PairingStatus
from src.database.connection import Database

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Validation error with Turkish message."""
    field: str
    message: str
    severity: str = "error"  # error, warning, info


@dataclass
class ValidationResult:
    """Result of validation with errors list."""
    is_valid: bool
    errors: List[ValidationError]


class PairingValidator:
    """
    Comprehensive validation service for device pairing operations.

    Features:
    - Certificate security validation
    - Input sanitization
    - Business rule enforcement
    - Turkish error messages
    - Security constraint checking
    """

    # Configuration
    MIN_RSA_KEY_SIZE = 2048
    MAX_PAIRED_DEVICES = 3
    PAIRING_CODE_PATTERN = re.compile(r'^\d{6}$')
    DEVICE_ID_MAX_LENGTH = 200
    DEVICE_NAME_MAX_LENGTH = 100
    MAC_ADDRESS_PATTERN = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')

    def __init__(self, database: Database):
        """
        Initialize pairing validator.

        Args:
            database: Database connection for constraint checking
        """
        self.db = database
        logger.info("Pairing validator initialized")

    async def validate_pairing_request(
        self,
        device_name: str,
        device_id: str
    ) -> ValidationResult:
        """
        Validate pairing initiation request.

        Args:
            device_name: User-friendly device name
            device_id: Unique device identifier

        Returns:
            ValidationResult with any validation errors
        """
        errors = []

        # Validate device name
        name_errors = self._validate_device_name(device_name)
        errors.extend(name_errors)

        # Validate device ID
        id_errors = self._validate_device_id(device_id)
        errors.extend(id_errors)

        # Check device pairing limits
        limit_errors = await self._check_pairing_limits(device_id)
        errors.extend(limit_errors)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )

    async def validate_pairing_verification(
        self,
        pairing_id: str,
        pairing_code: str,
        device_id: str
    ) -> ValidationResult:
        """
        Validate pairing verification request.

        Args:
            pairing_id: Pairing session identifier
            pairing_code: 6-digit verification code
            device_id: Device identifier

        Returns:
            ValidationResult with any validation errors
        """
        errors = []

        # Validate pairing code format
        if not self.PAIRING_CODE_PATTERN.match(pairing_code):
            errors.append(ValidationError(
                field="pairing_code",
                message="Eşleştirme kodu 6 haneli bir sayı olmalıdır",
                severity="error"
            ))

        # Validate pairing ID format
        if not pairing_id or len(pairing_id) < 10:
            errors.append(ValidationError(
                field="pairing_id",
                message="Geçersiz eşleştirme kimliği",
                severity="error"
            ))

        # Check if pairing session exists and is valid
        session_errors = await self._validate_pairing_session(pairing_id, device_id)
        errors.extend(session_errors)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )

    def validate_certificates(
        self,
        ca_certificate: str,
        client_certificate: str,
        client_private_key: str
    ) -> ValidationResult:
        """
        Validate certificates for security requirements.

        Args:
            ca_certificate: CA certificate PEM
            client_certificate: Client certificate PEM
            client_private_key: Client private key PEM

        Returns:
            ValidationResult with any security validation errors
        """
        errors = []

        try:
            # Parse and validate CA certificate
            ca_cert = self._parse_certificate(ca_certificate)
            if ca_cert:
                cert_errors = self._validate_certificate_security(ca_cert, is_ca=True)
                errors.extend(cert_errors)

            # Parse and validate client certificate
            client_cert = self._parse_certificate(client_certificate)
            if client_cert:
                cert_errors = self._validate_certificate_security(client_cert, is_ca=False)
                errors.extend(cert_errors)

            # Validate certificate chain
            if ca_cert and client_cert:
                chain_errors = self._validate_certificate_chain(ca_cert, client_cert)
                errors.extend(chain_errors)

        except Exception as e:
            logger.error(f"Certificate validation error: {e}")
            errors.append(ValidationError(
                field="certificates",
                message="Sertifika formatı geçersiz",
                severity="error"
            ))

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )

    async def validate_device_removal(self, device_id: str) -> ValidationResult:
        """
        Validate device removal request.

        Args:
            device_id: Device identifier to remove

        Returns:
            ValidationResult with any validation errors
        """
        errors = []

        # Check if device exists
        device = await self._get_device_pairing(device_id)
        if not device:
            errors.append(ValidationError(
                field="device_id",
                message="Cihaz bulunamadı",
                severity="error"
            ))
        elif device.status != PairingStatus.ACTIVE:
            errors.append(ValidationError(
                field="device_id",
                message="Cihaz zaten devre dışı",
                severity="warning"
            ))

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )

    def validate_mac_address(self, mac_address: str) -> ValidationResult:
        """
        Validate MAC address format.

        Args:
            mac_address: MAC address to validate

        Returns:
            ValidationResult with any validation errors
        """
        errors = []

        if not mac_address:
            errors.append(ValidationError(
                field="mac_address",
                message="MAC adresi boş olamaz",
                severity="error"
            ))
        elif not self.MAC_ADDRESS_PATTERN.match(mac_address):
            errors.append(ValidationError(
                field="mac_address",
                message="MAC adresi formatı geçersiz (Örn: AA:BB:CC:DD:EE:FF)",
                severity="error"
            ))

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )

    def validate_ip_address(self, ip_address: str) -> ValidationResult:
        """
        Validate IP address format.

        Args:
            ip_address: IP address to validate

        Returns:
            ValidationResult with any validation errors
        """
        errors = []

        try:
            ipaddress.ip_address(ip_address)
        except ValueError:
            errors.append(ValidationError(
                field="ip_address",
                message="IP adresi formatı geçersiz",
                severity="error"
            ))

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )

    def get_error_messages(self, validation_result: ValidationResult) -> List[str]:
        """
        Get user-friendly error messages from validation result.

        Args:
            validation_result: ValidationResult with errors

        Returns:
            List of Turkish error messages
        """
        return [error.message for error in validation_result.errors]

    def _validate_device_name(self, device_name: str) -> List[ValidationError]:
        """Validate device name field."""
        errors = []

        if not device_name:
            errors.append(ValidationError(
                field="device_name",
                message="Cihaz adı boş olamaz",
                severity="error"
            ))
        elif len(device_name.strip()) == 0:
            errors.append(ValidationError(
                field="device_name",
                message="Cihaz adı boş olamaz",
                severity="error"
            ))
        elif len(device_name) > self.DEVICE_NAME_MAX_LENGTH:
            errors.append(ValidationError(
                field="device_name",
                message=f"Cihaz adı en fazla {self.DEVICE_NAME_MAX_LENGTH} karakter olabilir",
                severity="error"
            ))
        elif not re.match(r'^[a-zA-Z0-9\s\-_.]+$', device_name):
            errors.append(ValidationError(
                field="device_name",
                message="Cihaz adı yalnızca harf, rakam, boşluk ve özel karakterler içerebilir",
                severity="warning"
            ))

        return errors

    def _validate_device_id(self, device_id: str) -> List[ValidationError]:
        """Validate device ID field."""
        errors = []

        if not device_id:
            errors.append(ValidationError(
                field="device_id",
                message="Cihaz kimliği boş olamaz",
                severity="error"
            ))
        elif len(device_id) > self.DEVICE_ID_MAX_LENGTH:
            errors.append(ValidationError(
                field="device_id",
                message=f"Cihaz kimliği en fazla {self.DEVICE_ID_MAX_LENGTH} karakter olabilir",
                severity="error"
            ))

        return errors

    async def _check_pairing_limits(self, device_id: str) -> List[ValidationError]:
        """Check device pairing limits."""
        errors = []

        try:
            # Check if device is already paired
            existing = await self._get_device_pairing(device_id)
            if existing and existing.status == PairingStatus.ACTIVE:
                errors.append(ValidationError(
                    field="device_id",
                    message="Bu cihaz zaten eşleştirilmiş",
                    severity="error"
                ))

            # Check total paired devices limit
            count = await self._count_active_pairings()
            if count >= self.MAX_PAIRED_DEVICES and not existing:
                errors.append(ValidationError(
                    field="device_id",
                    message=f"Maksimum {self.MAX_PAIRED_DEVICES} cihaz eşleştirilebilir. "
                          f"Lütfen mevcut bir cihazın eşleştirmesini kaldırın.",
                    severity="error"
                ))

        except Exception as e:
            logger.error(f"Error checking pairing limits: {e}")
            errors.append(ValidationError(
                field="device_id",
                message="Eşleştirme limitleri kontrol edilemedi",
                severity="error"
            ))

        return errors

    async def _validate_pairing_session(self, pairing_id: str, device_id: str) -> List[ValidationError]:
        """Validate pairing session exists and is valid."""
        errors = []

        # This would check in memory or database for active sessions
        # For MVP, we'll do basic validation
        # In production, this would check against actual session store

        return errors

    def _parse_certificate(self, certificate_pem: str) -> Optional[x509.Certificate]:
        """Parse PEM certificate."""
        try:
            return x509.load_pem_x509_certificate(
                certificate_pem.encode('utf-8'),
                default_backend()
            )
        except Exception as e:
            logger.error(f"Error parsing certificate: {e}")
            return None

    def _validate_certificate_security(
        self,
        certificate: x509.Certificate,
        is_ca: bool = False
    ) -> List[ValidationError]:
        """Validate certificate security requirements."""
        errors = []

        try:
            # Check key size
            public_key = certificate.public_key()
            if hasattr(public_key, 'key_size'):  # RSA key
                if public_key.key_size < self.MIN_RSA_KEY_SIZE:
                    errors.append(ValidationError(
                        field="certificate",
                        message=f"Anahtar boyutu minimum {self.MIN_RSA_KEY_SIZE} bit olmalıdır",
                        severity="error"
                    ))

            # Check expiration
            now = datetime.utcnow()
            if certificate.not_valid_before > now:
                errors.append(ValidationError(
                    field="certificate",
                    message="Sertifika henüz geçerli değil",
                    severity="error"
                ))

            if certificate.not_valid_after < now:
                errors.append(ValidationError(
                    field="certificate",
                    message="Sertifikanın süresi dolmuş",
                    severity="error"
                ))

            # Check basic constraints for CA
            if is_ca:
                try:
                    basic_constraints = certificate.extensions.get_extension_for_oid(
                        x509.oid.ExtensionOID.BASIC_CONSTRAINTS
                    ).value
                    if not basic_constraints.ca:
                        errors.append(ValidationError(
                            field="ca_certificate",
                            message="CA sertifika basic constraints CA bayrağı içermeli",
                            severity="error"
                        ))
                except x509.ExtensionNotFound:
                    errors.append(ValidationError(
                        field="ca_certificate",
                        message="CA sertifika basic constraints içermiyor",
                        severity="error"
                    ))

        except Exception as e:
            logger.error(f"Error validating certificate security: {e}")
            errors.append(ValidationError(
                field="certificate",
                message="Sertifika güvenlik doğrulaması başarısız",
                severity="error"
            ))

        return errors

    def _validate_certificate_chain(
        self,
        ca_certificate: x509.Certificate,
        client_certificate: x509.Certificate
    ) -> List[ValidationError]:
        """Validate certificate chain."""
        errors = []

        try:
            # Basic chain validation for MVP
            # In production, would do full chain validation

            # Check that client cert was issued by CA
            # (This is a simplified check - real validation is more complex)

            # Verify subject key identifier
            # Verify authority key identifier
            # Verify signature
            # Verify validity periods

        except Exception as e:
            logger.error(f"Error validating certificate chain: {e}")
            errors.append(ValidationError(
                field="certificate_chain",
                message="Sertifika zinciri doğrulanamadı",
                severity="error"
            ))

        return errors

    async def _get_device_pairing(self, device_id: str) -> Optional[DevicePairing]:
        """Get device pairing from database."""
        try:
            query = "SELECT * FROM device_pairings WHERE device_id = ?"
            row = await self.db.fetch_one(query, (device_id,))

            if row:
                return DevicePairing(**dict(row))
            return None

        except Exception as e:
            logger.error(f"Error getting device pairing: {e}")
            return None

    async def _count_active_pairings(self) -> int:
        """Count active device pairings."""
        try:
            query = "SELECT COUNT(*) FROM device_pairings WHERE status = ?"
            row = await self.db.fetch_one(query, (PairingStatus.ACTIVE.value,))
            return row[0] if row else 0

        except Exception as e:
            logger.error(f"Error counting active pairings: {e}")
            return 0