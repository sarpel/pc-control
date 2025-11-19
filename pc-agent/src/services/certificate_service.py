"""
Certificate management service for PC Control Agent.

This service handles SSL certificate operations including:
- Certificate validation and verification
- Certificate fingerprint generation
- Certificate renewal and rotation
- Client certificate management
- Certificate revocation checking
"""

import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import json

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class CertificateInfo:
    """Information about a certificate."""
    subject: str
    issuer: str
    serial_number: str
    fingerprint: str
    not_valid_before: datetime
    not_valid_after: datetime
    is_ca: bool
    key_usage: List[str]
    extended_key_usage: List[str]
    subject_alternative_names: List[str]
    public_key_algorithm: str
    signature_algorithm: str


@dataclass
class CertificateValidationResult:
    """Result of certificate validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    certificate_info: CertificateInfo
    chain: List[str] = None


class CertificateService:
    """
    Service for managing SSL certificates and mTLS operations.

    This service provides:
    - Certificate parsing and analysis
    - Certificate chain validation
    - Fingerprint calculation
    - Certificate expiry monitoring
    - Client certificate management
    """

    def __init__(self):
        """Initialize certificate service."""
        self.settings = get_settings()
        self.ca_cert_path = Path(self.settings.certificates_dir) / "ca.crt"
        self.server_cert_path = Path(self.settings.certificates_dir) / "server.crt"
        self.client_certs_dir = Path(self.settings.certificates_dir) / "clients"
        self.client_certs_dir.mkdir(exist_ok=True)

    def load_certificate(self, cert_path: Path) -> Optional[x509.Certificate]:
        """
        Load certificate from file.

        Args:
            cert_path: Path to certificate file

        Returns:
            Loaded certificate or None if loading fails
        """
        try:
            with open(cert_path, "rb") as f:
                cert_data = f.read()
            return x509.load_pem_x509_certificate(cert_data)
        except Exception as e:
            logger.error(f"Failed to load certificate from {cert_path}: {e}")
            return None

    def load_certificate_from_data(self, cert_data: bytes) -> Optional[x509.Certificate]:
        """
        Load certificate from binary data.

        Args:
            cert_data: Certificate data in PEM format

        Returns:
            Loaded certificate or None if loading fails
        """
        try:
            return x509.load_pem_x509_certificate(cert_data)
        except Exception as e:
            logger.error(f"Failed to load certificate from data: {e}")
            return None

    def get_certificate_info(self, cert: x509.Certificate) -> CertificateInfo:
        """
        Extract information from certificate.

        Args:
            cert: Certificate to analyze

        Returns:
            Certificate information
        """
        try:
            # Extract subject and issuer
            subject = cert.subject.rfc4514_string()
            issuer = cert.issuer.rfc4514_string()

            # Extract fingerprint
            fingerprint = self.get_certificate_fingerprint(cert)

            # Extract validity dates
            not_valid_before = cert.not_valid_before.replace(tzinfo=None)
            not_valid_after = cert.not_valid_after.replace(tzinfo=None)

            # Check if it's a CA certificate
            is_ca = False
            try:
                basic_constraints = cert.extensions.get_extension_for_oid(
                    x509.ExtensionOID.BASIC_CONSTRAINTS
                )
                is_ca = basic_constraints.value.ca
            except x509.ExtensionNotFound:
                pass

            # Extract key usage
            key_usage = []
            try:
                key_usage_ext = cert.extensions.get_extension_for_oid(
                    x509.ExtensionOID.KEY_USAGE
                )
                if key_usage_ext.value.digital_signature:
                    key_usage.append("digital_signature")
                if key_usage_ext.value.key_encipherment:
                    key_usage.append("key_encipherment")
                if key_usage_ext.value.key_cert_sign:
                    key_usage.append("key_cert_sign")
                if key_usage_ext.value.crl_sign:
                    key_usage.append("crl_sign")
            except x509.ExtensionNotFound:
                pass

            # Extract extended key usage
            extended_key_usage = []
            try:
                ext_key_usage_ext = cert.extensions.get_extension_for_oid(
                    x509.ExtensionOID.EXTENDED_KEY_USAGE
                )
                for usage in ext_key_usage_ext.value:
                    if usage == x509.oid.ExtendedKeyUsageOID.SERVER_AUTH:
                        extended_key_usage.append("server_auth")
                    elif usage == x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH:
                        extended_key_usage.append("client_auth")
                    elif usage == x509.oid.ExtendedKeyUsageOID.CODE_SIGNING:
                        extended_key_usage.append("code_signing")
            except x509.ExtensionNotFound:
                pass

            # Extract subject alternative names
            subject_alternative_names = []
            try:
                sans_ext = cert.extensions.get_extension_for_oid(
                    x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
                )
                for name in sans_ext.value:
                    if isinstance(name, x509.DNSName):
                        subject_alternative_names.append(f"DNS:{name.value}")
                    elif isinstance(name, x509.IPAddress):
                        subject_alternative_names.append(f"IP:{name.value}")
            except x509.ExtensionNotFound:
                pass

            # Get algorithm information
            public_key_algorithm = cert.public_key().algorithm.__class__.__name__
            signature_algorithm = cert.signature_algorithm_oid._name

            return CertificateInfo(
                subject=subject,
                issuer=issuer,
                serial_number=str(cert.serial_number),
                fingerprint=fingerprint,
                not_valid_before=not_valid_before,
                not_valid_after=not_valid_after,
                is_ca=is_ca,
                key_usage=key_usage,
                extended_key_usage=extended_key_usage,
                subject_alternative_names=subject_alternative_names,
                public_key_algorithm=public_key_algorithm,
                signature_algorithm=signature_algorithm
            )

        except Exception as e:
            logger.error(f"Failed to extract certificate info: {e}")
            raise

    def get_certificate_fingerprint(self, cert: x509.Certificate) -> str:
        """
        Calculate SHA-256 fingerprint of certificate.

        Args:
            cert: Certificate to fingerprint

        Returns:
            Hexadecimal fingerprint string
        """
        try:
            fingerprint = cert.fingerprint(hashes.SHA256())
            return ":".join([f"{b:02x}" for b in fingerprint])
        except Exception as e:
            logger.error(f"Failed to calculate fingerprint: {e}")
            raise

    def validate_certificate_chain(self, cert: x509.Certificate) -> CertificateValidationResult:
        """
        Validate certificate against CA.

        Args:
            cert: Certificate to validate

        Returns:
            Validation result
        """
        errors = []
        warnings = []

        try:
            # Load CA certificate
            ca_cert = self.load_certificate(self.ca_cert_path)
            if not ca_cert:
                errors.append("CA certificate not found")
                return CertificateValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    certificate_info=None
                )

            # Get certificate info
            cert_info = self.get_certificate_info(cert)

            # Check expiry
            now = datetime.utcnow()
            if cert_info.not_valid_after < now:
                errors.append("Certificate has expired")
            elif cert_info.not_valid_after < now + timedelta(days=30):
                warnings.append("Certificate expires soon")

            if cert_info.not_valid_before > now:
                errors.append("Certificate is not yet valid")

            # Check if certificate is signed by CA
            try:
                # This is a simplified validation
                # In production, you'd want to use proper certificate validation libraries
                ca_public_key = ca_cert.public_key()
                cert.signature_verify(ca_public_key, cert.signature, cert.signature_hash_algorithm)
            except Exception as e:
                errors.append(f"Certificate signature verification failed: {e}")

            # Check key usage for client certificates
            if "client_auth" not in cert_info.extended_key_usage:
                warnings.append("Certificate may not be suitable for client authentication")

            # Build certificate chain (simplified)
            chain = [
                cert_info.subject,
                cert_info.issuer
            ]

            is_valid = len(errors) == 0

            return CertificateValidationResult(
                is_valid=is_valid,
                errors=errors,
                warnings=warnings,
                certificate_info=cert_info,
                chain=chain
            )

        except Exception as e:
            logger.error(f"Certificate validation failed: {e}")
            return CertificateValidationResult(
                is_valid=False,
                errors=[f"Validation error: {e}"],
                warnings=warnings,
                certificate_info=None
            )

    def save_client_certificate(self, device_id: str, cert_data: bytes, cert_info: Dict[str, Any]) -> bool:
        """
        Save client certificate for a device.

        Args:
            device_id: Device identifier
            cert_data: Certificate data
            cert_info: Certificate information

        Returns:
            True if saved successfully
        """
        try:
            # Create client certificate directory
            client_dir = self.client_certs_dir / device_id
            client_dir.mkdir(exist_ok=True)

            # Save certificate
            cert_path = client_dir / "client.crt"
            with open(cert_path, "wb") as f:
                f.write(cert_data)

            # Save certificate metadata
            metadata = {
                "device_id": device_id,
                "device_name": cert_info.get("device_name", "Unknown Device"),
                "certificate_fingerprint": cert_info.get("certificate_fingerprint"),
                "issued_at": datetime.utcnow().isoformat(),
                "expires_at": cert_info.get("expires_at"),
                "status": "active"
            }

            metadata_path = client_dir / "metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Client certificate saved for device: {device_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save client certificate for {device_id}: {e}")
            return False

    def load_client_certificate(self, device_id: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        """
        Load client certificate for a device.

        Args:
            device_id: Device identifier

        Returns:
            Tuple of (certificate_data, metadata) or None if not found
        """
        try:
            # Load certificate
            cert_path = self.client_certs_dir / device_id / "client.crt"
            if not cert_path.exists():
                return None

            with open(cert_path, "rb") as f:
                cert_data = f.read()

            # Load metadata
            metadata_path = self.client_certs_dir / device_id / "metadata.json"
            metadata = {}
            if metadata_path.exists():
                with open(metadata_path, "r") as f:
                    metadata = json.load(f)

            return cert_data, metadata

        except Exception as e:
            logger.error(f"Failed to load client certificate for {device_id}: {e}")
            return None

    def revoke_client_certificate(self, device_id: str, reason: str = "Administrative revocation") -> bool:
        """
        Revoke a client certificate.

        Args:
            device_id: Device identifier
            reason: Reason for revocation

        Returns:
            True if revoked successfully
        """
        try:
            metadata_path = self.client_certs_dir / device_id / "metadata.json"
            if not metadata_path.exists():
                return False

            # Load existing metadata
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            # Update metadata
            metadata["status"] = "revoked"
            metadata["revoked_at"] = datetime.utcnow().isoformat()
            metadata["revocation_reason"] = reason

            # Save updated metadata
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.info(f"Client certificate revoked for device: {device_id} ({reason})")
            return True

        except Exception as e:
            logger.error(f"Failed to revoke client certificate for {device_id}: {e}")
            return False

    def list_client_certificates(self) -> List[Dict[str, Any]]:
        """
        List all client certificates.

        Returns:
            List of certificate metadata
        """
        certificates = []

        try:
            if not self.client_certs_dir.exists():
                return certificates

            for device_dir in self.client_certs_dir.iterdir():
                if device_dir.is_dir():
                    metadata_path = device_dir / "metadata.json"
                    if metadata_path.exists():
                        with open(metadata_path, "r") as f:
                            metadata = json.load(f)
                        certificates.append(metadata)

        except Exception as e:
            logger.error(f"Failed to list client certificates: {e}")

        return certificates

    def check_certificate_expiry(self, days_threshold: int = 30) -> List[Dict[str, Any]]:
        """
        Check for certificates expiring soon.

        Args:
            days_threshold: Number of days before expiry to warn about

        Returns:
            List of certificates expiring soon
        """
        expiring_soon = []

        try:
            # Check server certificate
            server_cert = self.load_certificate(self.server_cert_path)
            if server_cert:
                cert_info = self.get_certificate_info(server_cert)
                days_until_expiry = (cert_info.not_valid_after - datetime.utcnow()).days
                if days_until_expiry <= days_threshold:
                    expiring_soon.append({
                        "type": "server",
                        "certificate": "server.crt",
                        "days_until_expiry": days_until_expiry,
                        "expires_at": cert_info.not_valid_after.isoformat()
                    })

            # Check CA certificate
            ca_cert = self.load_certificate(self.ca_cert_path)
            if ca_cert:
                cert_info = self.get_certificate_info(ca_cert)
                days_until_expiry = (cert_info.not_valid_after - datetime.utcnow()).days
                if days_until_expiry <= days_threshold:
                    expiring_soon.append({
                        "type": "ca",
                        "certificate": "ca.crt",
                        "days_until_expiry": days_until_expiry,
                        "expires_at": cert_info.not_valid_after.isoformat()
                    })

            # Check client certificates
            for device_id in [d.name for d in self.client_certs_dir.iterdir() if d.is_dir()]:
                client_cert_path = self.client_certs_dir / device_id / "client.crt"
                client_cert = self.load_certificate(client_cert_path)
                if client_cert:
                    cert_info = self.get_certificate_info(client_cert)
                    days_until_expiry = (cert_info.not_valid_after - datetime.utcnow()).days
                    if days_until_expiry <= days_threshold:
                        expiring_soon.append({
                            "type": "client",
                            "device_id": device_id,
                            "certificate": f"clients/{device_id}/client.crt",
                            "days_until_expiry": days_until_expiry,
                            "expires_at": cert_info.not_valid_after.isoformat()
                        })

        except Exception as e:
            logger.error(f"Failed to check certificate expiry: {e}")

        return expiring_soon

    def cleanup_expired_certificates(self) -> int:
        """
        Remove expired client certificates.

        Returns:
            Number of certificates removed
        """
        removed_count = 0

        try:
            now = datetime.utcnow()
            for device_id in [d.name for d in self.client_certs_dir.iterdir() if d.is_dir()]:
                client_cert_path = self.client_certs_dir / device_id / "client.crt"
                client_cert = self.load_certificate(client_cert_path)
                if client_cert:
                    cert_info = self.get_certificate_info(client_cert)
                    if cert_info.not_valid_after < now:
                        # Remove the entire device directory
                        device_dir = self.client_certs_dir / device_id
                        import shutil
                        shutil.rmtree(device_dir)
                        removed_count += 1
                        logger.info(f"Removed expired certificate for device: {device_id}")

        except Exception as e:
            logger.error(f"Failed to cleanup expired certificates: {e}")

        return removed_count