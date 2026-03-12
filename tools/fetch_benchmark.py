#!/usr/bin/env python3
"""
tools/fetch_benchmark.py — Ground Motion Record Manager (EIU)
=============================================================
Verify and auto-download ground motion records for the active project.

On-demand philosophy: only download what the current paper needs.
The 27 GB NGA-West2 database is never fully downloaded. Per project:
  - flatfile (~50 MB index/catalog) → ~/.belico-cache/ shared across clones
  - individual .AT2 records (~100-500 KB each) → db/excitation/records/

Download sources (tried in order, all free/no-auth):
  1. CESMD REST API  (strongmotioncenter.org — NGA-West2 + COSMOS)
  2. ESM  (esm-db.eu — European + global, AT2-compatible)
  3. Manual fallback — prints exact PEER URL with RSN pre-filled

Usage:
    python3 tools/fetch_benchmark.py                     # Status report
    python3 tools/fetch_benchmark.py --auto              # Download missing records
    python3 tools/fetch_benchmark.py --verify            # Validate .AT2 headers
    python3 tools/fetch_benchmark.py --scan              # List all records found
    python3 tools/fetch_benchmark.py --update-manifest   # Sync manifest with disk
    python3 tools/fetch_benchmark.py --download-flatfile # Download NGA-W2 catalog
"""

import argparse
import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

ROOT = Path(__file__).resolve().parent.parent
RECORDS_DIR = ROOT / "db" / "excitation" / "records"
FLATFILES_DIR = ROOT / "db" / "excitation" / "flatfiles"
MANIFEST_PATH = ROOT / "db" / "manifest.yaml"

# Shared cache across all clones — flatfile lives here
BELICO_CACHE = Path.home() / ".belico-cache"
FLATFILE_CACHE = BELICO_CACHE / "nga_west2_flatfile.csv"
FLATFILE_SYMLINK = FLATFILES_DIR / "nga_west2_flatfile.csv"

PEER_URL = "https://ngawest2.berkeley.edu/"

# CESMD REST API (free, no authentication required)
CESMD_API = "https://strongmotioncenter.org/wserv/records/query"
CESMD_TIMEOUT = 20  # seconds


# ---------------------------------------------------------------------------
# .AT2 validation
# ---------------------------------------------------------------------------

def validate_at2(filepath: Path) -> dict:
    """Validate a .AT2 file against PEER NGA-West2 format expectations."""
    result = {"valid": True, "filename": filepath.name, "errors": [], "npts": None, "dt": None}

    try:
        lines = filepath.read_text(errors="replace").splitlines()
    except Exception as exc:
        result["valid"] = False
        result["errors"].append(f"Cannot read file: {exc}")
        return result

    if len(lines) < 5:
        result["valid"] = False
        result["errors"].append(f"Too few lines ({len(lines)}); expected at least 5")
        return result

    header_keywords = ["PEER", "STRONG MOTION", "ACCELERATION", "COSMOS", "RECORD"]
    if not any(kw in lines[0].upper() for kw in header_keywords):
        result["errors"].append(f"Line 1 missing recognizable header (got: {lines[0][:60]})")
        result["valid"] = False

    meta_line = lines[3]
    npts_match = re.search(r"NPTS\s*=\s*(\d+)", meta_line, re.IGNORECASE)
    dt_match = re.search(r"DT\s*=\s*([\d.Ee+-]+)", meta_line, re.IGNORECASE)

    if not npts_match:
        result["errors"].append(f"Line 4 missing NPTS= (got: {meta_line[:60]})")
        result["valid"] = False
    else:
        result["npts"] = int(npts_match.group(1))

    if not dt_match:
        result["errors"].append(f"Line 4 missing DT= (got: {meta_line[:60]})")
        result["valid"] = False
    else:
        result["dt"] = float(dt_match.group(1))

    data_lines = lines[4:]
    if not data_lines:
        result["errors"].append("No data lines after header")
        result["valid"] = False
    else:
        num_pattern = re.compile(r"[+-]?\d+\.?\d*[Ee]?[+-]?\d*")
        checked = 0
        for dl in data_lines[:10]:
            stripped = dl.strip()
            if not stripped:
                continue
            nums = num_pattern.findall(stripped)
            if not nums:
                result["errors"].append(f"Non-numeric data line: {stripped[:60]}")
                result["valid"] = False
                break
            checked += 1
        if checked == 0 and not result["errors"]:
            result["errors"].append("Data section appears empty")
            result["valid"] = False

    # H1 fix: compare declared NPTS vs actual data value count
    if result.get("npts") is not None and data_lines:
        num_pattern_full = re.compile(r"[+-]?\d+\.?\d*[Ee]?[+-]?\d*")
        actual_values = sum(
            len(num_pattern_full.findall(dl))
            for dl in data_lines
            if dl.strip()
        )
        result["actual_count"] = actual_values
        declared = result["npts"]
        if actual_values < int(declared * 0.9):
            result["errors"].append(
                f"Data truncation detected: declared NPTS={declared}, "
                f"found ~{actual_values} values (file may be incomplete)"
            )
            result["valid"] = False

    return result


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------

def load_manifest() -> dict | None:
    if not MANIFEST_PATH.exists():
        return None
    if not HAS_YAML:
        print("ERROR: PyYAML not installed. pip install pyyaml")
        sys.exit(2)
    try:
        with open(MANIFEST_PATH) as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        print(f"ERROR: Cannot parse {MANIFEST_PATH}: {exc}")
        return None


def get_needed_records(manifest: dict) -> list[dict]:
    exc = manifest.get("excitation", {})
    needed = exc.get("records_needed", [])
    if not needed:
        return []
    out = []
    for entry in needed:
        if isinstance(entry, dict):
            out.append(entry)
        elif isinstance(entry, int):
            # Plain RSN integer: 766 → {"rsn": 766}
            out.append({"rsn": entry, "label": f"RSN{entry}"})
        elif isinstance(entry, str):
            # Could be "RSN766" or a filename
            rsn_match = re.match(r"(?:RSN)?(\d+)$", entry.strip(), re.IGNORECASE)
            if rsn_match:
                out.append({"rsn": int(rsn_match.group(1)), "label": entry})
            else:
                out.append({"filename": entry})
        else:
            out.append({"filename": str(entry)})
    return out


def scan_records() -> list[Path]:
    if not RECORDS_DIR.exists():
        RECORDS_DIR.mkdir(parents=True, exist_ok=True)
        return []
    files = sorted(RECORDS_DIR.glob("*.AT2"), key=lambda p: p.name.upper())
    files_lower = sorted(RECORDS_DIR.glob("*.at2"), key=lambda p: p.name.upper())
    seen = {f.name for f in files}
    for f in files_lower:
        if f.name not in seen:
            files.append(f)
    return sorted(files, key=lambda p: p.name.upper())


def match_record(needed: dict, present_names: set[str]) -> str | None:
    fname = needed.get("filename", "")
    if fname and fname in present_names:
        return fname
    rsn = needed.get("rsn")
    if rsn:
        prefix = f"RSN{rsn}"
        for name in present_names:
            if name.upper().startswith(prefix.upper()):
                return name
    return None


# ---------------------------------------------------------------------------
# Auto-download: CESMD REST API (primary, free)
# ---------------------------------------------------------------------------

def _cesmd_query(rsn: int) -> dict | None:
    """Query CESMD REST API for record metadata by PEER RSN."""
    url = f"{CESMD_API}?format=json&peer_rsn={rsn}&limit=5"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "belico-stack/1.0"})
        with urllib.request.urlopen(req, timeout=CESMD_TIMEOUT) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"    [CESMD] HTTP {e.code} ({e.reason}) for RSN {rsn}")
        return None
    except (urllib.error.URLError, OSError) as e:
        print(f"    [CESMD] Connection error for RSN {rsn}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"    [CESMD] Invalid JSON response for RSN {rsn}: {e}")
        return None


def _cesmd_download_record(rsn: int, dest_dir: Path) -> tuple[bool, str]:
    """Try to download a .AT2 record from CESMD by PEER RSN.

    NOTE (tested 2026-03-10): CESMD /wserv/records/query returns HTTP 400
    for peer_rsn queries. The records endpoint requires authentication.
    Only the events endpoint (/wserv/events/query) is public.
    Returns (False, reason) so cmd_auto falls through to manual PEER URL.
    """
    print(f"    [CESMD] Querying RSN {rsn}...")
    data = _cesmd_query(rsn)
    if data is None:
        return False, "CESMD records API requires authentication (HTTP 400)"

    records = data.get("records", [])
    if not records:
        return False, f"RSN {rsn} not in CESMD public catalog"

    for rec in records:
        at2_url = rec.get("at2_url") or rec.get("download_url") or rec.get("file_url")
        if not at2_url:
            continue
        filename = rec.get("filename") or f"RSN{rsn}_CESMD.AT2"
        if not filename.upper().endswith(".AT2"):
            filename += ".AT2"
        dest_path = dest_dir / filename
        try:
            print(f"    [CESMD] Downloading {filename}...")
            req = urllib.request.Request(at2_url, headers={"User-Agent": "belico-stack/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                dest_path.write_bytes(resp.read())
            vr = validate_at2(dest_path)
            if not vr["valid"]:
                dest_path.unlink(missing_ok=True)
                return False, f"Downloaded file invalid: {vr['errors']}"
            return True, filename
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
            dest_path.unlink(missing_ok=True)
            print(f"    [CESMD] Download failed ({at2_url[:60]}): {e}")
            continue

    return False, f"RSN {rsn} found in CESMD but no downloadable AT2 URL"


def _peer_manual_url(rsn: int) -> str:
    """Return direct search URL for a PEER RSN."""
    return f"https://ngawest2.berkeley.edu/spectras/new?sourceDb_flag=1&rsn={rsn}"


def _try_peer_download(rsn: int, verbose: bool = True) -> list:
    """Attempt automated PEER download if credentials are configured. Returns list of Paths."""
    try:
        from tools.peer_downloader import download_records  # type: ignore
    except ImportError:
        # Try relative import when running as script
        # (sys alias eliminated: sys is already imported at module level)
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "peer_downloader",
            Path(__file__).parent / "peer_downloader.py",
        )
        mod = importlib.util.module_from_spec(spec)  # type: ignore
        spec.loader.exec_module(mod)  # type: ignore
        download_records = mod.download_records

    import os
    email = os.environ.get("PEER_EMAIL", "")
    password = os.environ.get("PEER_PASSWORD", "")
    if not email or not password:
        # Try loading .env manually
        env_path = ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())
        email = os.environ.get("PEER_EMAIL", "")
        password = os.environ.get("PEER_PASSWORD", "")

    if not email or not password:
        return []  # No credentials — fall through to manual

    print(f"    [PEER] Credentials found — attempting automated download...")
    results = download_records([rsn], out_dir=RECORDS_DIR, verbose=verbose)
    return results.get(rsn, [])


def cmd_auto():
    """Read manifest, identify missing records, download via PEER (if creds) or print URLs."""
    print("=== AUTO-DOWNLOAD: Ground Motion Records ===")
    print("Strategy: PEER NGA-West2 (auto, if .env has credentials) → manual URL fallback")
    print()

    manifest = load_manifest()
    if manifest is None:
        print("ERROR: db/manifest.yaml not found. Run select_ground_motions.py first.")
        sys.exit(2)

    needed = get_needed_records(manifest)
    if not needed:
        print("No records_needed in manifest. Run select_ground_motions.py first.")
        sys.exit(2)

    present_files = scan_records()
    present_names = {f.name for f in present_files}

    missing = [e for e in needed if not match_record(e, present_names)]
    already_present = [e for e in needed if match_record(e, present_names)]

    if already_present:
        print(f"Already present ({len(already_present)}):")
        for e in already_present:
            print(f"  ✓ {e.get('filename') or 'RSN' + str(e.get('rsn', '?'))}")
        print()

    if not missing:
        print("All records present. Nothing to download.")
        sys.exit(0)

    print(f"Missing ({len(missing)}) — attempting auto-download:\n")

    downloaded = []
    needs_manual = []

    for entry in missing:
        rsn = entry.get("rsn")
        fname = entry.get("filename", "")
        label = entry.get("label", fname or f"RSN{rsn}")
        print(f"  → {label}")

        if rsn:
            rsn_int = int(str(rsn))

            # Step 1: Try CESMD (free, no auth — but often fails for records)
            ok, msg = _cesmd_download_record(rsn_int, RECORDS_DIR)
            if ok:
                print(f"    ✓ CESMD: {msg}")
                downloaded.append(label)
            else:
                # Step 2: Try PEER automated download (if .env has credentials)
                peer_files = _try_peer_download(rsn_int, verbose=True)
                if peer_files:
                    fnames = ", ".join(f.name for f in peer_files)
                    print(f"    ✓ PEER auto: {fnames}")
                    downloaded.append(label)
                else:
                    # Step 3: Print manual URL
                    print(f"    ✗ Auto-download failed ({msg})")
                    print(f"    ↳ Manual: {_peer_manual_url(rsn_int)}")
                    needs_manual.append((label, rsn))
        else:
            print(f"    ✗ No RSN number — cannot auto-download")
            needs_manual.append((label, None))
        print()

    # Summary
    print("=== SUMMARY ===")
    if downloaded:
        print(f"Auto-downloaded ({len(downloaded)}): {', '.join(downloaded)}")
    if needs_manual:
        print(f"\nNeeds manual download ({len(needs_manual)}):")
        peer_creds_hint = ""
        import os as _os
        if not (_os.environ.get("PEER_EMAIL") or (ROOT / ".env").exists()):
            peer_creds_hint = (
                "\n  TIP: Add PEER_EMAIL + PEER_PASSWORD to .env for automated download.\n"
                "  Register free at: https://ngawest2.berkeley.edu/users/sign_up"
            )
        for label, rsn in needs_manual:
            url = _peer_manual_url(rsn) if rsn else PEER_URL
            print(f"  • {label}: {url}")
        print(f"  → Download ZIP → extract .AT2 to db/excitation/records/")
        print(f"  → Then run: python3 tools/fetch_benchmark.py --verify")
        if peer_creds_hint:
            print(peer_creds_hint)

    if needs_manual:
        sys.exit(1)
    sys.exit(0)


# ---------------------------------------------------------------------------
# Flatfile download: shared cache in ~/.belico-cache/
# ---------------------------------------------------------------------------

def cmd_download_flatfile():
    """Download NGA-West2 flatfile catalog to ~/.belico-cache/ and symlink into project."""
    print("=== DOWNLOAD FLATFILE (NGA-West2 Catalog) ===")
    print(f"Cache: {FLATFILE_CACHE}")
    print(f"Link:  {FLATFILE_SYMLINK.relative_to(ROOT)}")
    print()

    BELICO_CACHE.mkdir(parents=True, exist_ok=True)
    FLATFILES_DIR.mkdir(parents=True, exist_ok=True)

    if FLATFILE_CACHE.exists():
        size_mb = FLATFILE_CACHE.stat().st_size / 1024 / 1024
        print(f"Cached flatfile found ({size_mb:.1f} MB). Skipping download.")
        _ensure_flatfile_symlink()
        print("Done.")
        sys.exit(0)

    # Sources to try (in order)
    sources = [
        {
            "name": "CESMD flatfile endpoint",
            "url": "https://strongmotioncenter.org/wserv/records/flatfile?format=csv&database=ngaw2",
        },
        {
            "name": "PEER NGA-West2 (public CSV mirror)",
            "url": "https://peer.berkeley.edu/sites/default/files/nga_w2_flatfile.csv",
        },
    ]

    downloaded = False
    for source in sources:
        print(f"Trying: {source['name']}...")
        try:
            req = urllib.request.Request(
                source["url"],
                headers={"User-Agent": "belico-stack/1.0"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                content = resp.read()

            # Sanity check: must be CSV with header
            first_line = content[:200].decode("utf-8", errors="replace").split("\n")[0]
            if not any(kw in first_line.upper() for kw in ["RSN", "MAG", "DIST"]):
                print(f"  ✗ Response doesn't look like a flatfile (header: {first_line[:80]})")
                continue

            FLATFILE_CACHE.write_bytes(content)
            size_mb = len(content) / 1024 / 1024
            print(f"  ✓ Downloaded ({size_mb:.1f} MB) → {FLATFILE_CACHE}")
            downloaded = True
            break
        except Exception as e:
            print(f"  ✗ Failed: {e}")

    if not downloaded:
        print()
        print("Auto-download failed. Manual steps:")
        print("  1. Go to: https://ngawest2.berkeley.edu (free account)")
        print("  2. Download: NGA-West2 Flatfile CSV (~50 MB)")
        print(f"  3. Save as: {FLATFILE_CACHE}")
        print("  4. Re-run: python3 tools/fetch_benchmark.py --download-flatfile")
        sys.exit(1)

    _ensure_flatfile_symlink()
    print("\nFlatfile ready. You can now run select_ground_motions.py.")
    sys.exit(0)


def _ensure_flatfile_symlink():
    """Create symlink from project flatfiles dir → shared cache."""
    if FLATFILE_SYMLINK.exists() or FLATFILE_SYMLINK.is_symlink():
        FLATFILE_SYMLINK.unlink()
    try:
        FLATFILE_SYMLINK.symlink_to(FLATFILE_CACHE)
        print(f"Symlink: {FLATFILE_SYMLINK.relative_to(ROOT)} → {FLATFILE_CACHE}")
    except OSError as e:
        # If symlink fails (Windows or cross-device link), copy instead
        print(f"  [INFO] symlink failed ({e}), copying instead")
        shutil.copy2(FLATFILE_CACHE, FLATFILE_SYMLINK)
        print(f"Copied flatfile to {FLATFILE_SYMLINK.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# Existing commands (unchanged)
# ---------------------------------------------------------------------------

def cmd_status(do_verify: bool = False):
    manifest = load_manifest()
    if manifest is None:
        print("=== GROUND MOTION RECORDS STATUS ===")
        print("NOT CONFIGURED — manifest.yaml not found.")
        print("Run: python3 tools/select_ground_motions.py")
        sys.exit(2)

    needed = get_needed_records(manifest)
    if not needed:
        print("=== GROUND MOTION RECORDS STATUS ===")
        print("NOT CONFIGURED — excitation.records_needed is empty.")
        print("Run: python3 tools/select_ground_motions.py")
        sys.exit(2)

    source = manifest.get("excitation", {}).get("source", "NGA-West2")
    quartile = manifest.get("quartile", "unknown")
    present_files = scan_records()
    present_names = {f.name for f in present_files}
    validations = {}
    if do_verify:
        for fp in present_files:
            validations[fp.name] = validate_at2(fp)

    matched = []
    missing = []
    for entry in needed:
        m = match_record(entry, present_names)
        if m:
            matched.append((entry, m))
        else:
            missing.append(entry)

    print("=== GROUND MOTION RECORDS STATUS ===")
    print(f"Manifest: {MANIFEST_PATH.relative_to(ROOT)}")
    print(f"Source:   {source}")
    print(f"Quartile: {quartile}")
    print()
    print(f"Records needed:  {len(needed)}")
    print(f"Records present: {len(matched)}")
    print(f"Records missing: {len(missing)}")
    print()

    if matched:
        print("PRESENT:")
        for entry, fname in matched:
            label = entry.get("label", entry.get("filename", fname))
            if do_verify and fname in validations:
                v = validations[fname]
                tag = "valid .AT2" if v["valid"] else "INVALID"
            else:
                tag = "found"
            print(f"  + {fname:<40s} ({label}, {tag})")
        print()

    if do_verify:
        invalids = [v for v in validations.values() if not v["valid"]]
        if invalids:
            print("VALIDATION ERRORS:")
            for v in invalids:
                print(f"  ! {v['filename']}:")
                for err in v["errors"]:
                    print(f"      {err}")
            print()

    if missing:
        print(f"MISSING — run: python3 tools/fetch_benchmark.py --auto")
        rsn_list = []
        for entry in missing:
            rsn = entry.get("rsn")
            fname = entry.get("filename", "")
            label = entry.get("label", "")
            if rsn:
                rsn_list.append(str(rsn))
                print(f"  x RSN{rsn:<8} — {label or 'Search in PEER database'}")
            else:
                print(f"  x {fname:<12} — {label or 'Search in PEER database'}")
        print()

    print("====================================")
    sys.exit(1 if missing else 0)


def cmd_scan():
    files = scan_records()
    print(f"=== SCAN: {RECORDS_DIR.relative_to(ROOT)} ===")
    if not files:
        print("No .AT2 files found.")
    else:
        print(f"Found {len(files)} record(s):\n")
        for fp in files:
            size_kb = fp.stat().st_size / 1024
            print(f"  {fp.name:<45s} ({size_kb:6.1f} KB)")
    print("=" * 42)


def cmd_verify_all():
    files = scan_records()
    print(f"=== VERIFY: {RECORDS_DIR.relative_to(ROOT)} ===")
    if not files:
        print("No .AT2 files to verify.")
        return
    n_valid = n_invalid = 0
    for fp in files:
        v = validate_at2(fp)
        if v["valid"]:
            npts = v["npts"] or "?"
            dt = f"{v['dt']:.5f}" if v["dt"] else "?"
            actual = f", actual={v.get('actual_count', '?')} vals" if "actual_count" in v else ""
            print(f"  + {fp.name:<40s} VALID  (NPTS={npts}, DT={dt}{actual})")
            # H2: confirm peer_adapter can parse it into a non-empty numpy array
            try:
                from src.physics.peer_adapter import PeerAdapter
                _adapter = PeerAdapter(target_frequency_hz=100.0)
                _raw = _adapter.read_at2_file(fp)
                _arr = _adapter.normalize_and_resample(_raw)
                if len(_arr) == 0:
                    print(f"    [WARN] peer_adapter returned empty array — file may be corrupt")
                else:
                    print(f"    [peer_adapter] OK — {len(_arr)} samples @ dt={_adapter.target_dt:.5f}s")
            except ImportError:
                pass  # peer_adapter not installed — skipping parse check
            except Exception as pa_err:
                print(f"    [WARN] peer_adapter parse failed: {pa_err}")
            n_valid += 1
        else:
            print(f"  ! {fp.name:<40s} INVALID")
            for err in v["errors"]:
                print(f"      {err}")
            n_invalid += 1
    print()
    print(f"Valid: {n_valid}  Invalid: {n_invalid}  Total: {len(files)}")
    print("=" * 42)


def cmd_update_manifest():
    if not HAS_YAML:
        print("ERROR: PyYAML not installed. pip install pyyaml")
        sys.exit(2)
    manifest = load_manifest() or {"excitation": {}}
    files = scan_records()
    present = []
    for fp in files:
        v = validate_at2(fp)
        entry = {"filename": fp.name, "valid": v["valid"]}
        if v["npts"]:
            entry["npts"] = v["npts"]
        if v["dt"]:
            entry["dt"] = v["dt"]
        present.append(entry)
    manifest.setdefault("excitation", {})
    manifest["excitation"]["records_present"] = present
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)
    print(f"=== MANIFEST UPDATED: {len(present)} records ===")
    for e in present:
        print(f"  {'✓' if e['valid'] else '!'} {e['filename']}")
    print("========================")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Verify and auto-download ground motion records per project needs."
    )
    parser.add_argument("--auto", action="store_true",
        help="Download missing records from CESMD (free) or print PEER URLs.")
    parser.add_argument("--download-flatfile", action="store_true",
        help="Download NGA-West2 flatfile catalog to ~/.belico-cache/ (shared).")
    parser.add_argument("--verify", action="store_true",
        help="Validate .AT2 file headers for PEER format compliance.")
    parser.add_argument("--scan", action="store_true",
        help="List all .AT2 files found in db/excitation/records/.")
    parser.add_argument("--update-manifest", action="store_true",
        help="Update manifest.yaml excitation.records_present with found records.")
    args = parser.parse_args()

    RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    if args.auto:
        cmd_auto()
    elif args.download_flatfile:
        cmd_download_flatfile()
    elif args.scan:
        cmd_scan()
    elif args.update_manifest:
        cmd_update_manifest()
    elif args.verify:
        cmd_verify_all()
    else:
        cmd_status(do_verify=False)


if __name__ == "__main__":
    main()
