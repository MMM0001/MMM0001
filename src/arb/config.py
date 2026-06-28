"""Load event mappings and detector settings from YAML."""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from .models import EventMapping, VenueOutcome


@dataclass
class Settings:
    poll_interval_s: float
    size: float
    min_profit: float
    fee_table: dict[str, float]
    mappings: list[EventMapping]


def _venue_outcome(venue: str, node: dict) -> VenueOutcome:
    return VenueOutcome(venue=venue, yes_id=str(node["yes_id"]), no_id=str(node["no_id"]))


def load_settings(path: str) -> Settings:
    with open(path) as f:
        raw = yaml.safe_load(f)

    mappings = []
    for m in raw.get("events", []):
        mappings.append(
            EventMapping(
                name=m["name"],
                hyperliquid=_venue_outcome("hyperliquid", m["hyperliquid"]),
                polymarket=_venue_outcome("polymarket", m["polymarket"]),
                resolution_note=m.get("resolution_note", ""),
            )
        )

    s = raw.get("settings", {})
    return Settings(
        poll_interval_s=float(s.get("poll_interval_s", 5.0)),
        size=float(s.get("size", 100.0)),
        min_profit=float(s.get("min_profit", 0.0)),
        fee_table={k: float(v) for k, v in (s.get("fee_table") or {}).items()},
        mappings=mappings,
    )
