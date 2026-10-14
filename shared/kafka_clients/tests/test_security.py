"""Regression tests for managed-broker (Aiven/Confluent) SASL/TLS configuration.

The bug this guards against: `ssl.create_default_context(cadata=pem_bytes)`
raises "not enough data: cadata does not contain a certificate", because Python
treats `cadata` given as *bytes* as DER, and a PEM blob is never valid DER.
That failure was swallowed by `producer.start()` into offline stub mode, so a
service came up healthy while doing nothing. Passing a PEM path (`cafile`) is
the supported route and must keep working.
"""

from __future__ import annotations

import ssl

import pytest
from inclusaai_kafka_clients.security import security_kwargs

# Self-signed test CA, generated for this suite. NOT the Aiven production CA.
TEST_CA_PEM = '''-----BEGIN CERTIFICATE-----
MIIC2TCCAcGgAwIBAgIUSPyUDWWPSRKp0Gn0PnCz1r2bFoEwDQYJKoZIhvcNAQEL
BQAwHDEaMBgGA1UEAwwRSW5jbHVzYUFJIFRlc3QgQ0EwHhcNMjYwMTAxMDAwMDAw
WhcNMzUxMjMwMDAwMDAwWjAcMRowGAYDVQQDDBFJbmNsdXNhQUkgVGVzdCBDQTCC
ASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBALhKSoiAE0d6a7tdExC8S/6B
yYarvzC+mLJc4L4OTefPnvxRnkXaxNmGOxPoYVvKHg+3/eH0QN5it59FL4JRvY/X
cKpSiGnrborNt1U2KD4OBQzFZdmv9TQ/CIY7nHqJund1zTc1Zm2pEB8fjqaho3eJ
cgipU8e76ND6LZah5O2IbKZ2HYAk5Xn7AQrMXTHIa3yNtbeMsHUAA4RcjthY4SM4
aEFbNYS6kZZaDsX8uBUcKOkE8/FFt87ucAa+AsvMHWfE2DCZuP8sxAOTWwJNhkl2
PBvbAuGQlGCUtDkWubjZ/13Ad8yV6RhwVht/vdJpqKMC217lorWOtF933GAcRBMC
AwEAAaMTMBEwDwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAQEAsRab
U8c+yWUROGu5ab8Wf1rLkRXOPvrGrWdTJKU5YXRnMvQDTxt5BON9GbbgmwIzcdNX
g1a+3al1cxQs4MCEx1nxFc5yw5nqbH9FBPLLbX/NEeTv2JKZTNDnyLAS0lj5JRjm
wFWQuVr0CW84qEiScwfCg17aXz+u8cblu6yW9naGvTqARbfaLisO3d9xL3K+atTK
44ud8UpQ8XLB8Sq0Wfi3+u4STnbKLc5teV15L0JVSgbGzS5kJE8QliXwVRaarVNv
m6ukoxahWuv2QGuUIyEkVhKAlmHujqJMQ6KVE+w8TVbgRm/mabH6EiRAMcQwvEzl
2dYlpHIZfFIDrkcZfg==
-----END CERTIFICATE-----'''


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "KAFKA_SECURITY_PROTOCOL",
        "KAFKA_SASL_MECHANISM",
        "KAFKA_USERNAME",
        "KAFKA_PASSWORD",
        "KAFKA_CA_CERT",
    ):
        monkeypatch.delenv(key, raising=False)


def test_plaintext_by_default() -> None:
    """No env vars -> aiokafka's PLAINTEXT default, which dev redpanda needs."""
    assert security_kwargs() == {}


def test_credentials_imply_sasl_ssl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Credentials with no explicit protocol default to the managed-broker path."""
    monkeypatch.setenv("KAFKA_USERNAME", "u")
    assert security_kwargs()["security_protocol"] == "SASL_SSL"


def test_inline_pem_yields_a_usable_ssl_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Render path: the whole PEM arrives as an env var value."""
    monkeypatch.setenv("KAFKA_SECURITY_PROTOCOL", "SASL_SSL")
    monkeypatch.setenv("KAFKA_SASL_MECHANISM", "PLAIN")
    monkeypatch.setenv("KAFKA_USERNAME", "user")
    monkeypatch.setenv("KAFKA_PASSWORD", "pw")
    monkeypatch.setenv("KAFKA_CA_CERT", TEST_CA_PEM)

    kwargs = security_kwargs()
    ctx = kwargs["ssl_context"]

    assert isinstance(ctx, ssl.SSLContext)
    # Must actually have loaded the CA, not merely be a context object.
    assert len(ctx.get_ca_certs()) == 1
    assert ctx.get_ca_certs()[0]["subject"][0][0][1] == "InclusaAI Test CA"
    # A managed broker with a private CA is only safe if verification is on.
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True

    assert kwargs["security_protocol"] == "SASL_SSL"
    assert kwargs["sasl_mechanism"] == "PLAIN"
    assert kwargs["sasl_plain_username"] == "user"
    assert kwargs["sasl_plain_password"] == "pw"


def test_pem_without_trailing_newline_still_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Render strips trailing whitespace from env values; that must not break TLS."""
    monkeypatch.setenv("KAFKA_SECURITY_PROTOCOL", "SASL_SSL")
    monkeypatch.setenv("KAFKA_CA_CERT", TEST_CA_PEM)  # no trailing newline
    ctx = security_kwargs()["ssl_context"]
    assert len(ctx.get_ca_certs()) == 1


def test_ca_file_path_is_passed_through(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    p = tmp_path / "ca.pem"
    p.write_text(TEST_CA_PEM, encoding="ascii")
    monkeypatch.setenv("KAFKA_SECURITY_PROTOCOL", "SASL_SSL")
    monkeypatch.setenv("KAFKA_CA_CERT", str(p))
    assert len(security_kwargs()["ssl_context"].get_ca_certs()) == 1


def test_no_ssl_context_for_plaintext(monkeypatch: pytest.MonkeyPatch) -> None:
    """A CA configured with a non-SSL protocol must not build a context."""
    monkeypatch.setenv("KAFKA_SECURITY_PROTOCOL", "SASL_PLAINTEXT")
    monkeypatch.setenv("KAFKA_CA_CERT", TEST_CA_PEM)
    kwargs = security_kwargs()
    assert "ssl_context" not in kwargs
    assert kwargs["security_protocol"] == "SASL_PLAINTEXT"


def test_pem_as_bytes_is_not_der_and_must_not_be_used() -> None:
    """Pin the trap that broke the Aiven deploy.

    Python treats ``cadata`` given as *bytes* as DER-encoded, so a PEM blob
    raises "not enough data: cadata does not contain a certificate" no matter
    how it is newline-terminated. This is why ``security_kwargs`` writes the PEM
    to a temp file and passes ``cafile=`` instead of building a context from
    ``cadata``. If someone "simplifies" it back to bytes, this test fails.
    """
    from aiokafka.helpers import create_ssl_context

    with pytest.raises(Exception, match="not enough data"):
        create_ssl_context(cadata=TEST_CA_PEM.encode("ascii"))

    # The str form parses fine, which is why a cafile/ca-data round-trip works.
    assert len(create_ssl_context(cadata=TEST_CA_PEM).get_ca_certs()) == 1
