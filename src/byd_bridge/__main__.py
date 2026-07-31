"""Entry point — run the MCP server: python -m byd_bridge"""

from __future__ import annotations

import asyncio
import logging
import threading

from byd_bridge.config import settings
from byd_bridge.state import poller_loop
from byd_bridge.server import mcp


def _run_poller_in_thread() -> None:
    """Run the async poller loop in a daemon thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(poller_loop())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    _logger = logging.getLogger("byd-bridge")

    # Start background poller
    poller_thread = threading.Thread(target=_run_poller_in_thread, daemon=True)
    poller_thread.start()

    _logger.info(
        "Starting BYD bridge MCP server — mode=%s poll_interval=%ds port=%d",
        settings.mode,
        settings.poll_interval,
        settings.port,
    )

    # Run the SSE server (blocking)
    asyncio.run(mcp.run_sse_async(host="0.0.0.0", port=settings.port))


if __name__ == "__main__":
    main()
