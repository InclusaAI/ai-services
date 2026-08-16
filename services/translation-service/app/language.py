"""Language helpers: normalization and the supported set."""

from __future__ import annotations

# TODO(contracts): source the authoritative supported-language set from
# @inclusaai/kafka-contracts / the PRD once available.
SUPPORTED_LANGUAGES = {"en", "es", "fr", "de", "pt", "ar", "zh"}


def normalize(code: str) -> str:
    return code.strip().lower()


def is_supported(code: str) -> bool:
    return normalize(code) in SUPPORTED_LANGUAGES
