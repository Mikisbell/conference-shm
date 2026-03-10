#!/usr/bin/env python3
"""
PEER NGA-West2 Downloader via Playwright (headless Chromium)
=============================================================
Hybrid approach: curl handles login (avoids bot detection on login page),
then passes session cookies to Playwright which navigates the React SPA
and intercepts the actual AT2 download API calls.

Requirements:
    pip install playwright
    playwright install chromium --with-deps

Usage:
    python3 tools/peer_playwright.py --rsn 766
    python3 tools/peer_playwright.py --rsn 766 1158 4517
    python3 tools/peer_playwright.py --rsn 766 --cookie-jar /tmp/peer_cookies.txt

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


def _parse_netscape_cookies(jar_path: Path) -> list[dict]:
    """Parse curl Netscape-format cookie jar into Playwright cookie list."""
    cookies = []
    for line in jar_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _subdomains, path, secure, _expires, name, value = parts[:7]
        cookies.append({
            "name": name,
            "value": value,
            "domain": domain.lstrip("."),
            "path": path,
            "secure": secure.upper() == "TRUE",
        })
    return cookies


def _curl_login(email: str, password: str, cookie_jar: Path, verbose: bool = True) -> bool:
    """
    Login via curl (avoids bot detection on login page).
    Saves session cookies to cookie_jar.
    Returns True on success.
    """
    import subprocess
    import re
    import tempfile
    import urllib.parse

    UA = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def _run(url, *, data=None, referer=None):
        cmd = [
            "curl", "--silent", "--show-error", "--globoff",
            "--max-time", "360",   # PEER sign_in SSL/TLS can take 3-5 min
            "--connect-timeout", "60",
            "--cookie", str(cookie_jar),
            "--cookie-jar", str(cookie_jar),
            "--user-agent", UA,
            "--header", "Accept-Language: en-US,en;q=0.9",
            "--header", "Accept: text/html,application/xhtml+xml,*/*",
            "--write-out", "\n__STATUS__:%{http_code}",
            "--ipv4", "--location",
        ]
        if referer:
            cmd += ["--referer", referer]
        _post_file = None
        if data:
            body = urllib.parse.urlencode(data)
            _post_file = Path(tempfile.mktemp(suffix=".post"))
            _post_file.write_text(body)
            cmd += ["--data", f"@{_post_file}",
                    "--header", "Content-Type: application/x-www-form-urlencoded"]
        cmd.append(url)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=400)
        if _post_file and _post_file.exists():
            _post_file.unlink()
        body_out = result.stdout
        status = 0
        if "__STATUS__:" in body_out:
            parts = body_out.rsplit("__STATUS__:", 1)
            body_out = parts[0].rstrip("\n")
            try:
                status = int(parts[1].strip())
            except ValueError:
                pass
        if result.returncode != 0:
            return -1, result.stderr.strip() or f"(curl exit={result.returncode})"
        return status, body_out

    sign_in_url = f"{PEER_BASE}/members/sign_in"
    if verbose:
        print("[PEER] curl: fetching login page…")
    status, html = _run(sign_in_url)
    if status not in (200, 302) or not html:
        print(f"[PEER] curl: login page failed (HTTP {status})", file=sys.stderr)
        return False

    # Extract CSRF token
    m = re.search(
        r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)["\']', html
    )
    if not m:
        m = re.search(
            r'<input[^>]+name=["\']authenticity_token["\'][^>]+value=["\']([^"\']+)["\']', html
        )
    csrf = m.group(1) if m else ""

    spinner_match = re.search(r'name="spinner"[^>]+value="([^"]+)"', html)
    spinner_value = spinner_match.group(1) if spinner_match else ""

    if verbose:
        print("[PEER] curl: posting credentials…")
    status2, body2 = _run(
        sign_in_url,
        data={
            "authenticity_token": csrf,
            "member[email]": email,
            "member[password]": password,
            "member[remember_me]": "0",
            "member[subtitle]": "",
            "spinner": spinner_value,
            "commit": "Log in",
        },
        referer=sign_in_url,
    )

    if status2 == -1:
        print(f"[PEER] curl: login POST error: {body2}", file=sys.stderr)
        return False
    if "Invalid Email or password" in body2:
        print("[PEER] curl: invalid credentials", file=sys.stderr)
        return False

    if verbose:
        print("[PEER] curl: login POST done — checking cookie jar")
        if cookie_jar.exists():
            raw = cookie_jar.read_text()
            lines = [l for l in raw.splitlines() if l.strip() and not l.startswith("#")]
            print(f"[PEER] curl: cookie jar has {len(lines)} non-comment line(s)")
            for line in lines[:5]:
                parts_c = line.split("\t")
                name = parts_c[5] if len(parts_c) >= 6 else "?"
                domain = parts_c[0] if parts_c else "?"
                print(f"  cookie: name={name!r} domain={domain!r}")
        else:
            print("[PEER] curl: cookie jar file does NOT exist!")

    # Verify auth by hitting a protected page (members/edit = profile, redirects to sign_in if not logged in)
    status_verify, body_verify = _run(f"{PEER_BASE}/members/edit")
    if verbose:
        print(f"[PEER] curl: auth check GET /members/edit → HTTP {status_verify}, {len(body_verify)} chars")
        if "sign_in" in body_verify[:3000].lower():
            print("[PEER] curl: WARN — auth check shows sign_in → login may have FAILED")
        elif "edit" in body_verify[:3000].lower() or "profile" in body_verify[:3000].lower():
            print("[PEER] curl: CONFIRMED authenticated (edit page returned)")
        else:
            snippet = body_verify[:300].replace('\n', ' ')
            print(f"[PEER] curl: body snippet: {snippet}")
    return True


def download_records_playwright(
    rsns: list[int],
    out_dir: Path = DEFAULT_OUT,
    cookie_jar: Path | None = None,
    verbose: bool = True,
) -> dict[int, list[Path]]:
    """
    Download AT2 records using Playwright headless browser.
    If cookie_jar is provided, injects those cookies (from curl login) instead
    of doing Playwright-based login (which triggers bot detection).
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print(
            "ERROR: playwright not installed.\n"
            "  pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[int, list[Path]] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        ctx = browser.new_context(
            accept_downloads=True,
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # Inject curl session cookies (bypasses bot-detected login page)
        if cookie_jar and cookie_jar.exists():
            pw_cookies = _parse_netscape_cookies(cookie_jar)
            if verbose:
                print(f"[PEER] Playwright: parsed {len(pw_cookies)} cookies from jar")
                for c in pw_cookies:
                    print(f"  cookie: {c['name']} (domain={c['domain']})")
            if pw_cookies:
                ctx.add_cookies(pw_cookies)
                # Verify cookies are loaded
                loaded = ctx.cookies()
                if verbose:
                    print(f"[PEER] Playwright: context has {len(loaded)} cookie(s) after injection")
        else:
            # Fallback: Playwright login (may be detected, but try anyway)
            email, password = load_credentials()
            if verbose:
                print("[PEER] Playwright: doing browser login…")
            page_login = ctx.new_page()
            page_login.goto(f"{PEER_BASE}/members/sign_in", timeout=360_000)
            page_login.fill("input#member_email", email)
            page_login.fill("input#member_password", password)
            page_login.click("input[name='commit']")
            page_login.wait_for_load_state("networkidle", timeout=60_000)
            login_cookies = ctx.cookies()
            if verbose:
                print(f"[PEER] Playwright: {len(login_cookies)} cookie(s) after login form")
                for c in login_cookies:
                    print(f"  cookie: {c['name']} = {c['value'][:20]}...")
            page_login.close()
            if verbose:
                print("[PEER] Playwright: login page done")

        # ----- DOWNLOAD EACH RSN -----
        page = ctx.new_page()
        intercepted_at2: list[str] = []

        def _on_request(req):
            url = req.url
            if any(k in url for k in [".AT2", ".at2", "download", "flatfile"]):
                intercepted_at2.append(url)

        def _on_response(resp):
            url = resp.url
            cd = resp.headers.get("content-disposition", "")
            ct = resp.headers.get("content-type", "")
            if ".AT2" in url or ".at2" in url or "AT2" in cd or "at2" in cd.lower():
                intercepted_at2.append(url)

        page.on("request", _on_request)
        page.on("response", _on_response)

        for rsn in rsns:
            rsn_files: list[Path] = []
            intercepted_at2.clear()

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
                print(f"[PEER] RSN{rsn}: navigating to spectras page…")

            try:
                page.goto(
                    f"{PEER_BASE}/spectras/new?sourceDb_flag=1&rsn={rsn}",
                    timeout=120_000,
                    wait_until="domcontentloaded",
                )

                # Wait for React to render content (max 30s)
                # Look for download button, AT2 links, or the "Get PEER NGA" button
                for selector in [
                    "a[href*='.AT2']",
                    "a[href*='download']",
                    "button:has-text('Get PEER NGA')",
                    "input[value*='Get PEER']",
                    "#get-flatfile-wrapper",
                    ".record-download",
                    "table.records-table",
                ]:
                    try:
                        page.wait_for_selector(selector, timeout=5_000)
                        if verbose:
                            print(f"[PEER] RSN{rsn}: found selector: {selector}")
                        break
                    except PWTimeout:
                        continue

                # Also wait a bit more for React to fully render
                page.wait_for_timeout(3_000)

                # Extract all AT2-related links and buttons
                at2_links = page.evaluate("""
                    () => {
                        const links = [];
                        document.querySelectorAll('a, button, input[type="submit"]').forEach(el => {
                            const h = (el.href || el.action || '').toLowerCase();
                            const t = (el.textContent || el.value || '').toLowerCase().trim();
                            const d = (el.getAttribute('data-url') || '').toLowerCase();
                            const onclick = (el.getAttribute('onclick') || '').toLowerCase();
                            if (h.includes('.at2') || h.includes('download') ||
                                t.includes('.at2') || t.includes('get peer') ||
                                t.includes('download') || d.includes('.at2') ||
                                onclick.includes('at2') || onclick.includes('download')) {
                                links.push({
                                    href: el.href || el.getAttribute('data-url') || el.getAttribute('action') || '',
                                    text: (el.textContent || el.value || '').trim().slice(0, 80),
                                    tag: el.tagName,
                                    onclick: el.getAttribute('onclick') || ''
                                });
                            }
                        });
                        // Also check for React data embedded in page
                        const scripts = Array.from(document.querySelectorAll('script:not([src])'));
                        const at2Urls = [];
                        scripts.forEach(s => {
                            const text = s.textContent || '';
                            const matches = text.match(/https?[^"']*\\.AT2[^"']*/gi) || [];
                            at2Urls.push(...matches.slice(0, 5));
                        });
                        return {links, at2Urls};
                    }
                """)

                if isinstance(at2_links, dict):
                    link_list = at2_links.get("links", [])
                    at2_script_urls = at2_links.get("at2Urls", [])
                else:
                    link_list = at2_links
                    at2_script_urls = []

                if verbose:
                    if intercepted_at2:
                        print(f"[PEER] RSN{rsn}: intercepted {len(intercepted_at2)} AT2/download request(s):")
                        for u in intercepted_at2[:5]:
                            print(f"  → {u[:100]}")
                    if link_list:
                        print(f"[PEER] RSN{rsn}: found {len(link_list)} element(s) with download context:")
                        for lnk in link_list[:5]:
                            print(f"  [{lnk['tag']}] {lnk['text']!r} href={lnk.get('href','')[:80]}")
                    if at2_script_urls:
                        print(f"[PEER] RSN{rsn}: AT2 URLs in page scripts:")
                        for u in at2_script_urls[:5]:
                            print(f"  script: {u[:100]}")
                    if not intercepted_at2 and not link_list and not at2_script_urls:
                        body_text = page.evaluate("() => document.body?.innerText?.slice(0, 600) || ''")
                        print(f"[PEER] RSN{rsn}: no download elements found. Page snippet:")
                        print(f"  {body_text[:400]}")

                # Priority 1: Try intercepted AT2 URLs (most reliable)
                for at2_url in list(intercepted_at2) + at2_script_urls:
                    if ".AT2" not in at2_url.upper():
                        continue
                    try:
                        with page.expect_download(timeout=60_000) as dl_info:
                            page.goto(at2_url, wait_until="domcontentloaded", timeout=60_000)
                        dl = dl_info.value
                        fname = dl.suggested_filename or f"RSN{rsn}.AT2"
                        dest = out_dir / fname
                        dl.save_as(dest)
                        if verbose:
                            print(f"[PEER] RSN{rsn}: saved {fname} ({dest.stat().st_size // 1024}KB)")
                        rsn_files.append(dest)
                        break
                    except Exception as exc:
                        if verbose:
                            print(f"[PEER] RSN{rsn}: intercepted URL error: {exc}")

                # Priority 2: Try clicking download buttons
                if not rsn_files:
                    for lnk in link_list[:4]:
                        href = lnk.get("href", "")
                        tag = lnk.get("tag", "")
                        text = lnk.get("text", "").lower()
                        if not href and "button" not in tag.lower():
                            continue
                        try:
                            if href and href != page.url and ".AT2" in href.upper():
                                with page.expect_download(timeout=60_000) as dl_info:
                                    page.goto(href, timeout=60_000, wait_until="domcontentloaded")
                                dl = dl_info.value
                                fname = dl.suggested_filename or f"RSN{rsn}.AT2"
                                dest = out_dir / fname
                                dl.save_as(dest)
                                rsn_files.append(dest)
                                if verbose:
                                    print(f"[PEER] RSN{rsn}: saved via link: {fname}")
                                break
                            elif "get peer" in text or "download" in text:
                                # Try clicking the button and capturing any download
                                with page.expect_download(timeout=30_000) as dl_info:
                                    page.click(f"text={lnk['text'][:30]}")
                                dl = dl_info.value
                                fname = dl.suggested_filename or f"RSN{rsn}.AT2"
                                dest = out_dir / fname
                                dl.save_as(dest)
                                rsn_files.append(dest)
                                if verbose:
                                    print(f"[PEER] RSN{rsn}: saved via click: {fname}")
                                break
                        except PWTimeout:
                            pass
                        except Exception as exc:
                            if verbose:
                                print(f"[PEER] RSN{rsn}: link/click error: {exc}")

            except PWTimeout:
                print(f"[PEER] RSN{rsn}: page timeout")
            except Exception as exc:
                print(f"[PEER] RSN{rsn}: ERROR — {exc}")

            if not rsn_files:
                print(
                    f"[PEER] RSN{rsn}: automatic download failed.\n"
                    f"  Manual: {PEER_BASE}/spectras/new?sourceDb_flag=1&rsn={rsn}"
                )

            results[rsn] = rsn_files
            time.sleep(1)

        page.close()
        browser.close()

    return results


def main() -> None:
    p = argparse.ArgumentParser(
        description="Download PEER NGA-West2 AT2 records via Playwright"
    )
    p.add_argument("--rsn", nargs="+", type=int, required=True)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--cookie-jar", type=Path, default=None,
                   help="Curl Netscape cookie jar from prior login (skips Playwright login)")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    # If no cookie jar provided, do curl login first then pass cookies
    cookie_jar = args.cookie_jar
    if cookie_jar is None:
        import tempfile
        cookie_jar = Path(tempfile.mktemp(suffix="_peer_cookies.txt"))
        email, password = load_credentials()
        if not _curl_login(email, password, cookie_jar, verbose=not args.quiet):
            print("ERROR: curl login failed", file=sys.stderr)
            sys.exit(1)

    results = download_records_playwright(
        args.rsn, args.out,
        cookie_jar=cookie_jar,
        verbose=not args.quiet,
    )
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
