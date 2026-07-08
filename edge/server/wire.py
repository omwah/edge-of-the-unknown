"""`edge/server/wire.py` — the versioned wire codec for the Phase-4 transport (WP62, H16).

DESIGN §3/§14. The network layer (WP63) speaks JSON-RPC; this module is the *payload* codec
underneath it — the one place a command, event, or DTO becomes JSON and back. Design pins:

- **Commands and events reuse `store/codec.py` verbatim.** The wire and the durable log speak
  the same dialect; a divergence would be a replay-bug factory. `encode_command`/`decode_command`
  and `encode_event`/`decode_event` here are thin envelope wrappers around the store codec — the
  single source of truth.
- **DTOs use a self-describing dataclass value codec.** The plan's ideal is a hand-written
  `encode_dto`/`decode_dto` per class; with ~50 nested frozen dataclasses that is impractical to
  keep correct by hand, so instead this uses a compact recursive value codec driven by
  `dataclasses.fields()`, with every nested value **self-tagged** (`__dto__` for dataclasses,
  `__tuple__` / `__frozenset__` for the non-JSON containers) so decoding needs no type
  reflection. The "breaks loudly when a DTO gains a field" guarantee H16 wants is preserved by
  `wire_fingerprint()` + the golden fingerprint test: any field add/remove/rename or new DTO
  changes the fingerprint, failing the build. No pickle, no Pydantic (framing correction 1).
- **Envelope:** `{"v": WIRE_VERSION, "kind": ..., "payload": ...}`. `WIRE_VERSION` bumps on any
  breaking change; `wire_fingerprint()` (version + sorted DTO schema hash) lets client and
  server refuse mismatched builds at handshake — the `dialogue_fingerprint` pattern reused.

The DTOs contain only primitives, nested DTO dataclasses, lists/tuples/frozensets of those, and
optionals — no core enums (the projection stringifies enums at the `session` boundary), so the
value codec never has to encode an `Enum`; one sneaking in raises loudly here.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any

from edge.core import dto
from edge.core.events import Event
from edge.core.rules import Command
from edge.store import codec

WIRE_VERSION = 1
"""Bumps on any breaking change to the envelope or a codec entry (client/server handshake)."""


# --- the DTO registry ---------------------------------------------------------
# Every frozen dataclass declared in `edge.core.dto`, keyed by class name. Built by module
# scan (self-maintaining — a new DTO cannot be forgotten), and folded into `wire_fingerprint`
# so adding/renaming a DTO or one of its fields changes the fingerprint and fails the golden
# test — the "breaks loudly" guarantee H16 asks for.
DTO_REGISTRY: dict[str, type[Any]] = {
    name: obj
    for name, obj in vars(dto).items()
    if isinstance(obj, type) and dataclasses.is_dataclass(obj) and obj.__module__ == dto.__name__
}


class WireError(ValueError):
    """A malformed envelope, unknown kind, or version mismatch — a protocol fault, not gameplay."""


# --- self-describing value codec (DTOs) --------------------------------------


def _encode_value(value: Any) -> Any:
    """Encode one field value to a JSON-able form, self-tagging non-JSON containers/dataclasses."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        payload = {f.name: _encode_value(getattr(value, f.name)) for f in dataclasses.fields(value)}
        return {"__dto__": type(value).__name__, "fields": payload}
    if isinstance(value, tuple):
        return {"__tuple__": [_encode_value(v) for v in value]}
    if isinstance(value, frozenset):
        # Sorted for a canonical, deterministic encoding (fingerprint/golden stability).
        return {"__frozenset__": [_encode_value(v) for v in sorted(value)]}
    if isinstance(value, list):
        return [_encode_value(v) for v in value]
    raise WireError(f"cannot wire-encode value of type {type(value).__name__!r}")


def _decode_value(value: Any) -> Any:
    """Reconstruct a field value from `_encode_value`'s self-tagged form."""
    if isinstance(value, dict):
        if "__dto__" in value:
            return _decode_dto_body(value["__dto__"], value["fields"])
        if "__tuple__" in value:
            return tuple(_decode_value(v) for v in value["__tuple__"])
        if "__frozenset__" in value:
            return frozenset(_decode_value(v) for v in value["__frozenset__"])
        raise WireError(f"unknown tagged object in wire payload: {sorted(value)!r}")
    if isinstance(value, list):
        return [_decode_value(v) for v in value]
    return value


def _decode_dto_body(name: str, fields: dict[str, Any]) -> Any:
    cls = DTO_REGISTRY.get(name)
    if cls is None:
        raise WireError(f"unknown DTO type {name!r}")
    return cls(**{k: _decode_value(v) for k, v in fields.items()})


# --- envelopes ----------------------------------------------------------------


def encode_command(command: Command) -> dict[str, Any]:
    """Envelope a command for the wire, reusing the store codec's (type, payload)."""
    type_, payload = codec.encode_command(command)
    return {"v": WIRE_VERSION, "kind": "command", "type": type_, "payload": payload}


def decode_command(msg: dict[str, Any]) -> Command:
    _require(msg, "command")
    return codec.decode_command(msg["type"], msg["payload"])


def encode_event(event: Event) -> dict[str, Any]:
    """Envelope an event for the wire, reusing the store codec's (type, payload)."""
    type_, payload = codec.encode_event(event)
    return {"v": WIRE_VERSION, "kind": "event", "type": type_, "payload": payload}


def decode_event(msg: dict[str, Any]) -> Event:
    _require(msg, "event")
    return codec.decode_event(msg["type"], msg["payload"])


def encode_dto(obj: Any) -> dict[str, Any]:
    """Envelope a DTO dataclass instance for the wire (self-describing body)."""
    if not (dataclasses.is_dataclass(obj) and not isinstance(obj, type)):
        raise WireError(f"encode_dto expects a DTO instance, got {type(obj).__name__!r}")
    if type(obj).__name__ not in DTO_REGISTRY:
        raise WireError(f"{type(obj).__name__!r} is not a registered DTO")
    return {"v": WIRE_VERSION, "kind": "dto", "payload": _encode_value(obj)}


def decode_dto(msg: dict[str, Any]) -> Any:
    _require(msg, "dto")
    return _decode_value(msg["payload"])


def _require(msg: dict[str, Any], kind: str) -> None:
    """Guard envelope shape: right kind and a compatible version (a mismatch is a fault)."""
    if msg.get("kind") != kind:
        raise WireError(f"expected a {kind!r} envelope, got {msg.get('kind')!r}")
    if msg.get("v") != WIRE_VERSION:
        raise WireError(f"wire version mismatch: message v={msg.get('v')}, this build v={WIRE_VERSION}")


# --- handshake fingerprint ----------------------------------------------------


def wire_fingerprint() -> str:
    """A stable hash of the protocol surface — client and server refuse a mismatch at handshake.

    Covers the wire version and every registered DTO's name + ordered (field-name, field-type)
    schema, so any DTO change (new field, rename, retype, new/removed DTO) shifts the fingerprint
    and trips the golden fingerprint test — the loud break H16 wants without a hand table.
    """
    schema: list[Any] = [WIRE_VERSION]
    for name in sorted(DTO_REGISTRY):
        cls = DTO_REGISTRY[name]
        fields = [(f.name, str(f.type)) for f in dataclasses.fields(cls)]
        schema.append([name, fields])
    blob = json.dumps(schema, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]
