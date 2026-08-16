"""Streaming ASR gRPC server (implements @inclusaai/grpc-contracts AsrService).

SKELETON. The generated stubs live in ``inclusaai_contracts.grpc_stubs`` after
running ``make gen-contracts``; until then this module imports lazily and raises a
clear error rather than breaking import of the rest of the app. The Kafka pipeline
is the primary path — gRPC streaming is opt-in via ``grpc_enabled``.
"""

from __future__ import annotations

from typing import Any

from inclusaai_telemetry import get_logger

from app.config import Settings
from app.inference.engine import AsrEngine

log = get_logger(__name__)


def create_grpc_server(engine: AsrEngine, settings: Settings) -> Any:
    """Build (but do not start) a grpc.aio server hosting the ASR servicer."""
    import grpc  # local import: grpc is only needed when streaming is enabled

    try:
        from inclusaai_contracts.grpc_stubs import asr_pb2, asr_pb2_grpc  # noqa: F401
    except ImportError as exc:  # stubs not generated yet
        raise RuntimeError(
            "gRPC stubs are not generated. Run `make gen-contracts` first."
        ) from exc

    class AsrServicer(asr_pb2_grpc.AsrServiceServicer):  # type: ignore[misc, name-defined]
        async def StreamingRecognize(self, request_iterator: Any, context: Any) -> Any:
            async for _frame in request_iterator:
                # TODO(model-integration): map AudioFrame -> engine.transcribe -> Transcript
                # and yield Transcript messages as segments finalize.
                ...

    server = grpc.aio.server()
    asr_pb2_grpc.add_AsrServiceServicer_to_server(AsrServicer(), server)
    server.add_insecure_port(f"{settings.http_host}:{settings.grpc_port}")
    log.info("grpc.configured", port=settings.grpc_port)
    return server
