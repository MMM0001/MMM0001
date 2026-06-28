"""Web dashboard + JSON API for the arbitrage detector.

Runs the read-only scanner as a background task and serves a single-page
dashboard to view live opportunities and manage event pairs / settings without
editing YAML by hand.

Run it with:

    python -m src.arb.webapp --config config/events.yaml

then open http://localhost:8000 in a browser.

This remains READ-ONLY with respect to trading: the dashboard manages
configuration and displays detected edges, but never places an order.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import load_settings, save_settings
from .detector import Detector
from .hyperliquid_adapter import HyperliquidAdapter
from .models import EventMapping, VenueOutcome
from .polymarket_adapter import PolymarketAdapter
from .state import AppState

log = logging.getLogger("arb.web")
STATIC_DIR = Path(__file__).parent / "web" / "static"


# ---- request models -------------------------------------------------------

class SettingsUpdate(BaseModel):
    poll_interval_s: float | None = Field(default=None, gt=0.5)
    size: float | None = Field(default=None, gt=0)
    min_profit: float | None = None
    fee_hyperliquid: float | None = Field(default=None, ge=0)
    fee_polymarket: float | None = Field(default=None, ge=0)


class VenueIds(BaseModel):
    yes_id: str
    no_id: str


class EventCreate(BaseModel):
    name: str
    resolution_note: str = ""
    hyperliquid: VenueIds
    polymarket: VenueIds


class ScanToggle(BaseModel):
    enabled: bool


class DeleteEvent(BaseModel):
    name: str


# ---- app factory ----------------------------------------------------------

def create_app(config_path: str) -> FastAPI:
    settings = load_settings(config_path)
    state = AppState(settings, config_path)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        client = httpx.AsyncClient()
        detector = Detector(state, HyperliquidAdapter(client), PolymarketAdapter(client))
        import asyncio

        task = asyncio.create_task(detector.run())
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            await client.aclose()

    app = FastAPI(title="HL<->PM Arbitrage Dashboard", lifespan=lifespan)

    def persist() -> None:
        save_settings(state.config_path, state.settings)

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/state")
    async def get_state() -> dict:
        return state.snapshot()

    @app.post("/api/scan/toggle")
    async def toggle_scan(body: ScanToggle) -> dict:
        with state.lock():
            state.scan_enabled = body.enabled
        state.add_log(f"scanning {'enabled' if body.enabled else 'paused'}")
        return {"scan_enabled": state.scan_enabled}

    @app.post("/api/settings")
    async def update_settings(body: SettingsUpdate) -> dict:
        with state.lock():
            s = state.settings
            if body.poll_interval_s is not None:
                s.poll_interval_s = body.poll_interval_s
            if body.size is not None:
                s.size = body.size
            if body.min_profit is not None:
                s.min_profit = body.min_profit
            if body.fee_hyperliquid is not None:
                s.fee_table["hyperliquid"] = body.fee_hyperliquid
            if body.fee_polymarket is not None:
                s.fee_table["polymarket"] = body.fee_polymarket
            persist()
        state.add_log("settings updated")
        return state.snapshot()["settings"]

    @app.post("/api/events")
    async def add_event(body: EventCreate) -> dict:
        with state.lock():
            if any(m.name == body.name for m in state.settings.mappings):
                raise HTTPException(409, f"an event named {body.name!r} already exists")
            mapping = EventMapping(
                name=body.name,
                hyperliquid=VenueOutcome(
                    "hyperliquid", body.hyperliquid.yes_id, body.hyperliquid.no_id
                ),
                polymarket=VenueOutcome(
                    "polymarket", body.polymarket.yes_id, body.polymarket.no_id
                ),
                resolution_note=body.resolution_note,
            )
            state.settings.mappings.append(mapping)
            persist()
        state.add_log(f"event added: {body.name}")
        return state.snapshot()

    @app.post("/api/events/delete")
    async def delete_event(body: DeleteEvent) -> dict:
        with state.lock():
            before = len(state.settings.mappings)
            state.settings.mappings = [
                m for m in state.settings.mappings if m.name != body.name
            ]
            if len(state.settings.mappings) == before:
                raise HTTPException(404, f"no event named {body.name!r}")
            state.statuses.pop(body.name, None)
            persist()
        state.add_log(f"event removed: {body.name}")
        return state.snapshot()

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


def _open_browser_soon(url: str) -> None:
    """Open the dashboard in the default browser a moment after startup."""
    import threading
    import webbrowser

    threading.Timer(1.5, lambda: webbrowser.open(url)).start()


def main() -> None:
    parser = argparse.ArgumentParser(description="HL<->PM arbitrage dashboard")
    parser.add_argument("--config", default="config/events.yaml")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--open", action="store_true", help="open the dashboard in your browser")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    app = create_app(args.config)
    url = f"http://localhost:{args.port}"
    print("\n" + "=" * 56)
    print(f"  Dashboard running. Open this in your browser:\n      {url}")
    print("  Leave this window open. Press Ctrl+C here to stop.")
    print("=" * 56 + "\n")
    if args.open:
        _open_browser_soon(url)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
