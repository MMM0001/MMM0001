"""Read-only opportunity detector.

Polls both venues' books for each configured event mapping, computes the best
cross-venue lock after fees and executable depth, and logs any opportunity that
clears ``min_profit``. No orders are placed — this stage exists to validate
whether profitable, *executable* edges actually persist before any capital is
committed.

Production hardening (left as deliberate next steps):
  * replace REST polling with the venues' WebSocket book streams,
  * confirm the live HIP-4 l2Book payload shape against a real market,
  * add staleness checks so a frozen feed can't manufacture a phantom edge.
"""

from __future__ import annotations

import asyncio
import logging

from .config import Settings
from .edge import BookSet, find_opportunity
from .hyperliquid_adapter import HyperliquidAdapter
from .models import EventMapping
from .polymarket_adapter import PolymarketAdapter

log = logging.getLogger("arb.detector")


class Detector:
    def __init__(
        self,
        settings: Settings,
        hl: HyperliquidAdapter,
        pm: PolymarketAdapter,
    ):
        self._settings = settings
        self._hl = hl
        self._pm = pm

    async def _books_for(self, m: EventMapping) -> BookSet | None:
        """Fetch all four books for a mapping; skip the event on any failure."""
        try:
            hl_yes, hl_no, pm_yes, pm_no = await asyncio.gather(
                self._hl.fetch_book(m.hyperliquid.yes_id, "yes"),
                self._hl.fetch_book(m.hyperliquid.no_id, "no"),
                self._pm.fetch_book(m.polymarket.yes_id, "yes"),
                self._pm.fetch_book(m.polymarket.no_id, "no"),
            )
        except Exception as exc:  # noqa: BLE001 - one bad event must not kill the loop
            log.warning("book fetch failed for %s: %s", m.name, exc)
            return None
        return {
            "hyperliquid": {"yes": hl_yes, "no": hl_no},
            "polymarket": {"yes": pm_yes, "no": pm_no},
        }

    async def scan_once(self) -> None:
        for m in self._settings.mappings:
            books = await self._books_for(m)
            if books is None:
                continue
            opp = find_opportunity(
                m,
                books,
                size=self._settings.size,
                fee_table=self._settings.fee_table,
                min_profit=self._settings.min_profit,
            )
            if opp:
                log.info("OPPORTUNITY %s", opp.describe())
            else:
                log.debug("no edge for %s", m.name)

    async def run(self) -> None:
        log.info(
            "detector started: %d event(s), size=%s, min_profit=$%s, interval=%ss",
            len(self._settings.mappings),
            self._settings.size,
            self._settings.min_profit,
            self._settings.poll_interval_s,
        )
        while True:
            await self.scan_once()
            await asyncio.sleep(self._settings.poll_interval_s)
