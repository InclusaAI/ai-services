"""Session-level engagement aggregation.

PRIVACY-CRITICAL (ai-services-IMPLEMENTATION.md §2). Per-individual identifiers are
used ONLY, transiently, to compute counts inside this module — they are NEVER
emitted. The output contract (EngagementSignalAggregate) structurally has no
per-individual id field; keeping ids out here is the other half of that guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from inclusaai_contracts.events import EngagementSignalAggregate, ParticipantEvent
from inclusaai_utils import now_ms


@dataclass
class _SessionState:
    participants: set[str] = field(default_factory=set)
    reactions: dict[str, int] = field(default_factory=dict)
    window_start_ms: int = field(default_factory=now_ms)


class SessionEngagementAggregator:
    def __init__(self) -> None:
        self._sessions: dict[str, _SessionState] = {}

    def apply_participant(self, event: ParticipantEvent) -> None:
        state = self._sessions.setdefault(event.session_id, _SessionState())
        if event.event == "joined":
            state.participants.add(event.participant_id)
        elif event.event == "left":
            state.participants.discard(event.participant_id)

    def snapshot_all(self) -> list[EngagementSignalAggregate]:
        """Emit one aggregate per active session and roll the window. Prunes sessions
        that have emptied out."""
        now = now_ms()
        aggregates: list[EngagementSignalAggregate] = []
        empty: list[str] = []
        for session_id, state in self._sessions.items():
            if not state.participants and not state.reactions:
                empty.append(session_id)
                continue
            aggregates.append(
                EngagementSignalAggregate(
                    session_id=session_id,
                    window_start_ms=state.window_start_ms,
                    window_end_ms=now,
                    participant_count=len(state.participants),
                    attention_score=None,  # TODO: derive from reaction/gaze signals
                    reaction_counts=dict(state.reactions),
                )
            )
            state.window_start_ms = now
            state.reactions = {}
        for session_id in empty:
            del self._sessions[session_id]
        return aggregates
