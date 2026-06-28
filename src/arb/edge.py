"""Cross-venue edge calculation.

The canonical lock for two binary outcome markets that both settle to 0/1 USDC:

    Buy YES of the outcome on venue A, and buy NO of the same outcome on
    venue B. Exactly one of {YES, NO} pays 1 USDC at resolution, so owning one
    share of each guarantees a 1 USDC payout. If the combined cost to acquire
    that pair is < 1 USDC (after fees), the difference is locked profit,
    independent of how the event resolves.

We evaluate this in *both* directions (YES on HL / NO on PM, and YES on PM /
NO on HL) and size it against real executable depth, not just top-of-book.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import EventMapping, OutcomeBook, VenueLeg

# A bundle of the four normalized books for one event mapping.
# Keyed as books[venue][side] -> OutcomeBook.
BookSet = dict[str, dict[str, OutcomeBook]]


@dataclass
class Opportunity:
    event: str
    yes_leg: VenueLeg
    no_leg: VenueLeg
    size: float            # shares per leg
    yes_cost: float        # USDC to buy `size` YES shares
    no_cost: float         # USDC to buy `size` NO shares
    fees: float            # estimated total fees in USDC
    payout: float          # guaranteed payout at resolution (== size)
    profit: float          # payout - yes_cost - no_cost - fees

    @property
    def edge_per_share(self) -> float:
        return self.profit / self.size if self.size else 0.0

    def as_dict(self) -> dict:
        return {
            "event": self.event,
            "buy_yes_on": self.yes_leg.venue,
            "buy_yes_id": self.yes_leg.market_id,
            "buy_no_on": self.no_leg.venue,
            "buy_no_id": self.no_leg.market_id,
            "size": self.size,
            "yes_cost": round(self.yes_cost, 4),
            "no_cost": round(self.no_cost, 4),
            "fees": round(self.fees, 4),
            "payout": round(self.payout, 4),
            "profit": round(self.profit, 4),
            "edge_pct": round(self.edge_per_share * 100, 3),
        }

    def describe(self) -> str:
        return (
            f"[{self.event}] size={self.size:.1f} "
            f"BUY YES {self.yes_leg.venue}:{self.yes_leg.market_id} "
            f"(${self.yes_cost:.3f}) + BUY NO {self.no_leg.venue}:{self.no_leg.market_id} "
            f"(${self.no_cost:.3f}) + fees ${self.fees:.3f} "
            f"-> payout ${self.payout:.2f} | profit ${self.profit:.3f} "
            f"({self.edge_per_share * 100:.2f}%/share)"
        )


def _fee(venue: str, notional: float, fee_table: dict[str, float]) -> float:
    return notional * fee_table.get(venue, 0.0)


def _best_lock(
    event: str,
    yes_book: OutcomeBook,
    no_book: OutcomeBook,
    size: float,
    fee_table: dict[str, float],
) -> Opportunity | None:
    """Evaluate buying YES from ``yes_book`` and NO from ``no_book``."""
    yes_cost = yes_book.cost_to_buy(size)
    no_cost = no_book.cost_to_buy(size)
    if yes_cost is None or no_cost is None:
        return None  # not enough depth to fill the full size on one side

    fees = _fee(yes_book.venue, yes_cost, fee_table) + _fee(no_book.venue, no_cost, fee_table)
    payout = size
    profit = payout - yes_cost - no_cost - fees
    return Opportunity(
        event=event,
        yes_leg=VenueLeg(yes_book.venue, yes_book.market_id, "yes"),
        no_leg=VenueLeg(no_book.venue, no_book.market_id, "no"),
        size=size,
        yes_cost=yes_cost,
        no_cost=no_cost,
        fees=fees,
        payout=payout,
        profit=profit,
    )


def find_opportunity(
    mapping: EventMapping,
    books: BookSet,
    *,
    size: float,
    fee_table: dict[str, float],
    min_profit: float = 0.0,
) -> Opportunity | None:
    """Return the best profitable lock for ``mapping``, or ``None``.

    ``books`` is keyed ``books[venue][side]`` -> ``OutcomeBook``. We try both
    legging directions (YES on HL / NO on PM, and YES on PM / NO on HL) and
    keep the more profitable one that clears ``min_profit``.
    """
    hl = books.get(mapping.hyperliquid.venue)
    pm = books.get(mapping.polymarket.venue)
    if not hl or not pm or not all(s in hl and s in pm for s in ("yes", "no")):
        return None

    candidates = [
        _best_lock(mapping.name, hl["yes"], pm["no"], size, fee_table),
        _best_lock(mapping.name, pm["yes"], hl["no"], size, fee_table),
    ]
    profitable = [c for c in candidates if c and c.profit > min_profit]
    if not profitable:
        return None
    return max(profitable, key=lambda c: c.profit)
