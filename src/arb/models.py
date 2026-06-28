"""Normalized data models shared across venue adapters.

Both Hyperliquid HIP-4 outcome markets and Polymarket CLOB markets settle each
binary outcome to 0 or 1 USDC. That shared structure lets us normalize both
venues into the same ``OrderBook`` shape and reason about cross-venue edges in
one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

Side = Literal["yes", "no"]


@dataclass(frozen=True)
class Level:
    """A single price level in a normalized book.

    ``price`` is the per-share cost in USDC, always in [0, 1] for an outcome
    that settles to 0/1. ``size`` is the number of shares available at that
    price (each share pays 1 USDC if the outcome resolves true).
    """

    price: float
    size: float


@dataclass
class OutcomeBook:
    """Normalized order book for one *side* (yes or no) of one outcome.

    ``asks`` are sorted ascending (cheapest first) — these are the prices at
    which we can BUY this side. ``bids`` are sorted descending — prices at
    which we can SELL. For the detector we mainly consume ``asks`` because the
    canonical lock is "buy YES here + buy NO there".
    """

    venue: str
    market_id: str
    side: Side
    asks: list[Level] = field(default_factory=list)
    bids: list[Level] = field(default_factory=list)
    ts: float = 0.0

    @property
    def best_ask(self) -> Optional[Level]:
        return self.asks[0] if self.asks else None

    @property
    def best_bid(self) -> Optional[Level]:
        return self.bids[0] if self.bids else None

    def cost_to_buy(self, shares: float) -> Optional[float]:
        """Total USDC cost to buy ``shares`` by walking the ask side.

        Returns ``None`` if the book is too thin to fill the full size — we do
        not want to report an edge we cannot actually execute.
        """
        remaining = shares
        cost = 0.0
        for lvl in self.asks:
            take = min(remaining, lvl.size)
            cost += take * lvl.price
            remaining -= take
            if remaining <= 1e-9:
                return cost
        return None


@dataclass(frozen=True)
class VenueLeg:
    """Identifies one executable leg of an arb on a specific venue."""

    venue: str
    market_id: str
    side: Side


@dataclass(frozen=True)
class VenueOutcome:
    """The pair of market ids (yes + no books) for one outcome on one venue."""

    venue: str
    yes_id: str
    no_id: str

    def leg(self, side: Side) -> VenueLeg:
        return VenueLeg(self.venue, self.yes_id if side == "yes" else self.no_id, side)


@dataclass(frozen=True)
class EventMapping:
    """A human-approved mapping of the *same real-world outcome* across venues.

    Event matching is the riskiest part of the whole system: the two legs must
    resolve identically (same match, same handling of draw / extra time /
    postponement, same resolution source). This object is intentionally
    explicit and is meant to be reviewed by a human before going live.
    """

    name: str
    hyperliquid: VenueOutcome
    polymarket: VenueOutcome
    # Free-text note documenting the resolution-rule equivalence we verified.
    resolution_note: str = ""
