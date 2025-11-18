"""
SSL Certificate Generator for PC Control Agent

This module provides utilities to generate SSL certificates for mTLS communication
between Android clients and the PC server.
"""

import os
import socket
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Tuple, Optional

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption


class CertificateGenerator:
    """Generates SSL certificates for mTLS communication."""

    def __init__(self, certificates_dir: Path):
        """
        Initialize certificate generator.

        Args:
            certificates_dir: Directory to store certificates
        """
        self.certificates_dir = Path(certificates_dir)
        self.certificates_dir.mkdir(parents=True, exist_ok=True)

    def generate_ca_certificate(self, country: str = "TR", state: str = "Istanbul",
                              city: str = "Istanbul", organization: str = "PC Control",
                              common_name: str = "PC Control CA") -> Tuple[bytes, bytes]:
        """
        Generate a Certificate Authority certificate.

        Args:
            country: Country code
            state: State/province
            city: City
            organization: Organization name
            common_name: Common name for CA

        Returns:
            Tuple of (private_key_pem, certificate_pem)
        """
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Create subject name
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state),
            x509.NameAttribute(NameOID.LOCALITY_NAME, city),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        # Create certificate
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            subject  # Self-signed
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365 * 10)  # 10 years
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=1),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).sign(private_key, hashes.SHA256())

        # Serialize to PEM format
        private_key_pem = private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption()
        )

        cert_pem = cert.public_bytes(Encoding.PEM)

        return private_key_pem, cert_pem

    def generate_server_certificate(self, ca_private_key: bytes, ca_cert: bytes,
                                  hostname: Optional[str] = None) -> Tuple[bytes, bytes]:
        """
        Generate server certificate signed by CA.

        Args:
            ca_private_key: CA private key in PEM format
            ca_cert: CA certificate in PEM format
            hostname: Server hostname (auto-detected if not provided)

        Returns:
            Tuple of (private_key_pem, certificate_pem)
        """
        if hostname is None:
            hostname = socket.gethostname()

        # Load CA certificate and private key
        ca_cert_loaded = x509.load_pem_x509_certificate(ca_cert)
        ca_private_key_loaded = serialization.load_pem_private_key(
            ca_private_key, password=None
        )

        # Generate server private key
        server_private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Create subject name
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "TR"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Istanbul"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Istanbul"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PC Control"),
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        ])

        # Get IP addresses for Subject Alternative Names
        ip_addresses = self._get_local_ip_addresses()

        # Create certificate
        builder = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            ca_cert_loaded.subject
        ).public_key(
            server_private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)  # 1 year
        )

        # Add Subject Alternative Names
        sans = [x509.DNSName(hostname)]
        sans.extend([x509.DNSName("localhost"), x509.DNSName("pc.local")])
        sans.extend([x509.IPAddress(ip) for ip in ip_addresses])

        builder = builder.add_extension(
            x509.SubjectAlternativeName(sans),
            critical=False,
        )

        # Add key usage and extended key usage
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )

        # Sign certificate
        cert = builder.sign(ca_private_key_loaded, hashes.SHA256())

        # Serialize to PEM format
        private_key_pem = server_private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption()
        )

        cert_pem = cert.public_bytes(Encoding.PEM)

        return private_key_pem, cert_pem

    def generate_client_certificate(self, ca_private_key: bytes, ca_cert: bytes,
                                  device_name: str = "Android Device") -> Tuple[bytes, bytes]:
        """
        Generate client certificate for Android device.

        Args:
            ca_private_key: CA private key in PEM format
            ca_cert: CA certificate in PEM format
            device_name: Name of the Android device

        Returns:
            Tuple of (private_key_pem, certificate_pem)
        """
        # Load CA certificate and private key
        ca_cert_loaded = x509.load_pem_x509_certificate(ca_cert)
        ca_private_key_loaded = serialization.load_pem_private_key(
            ca_private_key, password=None
        )

        # Generate client private key
        client_private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Create subject name
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "TR"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Istanbul"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Istanbul"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PC Control"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Mobile Clients"),
            x509.NameAttribute(NameOID.COMMON_NAME, device_name),
        ])

        # Create certificate
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            ca_cert_loaded.subject
        ).public_key(
            client_private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)  # 1 year
        ).add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        ).sign(ca_private_key_loaded, hashes.SHA256())

        # Serialize to PEM format
        private_key_pem = client_private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption()
        )

        cert_pem = cert.public_bytes(Encoding.PEM)

        return private_key_pem, cert_pem

    def generate_all_certificates(self, hostname: Optional[str] = None) -> dict:
        """
        Generate all required certificates for mTLS setup.

        Args:
            hostname: Server hostname (auto-detected if not provided)

        Returns:
            Dictionary with certificate information
        """
        print("Generating SSL certificates for mTLS communication...")

        # Generate CA certificate
        print("  Generating Certificate Authority...")
        ca_key, ca_cert = self.generate_ca_certificate()

        # Save CA certificate
        ca_path = self.certificates_dir / "ca.crt"
        ca_key_path = self.certificates_dir / "ca.key"

        with open(ca_path, "wb") as f:
            f.write(ca_cert)
        with open(ca_key_path, "wb") as f:
            f.write(ca_key)

        print(f"  CA certificate saved: {ca_path}")

        # Generate server certificate
        print("  Generating server certificate...")
        server_key, server_cert = self.generate_server_certificate(
            ca_key, ca_cert, hostname
        )

        # Save server certificate
        server_cert_path = self.certificates_dir / "server.crt"
        server_key_path = self.certificates_dir / "server.key"

        with open(server_cert_path, "wb") as f:
            f.write(server_cert)
        with open(server_key_path, "wb") as f:
            f.write(server_key)

        print(f"  Server certificate saved: {server_cert_path}")

        # Generate sample client certificate (for testing)
        print("  Generating sample client certificate...")
        client_key, client_cert = self.generate_client_certificate(
            ca_key, ca_cert, "Test Android Device"
        )

        # Save client certificate
        client_cert_path = self.certificates_dir / "client.crt"
        client_key_path = self.certificates_dir / "client.key"

        with open(client_cert_path, "wb") as f:
            f.write(client_cert)
        with open(client_key_path, "wb") as f:
            f.write(client_key)

        print(f"  Client certificate saved: {client_cert_path}")

        # Generate certificate fingerprints
        ca_fingerprint = self._get_certificate_fingerprint(ca_cert)
        server_fingerprint = self._get_certificate_fingerprint(server_cert)

        result = {
            "ca_certificate": str(ca_path),
            "ca_private_key": str(ca_key_path),
            "ca_fingerprint": ca_fingerprint,
            "server_certificate": str(server_cert_path),
            "server_private_key": str(server_key_path),
            "server_fingerprint": server_fingerprint,
            "client_certificate": str(client_cert_path),
            "client_private_key": str(client_key_path),
            "hostname": hostname or socket.gethostname(),
        }

        print("All certificates generated successfully!")
        print(f"CA Fingerprint: {ca_fingerprint}")
        print(f"Server Fingerprint: {server_fingerprint}")

        return result

    def _get_local_ip_addresses(self):
        """Get local IP addresses for Subject Alternative Names."""
        import ipaddress

        try:
            hostname = socket.gethostname()
            ips = socket.getaddrinfo(hostname, None)
            ip_addresses = []
            for info in ips:
                if info[0] == socket.AF_INET:  # IPv4
                    ip_addresses.append(ipaddress.IPv4Address(info[4][0]))
                elif info[0] == socket.AF_INET6:  # IPv6
                    ip_addresses.append(ipaddress.IPv6Address(info[4][0]))

            # Add loopback addresses
            ip_addresses.extend([
                ipaddress.IPv4Address("127.0.0.1"),
                ipaddress.IPv6Address("::1")
            ])

            # Remove duplicates
            return list(set(ip_addresses))
        except Exception:
            return [
                ipaddress.IPv4Address("127.0.0.1"),
                ipaddress.IPv6Address("::1")
            ]

    def _get_certificate_fingerprint(self, cert_pem: bytes) -> str:
        """Get SHA-256 fingerprint of certificate."""
        cert = x509.load_pem_x509_certificate(cert_pem)
        fingerprint = cert.fingerprint(hashes.SHA256())
        return ":".join([f"{b:02x}" for b in fingerprint])


def generate_certificates(certificates_dir: str | Path, hostname: Optional[str] = None) -> dict:
    """
    Convenience function to generate all certificates.

    Args:
        certificates_dir: Directory to store certificates
        hostname: Server hostname (auto-detected if not provided)

    Returns:
        Dictionary with certificate information
    """
    generator = CertificateGenerator(Path(certificates_dir))
    return generator.generate_all_certificates(hostname)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate SSL certificates for PC Control")
    parser.add_argument(
        "--cert-dir",
        default="config/certificates",
        help="Directory to store certificates"
    )
    parser.add_argument(
        "--hostname",
        help="Server hostname (auto-detected if not provided)"
    )

    args = parser.parse_args()

    # Generate certificates
    result = generate_certificates(args.cert_dir, args.hostname)

    print("\nCertificate generation complete!")
    print("Use these certificates for mTLS setup:")
    print(f"   CA Certificate: {result['ca_certificate']}")
    print(f"   Server Certificate: {result['server_certificate']}")
    print(f"   Server Private Key: {result['server_private_key']}")
    print(f"   Hostname: {result['hostname']}")