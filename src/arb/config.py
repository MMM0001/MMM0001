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


def save_settings(path: str, settings: Settings) -> None:
    """Persist the current settings + event mappings back to YAML.

    Called when the dashboard edits settings or adds/removes events so changes
    survive a restart.
    """
    data = {
        "settings": {
            "poll_interval_s": settings.poll_interval_s,
            "size": settings.size,
            "min_profit": settings.min_profit,
            "fee_table": dict(settings.fee_table),
        },
        "events": [
            {
                "name": m.name,
                "resolution_note": m.resolution_note,
                "hyperliquid": {"yes_id": m.hyperliquid.yes_id, "no_id": m.hyperliquid.no_id},
                "polymarket": {"yes_id": m.polymarket.yes_id, "no_id": m.polymarket.no_id},
            }
            for m in settings.mappings
        ],
    }
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)
