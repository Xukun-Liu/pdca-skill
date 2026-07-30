"""Browser inspection: screenshot docs page and test interactions."""
import os
import sys
import tempfile
import threading
import time

from playwright.sync_api import sync_playwright


def main():
    port = 51235
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from server_lite.app import create_app

    app = create_app({"TESTING": True})
    server_thread = threading.Thread(
        target=app.run,
        kwargs={"host": "127.0.0.1", "port": port, "debug": False, "use_reloader": False},
        daemon=True,
    )
    server_thread.start()

    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            import urllib.request
            with urllib.request.urlopen(url + "/api/health", timeout=1) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.5)
    else:
        raise RuntimeError("server did not start")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(url)
        page.wait_for_load_state("networkidle")

        # Screenshot 1: initial dashboard
        page.screenshot(path="tmp_inspect_01_dashboard.png", full_page=True)

        # Click docs page
        page.click('[data-page="docs"]')
        page.wait_for_selector(".project-item", timeout=5000)
        page.wait_for_timeout(500)
        page.screenshot(path="tmp_inspect_02_docs.png", full_page=True)

        # Get project list for debugging
        projects = page.evaluate("""
            () => Array.from(document.querySelectorAll('.project-item')).map(el => ({
                name: el.dataset.name,
                text: el.textContent.trim().substring(0, 100)
            }))
        """)
        print("Projects found:", projects)

        # Click carnew-shouji if exists
        carnew = page.query_selector('.project-item[data-name="carnew-shouji"]')
        if carnew:
            print("Clicking carnew-shouji...")
            carnew.click()
            page.wait_for_timeout(800)
            page.screenshot(path="tmp_inspect_03_carnew_clicked.png", full_page=True)

            # Check active state and content
            active = page.evaluate("() => document.querySelector('.project-item.active')?.dataset.name")
            content = page.evaluate("() => document.getElementById('docsContent')?.innerText?.substring(0, 200)")
            console_logs = page.evaluate("() => { try { return window.console_logs || []; } catch(e) { return []; } }")
            print(f"Active project: {active}")
            print(f"Content preview: {content}")
        else:
            print("carnew-shouji not found in DOM")
            # Click first project
            first = page.query_selector('.project-item')
            if first:
                print("Clicking first project...")
                first.click()
                page.wait_for_timeout(800)
                page.screenshot(path="tmp_inspect_03_first_clicked.png", full_page=True)

        # Check console for errors
        logs = []
        page.on("console", lambda msg: logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: logs.append(f"[pageerror] {err}"))
        page.wait_for_timeout(500)

        print("\n--- Console logs ---")
        for log in logs:
            print(log)

        browser.close()

    print("\nScreenshots saved: tmp_inspect_01_dashboard.png, tmp_inspect_02_docs.png, tmp_inspect_03_*.png")


if __name__ == "__main__":
    main()
