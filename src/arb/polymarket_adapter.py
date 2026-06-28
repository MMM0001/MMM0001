"""Polymarket CLOB adapter (read-only market data).

Polymarket runs a Central Limit Order Book on Polygon. Each market has YES and
NO outcome tokens, identified by ERC-1155 ``token_id`` strings. The public CLOB
REST endpoint ``GET /book?token_id=<id>`` returns the order book with no auth:

    {"market": "...", "asset_id": "...",
     "bids": [{"price": "0.39", "size": "1200"}, ...],
     "asks": [{"price": "0.41", "size": "800"}, ...]}

Note Polymarket sorts ``bids`` ascending and ``asks`` descending in its raw
payload; we re-sort into our convention (asks cheapest-first, bids
highest-first).

Execution requires py-clob-client with L1 (private key) + L2 (API key) auth and
USDC on Polygon — out of scope for this read-only detector.
"""

from __future__ import annotations

import time

import httpx

from .models import Level, OutcomeBook

VENUE = "polymarket"
CLOB_URL = "https://clob.polymarket.com"


class PolymarketAdapter:
    def __init__(self, client: httpx.AsyncClient, clob_url: str = CLOB_URL):
        self._client = client
        self._clob_url = clob_url.rstrip("/")

    async def _book(self, token_id: str) -> dict:
        resp = await self._client.get(
            f"{self._clob_url}/book", params={"token_id": token_id}, timeout=10.0
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _levels(raw: list[dict]) -> list[Level]:
        out = []
        for lvl in raw or []:
            try:
                out.append(Level(price=float(lvl["price"]), size=float(lvl["size"])))
            except (KeyError, TypeError, ValueError):
                continue
        return out

    async def fetch_book(self, market_id: str, side: str) -> OutcomeBook:
        """Fetch the normalized book for one outcome token.

        ``market_id`` is the Polymarket ``token_id`` for the side requested
        (YES and NO are separate token ids). The event mapping supplies the
        correct token id per side.
        """
        raw = await self._book(market_id)
        asks = sorted(self._levels(raw.get("asks")), key=lambda x: x.price)
        bids = sorted(self._levels(raw.get("bids")), key=lambda x: x.price, reverse=True)
        return OutcomeBook(
            venue=VENUE,
            market_id=market_id,
            side=side,  # type: ignore[arg-type]
            asks=asks,
            bids=bids,
            ts=time.time(),
        )
