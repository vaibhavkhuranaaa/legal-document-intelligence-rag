"""Re-measure the responsive publication claims this project makes.

The release records two responsive numbers: how far any checked page overflows
its viewport horizontally, and how small the primary navigation targets render
on a phone. Both were originally measured by hand in a browser, which makes them
claims rather than results. This script re-measures them from a real rendering
engine so the numbers can be reproduced on demand.

It prints one number and nothing else, so a verification harness can compare
what it printed against what the project recorded.

    python scripts/verify_responsive.py responsive_overflow_px
    python scripts/verify_responsive.py mobile_nav_target_px

The application is served locally on an ephemeral port against the local
retrieval backend. No cloud call is made for either metric, because both
measure the empty workspace and the release register rather than a generated
answer.
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
from contextlib import contextmanager

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from legal_rag.ui.flask_app import create_app

DESKTOP = {"width": 1440, "height": 1000}
MOBILE = {"width": 390, "height": 844}

# The two pages the responsive claim actually names.
CHECKED_ROUTES = ("/", "/evaluation")

NAV_LINKS = 'nav[aria-label="Primary navigation"] a'


@contextmanager
def serve():
    """Run the research application on a local ephemeral port."""
    # A caller reads the last line of this process to get the number, so the
    # request log must not be the last thing written.
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    server = make_server("127.0.0.1", 0, create_app(), threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=10)


def measure_overflow(page, base: str) -> float:
    """Largest horizontal overflow across the checked pages and viewports."""
    worst = 0.0
    for viewport in (DESKTOP, MOBILE):
        page.set_viewport_size(viewport)
        for route in CHECKED_ROUTES:
            page.goto(f"{base}{route}", wait_until="load")
            overflow = page.evaluate(
                "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            worst = max(worst, float(overflow))
    return worst


def measure_nav_target(page, base: str) -> float:
    """Smallest rendered navigation link height at the checked mobile viewport."""
    page.set_viewport_size(MOBILE)
    page.goto(f"{base}/", wait_until="load")
    heights = page.eval_on_selector_all(
        NAV_LINKS,
        "nodes => nodes.map(node => node.getBoundingClientRect().height)",
    )
    if not heights:
        raise SystemExit("no primary navigation links rendered; the selector is stale")
    return float(min(heights))


METRICS = {
    "responsive_overflow_px": measure_overflow,
    "mobile_nav_target_px": measure_nav_target,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metric", choices=sorted(METRICS))
    arguments = parser.parse_args()

    with serve() as base, sync_playwright() as driver:
        browser = driver.chromium.launch()
        page = browser.new_page()
        try:
            value = METRICS[arguments.metric](page, base)
        finally:
            browser.close()

    # A verification harness reads the last line, so print the number alone.
    print(value)
    return 0


if __name__ == "__main__":
    sys.exit(main())
