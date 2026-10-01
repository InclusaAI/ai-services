# Generated JSON Schemas

Files in this directory are **generated** from the pydantic models in
`inclusaai_contracts.events` by `scripts/gen_contracts.py`, and are git-ignored.

Run from the repo root:

```
uv run python scripts/gen_contracts.py
```

They are emitted here as `<event_key>.schema.json` for consumption by non-Python
services and for contract-validation tooling.
