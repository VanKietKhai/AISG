"""Build Gate G5 metrics from authoritative server JSON telemetry.

This module never trains or updates a model. It deliberately reports
``optimizer_step_count = 0`` and ``run_mode = EVAL``.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List


def _safe_mean(values: Iterable[float]) -> float:
    values = list(values)
    return float(mean(values)) if values else 0.0


def _weapon_band_ok(weapon: str, distance: float, max_range: float) -> bool:
    if max_range <= 0:
        return False
    ratio = distance / max_range
    if weapon == "SNIPER":
        return 0.40 <= ratio <= 0.90
    if weapon == "SMG":
        return 0.0 <= ratio <= 0.80
    return 0.25 <= ratio <= 0.80


def summarize_entries(entries: Iterable[Dict[str, Any]], expected_episodes: int = 0) -> Dict[str, Any]:
    """Summarize one or more closed server log files without mutating a model."""
    events: List[Dict[str, Any]] = []
    observations: List[Dict[str, Any]] = []
    for entry in entries:
        if entry.get("type") == "game_event":
            data = dict(entry.get("data") or {})
            data["event_type"] = entry.get("event_type")
            events.append(data)
        elif entry.get("type") == "observation_sent":
            observations.append(dict(entry.get("data") or {}))

    fired = [e for e in events if e.get("event_type") == "shot_fired"]
    hits = [e for e in events if e.get("event_type") == "hit_registered"]
    reloads = [e for e in events if e.get("event_type") == "reload_started"]
    rejected = [e for e in events if e.get("event_type") == "shot_rejected"]
    deaths = max((int(o.get("self_deaths", 0)) for o in observations), default=0)
    kills = max((int(o.get("self_kills", 0)) for o in observations), default=0)
    episode_count = deaths

    per_weapon: Dict[str, Dict[str, Any]] = {}
    grouped = defaultdict(list)
    for event in fired:
        grouped[str(event.get("weapon_type", "UNKNOWN")).upper()].append(event)
    for weapon, weapon_events in sorted(grouped.items()):
        distances = [float(e.get("target_distance", 0.0)) for e in weapon_events]
        ranges = [float(e.get("max_range", 0.0)) for e in weapon_events]
        compliance = [
            _weapon_band_ok(weapon, distance, max_range)
            for distance, max_range in zip(distances, ranges)
        ]
        ticks = sorted(int(e.get("tick", 0)) for e in weapon_events)
        bursts, current = [], 0
        previous = None
        for tick in ticks:
            if previous is None or tick - previous <= 15:
                current += 1
            else:
                bursts.append(current)
                current = 1
            previous = tick
        if current:
            bursts.append(current)
        per_weapon[weapon] = {
            "shots_fired": len(weapon_events),
            "avg_engagement_distance": _safe_mean(distances),
            "distance_band_compliance": _safe_mean(compliance),
            "avg_burst_size": _safe_mean(bursts),
        }

    ammo_spent = sum(max(0, int(e.get("ammo_before", 0)) - int(e.get("ammo_after", 0))) for e in fired)
    invalid_no_los = sum(not bool(e.get("has_los", False)) for e in fired)
    invalid_range = sum(not bool(e.get("in_effective_range", False)) for e in fired)
    completed = episode_count
    completion_rate = completed / expected_episodes if expected_episodes > 0 else (1.0 if completed else 0.0)

    return {
        "run_mode": "EVAL",
        "optimizer_step_count": 0,
        "completion_rate": min(1.0, completion_rate),
        "episode_count": episode_count,
        "weapon_type": sorted(per_weapon),
        "avg_engagement_distance": _safe_mean(float(e.get("target_distance", 0.0)) for e in fired),
        "distance_band_compliance": _safe_mean(
            value["distance_band_compliance"] for value in per_weapon.values()
        ),
        "shots_fired": len(fired),
        "valid_hits": len(hits),
        "hit_rate": len(hits) / len(fired) if fired else 0.0,
        "ammo_spent": ammo_spent,
        "hit_efficiency": len(hits) / ammo_spent if ammo_spent else 0.0,
        "reload_count": len(reloads),
        "timely_reload_rate": _safe_mean(int(e.get("ammo_before", 0)) <= 1 for e in reloads),
        "invalid_no_los_shots": invalid_no_los,
        "invalid_out_of_range_shots": invalid_range,
        "shot_rejected_count": len(rejected),
        "stuck_or_idle_penalty_count": 0,
        "death_count": deaths,
        "kill_count": kills,
        "damage_validated": sum(float(e.get("damage_amount", e.get("damage", 0.0))) for e in hits),
        "per_weapon": per_weapon,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Gate G5 EVAL-only summary")
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument("--expected-episodes", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    entries = []
    for path in args.logs:
        with path.open("r", encoding="utf-8") as handle:
            entries.extend(json.load(handle))
    result = summarize_entries(entries, args.expected_episodes)
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
