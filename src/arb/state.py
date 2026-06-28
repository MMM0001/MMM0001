"""Shared in-memory application state.

The background scanner writes scan results here; the web dashboard reads from
here. Settings and event mappings are mutable so the dashboard can edit them
live (and they get persisted back to the YAML config).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from .config import Settings


@dataclass
class EventStatus:
    """Most recent scan outcome for one event mapping (for the dashboard)."""

    name: str
    has_books: bool = False
    last_error: Optional[str] = None
    best_profit: Optional[float] = None   # best lock found, even if below the gate
    is_live: bool = False                 # True when best_profit clears min_profit
    opportunity: Optional[dict] = None    # serialized Opportunity when live
    updated_ts: float = 0.0


class AppState:
    """Thread-safe-ish container shared between the scanner task and the API.

    Everything runs in one asyncio loop, but we guard the mutable bits with a
    lock so the (synchronous) config-save path and the API handlers can't race
    the scanner mid-update.
    """

    def __init__(self, settings: Settings, config_path: str):
        self.settings = settings
        self.config_path = config_path
        self.scan_enabled = True
        self.last_scan_ts: Optional[float] = None
        self.last_scan_duration = 0.0
        self.statuses: dict[str, EventStatus] = {}
        self.log: deque[str] = deque(maxlen=200)
        self._lock = threading.Lock()

    def lock(self) -> threading.Lock:
        return self._lock

    def add_log(self, line: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self.log.appendleft(f"{ts}  {line}")

    def live_opportunities(self) -> list[dict]:
        out = []
        for st in self.statuses.values():
            if st.is_live and st.opportunity:
                out.append(st.opportunity)
        out.sort(key=lambda o: o.get("profit", 0), reverse=True)
        return out

    def snapshot(self) -> dict:
        """Serialize everything the dashboard needs in one JSON-able dict."""
        with self._lock:
            return {
                "scan_enabled": self.scan_enabled,
                "last_scan_ts": self.last_scan_ts,
                "last_scan_duration": round(self.last_scan_duration, 3),
                "settings": {
                    "poll_interval_s": self.settings.poll_interval_s,
                    "size": self.settings.size,
                    "min_profit": self.settings.min_profit,
                    "fee_table": dict(self.settings.fee_table),
                },
                "events": [self._event_view(m) for m in self.settings.mappings],
                "opportunities": self.live_opportunities(),
                "log": list(self.log),
            }

    def _event_view(self, m) -> dict:
        st = self.statuses.get(m.name)
        return {
            "name": m.name,
            "resolution_note": m.resolution_note,
            "hyperliquid": {"yes_id": m.hyperliquid.yes_id, "no_id": m.hyperliquid.no_id},
            "polymarket": {"yes_id": m.polymarket.yes_id, "no_id": m.polymarket.no_id},
            "status": {
                "has_books": st.has_books if st else False,
                "last_error": st.last_error if st else None,
                "best_profit": st.best_profit if st else None,
                "is_live": st.is_live if st else False,
                "updated_ts": st.updated_ts if st else 0.0,
            },
        }
