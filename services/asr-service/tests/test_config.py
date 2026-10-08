from __future__ import annotations

from app.config import Settings


def test_model_name_defaults_to_none(monkeypatch) -> None:
    monkeypatch.delenv("MODEL_NAME", raising=False)

    settings = Settings(_env_file=None)

    assert settings.model_name is None
