"""Pure weapon-domain models shared by the game state and physics engine."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Dict, Iterable, Mapping


@dataclass(frozen=True)
class WeaponDefinition:
    """Immutable authoring values plus deterministic runtime conversions."""

    key: str
    damage: int
    fire_rate: int
    range: int
    mobility: int
    bloom_recoil: int
    magazine: int
    reload_seconds: float
    bloom_recovery_degrees_per_second: float = 6.0

    def __post_init__(self):
        normalized_key = self.key.upper()
        object.__setattr__(self, "key", normalized_key)

        for field_name in ("damage", "fire_rate", "range", "mobility", "bloom_recoil"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 10:
                raise ValueError(f"{normalized_key}.{field_name} must be an integer in [1, 10]")
        if not isinstance(self.magazine, int) or isinstance(self.magazine, bool) or not 1 <= self.magazine <= 100:
            raise ValueError(f"{normalized_key}.magazine must be an integer in [1, 100]")
        if self.reload_seconds <= 0:
            raise ValueError(f"{normalized_key}.reload_seconds must be > 0")
        if self.bloom_recovery_degrees_per_second <= 0:
            raise ValueError(
                f"{normalized_key}.bloom_recovery_degrees_per_second must be > 0"
            )

    @property
    def base_damage(self) -> float:
        return float(self.damage * 5)

    @property
    def shots_per_second(self) -> float:
        return 0.5 + 0.75 * self.fire_rate

    @property
    def shot_cooldown(self) -> float:
        return 1.0 / self.shots_per_second

    @property
    def max_range(self) -> float:
        return float(self.range * 60)

    @property
    def speed_multiplier(self) -> float:
        return 0.70 + 0.06 * self.mobility

    @property
    def max_speed(self) -> float:
        return 320.0 * self.speed_multiplier

    @property
    def acceleration(self) -> float:
        return 1200.0 * self.speed_multiplier

    @property
    def bloom_per_shot_degrees(self) -> float:
        return 0.20 + 0.18 * self.bloom_recoil

    def damage_at_distance(self, distance: float) -> float:
        """Quadratic falloff from full damage at the muzzle to zero at max range."""
        if distance < 0:
            raise ValueError("distance must be >= 0")
        if distance >= self.max_range:
            return 0.0
        ratio = distance / self.max_range
        return self.base_damage * (1.0 - ratio * ratio)


@dataclass
class WeaponRuntimeState:
    """Mutable per-bot state. All timers use simulation seconds."""

    weapon_type: str
    ammo: int
    cooldown_remaining: float = 0.0
    reload_remaining: float = 0.0
    current_bloom_degrees: float = 0.0

    @classmethod
    def fresh(cls, definition: WeaponDefinition) -> "WeaponRuntimeState":
        return cls(weapon_type=definition.key, ammo=definition.magazine)

    @property
    def is_reloading(self) -> bool:
        return self.reload_remaining > 0.0

    def can_fire(self) -> bool:
        return self.ammo > 0 and self.cooldown_remaining <= 0.0 and not self.is_reloading

    def start_reload(self, definition: WeaponDefinition) -> bool:
        if self.is_reloading or self.ammo >= definition.magazine:
            return False
        self.reload_remaining = definition.reload_seconds
        return True

    def update(self, dt: float, definition: WeaponDefinition):
        if dt < 0:
            raise ValueError("dt must be >= 0")

        self.cooldown_remaining = max(0.0, self.cooldown_remaining - dt)
        self.current_bloom_degrees = max(
            0.0,
            self.current_bloom_degrees
            - definition.bloom_recovery_degrees_per_second * dt,
        )

        if self.is_reloading:
            self.reload_remaining = max(0.0, self.reload_remaining - dt)
            if self.reload_remaining == 0.0:
                self.ammo = definition.magazine
        elif self.ammo == 0:
            self.start_reload(definition)

    def consume_shot(self, definition: WeaponDefinition):
        if not self.can_fire():
            raise RuntimeError("weapon cannot fire in its current state")
        self.ammo -= 1
        self.cooldown_remaining = definition.shot_cooldown
        self.current_bloom_degrees += definition.bloom_per_shot_degrees

    def reset(self, definition: WeaponDefinition):
        self.weapon_type = definition.key
        self.ammo = definition.magazine
        self.cooldown_remaining = 0.0
        self.reload_remaining = 0.0
        self.current_bloom_degrees = 0.0

    def reload_progress(self, definition: WeaponDefinition) -> float:
        if not self.is_reloading:
            return 0.0
        return max(0.0, min(1.0, 1.0 - self.reload_remaining / definition.reload_seconds))


@dataclass(frozen=True)
class WeaponConfigSnapshot:
    """Immutable configuration snapshot pinned to a room/match."""

    version: str
    schema_version: int
    weapons: Mapping[str, WeaponDefinition]

    def __post_init__(self):
        if not self.version.strip():
            raise ValueError("weapon config version cannot be empty")
        if self.schema_version != 1:
            raise ValueError(f"unsupported weapon schema_version: {self.schema_version}")

        normalized: Dict[str, WeaponDefinition] = {}
        for key, definition in self.weapons.items():
            normalized_key = key.upper()
            if normalized_key != definition.key:
                raise ValueError(f"weapon map key {key} does not match {definition.key}")
            if normalized_key in normalized:
                raise ValueError(f"duplicate weapon key: {normalized_key}")
            normalized[normalized_key] = definition

        required = {"SNIPER", "AR", "SMG"}
        missing = required.difference(normalized)
        if missing:
            raise ValueError(f"missing required weapons: {sorted(missing)}")
        object.__setattr__(self, "weapons", MappingProxyType(normalized))

    def get(self, weapon_type: str) -> WeaponDefinition:
        key = (weapon_type or "").upper()
        try:
            return self.weapons[key]
        except KeyError as exc:
            raise ValueError(f"unknown weapon type: {weapon_type}") from exc

    def create_runtime(self, weapon_type: str) -> WeaponRuntimeState:
        return WeaponRuntimeState.fresh(self.get(weapon_type))

    def keys(self) -> Iterable[str]:
        return self.weapons.keys()

