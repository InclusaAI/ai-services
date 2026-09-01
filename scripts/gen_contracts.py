#!/usr/bin/env python
"""Regenerate contract artifacts from their single sources of truth.

1. gRPC stubs — run ``grpcio-tools`` protoc over ``shared/contracts/proto/`` into
   ``shared/contracts/src/inclusaai_contracts/grpc_stubs/``.
2. JSON Schemas — dump ``model_json_schema()`` for every event in the schema
   registry into ``.../inclusaai_contracts/schemas/<event_key>.schema.json``.
3. TypeScript interfaces — derive typed interfaces from Pydantic models into
   ``shared/contracts/src/inclusaai_contracts/typescript/events.ts``.

All halves are independent: a failure in one is reported but does not abort the
other, and the exit code is non-zero if any failed.

Run from the repo root:
    uv run python scripts/gen_contracts.py

(Placeholder generator — see shared/contracts/README.md. The real
@inclusaai/grpc-contracts / @inclusaai/kafka-contracts packages will ship these
pre-generated; keep the ``inclusaai_contracts`` import path stable when they land.)
"""

from __future__ import annotations

import json
import sys
import typing
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = REPO_ROOT / "shared" / "contracts"
PROTO_ROOT = CONTRACTS / "proto"
PKG = CONTRACTS / "src" / "inclusaai_contracts"
GRPC_OUT = PKG / "grpc_stubs"
SCHEMA_OUT = PKG / "schemas"
TS_OUT = PKG / "typescript"


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

    for pb2 in GRPC_OUT.rglob("*_pb2.py"):
        init = pb2.parent / "__init__.py"
        if not init.exists():
            init.write_text('"""Generated gRPC package (git-ignored)."""\n', encoding="utf-8")

    print(
        f"[grpc] generated stubs for {len(protos)} proto file(s) -> "
        f"{GRPC_OUT.relative_to(REPO_ROOT)}"
    )
    print("       NOTE (placeholder): cross-file proto imports assume the proto package")
    print("       root is importable; real bindings ship in @inclusaai/grpc-contracts.")
    return 0


def gen_schemas() -> int:
    sys.path.insert(0, str(PKG.parent))
    try:
        from inclusaai_contracts.schema_registry import EVENT_MODELS
    except Exception as exc:  # noqa: BLE001
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


# ---------------------------------------------------------------------------
# TypeScript generation
# ---------------------------------------------------------------------------

_PY_TO_TS: dict[str, str] = {
    "str": "string",
    "int": "number",
    "float": "number",
    "bool": "boolean",
    "None": "null",
    "any": "unknown",
}


def _is_union(annotation: object) -> bool:
    """Check if annotation is a Union type (typing.Union or types.UnionType)."""
    import types
    origin = getattr(annotation, "__origin__", None)
    if origin is typing.Union:
        return True
    # Python 3.10+ PEP 604: str | None creates types.UnionType
    if isinstance(annotation, types.UnionType):
        return True
    return False


def _union_args(annotation: object) -> tuple[object, ...]:
    """Get the args of a Union type."""
    import types
    if isinstance(annotation, types.UnionType):
        return annotation.__args__
    return annotation.__args__


def _is_optional(annotation: object) -> bool:
    """Check if a type annotation is Optional (Union[X, None])."""
    if _is_union(annotation):
        return type(None) in _union_args(annotation)
    return False


def _unwrap_optional(annotation: object) -> object:
    """Strip None from Optional[X] → X."""
    if _is_optional(annotation):
        args = [a for a in _union_args(annotation) if a is not type(None)]
        return args[0] if len(args) == 1 else typing.Union[tuple(args)]
    return annotation


def _is_enum(annotation: object) -> bool:
    """Check if a type is a StrEnum or Enum."""
    if not isinstance(annotation, type):
        return False
    try:
        import enum
        return issubclass(annotation, enum.Enum)
    except TypeError:
        return False


def _py_type_to_ts(annotation: object, enum_names: set[str]) -> str:
    """Convert a Python type annotation to a TypeScript type string.

    ``enum_names`` is the set of known enum class names for rendering.
    """
    origin = getattr(annotation, "__origin__", None)

    # --- None ---
    if annotation is type(None) or annotation is None:
        return "null"

    # --- Union types (including Optional, PEP 604 X | Y) ---
    if _is_union(annotation):
        args = _union_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        if not non_none:
            return "null"
        inner = " | ".join(_py_type_to_ts(a, enum_names) for a in non_none)
        if len(non_none) < len(args):
            inner += " | null"
        return inner

    # --- list[X] → X[] ---
    if origin is list:
        inner = _py_type_to_ts(annotation.__args__[0], enum_names)
        return f"{inner}[]"

    # --- dict[K, V] → Record<K, V> ---
    if origin is dict:
        key_ts = _py_type_to_ts(annotation.__args__[0], enum_names)
        val_ts = _py_type_to_ts(annotation.__args__[1], enum_names)
        return f"Record<{key_ts}, {val_ts}>"

    # --- Enum name (e.g. AccessibilityChannel) ---
    name = getattr(annotation, "__name__", None)
    if name and name in enum_names:
        return name

    # --- Primitives ---
    ts = _PY_TO_TS.get(getattr(annotation, "__name__", str(annotation)))
    if ts:
        return ts

    # --- Nested model name (e.g. PoseKeypoint) ---
    if name:
        return name

    return "unknown"


def _is_required(fi: object) -> bool:
    """Check if a Pydantic v2 field is required (no default value)."""
    from pydantic_core import PydanticUndefined
    return fi.default is PydanticUndefined and fi.default_factory is None


def _field_ts(field_name: str, fi: object, enum_names: set[str]) -> str:
    """Generate a TypeScript field line."""
    annotation = fi.annotation
    required = _is_required(fi)

    is_opt = _is_optional(annotation)
    if is_opt:
        inner = _unwrap_optional(annotation)
        ts_type = _py_type_to_ts(inner, enum_names) + " | null"
    else:
        ts_type = _py_type_to_ts(annotation, enum_names)

    suffix = "" if required else "?"

    # JSDoc description
    doc = ""
    desc = getattr(fi, "description", None)
    if not desc and hasattr(fi, "metadata"):
        for m in fi.metadata:
            if hasattr(m, "description"):
                desc = m.description
                break
    if desc:
        safe = desc.replace("*/", "* /")
        doc = f"  /** {safe} */\n"

    return f"{doc}  {field_name}{suffix}: {ts_type};"


def _collect_enums(events_module: object) -> dict[str, object]:
    """Find all enum classes in the events module."""
    import enum

    enums: dict[str, object] = {}
    for attr_name in dir(events_module):
        attr = getattr(events_module, attr_name, None)
        if (
            isinstance(attr, type)
            and issubclass(attr, enum.Enum)
            and attr is not enum.Enum
            and attr is not enum.StrEnum
            and hasattr(attr, "__members__")
            and len(attr.__members__) > 0
        ):
            enums[attr_name] = attr
    return enums


def _collect_nested_models(
    annotation: object,
    collected: set[str],
    all_models: dict[str, object],
    events_module: object,
    enum_names: set[str],
) -> None:
    """Recursively find nested Pydantic BaseModel classes in type annotations."""
    if annotation is None or annotation is type(None):
        return

    origin = getattr(annotation, "__origin__", None)

    if origin is typing.Union:
        for arg in annotation.__args__:
            _collect_nested_models(arg, collected, all_models, events_module, enum_names)
        return

    if origin in (list, dict):
        for arg in annotation.__args__:
            _collect_nested_models(arg, collected, all_models, events_module, enum_names)
        return

    name = getattr(annotation, "__name__", None)
    if name and name not in collected and name not in enum_names:
        if hasattr(annotation, "model_fields"):
            collected.add(name)
            all_models[name] = annotation
            for fi in annotation.model_fields.values():
                _collect_nested_models(fi.annotation, collected, all_models, events_module, enum_names)


def gen_typescript() -> int:
    """Generate TypeScript interfaces from Pydantic models."""
    sys.path.insert(0, str(PKG.parent))
    try:
        from inclusaai_contracts import events
        from inclusaai_contracts.schema_registry import EVENT_MODELS
    except Exception as exc:  # noqa: BLE001
        print(f"[typescript] cannot import schema registry: {exc}", file=sys.stderr)
        return 1

    enums = _collect_enums(events)
    enum_names = set(enums.keys())

    # Collect nested models (e.g. PoseKeypoint used inside AvatarPoseFrame)
    nested: dict[str, object] = {}
    nested_names: set[str] = set()
    for model in EVENT_MODELS.values():
        for fi in model.model_fields.values():
            _collect_nested_models(fi.annotation, nested_names, nested, events, enum_names)

    # Event model names (for deduplication)
    event_model_names = {m.__name__ for m in EVENT_MODELS.values()}

    TS_OUT.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "// Auto-generated by scripts/gen_contracts.py — DO NOT EDIT.",
        "// Source of truth: shared/contracts/src/inclusaai_contracts/events.py",
        "//",
        f"// Generated from {len(event_model_names)} event model(s), "
        f"{len(nested)} nested type(s), {len(enums)} enum(s).",
        "",
    ]

    # --- Enums ---
    if enums:
        lines.append("// ─── Enums ───────────────────────────────────────────────────")
        lines.append("")
        for name, cls in sorted(enums.items()):
            lines.append(f"export enum {name} {{")
            for member in cls.__members__.values():
                lines.append(f'  {member.name} = "{member.value}",')
            lines.append("}")
            lines.append("")

    # --- Nested models (not in EVENT_MODELS) ---
    nested_only = {k: v for k, v in nested.items() if k not in event_model_names}
    if nested_only:
        lines.append("// ─── Shared Types ────────────────────────────────────────────")
        lines.append("")
        for name, model in sorted(nested_only.items()):
            _emit_interface(lines, name, model, enum_names)
            lines.append("")

    # --- Event models ---
    lines.append("// ─── Event Payloads ──────────────────────────────────────────")
    lines.append("")
    for event_key in sorted(EVENT_MODELS.keys()):
        model = EVENT_MODELS[event_key]
        model_name = model.__name__
        if model_name in enum_names:
            continue
        lines.append(f"// Topic: {event_key}")
        _emit_interface(lines, model_name, model, enum_names)
        lines.append("")

    # --- Event key → type map ---
    lines.append("// ─── Event Key → Type Map ────────────────────────────────────")
    lines.append("")
    lines.append("export interface AiServiceEvents {")
    for event_key in sorted(EVENT_MODELS.keys()):
        model_name = EVENT_MODELS[event_key].__name__
        if model_name in enum_names:
            continue
        lines.append(f'  "{event_key}": {model_name};')
    lines.append("}")
    lines.append("")

    # --- Topic constants ---
    lines.append("// ─── Topic Names ─────────────────────────────────────────────")
    lines.append("")
    lines.append("export const AI_TOPICS = {")
    for event_key in sorted(EVENT_MODELS.keys()):
        model_name = EVENT_MODELS[event_key].__name__
        if model_name in enum_names:
            continue
        lines.append(f'  "{event_key}": "{event_key}",')
    lines.append("} as const;")
    lines.append("")

    content = "\n".join(lines)
    dest = TS_OUT / "events.ts"
    dest.write_text(content, encoding="utf-8")

    event_count = sum(1 for m in EVENT_MODELS.values() if m.__name__ not in enum_names)
    total = len(enum_names) + len(nested_only) + event_count
    print(f"[typescript] wrote {total} types -> {dest.relative_to(REPO_ROOT)}")
    return 0


def _emit_interface(lines: list[str], name: str, model: object, enum_names: set[str]) -> None:
    """Emit a TypeScript interface for a Pydantic model."""
    docstring = getattr(model, "__doc__", None)
    if docstring:
        doc_lines = [l.strip() for l in docstring.strip().split("\n") if l.strip()]
        if len(doc_lines) > 1:
            lines.append("/**")
            for dl in doc_lines[:4]:
                lines.append(f" * {dl}")
            lines.append(" */")

    lines.append(f"export interface {name} {{")

    if hasattr(model, "model_fields"):
        for field_name, fi in model.model_fields.items():
            lines.append(_field_ts(field_name, fi, enum_names))

    lines.append("}")


def main() -> int:
    rc_grpc = gen_grpc()
    rc_schema = gen_schemas()
    rc_ts = gen_typescript()
    return rc_grpc or rc_schema or rc_ts


if __name__ == "__main__":
    raise SystemExit(main())
