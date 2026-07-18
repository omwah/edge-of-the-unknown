"""Typed loader for `config/spacebattle_default.yaml` — all balance lives there, not here."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "spacebattle_default.yaml"

Arc = Literal["spinal", "ahead", "all_round"]
Quadrant = Literal["fore", "aft", "port", "starboard"]
QUADRANTS: tuple[Quadrant, ...] = ("fore", "aft", "port", "starboard")


@dataclass(frozen=True, slots=True)
class GunStats:
    damage: int
    range: int
    arc: Arc
    accuracy: float
    falloff: float  # accuracy lost per cell of range


@dataclass(frozen=True, slots=True)
class MissileStats:
    damage: int
    speed: int      # cells per owner turn
    endurance: int  # turns of flight before fizzling
    accuracy: float


@dataclass(frozen=True, slots=True)
class ShipClass:
    key: str
    label: str
    hull_art: str        # sprite-set key, a ship_classes id from the main game config
    station: bool        # immobile emplacement (starbase): no thrust/rotate/drift
    size: int            # footprint edge in placement cells (ships 1, starbases 3)
    hull_max: int
    thrust: int
    max_speed: int
    sensor_range: int
    main_gun: GunStats
    salvos: int
    salvo_size: int
    missile: MissileStats
    screens: dict[Quadrant, int]
    components: dict[Quadrant, tuple[str, ...]]
    fighter_wings: int
    mine_stock: int
    recon_drones: int


@dataclass(frozen=True, slots=True)
class FighterConfig:
    wing_size: int
    speed: int
    endurance: int
    gun: GunStats
    intercept_per_craft: float
    dogfight_bonus: float


@dataclass(frozen=True, slots=True)
class CombatConfig:
    knockout_chance: float
    raking_bonus: float
    velocity_evasion: float
    mine_damage: int
    deploy_reach: int
    salvo_action_cost: int
    point_defense: float
    point_defense_open: float
    screen_regen: int
    kilt_bonus: float
    damage_control_cost: int


@dataclass(frozen=True, slots=True)
class RocksConfig:
    impact_base: int
    impact_per_speed: int


@dataclass(frozen=True, slots=True)
class LanceConfig:
    range: int
    recharge_turns: int
    salvo_penalty: float


@dataclass(frozen=True, slots=True)
class DroneConfig:
    range: int
    reveal_radius: int


@dataclass(frozen=True, slots=True)
class Scenario:
    key: str
    label: str
    blurb: str
    deploy: Literal["full", "warp_in"]
    player: tuple[str, ...]
    enemy: tuple[str, ...]
    enemy_mines: int
    player_zone_frac: float
    warp_zone_cells: int
    rock_clusters: int
    rock_cluster_size: int
    station: str | None       # ship-class key of the defended starbase (siege scenarios)
    debris_clusters: int      # drifting-wreckage clumps (graveyard scenarios)
    debris_cluster_size: int


@dataclass(frozen=True, slots=True)
class SpacebattleConfig:
    width: int
    height: int
    cell_w: int
    cell_h: int
    ship_actions: int
    fighter_actions: int
    combat: CombatConfig
    rocks: RocksConfig
    debris: RocksConfig
    lance: LanceConfig
    drone: DroneConfig
    fighters: FighterConfig
    ships: dict[str, ShipClass]
    scenarios: dict[str, Scenario]


def _gun(d: dict[str, object]) -> GunStats:
    return GunStats(damage=int(d["damage"]), range=int(d["range"]),  # type: ignore[arg-type]
                    arc=str(d.get("arc", "all_round")),  # type: ignore[arg-type]
                    accuracy=float(d["accuracy"]), falloff=float(d.get("falloff", 0.0)))  # type: ignore[arg-type]


def _ship(key: str, d: dict[str, object]) -> ShipClass:
    ms = d["missile"]
    return ShipClass(
        key=key, label=str(d["label"]), hull_art=str(d["hull_art"]),
        station=bool(d.get("station", False)), size=int(d.get("size", 1)),  # type: ignore[arg-type]
        hull_max=int(d["hull_max"]), thrust=int(d["thrust"]),  # type: ignore[arg-type]
        max_speed=int(d["max_speed"]), sensor_range=int(d["sensor_range"]),  # type: ignore[arg-type]
        main_gun=_gun(d["main_gun"]),  # type: ignore[arg-type]
        salvos=int(d["salvos"]), salvo_size=int(d["salvo_size"]),  # type: ignore[arg-type]
        missile=MissileStats(damage=int(ms["damage"]), speed=int(ms["speed"]),  # type: ignore[index]
                             endurance=int(ms["endurance"]), accuracy=float(ms["accuracy"])),  # type: ignore[index]
        screens={q: int(v) for q, v in d["screens"].items()},  # type: ignore[union-attr]
        components={q: tuple(v) for q, v in d["components"].items()},  # type: ignore[union-attr]
        fighter_wings=int(d.get("fighter_wings", 0)),  # type: ignore[arg-type]
        mine_stock=int(d.get("mine_stock", 0)),  # type: ignore[arg-type]
        recon_drones=int(d.get("recon_drones", 0)),  # type: ignore[arg-type]
    )


def load_config(path: Path | None = None) -> SpacebattleConfig:
    with open(path or DEFAULT_CONFIG_PATH, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    bd, tn, cb, fi = data["board"], data["turn"], data["combat"], data["fighters"]
    return SpacebattleConfig(
        width=int(bd["width"]), height=int(bd["height"]),
        cell_w=int(bd["cell_w"]), cell_h=int(bd["cell_h"]),
        ship_actions=int(tn["ship_actions"]),
        fighter_actions=int(tn["fighter_actions"]),
        combat=CombatConfig(
            knockout_chance=float(cb["knockout_chance"]),
            raking_bonus=float(cb["raking_bonus"]),
            velocity_evasion=float(cb["velocity_evasion"]),
            mine_damage=int(cb["mine_damage"]),
            deploy_reach=int(cb["deploy_reach"]),
            salvo_action_cost=int(cb.get("salvo_action_cost", 2)),
            point_defense=float(cb.get("point_defense", 0.0)),
            point_defense_open=float(cb.get("point_defense_open", 0.0)),
            screen_regen=int(cb.get("screen_regen", 0)),
            kilt_bonus=float(cb.get("kilt_bonus", 0.0)),
            damage_control_cost=int(cb.get("damage_control_cost", 2)),
        ),
        rocks=RocksConfig(
            impact_base=int(data["rocks"]["impact_base"]),
            impact_per_speed=int(data["rocks"]["impact_per_speed"]),
        ),
        debris=RocksConfig(
            impact_base=int(data["debris"]["impact_base"]),
            impact_per_speed=int(data["debris"]["impact_per_speed"]),
        ),
        lance=LanceConfig(
            range=int(data["lance"]["range"]),
            recharge_turns=int(data["lance"]["recharge_turns"]),
            salvo_penalty=float(data["lance"]["salvo_penalty"]),
        ),
        drone=DroneConfig(
            range=int(data["drone"]["range"]),
            reveal_radius=int(data["drone"]["reveal_radius"]),
        ),
        fighters=FighterConfig(
            wing_size=int(fi["wing_size"]), speed=int(fi["speed"]),
            endurance=int(fi["endurance"]), gun=_gun(fi["gun"]),
            intercept_per_craft=float(fi["intercept_per_craft"]),
            dogfight_bonus=float(fi["dogfight_bonus"]),
        ),
        ships={key: _ship(key, d) for key, d in data["ships"].items()},
        scenarios={
            key: Scenario(
                key=key, label=str(d["label"]), blurb=str(d["blurb"]),
                deploy=str(d["deploy"]),  # type: ignore[arg-type]
                player=tuple(d["player"]), enemy=tuple(d["enemy"]),
                enemy_mines=int(d.get("enemy_mines", 0)),
                player_zone_frac=float(d.get("player_zone_frac", 0.5)),
                warp_zone_cells=int(d.get("warp_zone_cells", 6)),
                rock_clusters=int(d.get("rock_clusters", 0)),
                rock_cluster_size=int(d.get("rock_cluster_size", 0)),
                station=str(d["station"]) if "station" in d else None,
                debris_clusters=int(d.get("debris_clusters", 0)),
                debris_cluster_size=int(d.get("debris_cluster_size", 0)),
            )
            for key, d in data["scenarios"].items()
        },
    )
