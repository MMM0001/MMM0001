"""CLI entry point for the read-only arbitrage detector.

Usage:
    python -m src.arb.main --config config/events.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import logging

import httpx

from .config import load_settings
from .detector import Detector
from .hyperliquid_adapter import HyperliquidAdapter
from .polymarket_adapter import PolymarketAdapter
from .state import AppState


async def _amain(config_path: str) -> None:
    settings = load_settings(config_path)
    if not settings.mappings:
        logging.getLogger("arb").error(
            "no event mappings in %s — add at least one verified pair", config_path
        )
        return
    state = AppState(settings, config_path)
    async with httpx.AsyncClient() as client:
        detector = Detector(
            state,
            HyperliquidAdapter(client),
            PolymarketAdapter(client),
        )
        await detector.run()


def main() -> None:
    parser = argparse.ArgumentParser(description="HL<->PM arbitrage detector (read-only)")
    parser.add_argument("--config", default="config/events.yaml")
    parser.add_argument("--verbose", "-v", action="store_true", help="show per-event no-edge logs")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        asyncio.run(_amain(args.config))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
