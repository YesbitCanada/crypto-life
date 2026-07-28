#!/usr/bin/env python3
"""Check and deploy a wildcard certificate to Tencent COS custom domains."""

from __future__ import annotations

import argparse
import os
import socket
import ssl
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from qcloud_cos import CosConfig, CosS3Client


TARGETS = [
    {
        "bucket": "degen-1256918364",
        "region": "ap-hongkong",
        "domains": ["degen.app-sands.com"],
    },
]
WILDCARD_NAME = "*.app-sands.com"


def fetch_certificate(hostname: str) -> x509.Certificate:
    context = ssl.create_default_context()
    with socket.create_connection((hostname, 443), timeout=15) as raw_socket:
        with context.wrap_socket(raw_socket, server_hostname=hostname) as tls_socket:
            der = tls_socket.getpeercert(binary_form=True)
    return x509.load_der_x509_certificate(der)


def dns_names(certificate: x509.Certificate) -> set[str]:
    extension = certificate.extensions.get_extension_for_class(
        x509.SubjectAlternativeName
    )
    return set(extension.value.get_values_for_type(x509.DNSName))


def certificate_matches(
    certificate: x509.Certificate, expected_serial: int | None = None
) -> bool:
    if expected_serial is not None and certificate.serial_number != expected_serial:
        return False
    return WILDCARD_NAME in dns_names(certificate)


def check(hostname: str, renew_before_days: int) -> int:
    try:
        certificate = fetch_certificate(hostname)
    except Exception as error:
        print(f"Certificate check failed: {error}", file=sys.stderr, flush=True)
        return 0

    expires = certificate.not_valid_after_utc
    remaining = expires - datetime.now(timezone.utc)
    wildcard = WILDCARD_NAME in dns_names(certificate)
    print(
        f"{hostname}: expires={expires.isoformat()} "
        f"remaining_days={remaining.days} wildcard={wildcard}",
        flush=True,
    )
    return int(wildcard and remaining > timedelta(days=renew_before_days))


def cos_client(region: str) -> CosS3Client:
    return CosS3Client(
        CosConfig(
            Region=region,
            SecretId=os.environ["TCB_SECRET_ID"],
            SecretKey=os.environ["TCB_SECRET_KEY"],
        )
    )


def deploy(cert_path: Path, key_path: Path) -> None:
    certificate_pem = cert_path.read_text()
    private_key_pem = key_path.read_text()
    certificate = x509.load_pem_x509_certificate(certificate_pem.encode())

    if WILDCARD_NAME not in dns_names(certificate):
        raise ValueError(f"Certificate does not cover {WILDCARD_NAME}")

    for target in TARGETS:
        client = cos_client(target["region"])
        client.put_bucket_domain_certificate(
            Bucket=target["bucket"],
            DomainCertificateConfiguration={
                "DomainList": {"DomainName": target["domains"]},
                "CertificateInfo": {
                    "CertType": "CustomCert",
                    "CustomCert": {
                        "Cert": certificate_pem,
                        "PrivateKey": private_key_pem,
                    },
                },
            },
        )
        for domain in target["domains"]:
            result = client.get_bucket_domain_certificate(
                Bucket=target["bucket"], DomainName=domain
            )
            print(
                f"Deployed {domain}: cert_id="
                f"{result.get('CertificateInfo', {}).get('CertId', 'unknown')}",
                flush=True,
            )

    verify_deployment(certificate.serial_number)


def verify_deployment(expected_serial: int) -> None:
    pending = {domain for target in TARGETS for domain in target["domains"]}
    consecutive = {domain: 0 for domain in pending}
    deadline = time.monotonic() + 30 * 60

    while pending and time.monotonic() < deadline:
        for domain in list(pending):
            try:
                current = fetch_certificate(domain)
                if certificate_matches(current, expected_serial):
                    consecutive[domain] += 1
                    if consecutive[domain] >= 3:
                        pending.remove(domain)
                        print(
                            f"Verified {domain} on three consecutive TLS handshakes",
                            flush=True,
                        )
                else:
                    consecutive[domain] = 0
            except Exception as error:
                consecutive[domain] = 0
                print(f"Waiting for {domain}: {error}", flush=True)
        if pending:
            time.sleep(30)

    if pending:
        raise TimeoutError(
            "COS accepted the certificate, but TLS propagation did not stabilize for: "
            + ", ".join(sorted(pending))
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--hostname", default="degen.app-sands.com")
    check_parser.add_argument("--renew-before-days", type=int, default=30)

    deploy_parser = subparsers.add_parser("deploy")
    deploy_parser.add_argument("--certificate", type=Path, required=True)
    deploy_parser.add_argument("--private-key", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "check":
        current = check(args.hostname, args.renew_before_days)
        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with open(output, "a", encoding="utf-8") as file:
                file.write(f"current={current}\n")
        sys.exit(0)

    deploy(args.certificate, args.private_key)


if __name__ == "__main__":
    main()
