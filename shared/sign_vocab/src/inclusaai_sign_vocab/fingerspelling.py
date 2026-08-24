"""Fingerspelling fallback for out-of-vocabulary content (ADR-0002).

The constrained vocabulary covers common presentation/classroom phrases; anything
outside it is spelled letter-by-letter. This bounded ~26-symbol manual alphabet is
what both sides fall back to: the avatar renders a handshape per letter, and the
recognizer classifies a handshape per letter. Fingerspelling recognition is a
deliberately bounded problem, unlike open-vocabulary translation.
"""

from __future__ import annotations

import string

#: The fingerspelling alphabet (ASL manual alphabet — one handshape per letter).
FINGERSPELL_ALPHABET: tuple[str, ...] = tuple(string.ascii_lowercase)

_ALPHABET_SET = frozenset(FINGERSPELL_ALPHABET)


def fingerspell(text: str) -> list[str]:
    """Spell ``text`` as a list of alphabet symbols (letters only, lowercased).

    Non-letters (spaces, digits, punctuation) are dropped — digits are covered by
    the number phrases in the vocabulary, not fingerspelled.
    """
    return [ch for ch in text.lower() if ch in _ALPHABET_SET]
