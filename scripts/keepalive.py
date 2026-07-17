"""
Visit the Streamlit app in a headless browser to keep it awake.

A plain HTTP GET (curl/requests) only downloads the static HTML shell;
the Python process never starts because Streamlit requires a WebSocket
connection initiated by JavaScript.  Playwright solves this by running
real Chromium, executing the JS, and — if the app is already asleep —
clicking the "Yes, get this app back up!" button automatically.
"""

import os
import sys
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

WAKE_BUTTON_TEXT = "Yes, get this app back up!"
APP_SELECTOR = 'section[data-testid="stApp"]'
NAVIGATE_TIMEOUT_MS = 60_000
WAKE_TIMEOUT_MS = 120_000
SETTLE_SECONDS = 5


def main() -> None:
    url = os.environ.get("STREAMLIT_APP_URL", "").strip()
    if not url:
        print("ERROR: STREAMLIT_APP_URL is not set.")
        sys.exit(1)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        page = browser.new_page()

        try:
            print(f"Navigating to {url} ...")
            page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATE_TIMEOUT_MS)

            wake_btn = page.get_by_role("button", name=WAKE_BUTTON_TEXT)
            if wake_btn.count() > 0:
                print("App is asleep — clicking wake button ...")
                wake_btn.first.click()
                print("Waiting for the app to fully load ...")
                page.wait_for_selector(APP_SELECTOR, timeout=WAKE_TIMEOUT_MS)
                page.wait_for_timeout(SETTLE_SECONDS * 1000)
                print("App woke up successfully.")
            else:
                try:
                    page.wait_for_selector(APP_SELECTOR, timeout=NAVIGATE_TIMEOUT_MS)
                    page.wait_for_timeout(SETTLE_SECONDS * 1000)
                    print("App is already awake — session registered.")
                except PwTimeout:
                    print("WARNING: Could not confirm app loaded, but no wake button found.")

        except Exception as exc:
            print(f"WARNING: keepalive encountered an error: {exc}")

        finally:
            browser.close()


if __name__ == "__main__":
    main()
