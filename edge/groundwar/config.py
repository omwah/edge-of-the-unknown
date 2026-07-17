"""Typed loader for `config/groundwar_default.yaml` — all balance lives there, not here."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "groundwar_default.yaml"


@dataclass(frozen=True, slots=True)
class WeaponStats:
    range: int
    damage: int
    accuracy: float
    structure_mult: float = 1.0


@dataclass(frozen=True, slots=True)
class SuitClass:
    key: str
    label: str
    glyph: str
    cost: int
    hp: int
    armor: int
    move: int
    jump_range: int
    jump_charges: int
    sight: int
    signature: float
    weapon: WeaponStats
    missiles: int
    missile: WeaponStats
    jam_radius: int = 0
    command_radius: int = 0
    command_acc_bonus: float = 0.0
    broadcast_range: int = 0


@dataclass(frozen=True, slots=True)
class GarrisonClass:
    key: str
    hp: int
    armor: int
    move: int
    sight: int
    weapon: WeaponStats


@dataclass(frozen=True, slots=True)
class TerrainClass:
    move_cost: int  # 0 == impassable on foot (jump jets clear it)
    cover: float
    blocks_los: bool


@dataclass(frozen=True, slots=True)
class PressureConfig:
    retrieval_turns: int
    casualty_ceiling: float
    escalation_every: int
    escalation_acc_bonus: float
    escalation_acc_cap: float


@dataclass(frozen=True, slots=True)
class ResolveConfig:
    start: int
    surrender_threshold: int
    turret_destroyed: int
    aa_destroyed: int
    sensor_destroyed: int
    wall_breached: int
    garrison_killed: int
    military_building_destroyed: int
    citadel_gun_destroyed: int
    city_cowed: int
    broadcast: int
    civilian_building_destroyed: int
    trooper_killed: int


@dataclass(frozen=True, slots=True)
class EmplacementStats:
    hp: int
    range: int = 0
    damage: int = 0
    accuracy: float = 0.0
    radius: int = 0


@dataclass(frozen=True, slots=True)
class DefensesConfig:
    wall: EmplacementStats
    gate: EmplacementStats
    turret: EmplacementStats
    aa: EmplacementStats
    sensor: EmplacementStats
    citadel_gun: EmplacementStats
    building_military_hp: int
    building_civilian_hp: int


@dataclass(frozen=True, slots=True)
class GarrisonConfig:
    infantry: GarrisonClass
    armor: GarrisonClass
    sortie_base: int
    sortie_growth: int
    armor_from_wave: int
    undetected_first_strike: float


@dataclass(frozen=True, slots=True)
class Difficulty:
    key: str
    label: str
    cities: int
    citadel_level: int
    surrender_threshold: int
    garrison_mult: float


@dataclass(frozen=True, slots=True)
class GroundwarConfig:
    width: int
    height: int
    pressure: PressureConfig
    resolve: ResolveConfig
    budget: int
    max_troopers: int
    actions_per_turn: int
    suits: dict[str, SuitClass]
    defenses: DefensesConfig
    garrison: GarrisonConfig
    terrain: dict[str, TerrainClass]
    difficulties: dict[str, Difficulty] = field(default_factory=dict)


def _weapon(data: dict[str, float]) -> WeaponStats:
    return WeaponStats(
        range=int(data["range"]), damage=int(data["damage"]),
        accuracy=float(data["accuracy"]),
        structure_mult=float(data.get("structure_mult", 1.0)),
    )


def _suit(key: str, d: dict[str, object]) -> SuitClass:
    return SuitClass(
        key=key, label=str(d["label"]), glyph=str(d["glyph"]), cost=int(d["cost"]),  # type: ignore[arg-type]
        hp=int(d["hp"]), armor=int(d["armor"]), move=int(d["move"]),  # type: ignore[arg-type]
        jump_range=int(d["jump_range"]), jump_charges=int(d["jump_charges"]),  # type: ignore[arg-type]
        sight=int(d["sight"]), signature=float(d["signature"]),  # type: ignore[arg-type]
        weapon=_weapon(d["weapon"]),  # type: ignore[arg-type]
        missiles=int(d["missiles"]), missile=_weapon(d["missile"]),  # type: ignore[arg-type]
        jam_radius=int(d.get("jam_radius", 0)),  # type: ignore[arg-type]
        command_radius=int(d.get("command_radius", 0)),  # type: ignore[arg-type]
        command_acc_bonus=float(d.get("command_acc_bonus", 0.0)),  # type: ignore[arg-type]
        broadcast_range=int(d.get("broadcast_range", 0)),  # type: ignore[arg-type]
    )


def _emplacement(d: dict[str, float]) -> EmplacementStats:
    return EmplacementStats(
        hp=int(d["hp"]), range=int(d.get("range", 0)), damage=int(d.get("damage", 0)),
        accuracy=float(d.get("accuracy", 0.0)), radius=int(d.get("radius", 0)),
    )


def load_config(path: Path | None = None) -> GroundwarConfig:
    with open(path or DEFAULT_CONFIG_PATH, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    bf = data["battlefield"]
    pr = data["pressure"]
    rs = data["resolve"]
    df = data["defenses"]
    ga = data["garrison"]
    return GroundwarConfig(
        width=int(bf["width"]), height=int(bf["height"]),
        pressure=PressureConfig(
            retrieval_turns=int(pr["retrieval_turns"]),
            casualty_ceiling=float(pr["casualty_ceiling"]),
            escalation_every=int(pr["escalation_every"]),
            escalation_acc_bonus=float(pr["escalation_acc_bonus"]),
            escalation_acc_cap=float(pr["escalation_acc_cap"]),
        ),
        resolve=ResolveConfig(**{k: int(v) for k, v in rs.items()}),
        budget=int(data["platoon"]["budget"]),
        max_troopers=int(data["platoon"]["max_troopers"]),
        actions_per_turn=int(data["platoon"].get("actions_per_turn", 2)),
        suits={key: _suit(key, d) for key, d in data["suits"].items()},
        defenses=DefensesConfig(
            wall=_emplacement(df["wall"]), gate=_emplacement(df["gate"]),
            turret=_emplacement(df["turret"]), aa=_emplacement(df["aa"]),
            sensor=_emplacement(df["sensor"]), citadel_gun=_emplacement(df["citadel_gun"]),
            building_military_hp=int(df["building_military_hp"]),
            building_civilian_hp=int(df["building_civilian_hp"]),
        ),
        garrison=GarrisonConfig(
            infantry=GarrisonClass(key="infantry", weapon=_weapon(ga["infantry"]["weapon"]),
                                   **{k: int(v) for k, v in ga["infantry"].items() if k != "weapon"}),
            armor=GarrisonClass(key="armor", weapon=_weapon(ga["armor"]["weapon"]),
                                **{k: int(v) for k, v in ga["armor"].items() if k != "weapon"}),
            sortie_base=int(ga["sortie_base"]), sortie_growth=int(ga["sortie_growth"]),
            armor_from_wave=int(ga["armor_from_wave"]),
            undetected_first_strike=float(ga["undetected_first_strike"]),
        ),
        terrain={
            key: TerrainClass(move_cost=int(d["move_cost"]), cover=float(d["cover"]),
                              blocks_los=bool(d["blocks_los"]))
            for key, d in data["terrain"].items()
        },
        difficulties={
            key: Difficulty(key=key, label=str(d["label"]), cities=int(d["cities"]),
                            citadel_level=int(d["citadel_level"]),
                            surrender_threshold=int(d["surrender_threshold"]),
                            garrison_mult=float(d["garrison_mult"]))
            for key, d in data["difficulties"].items()
        },
    )
