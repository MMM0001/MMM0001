"""Unit tests for the cross-venue edge math."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.arb.edge import find_opportunity  # noqa: E402
from src.arb.models import EventMapping, Level, OutcomeBook, VenueOutcome  # noqa: E402

MAPPING = EventMapping(
    name="test",
    hyperliquid=VenueOutcome("hyperliquid", "hl-yes", "hl-no"),
    polymarket=VenueOutcome("polymarket", "pm-yes", "pm-no"),
)
NO_FEES = {"hyperliquid": 0.0, "polymarket": 0.0}


def _book(venue, mid, side, asks):
    return OutcomeBook(venue=venue, market_id=mid, side=side,
                       asks=[Level(p, s) for p, s in asks])


def _books(hl_yes, hl_no, pm_yes, pm_no):
    return {
        "hyperliquid": {"yes": _book("hyperliquid", "hl-yes", "yes", hl_yes),
                        "no": _book("hyperliquid", "hl-no", "no", hl_no)},
        "polymarket": {"yes": _book("polymarket", "pm-yes", "yes", pm_yes),
                       "no": _book("polymarket", "pm-no", "no", pm_no)},
    }


def test_locks_profit_when_yes_plus_no_below_one():
    # Buy YES on HL @0.40 + NO on PM @0.55 = 0.95 -> $0.05/share locked.
    books = _books(hl_yes=[(0.40, 100)], hl_no=[(0.99, 100)],
                   pm_yes=[(0.99, 100)], pm_no=[(0.55, 100)])
    opp = find_opportunity(MAPPING, books, size=100, fee_table=NO_FEES)
    assert opp is not None
    assert opp.yes_leg.venue == "hyperliquid"
    assert opp.no_leg.venue == "polymarket"
    assert abs(opp.profit - 5.0) < 1e-6


def test_no_opportunity_when_sum_above_one():
    books = _books(hl_yes=[(0.60, 100)], hl_no=[(0.60, 100)],
                   pm_yes=[(0.60, 100)], pm_no=[(0.60, 100)])
    assert find_opportunity(MAPPING, books, size=100, fee_table=NO_FEES) is None


def test_insufficient_depth_returns_none():
    # Edge exists at top-of-book but only 10 shares; we need 100.
    books = _books(hl_yes=[(0.40, 10)], hl_no=[(0.99, 100)],
                   pm_yes=[(0.99, 100)], pm_no=[(0.55, 100)])
    assert find_opportunity(MAPPING, books, size=100, fee_table=NO_FEES) is None


def test_fees_can_erase_edge():
    books = _books(hl_yes=[(0.40, 100)], hl_no=[(0.99, 100)],
                   pm_yes=[(0.99, 100)], pm_no=[(0.55, 100)])
    # 2% taker fees on ~$95 notional ≈ $1.9 > $5 edge? No — but min_profit gate filters it.
    fat = {"hyperliquid": 0.02, "polymarket": 0.02}
    opp = find_opportunity(MAPPING, books, size=100, fee_table=fat, min_profit=4.0)
    assert opp is None  # ~$3.1 net profit < $4 gate


def test_depth_weighted_cost_across_levels():
    # 60 @0.40 then 40 @0.50 -> avg cost = (24 + 20)/100 = 0.44 per share.
    books = _books(hl_yes=[(0.40, 60), (0.50, 40)], hl_no=[(0.99, 100)],
                   pm_yes=[(0.99, 100)], pm_no=[(0.50, 100)])
    opp = find_opportunity(MAPPING, books, size=100, fee_table=NO_FEES)
    assert opp is not None
    assert abs(opp.yes_cost - 44.0) < 1e-6
    assert abs(opp.profit - (100 - 44 - 50)) < 1e-6
