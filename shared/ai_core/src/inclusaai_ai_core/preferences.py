"""Preference-aware gating (ai-services-IMPLEMENTATION.md §5/§9).

ai-services consumes ``accessibility.preference.updated`` and skips inference work
whose output no active participant in a session has enabled (e.g. don't run
avatar-pose generation for a session where nobody turned the avatar on). Built in
from v1, not bolted on later.
"""

from __future__ import annotations

from inclusaai_contracts.events import AccessibilityChannel, AccessibilityPreferenceUpdated


class PreferenceCache:
    """Per-session view of which output channels at least one participant needs."""

    def __init__(self) -> None:
        # session_id -> participant_id -> set of channels
        self._by_session: dict[str, dict[str, set[AccessibilityChannel]]] = {}

    def update(self, pref: AccessibilityPreferenceUpdated) -> None:
        participants = self._by_session.setdefault(pref.session_id, {})
        participants[pref.participant_id] = set(pref.channels)

    def remove_participant(self, session_id: str, participant_id: str) -> None:
        participants = self._by_session.get(session_id)
        if participants:
            participants.pop(participant_id, None)
            if not participants:
                self._by_session.pop(session_id, None)

    def channels_needed(self, session_id: str) -> set[AccessibilityChannel]:
        needed: set[AccessibilityChannel] = set()
        for channels in self._by_session.get(session_id, {}).values():
            needed |= channels
        return needed

    def session_count(self) -> int:
        return len(self._by_session)

    def should_generate(self, session_id: str, channel: AccessibilityChannel) -> bool:
        """Whether to run inference that produces ``channel`` for ``session_id``.

        Fail-open: if we have received no preference data for a session yet, generate
        (avoids dropping needed output during the brief race before preferences
        propagate). Once we know the session's preferences and nobody needs the
        channel, gate it off to save GPU.
        """
        if session_id not in self._by_session:
            return True
        return channel in self.channels_needed(session_id)
