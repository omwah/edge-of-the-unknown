"""Versioned, safe checkpoint encoding for authoritative universe state.

Checkpoints are an acceleration cache, not the save's source of truth.  The
command and maintenance logs remain canonical; this codec merely lets loading
start near the end of those logs.  The tagged JSON format deliberately avoids
``pickle`` so a damaged or edited save cannot execute code while loading.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import zlib
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any

from edge.core.models import UniverseState

CHECKPOINT_CODEC_VERSION = 1

# These are the evolving fields covered by state_hash.  Runtime-only indexes
# (adjacency, spatial ids, knowledge caches, etc.) are regenerated from the
# seed and current config before this authoritative overlay is applied.
AUTHORITATIVE_STATE_FIELDS = (
    "game",
    "regions",
    "sectors",
    "ports",
    "planets",
    "starbases",
    "discoveries",
    "ships",
    "players",
    "alliances",
    "corporations",
    "species",
    "grudges",
    "sector_forces",
    "port_orders",
    "notices",
)

_ALLOWED_MODULE_PREFIX = "edge.core."


class CheckpointCodecError(ValueError):
    """A checkpoint payload is malformed, unsafe, or unsupported."""


def _type_name(value: object) -> str:
    cls = type(value)
    return f"{cls.__module__}:{cls.__qualname__}"


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return {"$enum": _type_name(value), "value": _encode(value.value)}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "$dataclass": _type_name(value),
            "fields": {item.name: _encode(getattr(value, item.name)) for item in fields(value)},
        }
    if isinstance(value, dict):
        return {"$dict": [[_encode(key), _encode(item)] for key, item in value.items()]}
    if isinstance(value, tuple):
        return {"$tuple": [_encode(item) for item in value]}
    if isinstance(value, frozenset):
        return {"$frozenset": [_encode(item) for item in value]}
    if isinstance(value, set):
        return {"$set": [_encode(item) for item in value]}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise CheckpointCodecError(f"unsupported checkpoint value: {type(value)!r}")


def _resolve_type(name: object) -> type[Any]:
    if not isinstance(name, str) or ":" not in name:
        raise CheckpointCodecError("invalid checkpoint type tag")
    module_name, qualname = name.split(":", 1)
    if not module_name.startswith(_ALLOWED_MODULE_PREFIX):
        raise CheckpointCodecError(f"checkpoint type outside edge.core: {module_name}")
    if "<locals>" in qualname:
        raise CheckpointCodecError("local classes are not valid checkpoint types")
    try:
        value: Any = importlib.import_module(module_name)
        for part in qualname.split("."):
            value = getattr(value, part)
    except (ImportError, AttributeError) as exc:
        raise CheckpointCodecError(f"unknown checkpoint type: {name}") from exc
    if not isinstance(value, type):
        raise CheckpointCodecError(f"checkpoint tag is not a type: {name}")
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        raise CheckpointCodecError("invalid checkpoint scalar")

    if set(value) == {"$dict"}:
        pairs = value["$dict"]
        if not isinstance(pairs, list):
            raise CheckpointCodecError("invalid checkpoint mapping")
        result: dict[Any, Any] = {}
        for pair in pairs:
            if not isinstance(pair, list) or len(pair) != 2:
                raise CheckpointCodecError("invalid checkpoint mapping entry")
            result[_decode(pair[0])] = _decode(pair[1])
        return result
    if set(value) == {"$tuple"}:
        items = value["$tuple"]
        if not isinstance(items, list):
            raise CheckpointCodecError("invalid checkpoint tuple")
        return tuple(_decode(item) for item in items)
    if set(value) == {"$frozenset"}:
        items = value["$frozenset"]
        if not isinstance(items, list):
            raise CheckpointCodecError("invalid checkpoint frozenset")
        return frozenset(_decode(item) for item in items)
    if set(value) == {"$set"}:
        items = value["$set"]
        if not isinstance(items, list):
            raise CheckpointCodecError("invalid checkpoint set")
        return {_decode(item) for item in items}
    if set(value) == {"$enum", "value"}:
        cls = _resolve_type(value["$enum"])
        if not issubclass(cls, Enum):
            raise CheckpointCodecError("checkpoint enum tag names a non-enum")
        return cls(_decode(value["value"]))
    if set(value) == {"$dataclass", "fields"}:
        cls = _resolve_type(value["$dataclass"])
        if not is_dataclass(cls):
            raise CheckpointCodecError("checkpoint dataclass tag names a non-dataclass")
        encoded_fields = value["fields"]
        if not isinstance(encoded_fields, dict):
            raise CheckpointCodecError("invalid checkpoint dataclass fields")
        expected = {item.name for item in fields(cls)}
        if set(encoded_fields) != expected:
            raise CheckpointCodecError(f"checkpoint fields do not match {cls.__name__}")
        return cls(**{name: _decode(item) for name, item in encoded_fields.items()})
    raise CheckpointCodecError("unknown checkpoint object tag")


def encode_state(state: UniverseState) -> tuple[bytes, str]:
    """Return a compressed checkpoint payload and its corruption checksum."""
    document = {
        "codec_version": CHECKPOINT_CODEC_VERSION,
        "state": {name: _encode(getattr(state, name)) for name in AUTHORITATIVE_STATE_FIELDS},
        "rng_state": _encode(state.rng.getstate()),
    }
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload = zlib.compress(raw, level=6)
    return payload, hashlib.sha256(payload).hexdigest()


def restore_state(base: UniverseState, payload: bytes) -> UniverseState:
    """Overlay checkpointed authoritative state onto a freshly generated base."""
    try:
        raw = zlib.decompress(payload)
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckpointCodecError("checkpoint payload is not valid compressed JSON") from exc
    if not isinstance(document, dict):
        raise CheckpointCodecError("checkpoint document must be an object")
    if document.get("codec_version") != CHECKPOINT_CODEC_VERSION:
        raise CheckpointCodecError("unsupported checkpoint codec version")
    encoded_state = document.get("state")
    if not isinstance(encoded_state, dict) or set(encoded_state) != set(AUTHORITATIVE_STATE_FIELDS):
        raise CheckpointCodecError("checkpoint authoritative fields do not match")
    for name in AUTHORITATIVE_STATE_FIELDS:
        setattr(base, name, _decode(encoded_state[name]))
    rng_state = _decode(document.get("rng_state"))
    if not isinstance(rng_state, tuple):
        raise CheckpointCodecError("checkpoint RNG state must be a tuple")
    try:
        base.rng.setstate(rng_state)
    except (TypeError, ValueError) as exc:
        raise CheckpointCodecError("invalid checkpoint RNG state") from exc
    return base


def payload_checksum(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
