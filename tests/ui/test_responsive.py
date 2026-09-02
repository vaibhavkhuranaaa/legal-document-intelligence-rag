"""Guard the responsive property the public workspace is required to hold.

Horizontal overflow on this site has always been zero, on every public route,
at both checked viewports. That makes it a property to defend rather than a
result to claim, so it lives here instead of in the delivery metrics.

The check needs a real rendering engine. Continuous integration installs the
dependency group but not a browser binary, so the module skips when either the
driver or the browser is missing rather than failing a run that cannot perform
the measurement.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

playwright_api = pytest.importorskip(
    "playwright.sync_api", reason="playwright is a dev-only dependency"
)

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_responsive.py"

# The measurement code is the same code the delivery record points at. Importing
# it here keeps one definition of how a viewport is set up and how the
# application is served.
_spec = importlib.util.spec_from_file_location("verify_responsive", _SCRIPT)
verify_responsive = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify_responsive)

PUBLIC_ROUTES = ("/", "/evidence", "/corpus", "/evaluation", "/how-it-works")
VIEWPORTS = (verify_responsive.DESKTOP, verify_responsive.MOBILE)


@pytest.fixture(scope="module")
def page():
    with verify_responsive.serve() as base, playwright_api.sync_playwright() as driver:
        try:
            browser = driver.chromium.launch()
        except playwright_api.Error as error:
            pytest.skip(f"chromium is not installed: {error}")
        rendered = browser.new_page()
        rendered.base_url = base
        try:
            yield rendered
        finally:
            browser.close()


@pytest.mark.parametrize("viewport", VIEWPORTS, ids=lambda item: f"{item['width']}px")
@pytest.mark.parametrize("route", PUBLIC_ROUTES)
def test_public_route_does_not_overflow_horizontally(page, route, viewport):
    page.set_viewport_size(viewport)
    page.goto(f"{page.base_url}{route}", wait_until="load")
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow == 0, (
        f"{route} overflows by {overflow}px at {viewport['width']}px; "
        "the workspace is required to fit its viewport"
    )
