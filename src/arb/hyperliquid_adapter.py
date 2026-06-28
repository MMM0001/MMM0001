"""Hyperliquid HIP-4 outcome-market adapter (read-only market data).

HIP-4 markets live in HyperCore on the same CLOB/REST/WS infrastructure as
perps and spot. Order books are served by the public ``/info`` endpoint with
``{"type": "l2Book", "coin": <coin>}`` — no auth required for market data.

For HIP-4, ``coin`` is the outcome's ``#`` alias (e.g. ``#10``) or its native
asset index. Each outcome trades YES and NO on linked books. The exact field
shape returned for HIP-4 l2 books should be confirmed against a live response
the first time you point this at a real market — the parsing below follows the
documented perps/spot l2Book shape (a two-element ``levels`` array of
``[bids, asks]`` where each level is ``{"px": str, "sz": str, "n": int}``).

Execution (signing/order placement) requires the hyperliquid-python-sdk and a
funded USDH account; that is intentionally out of scope for this read-only
detector.
"""

from __future__ import annotations

import time

import httpx

from .models import Level, OutcomeBook

VENUE = "hyperliquid"
INFO_URL = "https://api.hyperliquid.xyz/info"


class HyperliquidAdapter:
    def __init__(self, client: httpx.AsyncClient, info_url: str = INFO_URL):
        self._client = client
        self._info_url = info_url

    async def _l2_book(self, coin: str) -> dict:
        resp = await self._client.post(
            self._info_url, json={"type": "l2Book", "coin": coin}, timeout=10.0
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _levels(raw: list[dict]) -> list[Level]:
        out = []
        for lvl in raw:
            try:
                out.append(Level(price=float(lvl["px"]), size=float(lvl["sz"])))
            except (KeyError, TypeError, ValueError):
                continue
        return out

    async def fetch_book(self, market_id: str, side: str) -> OutcomeBook:
        """Fetch the normalized book for one side of an outcome.

        ``market_id`` is the coin alias/index for the side being requested. The
        YES and NO sides of a HIP-4 outcome are linked but addressed as
        distinct coins; the event mapping config supplies the right id per side
        (see ``config/events.yaml``).
        """
        raw = await self._l2_book(market_id)
        levels = raw.get("levels") or [[], []]
        bids_raw, asks_raw = (levels + [[], []])[:2]

        asks = sorted(self._levels(asks_raw), key=lambda x: x.price)
        bids = sorted(self._levels(bids_raw), key=lambda x: x.price, reverse=True)
        return OutcomeBook(
            venue=VENUE,
            market_id=market_id,
            side=side,  # type: ignore[arg-type]
            asks=asks,
            bids=bids,
            ts=time.time(),
        )
