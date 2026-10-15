"""Translation engine: real model when configured, deterministic stub otherwise.

Three backends, in priority order:

* ``local``  — an in-process Hugging Face MT model, chosen by
  ``TRANSLATION_MODEL_ID`` (e.g. ``Helsinki-NLP/opus-mt-en-es``). DEV pattern,
  mirroring ``ASR_WHISPER_SIZE``: bypasses MLflow so a real translation runs on a
  box with no registry. The model id fixes the language pair (an NLLB-style
  multilingual tokenizer needs a wrapper — not wired yet).
* ``mlflow`` — a registered model (``MODEL_NAME``, ADR-0005) loaded as
  ``mlflow.pyfunc``. **Calling contract** (what research must package the model
  as): ``predict({"text": str, "source": str, "target": str}) -> str`` (or a
  ``{"translation": str}`` mapping). An interface mismatch raises a loud
  RuntimeError naming the contract — it must never degrade into the stub.
* ``stub``   — deterministic ``"[{target}] {text}"`` placeholder (no gradients,
  no surprises); the default when nothing is configured or load failed.
"""

from __future__ import annotations

from typing import Any

from inclusaai_model_loading import ModelNotAvailable, load_model, measure_latency
from inclusaai_telemetry import get_logger

from app.config import Settings

log = get_logger(__name__)

_BACKEND_LOCAL = "local"
_BACKEND_MLFLOW = "mlflow"
_BACKEND_STUB = "stub"

#: Runtime deps of the local backend; installed via ``uv sync --extra real-model``.
_LOCAL_BACKEND_EXTRAS = "uv sync --extra real-model"


def _extract_text(prediction: Any) -> str:
    """Unwrap common model/pipeline return shapes into plain translated text."""
    if isinstance(prediction, dict):
        for key in ("translation_text", "translation", "text", "output"):
            if value := prediction.get(key):
                return str(value)
    if isinstance(prediction, (list, tuple)) and prediction:
        return _extract_text(prediction[0])
    return str(prediction)


class TranslationEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._backend = _BACKEND_STUB
        self._model: Any | None = None     # registered mlflow.pyfunc model
        self._hf: Any | None = None        # in-process HF translation pipeline
        # kept for callers that treat the engine as truthy-or-not
        self._stub = True

    # ------------------------------------------------------------------ loading
    def load(self) -> None:
        if self._load_local():
            return
        if self._load_registered():
            return
        self._stub = True
        if self.settings.translation_model_id or self.settings.model_name:
            log.warning("translation.stub_fallback", reason="model load failed")

    def _load_local(self) -> bool:
        model_id = self.settings.translation_model_id
        if not model_id:
            return False
        try:
            from transformers import pipeline as hf_pipeline
        except ImportError as exc:
            log.error(
                "translation.deps_missing",
                hint=f"install the real-model runtime extras first: {_LOCAL_BACKEND_EXTRAS}",
                error=str(exc),
            )
            return False
        try:
            self._hf = hf_pipeline("translation", model=model_id)
        except Exception as exc:  # noqa: BLE001 — network/config problems both count
            log.error("translation.local_model_failed", model=model_id, error=str(exc))
            return False
        log.info("translation.local_model_loaded", model=model_id)
        self._backend, self._stub = _BACKEND_LOCAL, False
        return True

    def _load_registered(self) -> bool:
        if not self.settings.model_name:
            return False
        try:
            self._model = load_model(
                self.settings.model_name,
                stage=self.settings.model_stage,
                version=self.settings.model_version,
                tracking_uri=self.settings.mlflow_tracking_uri,
            )
            self._backend, self._stub = _BACKEND_MLFLOW, False
            return True
        except ModelNotAvailable as exc:
            log.error("translation.model_unavailable", error=str(exc))
            return False

    # ---------------------------------------------------------------- inference
    @property
    def ready(self) -> bool:
        """True when the engine can actually translate as configured.

        Stub-only because nothing was requested → True (stub is the intended dev
        path). A requested real model that failed to load → False: the pipeline's
        ``model_ready`` flag picks this up so REQUIRE_MODEL turns /readyz to 503
        instead of silently serving ``[es] hello`` forever.
        """
        if self.settings.translation_model_id:
            return self._backend == _BACKEND_LOCAL
        if self.settings.model_name:
            return self._backend == _BACKEND_MLFLOW
        return True

    def translate(self, text: str, *, source: str, target: str) -> str:
        with measure_latency(self.settings.service_name, self.settings.model_name or "stub"):
            if self._backend == _BACKEND_LOCAL and self._hf is not None:
                prediction = self._hf(text)
                return _extract_text(prediction)
            if self._backend == _BACKEND_MLFLOW and self._model is not None:
                return self._registered_predict(text, source=source, target=target)
            return f"[{target}] {text}"

    def _registered_predict(self, text: str, *, source: str, target: str) -> str:
        """Call the registered pyfunc model under the documented contract.

        Raises RuntimeError naming the contract when the model doesn't satisfy it —
        callers see inference errors (and the offline log), not silent stub output.
        """
        payload = {"text": text, "source": source, "target": target}
        if self._model is None:  # unreachable via translate(), keeps mypy + honesty tight
            raise RuntimeError("registered model backend selected but no model is loaded")
        try:
            prediction = self._model.predict(payload)
        except Exception as exc:  # noqa: BLE001 — surface the contract, not the traceback shape
            raise RuntimeError(
                "contract violation: registered translation model must implement "
                "predict({'text','source','target'}) -> str (or {'translation': str})"
            ) from exc
        return _extract_text(prediction)
