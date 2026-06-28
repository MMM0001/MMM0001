"""Read-only opportunity detector.

Polls both venues' books for each configured event mapping, computes the best
cross-venue lock after fees and executable depth, and records the result into
the shared ``AppState`` (which the web dashboard reads). No orders are placed.

It reads ``settings`` and the ``scan_enabled`` flag from ``AppState`` on every
pass, so edits made through the dashboard take effect on the next scan.

Production hardening (deliberate next steps):
  * replace REST polling with the venues' WebSocket book streams,
  * confirm the live HIP-4 l2Book payload shape against a real market,
  * add staleness checks so a frozen feed can't manufacture a phantom edge.
"""

from __future__ import annotations

import asyncio
import logging
import time

from .edge import BookSet, find_opportunity
from .hyperliquid_adapter import HyperliquidAdapter
from .models import EventMapping
from .polymarket_adapter import PolymarketAdapter
from .state import AppState, EventStatus

log = logging.getLogger("arb.detector")

NEG_INF = float("-inf")


class Detector:
    def __init__(self, state: AppState, hl: HyperliquidAdapter, pm: PolymarketAdapter):
        self._state = state
        self._hl = hl
        self._pm = pm

    async def _books_for(self, m: EventMapping) -> tuple[BookSet | None, str | None]:
        """Fetch all four books for a mapping. Returns (books, error)."""
        try:
            hl_yes, hl_no, pm_yes, pm_no = await asyncio.gather(
                self._hl.fetch_book(m.hyperliquid.yes_id, "yes"),
                self._hl.fetch_book(m.hyperliquid.no_id, "no"),
                self._pm.fetch_book(m.polymarket.yes_id, "yes"),
                self._pm.fetch_book(m.polymarket.no_id, "no"),
            )
        except Exception as exc:  # noqa: BLE001 - one bad event must not kill the loop
            return None, str(exc)
        return (
            {
                "hyperliquid": {"yes": hl_yes, "no": hl_no},
                "polymarket": {"yes": pm_yes, "no": pm_no},
            },
            None,
        )

    async def _scan_event(self, m: EventMapping) -> EventStatus:
        st = EventStatus(name=m.name, updated_ts=time.time())
        books, err = await self._books_for(m)
        if err is not None:
            st.last_error = err
            return st

        st.has_books = True
        settings = self._state.settings
        # Best lock regardless of the profit gate, so the dashboard can show the
        # current edge even when it is below threshold (or negative).
        best = find_opportunity(
            m, books, size=settings.size, fee_table=settings.fee_table, min_profit=NEG_INF
        )
        if best is None:
            st.last_error = "insufficient depth to size both legs"
            return st

        st.best_profit = best.profit
        st.is_live = best.profit > settings.min_profit
        if st.is_live:
            st.opportunity = best.as_dict()
        return st

    async def scan_once(self) -> None:
        start = time.time()
        mappings = list(self._state.settings.mappings)
        results = await asyncio.gather(*(self._scan_event(m) for m in mappings))

        with self._state.lock():
            self._state.statuses = {st.name: st for st in results}
            self._state.last_scan_ts = time.time()
            self._state.last_scan_duration = time.time() - start

        for st in results:
            if st.is_live and st.opportunity:
                o = st.opportunity
                msg = (
                    f"OPPORTUNITY [{o['event']}] profit ${o['profit']:.2f} "
                    f"({o['edge_pct']:.2f}%/share): BUY YES {o['buy_yes_on']} "
                    f"+ BUY NO {o['buy_no_on']}"
                )
                log.info(msg)
                self._state.add_log(msg)
            elif st.last_error:
                log.debug("%s: %s", st.name, st.last_error)

    async def run(self) -> None:
        self._state.add_log("scanner started")
        log.info("detector started")
        while True:
            if self._state.scan_enabled:
                try:
                    await self.scan_once()
                except Exception as exc:  # noqa: BLE001 - keep the loop alive
                    log.exception("scan failed")
                    self._state.add_log(f"scan error: {exc}")
            await asyncio.sleep(self._state.settings.poll_interval_s)
