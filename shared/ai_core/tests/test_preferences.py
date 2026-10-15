"""Preference-aware gating: single-channel and multi-channel checks.

Pins the two properties the services depend on: gating is **fail-open** before
preferences arrive (we never drop needed output during the propagation race), and a
service whose output feeds *several* channels is gated off only when nobody in the
session needs *any* of them.
"""

from __future__ import annotations

from inclusaai_ai_core.config import BaseServiceSettings
from inclusaai_ai_core.pipeline import BaseInferencePipeline
from inclusaai_ai_core.preferences import PreferenceCache
from inclusaai_contracts.events import AccessibilityChannel, AccessibilityPreferenceUpdated

CAPTIONS = AccessibilityChannel.CAPTIONS
TRANSLATION = AccessibilityChannel.TRANSLATION
AVATAR = AccessibilityChannel.AVATAR


def _pref(session_id: str, participant_id: str, *channels: AccessibilityChannel):
    return AccessibilityPreferenceUpdated(
        session_id=session_id,
        participant_id=participant_id,
        channels=list(channels),
        updated_at_ms=0,
    )


def _cache(*prefs: AccessibilityPreferenceUpdated) -> PreferenceCache:
    cache = PreferenceCache()
    for pref in prefs:
        cache.update(pref)
    return cache


# ------------------------------------------------------------------ fail-open
def test_single_channel_fails_open_before_preferences_arrive() -> None:
    assert PreferenceCache().should_generate("s1", CAPTIONS) is True


def test_multi_channel_fails_open_before_preferences_arrive() -> None:
    assert PreferenceCache().should_generate_any("s1", (CAPTIONS, TRANSLATION)) is True


def test_multi_channel_fails_open_for_an_unknown_session() -> None:
    """Preferences for *other* sessions must not gate an unseen one."""
    cache = _cache(_pref("s1", "p1", AVATAR))
    assert cache.should_generate_any("unseen", (CAPTIONS, TRANSLATION)) is True


# ------------------------------------------------------- multi-channel semantics
def test_multi_channel_runs_when_any_one_channel_is_needed() -> None:
    """The whole point: a single-channel check would gate this off and drop output."""
    for needed in (CAPTIONS, TRANSLATION):
        cache = _cache(_pref("s1", "p1", needed))
        assert cache.should_generate_any("s1", (CAPTIONS, TRANSLATION)) is True


def test_multi_channel_gates_off_when_no_channel_is_needed() -> None:
    cache = _cache(_pref("s1", "p1", AVATAR))
    assert cache.should_generate_any("s1", (CAPTIONS, TRANSLATION)) is False


def test_multi_channel_is_a_union_across_participants() -> None:
    cache = _cache(
        _pref("s1", "p1", AVATAR),
        _pref("s1", "p2", TRANSLATION),
    )
    assert cache.should_generate_any("s1", (CAPTIONS, TRANSLATION)) is True


def test_multi_channel_differs_from_single_channel() -> None:
    """Captions off but translation on: single-channel says no, multi says yes."""
    cache = _cache(_pref("s1", "p1", TRANSLATION))
    assert cache.should_generate("s1", CAPTIONS) is False
    assert cache.should_generate_any("s1", (CAPTIONS, TRANSLATION)) is True


def test_empty_channel_set_gates_off_a_known_session() -> None:
    """No channels demanded by anyone == nothing to generate."""
    cache = _cache(_pref("s1", "p1"))
    assert cache.should_generate_any("s1", (CAPTIONS, TRANSLATION)) is False


# ------------------------------------------------------------- pipeline wiring
def test_pipeline_uses_multi_channel_gate_when_output_channels_set() -> None:
    class MultiChannel(BaseInferencePipeline):
        output_channels = (CAPTIONS, TRANSLATION)

    pipeline = MultiChannel(
        BaseServiceSettings(service_name="multi-svc", env="test"),
        topics=["ai.transcript.segment"],
    )
    pipeline.preferences.update(_pref("s1", "p1", TRANSLATION))
    assert pipeline.should_generate("s1") is True
    pipeline.preferences.update(_pref("s1", "p2", AVATAR))
    pipeline.preferences.remove_participant("s1", "p2")
    assert pipeline.should_generate("s1") is True


def test_pipeline_with_no_channel_always_generates() -> None:
    """``output_channel = None`` / ``output_channels = None`` means never gate."""

    class Ungated(BaseInferencePipeline):
        pass

    pipeline = Ungated(
        BaseServiceSettings(service_name="ungated-svc", env="test"),
        topics=["ai.transcript.segment"],
    )
    pipeline.preferences.update(_pref("s1", "p1"))
    assert pipeline.should_generate("s1") is True
