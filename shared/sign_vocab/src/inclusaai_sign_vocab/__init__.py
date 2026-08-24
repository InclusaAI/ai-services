"""inclusaai_sign_vocab — the closed constrained ASL vocabulary.

Single source of truth for the **symmetric vocabulary** mandated by ADR-0002: the
avatar-pose service generates from exactly the set the sign-recognition service
classifies against. Both import from here, so the two can never drift.

Public surface:
    PhraseEntry, PHRASES, PHRASE_BY_ID, phrase_ids(), match(), normalize()
    FINGERSPELL_ALPHABET, fingerspell()          — out-of-vocabulary fallback
    SKELETON, NUM_KEYPOINTS                       — canonical keypoint layout
"""

from __future__ import annotations

from inclusaai_sign_vocab.fingerspelling import FINGERSPELL_ALPHABET, fingerspell
from inclusaai_sign_vocab.skeleton import NUM_KEYPOINTS, SKELETON
from inclusaai_sign_vocab.vocabulary import (
    CLASSROOM,
    GREETING,
    NUMBER,
    PHRASE_BY_ID,
    PHRASES,
    POLITENESS,
    QA,
    TRANSITION,
    PhraseEntry,
    match,
    normalize,
    phrase_ids,
)

__all__ = [
    "PhraseEntry",
    "PHRASES",
    "PHRASE_BY_ID",
    "phrase_ids",
    "match",
    "normalize",
    "FINGERSPELL_ALPHABET",
    "fingerspell",
    "SKELETON",
    "NUM_KEYPOINTS",
    "GREETING",
    "QA",
    "TRANSITION",
    "POLITENESS",
    "NUMBER",
    "CLASSROOM",
]
