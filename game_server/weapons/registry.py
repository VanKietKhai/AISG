"""Load and validate versioned weapon configuration files."""

import hashlib
import json
from pathlib import Path
from typing import Optional, Union

from .models import WeaponConfigSnapshot, WeaponDefinition


PathLike = Union[str, Path]


def default_weapon_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "weapon_config.json"


def load_weapon_config(path: Optional[PathLike] = None) -> WeaponConfigSnapshot:
    config_path = Path(path) if path else default_weapon_config_path()
    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    defaults = payload.get("defaults", {})
    recovery = float(defaults.get("bloom_recovery_degrees_per_second", 6.0))
    definitions = {}
    for raw_key, raw in payload.get("weapons", {}).items():
        key = raw_key.upper()
        definitions[key] = WeaponDefinition(
            key=key,
            damage=raw["damage"],
            fire_rate=raw["fire_rate"],
            range=raw["range"],
            mobility=raw["mobility"],
            bloom_recoil=raw["bloom_recoil"],
            magazine=raw["magazine"],
            reload_seconds=float(raw["reload_seconds"]),
            bloom_recovery_degrees_per_second=recovery,
        )

    return WeaponConfigSnapshot(
        version=str(payload["version"]),
        schema_version=int(payload["schema_version"]),
        weapons=definitions,
    )


def derive_match_seed(room_id: str, config_version: str) -> int:
    material = f"{room_id}:{config_version}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")

