"""Kafka client security options, driven by environment variables.

Managed Kafka providers (Upstash, Redpanda Cloud, Confluent Cloud, Aiven, ...)
require SASL auth + TLS. These are optional: with no env vars set, clients use
aiokafka's PLAINTEXT default (matches local redpanda in docker-compose.dev.yml).

Env vars (read at client construction):
    KAFKA_SECURITY_PROTOCOL  PLAINTEXT | SASL_PLAINTEXT | SSL | SASL_SSL
    KAFKA_SASL_MECHANISM     default SCRAM-SHA-256 when credentials are set
    KAFKA_USERNAME           SASL username
    KAFKA_PASSWORD           SASL password
    KAFKA_CA_CERT            path to a PEM CA certificate for SSL protocols, OR the
                             inline PEM body itself -- on single-file diagnostics
                             hosts (Render, container orchestrators) a cert file
                             can't be mounted, so the string form writes it to a
                             temp file once and uses that.
"""

from __future__ import annotations

import os
import ssl
import tempfile
from typing import Any


def security_kwargs() -> dict[str, Any]:
    """Build aiokafka security kwargs from KAFKA_* env vars (empty dict = defaults)."""
    protocol = os.environ.get("KAFKA_SECURITY_PROTOCOL", "").strip()
    username = os.environ.get("KAFKA_USERNAME", "").strip()
    password = os.environ.get("KAFKA_PASSWORD", "").strip()

    # Credentials without an explicit protocol imply SASL_SSL (the managed-broker
    # default); explicitly setting only KAFKA_SECURITY_PROTOCOL enables SASL with
    # empty credentials too (e.g. SASL_PLAINTEXT against a local broker).
    if not protocol and (username or password):
        protocol = "SASL_SSL"

    ca_file = os.environ.get("KAFKA_CA_CERT", "").strip()
    if ca_file:
        # Inline PEM body (Render env var) instead of a filesystem path.
        if "-----BEGIN CERTIFICATE-----" in ca_file:
            fd, ca_path = tempfile.mkstemp(prefix="kafka-ca-", suffix=".pem")
            with os.fdopen(fd, "w", encoding="ascii") as fh:
                fh.write(ca_file)
            ca_file = ca_path

    kwargs: dict[str, Any] = {}
    if protocol:
        kwargs["security_protocol"] = protocol
    # Managed providers (Aiven, Confluent Cloud, ...) sign their TLS chain with a
    # private CA that is not in the system trust store: build a context pinned to
    # the PEM file. aiokafka takes an ``ssl_context``, not ``ssl_cafile``.
    if protocol.endswith("SSL") and ca_file:
        kwargs["ssl_context"] = ssl.create_default_context(cafile=ca_file)
    if username or password:
        kwargs["sasl_mechanism"] = os.environ.get("KAFKA_SASL_MECHANISM", "SCRAM-SHA-256")
        if username:
            kwargs["sasl_plain_username"] = username
        if password:
            kwargs["sasl_plain_password"] = password
    return kwargs
