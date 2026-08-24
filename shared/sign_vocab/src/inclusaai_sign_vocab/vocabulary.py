"""The closed constrained vocabulary — the single source of truth shared by
avatar-pose (generation) and sign-recognition (recognition), per ADR-0002.

The avatar generates from exactly this set; the recognizer classifies against
exactly this set (symmetric vocabulary). Out-of-vocabulary content falls back to
fingerspelling (see :mod:`inclusaai_sign_vocab.fingerspelling`).

⚠️  STARTER SET — NOT YET AUTHORITATIVE. ADR-0002 makes a Deaf-community/linguist
consultation a **blocking prerequisite** before real ASL data work: the target is
~150–300 curated phrases, and the ``gloss`` values below are unverified engineering
placeholders (real ASL glosses are not a 1:1 uppercasing of English). This module
ships a small, clearly-labeled, easily-extended starter set so the two services can
be wired symmetrically now; the curated list and verified glosses land after that
consultation. Extend ``_PHRASES`` / ``_NUMBER_WORDS`` — everything downstream keys
off :func:`phrase_ids`, so both services stay in lock-step automatically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Phrase categories (the axes a ~150–300 curated set would fill out).
GREETING = "greeting"
QA = "qa"
TRANSITION = "transition"
POLITENESS = "politeness"
NUMBER = "number"
CLASSROOM = "classroom"


@dataclass(frozen=True)
class PhraseEntry:
    """One phrase in the closed vocabulary.

    ``id`` is a stable slug (the recognizer's label + the avatar's ``phrase_id``);
    ``english`` is the human-readable phrase used to match transcript text;
    ``gloss`` is an unverified placeholder ASL gloss (see module note); ``aliases``
    are extra surface forms that should also map to this phrase.
    """

    id: str
    english: str
    gloss: str
    category: str
    aliases: tuple[str, ...] = ()


def _p(pid: str, english: str, gloss: str, category: str, *aliases: str) -> PhraseEntry:
    return PhraseEntry(id=pid, english=english, gloss=gloss, category=category, aliases=aliases)


_PHRASES: tuple[PhraseEntry, ...] = (
    # --- greetings ---
    _p("hello", "hello", "HELLO", GREETING, "hi", "hey"),
    _p("good_morning", "good morning", "MORNING", GREETING, "morning"),
    _p("good_afternoon", "good afternoon", "AFTERNOON", GREETING, "afternoon"),
    _p("goodbye", "goodbye", "GOODBYE", GREETING, "bye", "good bye"),
    _p("welcome", "welcome", "WELCOME", GREETING),
    _p("nice_to_meet_you", "nice to meet you", "NICE MEET YOU", GREETING, "nice to meet"),
    _p("how_are_you", "how are you", "HOW YOU", GREETING),
    # --- question / answer ---
    _p("yes", "yes", "YES", QA, "yeah", "yep"),
    _p("no", "no", "NO", QA, "nope"),
    _p("maybe", "maybe", "MAYBE", QA),
    _p("i_understand", "i understand", "UNDERSTAND", QA, "understand"),
    _p("i_dont_understand", "i don't understand", "NOT UNDERSTAND", QA,
       "dont understand", "do not understand"),
    _p("i_dont_know", "i don't know", "KNOW NOT", QA, "dont know", "do not know"),
    _p("please_repeat", "can you repeat", "REPEAT", QA, "repeat", "say again", "repeat that"),
    _p("correct", "correct", "RIGHT", QA, "right", "thats right"),
    _p("wrong", "wrong", "WRONG", QA, "incorrect", "not right"),
    _p("what", "what", "WHAT", QA),
    _p("why", "why", "WHY", QA),
    _p("who", "who", "WHO", QA),
    _p("where", "where", "WHERE", QA),
    _p("when", "when", "WHEN", QA),
    _p("how", "how", "HOW", QA),
    # --- presentation transitions ---
    _p("lets_begin", "let's begin", "START", TRANSITION, "lets start", "begin", "start"),
    _p("lets_continue", "let's continue", "CONTINUE", TRANSITION, "continue"),
    _p("next", "next", "NEXT", TRANSITION, "next slide", "move on", "moving on"),
    _p("previous", "previous", "BEFORE", TRANSITION, "go back", "previous slide", "back"),
    _p("any_questions", "any questions", "QUESTION ANY", TRANSITION, "questions", "any question"),
    _p("lets_take_a_break", "let's take a break", "BREAK", TRANSITION, "take a break", "break"),
    _p("for_example", "for example", "EXAMPLE", TRANSITION, "example", "such as"),
    _p("in_conclusion", "in conclusion", "FINISH", TRANSITION, "to conclude", "in summary",
       "finally"),
    _p("important", "important", "IMPORTANT", TRANSITION, "very important"),
    # --- politeness ---
    _p("please", "please", "PLEASE", POLITENESS),
    _p("thank_you", "thank you", "THANK-YOU", POLITENESS, "thanks", "thank you very much"),
    _p("youre_welcome", "you're welcome", "WELCOME", POLITENESS, "your welcome", "youre welcome"),
    _p("sorry", "sorry", "SORRY", POLITENESS, "i'm sorry", "apologies"),
    _p("excuse_me", "excuse me", "EXCUSE-ME", POLITENESS, "pardon"),
    _p("good_job", "good job", "GOOD-JOB", POLITENESS, "well done", "great job", "nice work"),
    # --- classroom / content ---
    _p("name", "name", "NAME", CLASSROOM, "my name is", "your name"),
    _p("learn", "learn", "LEARN", CLASSROOM, "learning"),
    _p("teach", "teach", "TEACH", CLASSROOM, "teaching"),
    _p("read", "read", "READ", CLASSROOM, "reading"),
    _p("write", "write", "WRITE", CLASSROOM, "writing"),
    _p("book", "book", "BOOK", CLASSROOM, "textbook"),
    _p("help", "help", "HELP", CLASSROOM, "help me", "need help"),
    _p("finished", "finished", "FINISH", CLASSROOM, "done", "complete", "all done"),
)

_NUMBER_WORDS: tuple[str, ...] = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
)
_NUMBERS: tuple[PhraseEntry, ...] = tuple(
    _p(f"number_{i}", word, word.upper(), NUMBER, str(i))
    for i, word in enumerate(_NUMBER_WORDS)
)

#: The full closed vocabulary (phrases + numbers), in a stable order.
PHRASES: tuple[PhraseEntry, ...] = _PHRASES + _NUMBERS

#: Lookup by id.
PHRASE_BY_ID: dict[str, PhraseEntry] = {p.id: p for p in PHRASES}

# Fail fast at import if two entries collide on id (keeps the closed set well-formed).
assert len(PHRASE_BY_ID) == len(PHRASES), "duplicate phrase id in the constrained vocabulary"


def phrase_ids() -> tuple[str, ...]:
    """The closed classification label set: every phrase id, in vocabulary order.

    This is the set the recognizer classifies into and the set the avatar can
    generate from — the symmetric vocabulary of ADR-0002.
    """
    return tuple(p.id for p in PHRASES)


_WORD_RE = re.compile(r"[a-z0-9]+")


def normalize(text: str) -> str:
    """Lowercase ``text`` and collapse it to space-separated alphanumeric tokens."""
    return " ".join(_WORD_RE.findall(text.lower()))


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _is_sublist(needle: list[str], haystack: list[str]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    span = len(needle)
    return any(haystack[i : i + span] == needle for i in range(len(haystack) - span + 1))


def match(text: str) -> PhraseEntry | None:
    """Map free transcript text to a vocabulary phrase, or ``None`` if out-of-vocab.

    Matches on whole-word (token) subsequences — so ``"everyone"`` does not match
    ``"one"`` — and prefers the phrase with the longest matching surface form, so
    ``"good morning everyone"`` resolves to ``good_morning`` rather than nothing and
    ``"how are you today"`` resolves to ``how_are_you`` rather than ``how``.
    """
    haystack = _tokens(text)
    if not haystack:
        return None
    best: PhraseEntry | None = None
    best_len = 0
    for phrase in PHRASES:
        for surface in (phrase.english, *phrase.aliases):
            candidate = _tokens(surface)
            if len(candidate) > best_len and _is_sublist(candidate, haystack):
                best, best_len = phrase, len(candidate)
    return best
