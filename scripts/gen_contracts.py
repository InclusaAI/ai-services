#!/usr/bin/env python
"""Regenerate contract artifacts from their single sources of truth.

1. gRPC stubs — run ``grpcio-tools`` protoc over ``shared/contracts/proto/`` into
   ``shared/contracts/src/inclusaai_contracts/grpc_stubs/``.
2. JSON Schemas — dump ``model_json_schema()`` for every event in the schema
   registry into ``.../inclusaai_contracts/schemas/<event_key>.schema.json``.

Both halves are independent: a failure in one is reported but does not abort the
other, and the exit code is non-zero if either failed.

Run from the repo root:
    uv run python scripts/gen_contracts.py

(Placeholder generator — see shared/contracts/README.md. The real
@inclusaai/grpc-contracts / @inclusaai/kafka-contracts packages will ship these
pre-generated; keep the ``inclusaai_contracts`` import path stable when they land.)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = REPO_ROOT / "shared" / "contracts"
PROTO_ROOT = CONTRACTS / "proto"
PKG = CONTRACTS / "src" / "inclusaai_contracts"
GRPC_OUT = PKG / "grpc_stubs"
SCHEMA_OUT = PKG / "schemas"


def gen_grpc() -> int:
    protos = sorted(PROTO_ROOT.rglob("*.proto"))
    if not protos:
        print("[grpc] no .proto files found; skipping")
        return 0
    try:
        from grpc_tools import protoc
    except ImportError:
        print("[grpc] grpcio-tools not installed; skipping stub generation.")
        print("       it is a repo dev dependency — run `uv sync` at the repo root first,")
        print("       or `uv add --dev grpcio-tools` if it is missing.")
        return 0

    GRPC_OUT.mkdir(parents=True, exist_ok=True)
    args = [
        "grpc_tools.protoc",
        f"-I{PROTO_ROOT}",
        f"--python_out={GRPC_OUT}",
        f"--grpc_python_out={GRPC_OUT}",
        *[str(p) for p in protos],
    ]
    rc = protoc.main(args)
    if rc != 0:
        print(f"[grpc] protoc exited {rc}", file=sys.stderr)
        return rc

    # Make every generated directory an importable package (without clobbering the
    # committed grpc_stubs/__init__.py).
    for pb2 in GRPC_OUT.rglob("*_pb2.py"):
        init = pb2.parent / "__init__.py"
        if not init.exists():
            init.write_text('"""Generated gRPC package (git-ignored)."""\n', encoding="utf-8")

    print(f"[grpc] generated stubs for {len(protos)} proto file(s) -> "
          f"{GRPC_OUT.relative_to(REPO_ROOT)}")
    print("       NOTE (placeholder): cross-file proto imports assume the proto package")
    print("       root is importable; real bindings ship in @inclusaai/grpc-contracts.")
    return 0


def gen_schemas() -> int:
    # Import lazily and make the package importable even without an editable install.
    sys.path.insert(0, str(PKG.parent))
    try:
        from inclusaai_contracts.schema_registry import EVENT_MODELS
    except Exception as exc:  # noqa: BLE001 — report, don't crash the whole generator
        print(f"[schemas] cannot import schema registry: {exc}", file=sys.stderr)
        return 1

    SCHEMA_OUT.mkdir(parents=True, exist_ok=True)
    count = 0
    for event_key, model in sorted(EVENT_MODELS.items()):
        schema = model.model_json_schema()
        schema["$id"] = f"inclusaai:event:{event_key}"
        schema["title"] = model.__name__
        dest = SCHEMA_OUT / f"{event_key}.schema.json"
        dest.write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        count += 1
    print(f"[schemas] wrote {count} JSON Schema(s) -> {SCHEMA_OUT.relative_to(REPO_ROOT)}")
    return 0


def main() -> int:
    rc_grpc = gen_grpc()
    rc_schema = gen_schemas()
    return rc_grpc or rc_schema


if __name__ == "__main__":
    raise SystemExit(main())
