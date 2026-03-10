#!/usr/bin/env python3
"""
PEER NGA-West2 Downloader via Playwright (headless Chromium)
=============================================================
Uses a real browser to navigate PEER's JavaScript-heavy interface.
This is the only reliable way to automate PEER downloads since the
AT2 download links are rendered dynamically via React/JS.

Requirements:
    pip install playwright
    playwright install chromium

Usage:
    python3 tools/peer_playwright.py --rsn 766
    python3 tools/peer_playwright.py --rsn 766 1158 4517

Credentials from .env (gitignored):
    PEER_EMAIL=your@email.com
    PEER_PASSWORD=yourpassword
"""

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "db" / "excitation" / "records"

PEER_BASE = "https://ngawest2.berkeley.edu"


def load_credentials() -> tuple[str, str]:
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
    email = os.environ.get("PEER_EMAIL", "")
    password = os.environ.get("PEER_PASSWORD", "")
    if not email or not password:
        print("ERROR: Set PEER_EMAIL and PEER_PASSWORD in .env", file=sys.stderr)
        sys.exit(1)
    return email, password


def download_records_playwright(
    rsns: list[int],
    out_dir: Path = DEFAULT_OUT,
    verbose: bool = True,
) -> dict[int, list[Path]]:
    """Download AT2 records using Playwright headless browser."""
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print(
            "ERROR: playwright not installed.\n"
            "  pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)

    email, password = load_credentials()
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[int, list[Path]] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()

        # ----- LOGIN -----
        if verbose:
            print(f"[PEER] Navigating to login page… (may take 3-5 min, PEER is slow)")
        # PEER sign_in page has very slow TLS/SSL response — needs 5min timeout
        page.goto(f"{PEER_BASE}/members/sign_in", timeout=360_000)
        page.fill("input#member_email", email)
        page.fill("input#member_password", password)
        page.click("input[name='commit']")
        page.wait_for_load_state("networkidle", timeout=60_000)

        if "sign_in" in page.url and "Invalid" in page.content():
            print("ERROR: PEER login failed — invalid credentials", file=sys.stderr)
            browser.close()
            return {rsn: [] for rsn in rsns}

        if verbose:
            print(f"[PEER] Login successful (at {page.url})")

        # ----- DOWNLOAD EACH RSN -----
        # Intercept network requests to find actual AT2 download API calls
        api_calls: list[str] = []
        page.on("request", lambda req: api_calls.append(req.url)
                if any(k in req.url for k in ["at2", "AT2", "download", "record", "flatfile"])
                else None)

        for rsn in rsns:
            rsn_files: list[Path] = []
            api_calls.clear()

            # Skip if already downloaded
            existing = (
                list(out_dir.glob(f"RSN{rsn}_*.AT2"))
                + list(out_dir.glob(f"RSN{rsn}.AT2"))
            )
            if existing:
                if verbose:
                    print(f"[PEER] RSN{rsn}: already downloaded, skipping")
                results[rsn] = existing
                continue

            if verbose:
                print(f"[PEER] RSN{rsn}: navigating…")

            try:
                # Use domcontentloaded (not networkidle) to avoid indefinite wait
                page.goto(
                    f"{PEER_BASE}/spectras/new?sourceDb_flag=1&rsn={rsn}",
                    timeout=120_000,
                    wait_until="domcontentloaded",
                )

                # Wait briefly for JS to inject download links (max 15s)
                try:
                    page.wait_for_selector(
                        "a[href*='.AT2'], a[href*='download'], button:has-text('Download')",
                        timeout=15_000,
                    )
                except PWTimeout:
                    pass  # links may not appear — continue anyway

                # Extract all links and buttons related to AT2 download
                at2_links = page.evaluate("""
                    () => {
                        const links = [];
                        document.querySelectorAll('a, button').forEach(el => {
                            const h = (el.href || '').toLowerCase();
                            const t = (el.textContent || '').toLowerCase();
                            const d = (el.getAttribute('data-url') || '').toLowerCase();
                            if (h.includes('.at2') || h.includes('download') ||
                                t.includes('.at2') || d.includes('.at2')) {
                                links.push({
                                    href: el.href || el.getAttribute('data-url') || '',
                                    text: el.textContent.trim().slice(0, 60),
                                    tag: el.tagName
                                });
                            }
                        });
                        return links;
                    }
                """)

                # Log all intercepted API calls
                if api_calls:
                    print(f"[PEER] RSN{rsn}: intercepted API calls:")
                    for u in api_calls[:8]:
                        print(f"  API: {u}")

                if at2_links:
                    print(f"[PEER] RSN{rsn}: found {len(at2_links)} link(s):")
                    for lnk in at2_links[:5]:
                        print(f"  → [{lnk['tag']}] {lnk['text']!r} href={lnk['href'][:80]}")
                else:
                    # No links found — print page text snippet for diagnosis
                    body_text = page.evaluate("() => document.body?.innerText?.slice(0, 500) || ''")
                    print(f"[PEER] RSN{rsn}: no download links found. Page snippet:")
                    print(f"  {body_text[:300]}")

                # Try downloading via found links
                for lnk in at2_links[:3]:
                    href = lnk.get("href", "")
                    if not href or href == page.url:
                        continue
                    try:
                        with page.expect_download(timeout=60_000) as dl_info:
                            page.goto(href, timeout=60_000, wait_until="domcontentloaded")
                        download = dl_info.value
                        fname = download.suggested_filename or f"RSN{rsn}.AT2"
                        dest = out_dir / fname
                        download.save_as(dest)
                        if verbose:
                            print(f"[PEER] RSN{rsn}: saved {fname} ({dest.stat().st_size//1024}KB)")
                        rsn_files.append(dest)
                    except PWTimeout:
                        pass
                    except Exception as exc:
                        print(f"[PEER] RSN{rsn}: link error: {exc}")
                    if rsn_files:
                        break

                # Try intercepted API calls that look like direct AT2 URLs
                if not rsn_files:
                    for api_url in api_calls:
                        if ".AT2" in api_url or ".at2" in api_url:
                            try:
                                with page.expect_download(timeout=30_000) as dl_info:
                                    page.goto(api_url, wait_until="domcontentloaded")
                                download = dl_info.value
                                fname = download.suggested_filename or f"RSN{rsn}.AT2"
                                dest = out_dir / fname
                                download.save_as(dest)
                                rsn_files.append(dest)
                                print(f"[PEER] RSN{rsn}: saved via API intercept: {fname}")
                                break
                            except Exception:
                                pass

            except PWTimeout:
                print(f"[PEER] RSN{rsn}: page timeout after 2 minutes")
            except Exception as exc:
                print(f"[PEER] RSN{rsn}: ERROR — {exc}")

            if not rsn_files:
                print(
                    f"[PEER] RSN{rsn}: automatic download failed.\n"
                    f"  Manual: {PEER_BASE}/spectras/new?sourceDb_flag=1&rsn={rsn}"
                )

            results[rsn] = rsn_files
            time.sleep(1)

        browser.close()

    return results


def main() -> None:
    p = argparse.ArgumentParser(
        description="Download PEER NGA-West2 AT2 records via Playwright"
    )
    p.add_argument("--rsn", nargs="+", type=int, required=True)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    results = download_records_playwright(args.rsn, args.out, verbose=not args.quiet)
    print("\n=== PEER Playwright Summary ===")
    total = 0
    for rsn, files in results.items():
        if files:
            print(f"  RSN{rsn}: {len(files)} file(s) → {', '.join(f.name for f in files)}")
            total += len(files)
        else:
            print(f"  RSN{rsn}: FAILED — {PEER_BASE}/spectras/new?sourceDb_flag=1&rsn={rsn}")
    print(f"Total: {total} .AT2 file(s) → {args.out}")


if __name__ == "__main__":
    main()
