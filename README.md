# Hyperliquid ↔ Polymarket arbitrage detector

A **read-only** opportunity detector for cross-venue arbitrage between
[Hyperliquid HIP-4 outcome markets](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-4-outcome-markets)
and [Polymarket](https://docs.polymarket.com/) CLOB markets.

This is **stage 1** of a staged build. It places **no orders**. Its job is to
answer the only question that matters before risking capital: *do profitable,
executable cross-venue edges actually persist?*

## Why this is a "lock", not instant arbitrage

Both venues settle each binary outcome to **0 or 1 USDC**. So if you can buy the
YES share of an outcome on one venue and the NO share on the other for a
**combined cost < $1**, exactly one side pays $1 at resolution and you keep the
difference — regardless of how the event resolves.

The catch: the payout arrives **at resolution**, not instantly. Capital is
locked on both chains (USDH on HyperCore, USDC on Polygon) until the event
settles. Judge returns *annualized against lock-up*, not per-trade.

## The hard parts (designed-around, not solved)

1. **Event matching** is safety-critical. Both legs must resolve identically —
   same match, same source, same draw/extra-time/postponement handling. Pairs
   live in `config/events.yaml` and are meant to be **human-reviewed**.
2. **Executable depth, not top-of-book.** The detector sizes every edge against
   real order-book depth (`settings.size`) and reports `None` if a leg can't
   fill — a quoted price you can't trade into is not an edge. (That World Cup
   screenshot whose implied probabilities summed to ~144% is the cautionary
   case: "mispriced" often just means "thin/stale".)
3. **Two chains, no shared margin.** Live execution will need pre-funded capital
   on both sides plus rebalancing — out of scope here, noted in the roadmap.

## Layout

```
src/arb/
  models.py               normalized OrderBook / outcome / event-mapping types
  edge.py                 cross-venue lock math (depth-weighted, fee-aware)
  hyperliquid_adapter.py  HIP-4 l2Book via public /info endpoint (read-only)
  polymarket_adapter.py   CLOB /book via public endpoint (read-only)
  config.py               YAML loader
  detector.py             poll -> normalize -> find edge -> log
  main.py                 CLI entry point
config/events.yaml        human-verified event pairs (placeholders to start)
tests/test_edge.py        unit tests for the edge math
```

## Run

```bash
pip install -r requirements.txt

# Fill config/events.yaml with real, human-verified market ids first, then:
python -m src.arb.main --config config/events.yaml -v

pytest -q   # exercises the edge math without touching the network
```

## Roadmap

- **Stage 1 (this):** read-only detector, REST polling, edge logging.
- **Stage 2:** WebSocket book streams; paper-trade simulator tracking
  hypothetical fills + PnL.
- **Stage 3:** live two-leg execution (`hyperliquid-python-sdk` +
  `py-clob-client`), passive-then-aggressive legging to limit leg risk, strict
  per-event caps + kill switch.
- **Stage 4:** cross-chain inventory / capital rebalancing automation.

> Trading involves risk. Verify every event mapping and every fee assumption
> against live data before committing capital.
