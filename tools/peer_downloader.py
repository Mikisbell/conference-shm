#!/usr/bin/env python3
"""
PEER NGA-West2 Automated Downloader
====================================
Downloads seismic records (.AT2) from PEER NGA-West2 using session-based
web scraping. Credentials are read from .env (PEER_EMAIL / PEER_PASSWORD).

Usage:
    python3 tools/peer_downloader.py --rsn 766
    python3 tools/peer_downloader.py --rsn 766 1158 4517
    python3 tools/peer_downloader.py --rsn 766 --out db/excitation/records/

Credentials setup:
    Add to .env (gitignored):
        PEER_EMAIL=your@email.com
        PEER_PASSWORD=yourpassword

PEER NGA-West2: https://ngawest2.berkeley.edu
Registration is free at: https://ngawest2.berkeley.edu/users/sign_up
"""

import argparse
import os
import re
import sys
import time
import zipfile
from pathlib import Path
from io import BytesIO

# ---------------------------------------------------------------------------
# Optional imports — fail with clear message if missing
# ---------------------------------------------------------------------------
try:
    import requests
    from requests import Session
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

try:
    from dotenv import load_dotenv  # type: ignore
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "db" / "excitation" / "records"

PEER_BASE = "https://ngawest2.berkeley.edu"
PEER_SIGN_IN = f"{PEER_BASE}/users/sign_in"
PEER_SIGN_OUT = f"{PEER_BASE}/users/sign_out"
PEER_SEARCH_URL = f"{PEER_BASE}/spectras/new"
PEER_SEARCH_RESULTS = f"{PEER_BASE}/spectras"

# User-agent that mimics a real browser (PEER rejects plain Python UA)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------

def load_credentials() -> tuple[str, str]:
    """Read PEER_EMAIL and PEER_PASSWORD from environment or .env file."""
    if _HAS_DOTENV:
        env_path = ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)

    email = os.environ.get("PEER_EMAIL", "")
    password = os.environ.get("PEER_PASSWORD", "")

    if not email or not password:
        print(
            "ERROR: PEER credentials not found.\n"
            "Add to .env (gitignored):\n"
            "  PEER_EMAIL=your@email.com\n"
            "  PEER_PASSWORD=yourpassword\n"
            "Register free at: https://ngawest2.berkeley.edu/users/sign_up",
            file=sys.stderr,
        )
        sys.exit(1)

    return email, password


# ---------------------------------------------------------------------------
# CSRF token extraction
# ---------------------------------------------------------------------------

def _extract_csrf(html: str) -> str:
    """Extract Rails authenticity_token from HTML."""
    # <meta name="csrf-token" content="...">
    m = re.search(r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)["\']', html)
    if m:
        return m.group(1)
    # fallback: hidden input
    m = re.search(r'<input[^>]+name=["\']authenticity_token["\'][^>]+value=["\']([^"\']+)["\']', html)
    if m:
        return m.group(1)
    raise ValueError("Could not extract CSRF token from page")


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

class PeerSession:
    """Authenticated requests session to PEER NGA-West2."""

    def __init__(self, email: str, password: str, verbose: bool = True):
        self.email = email
        self.password = password
        self.verbose = verbose
        self.session = Session()
        self.session.headers.update(HEADERS)
        self._logged_in = False

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[PEER] {msg}")

    def login(self) -> bool:
        """Perform Rails session login. Returns True on success."""
        self._log("Fetching login page…")
        resp = self.session.get(PEER_SIGN_IN, timeout=60)
        resp.raise_for_status()

        try:
            csrf = _extract_csrf(resp.text)
        except ValueError as exc:
            self._log(f"CSRF extraction failed: {exc}")
            return False

        payload = {
            "authenticity_token": csrf,
            "user[email]": self.email,
            "user[password]": self.password,
            "user[remember_me]": "0",
            "commit": "Sign in",
        }

        self._log("Posting credentials…")
        resp2 = self.session.post(
            PEER_SIGN_IN,
            data=payload,
            allow_redirects=True,
            timeout=60,
        )

        # PEER redirects to root on success; login page reloads on failure
        if "sign_in" in resp2.url and "Invalid" in resp2.text:
            self._log("Login failed — check PEER_EMAIL / PEER_PASSWORD")
            return False

        # Check for successful login indicators
        if resp2.status_code == 200 and (
            "sign_out" in resp2.text.lower()
            or "log out" in resp2.text.lower()
            or resp2.url == f"{PEER_BASE}/"
            or resp2.url == PEER_BASE
        ):
            self._log("Login successful")
            self._logged_in = True
            return True

        # Some redirects end at dashboard or another page — treat as success
        if resp2.status_code in (200, 302) and "sign_in" not in resp2.url:
            self._log(f"Login likely successful (redirected to {resp2.url})")
            self._logged_in = True
            return True

        self._log(f"Unexpected response after login: {resp2.status_code} {resp2.url}")
        return False

    def download_rsn(self, rsn: int, out_dir: Path) -> list[Path]:
        """
        Download .AT2 file(s) for a given RSN.
        Returns list of paths to downloaded files.
        """
        if not self._logged_in:
            raise RuntimeError("Not logged in — call login() first")

        out_dir.mkdir(parents=True, exist_ok=True)

        # Check if already downloaded
        existing = list(out_dir.glob(f"RSN{rsn}_*.AT2")) + list(out_dir.glob(f"RSN{rsn}.AT2"))
        if existing:
            self._log(f"RSN{rsn}: already in {out_dir}, skipping")
            return existing

        self._log(f"RSN{rsn}: initiating search…")

        # Step 1: POST search by RSN
        search_resp = self.session.get(
            PEER_SEARCH_URL,
            params={"sourceDb_flag": "1", "rsn": str(rsn)},
            timeout=30,
        )
        search_resp.raise_for_status()

        # Step 2: Look for download link in response or follow to results
        files = self._find_and_download(rsn, search_resp, out_dir)
        return files

    def _find_and_download(self, rsn: int, page_resp, out_dir: Path) -> list[Path]:
        """Parse page response to find download link(s) for RSN."""
        html = page_resp.text

        # Pattern 1: direct download link to ZIP
        zip_links = re.findall(
            r'href=["\']([^"\']*(?:download|get_file|zip)[^"\']*)["\']',
            html,
            re.IGNORECASE,
        )

        # Pattern 2: PEER uses a form POST to trigger download
        # Look for form action with download
        form_actions = re.findall(
            r'action=["\']([^"\']*download[^"\']*)["\']',
            html,
            re.IGNORECASE,
        )

        # Pattern 3: individual AT2 links
        at2_links = re.findall(
            r'href=["\']([^"\']*\.AT2[^"\']*)["\']',
            html,
            re.IGNORECASE,
        )

        self._log(f"RSN{rsn}: found {len(zip_links)} zip links, {len(at2_links)} .AT2 links")

        downloaded = []

        # Try direct .AT2 links first
        for link in at2_links[:3]:  # limit to first 3 components (H1, H2, V)
            url = link if link.startswith("http") else f"{PEER_BASE}{link}"
            fname = url.split("/")[-1].split("?")[0] or f"RSN{rsn}.AT2"
            dest = out_dir / fname
            self._log(f"RSN{rsn}: downloading {fname}…")
            r = self.session.get(url, timeout=60)
            if r.status_code == 200 and len(r.content) > 100:
                dest.write_bytes(r.content)
                downloaded.append(dest)
                self._log(f"RSN{rsn}: saved {dest.name} ({len(r.content)//1024}KB)")

        # Try ZIP links
        if not downloaded:
            for link in zip_links[:2]:
                url = link if link.startswith("http") else f"{PEER_BASE}{link}"
                self._log(f"RSN{rsn}: downloading ZIP from {url}…")
                r = self.session.get(url, timeout=120)
                if r.status_code == 200 and len(r.content) > 100:
                    extracted = _extract_zip(r.content, out_dir, rsn)
                    downloaded.extend(extracted)
                    if extracted:
                        break

        if not downloaded:
            # Last resort: generate manual URL for user
            manual = f"{PEER_BASE}/spectras/new?sourceDb_flag=1&rsn={rsn}"
            self._log(
                f"RSN{rsn}: automatic download failed.\n"
                f"  Manual download: {manual}\n"
                f"  Extract .AT2 to: {out_dir}"
            )

        return downloaded

    def logout(self) -> None:
        """Politely sign out."""
        if self._logged_in:
            try:
                self.session.delete(PEER_SIGN_OUT, timeout=10)
            except Exception:
                pass
            self._logged_in = False


# ---------------------------------------------------------------------------
# ZIP extraction helper
# ---------------------------------------------------------------------------

def _extract_zip(data: bytes, out_dir: Path, rsn: int) -> list[Path]:
    """Extract .AT2 files from a ZIP archive."""
    extracted = []
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            for name in zf.namelist():
                if name.upper().endswith(".AT2"):
                    # Flatten directory structure
                    fname = Path(name).name
                    dest = out_dir / fname
                    dest.write_bytes(zf.read(name))
                    extracted.append(dest)
    except zipfile.BadZipFile:
        pass
    return extracted


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_records(
    rsns: list[int],
    out_dir: Path = DEFAULT_OUT,
    verbose: bool = True,
) -> dict[int, list[Path]]:
    """
    Download multiple RSN records to out_dir.
    Returns {rsn: [paths]} for each RSN.
    Credentials are read from PEER_EMAIL / PEER_PASSWORD env vars or .env.
    """
    email, password = load_credentials()
    peer = PeerSession(email, password, verbose=verbose)

    if not peer.login():
        print("ERROR: PEER login failed", file=sys.stderr)
        sys.exit(1)

    results: dict[int, list[Path]] = {}
    for rsn in rsns:
        try:
            files = peer.download_rsn(rsn, out_dir)
            results[rsn] = files
            time.sleep(1)  # polite delay between requests
        except Exception as exc:
            print(f"[PEER] RSN{rsn}: ERROR — {exc}", file=sys.stderr)
            results[rsn] = []

    peer.logout()
    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download PEER NGA-West2 seismic records (.AT2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--rsn",
        nargs="+",
        type=int,
        required=True,
        help="RSN number(s) to download (e.g. --rsn 766 1158 4517)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output directory (default: {DEFAULT_OUT})",
    )
    p.add_argument("--quiet", action="store_true", help="Suppress progress messages")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    results = download_records(args.rsn, out_dir=args.out, verbose=not args.quiet)

    print("\n=== PEER Download Summary ===")
    total_files = 0
    for rsn, files in results.items():
        if files:
            print(f"  RSN{rsn}: {len(files)} file(s) → {', '.join(f.name for f in files)}")
            total_files += len(files)
        else:
            print(f"  RSN{rsn}: FAILED (check credentials or download manually)")
    print(f"Total: {total_files} .AT2 file(s) downloaded to {args.out}")


if __name__ == "__main__":
    main()
