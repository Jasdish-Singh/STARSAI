"""Bronze stage: download StatCan 2021 Census Profile (CT) + CT boundary shapefile.

SDLC ref: FR-006 — StatCan census-tract income & population.
Outputs:
  data/bronze/statcan/profile_ct.csv         (extracted from 98-401-X2021006 zip)
  data/bronze/statcan/lct_000b21a_e/*.shp    (extracted CT boundaries)
  data/bronze/statcan/manifest.json
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(r"C:\Jasdish-IMP\STARSAI")
sys.path.insert(0, str(ROOT / "pipeline"))

from config import (  # noqa: E402
    HTTP_RETRY_BACKOFF,
    HTTP_RETRY_TOTAL,
    HTTP_TIMEOUT_SECONDS,
    HTTP_USER_AGENT,
    STATCAN_CT_BOUNDARY_FILENAME,
    STATCAN_CT_BOUNDARY_URL,
    STATCAN_PROFILE_FILENAME,
    STATCAN_PROFILE_URL,
)

OUT_DIR = ROOT / "data" / "bronze" / "statcan"
MANIFEST_PATH = OUT_DIR / "manifest.json"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = HTTP_USER_AGENT
    retry = Retry(
        total=HTTP_RETRY_TOTAL,
        backoff_factor=HTTP_RETRY_BACKOFF,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
    )
    a = HTTPAdapter(max_retries=retry, pool_connections=2, pool_maxsize=2)
    s.mount("http://", a)
    s.mount("https://", a)
    return s


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(sess: requests.Session, url: str, dest: Path) -> dict:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"skip (exists): {dest.name} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
        return {"url": url, "bytes": dest.stat().st_size, "sha256": _sha256(dest), "fetched_at": "cached"}

    print(f"GET {url}")
    with sess.get(url, stream=True, timeout=HTTP_TIMEOUT_SECONDS) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        last_report = 0
        with dest.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                downloaded += len(chunk)
                if total and downloaded - last_report > 20 * (1 << 20):
                    pct = 100 * downloaded / total
                    print(f"  {downloaded / 1024 / 1024:.0f}/{total / 1024 / 1024:.0f} MB ({pct:.0f}%)")
                    last_report = downloaded
    size = dest.stat().st_size
    print(f"  done: {size / 1024 / 1024:.1f} MB")
    return {
        "url": url,
        "bytes": size,
        "sha256": _sha256(dest),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _extract_zip(zpath: Path, out_dir: Path, *, want_ext: tuple[str, ...] = ()) -> list[str]:
    """Extract zip to out_dir. If want_ext given, only members with those extensions."""
    extracted = []
    with zipfile.ZipFile(zpath) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if want_ext and not info.filename.lower().endswith(want_ext):
                continue
            zf.extract(info, out_dir)
            extracted.append(info.filename)
    return extracted


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sess = _session()
    manifest: dict[str, dict] = {}

    # 1. Census Profile (CT) — large zip (~243 MB)
    profile_zip = OUT_DIR / STATCAN_PROFILE_FILENAME
    manifest["profile_zip"] = _download(sess, STATCAN_PROFILE_URL, profile_zip)

    # Extract the profile CSV (rename to predictable name)
    print(f"extracting CSV from {profile_zip.name}...")
    csv_members = _extract_zip(profile_zip, OUT_DIR, want_ext=(".csv",))
    if not csv_members:
        raise RuntimeError(f"no CSV in {profile_zip}")
    # Rename main profile CSV (largest one) to profile_ct.csv
    csvs = sorted([OUT_DIR / m for m in csv_members], key=lambda p: p.stat().st_size, reverse=True)
    main_csv = csvs[0]
    target_csv = OUT_DIR / "profile_ct.csv"
    if main_csv != target_csv:
        if target_csv.exists():
            target_csv.unlink()
        main_csv.rename(target_csv)
    manifest["profile_csv"] = {
        "path": str(target_csv.relative_to(ROOT)),
        "bytes": target_csv.stat().st_size,
        "sha256": _sha256(target_csv),
    }
    print(f"  profile_ct.csv: {target_csv.stat().st_size / 1024 / 1024:.0f} MB")

    # 2. CT boundary shapefile (small, ~8 MB)
    boundary_zip = OUT_DIR / STATCAN_CT_BOUNDARY_FILENAME
    manifest["boundary_zip"] = _download(sess, STATCAN_CT_BOUNDARY_URL, boundary_zip)

    boundary_dir = OUT_DIR / "lct_000b21a_e"
    boundary_dir.mkdir(exist_ok=True)
    print(f"extracting shapefile to {boundary_dir.name}/...")
    extracted = _extract_zip(boundary_zip, boundary_dir)
    shp = next((boundary_dir / m for m in extracted if m.lower().endswith(".shp")), None)
    if shp is None:
        # shp may be nested one level
        shps = list(boundary_dir.rglob("*.shp"))
        if not shps:
            raise RuntimeError(f"no .shp in {boundary_zip}")
        shp = shps[0]
    manifest["boundary_shp"] = {
        "path": str(shp.relative_to(ROOT)),
        "bytes": shp.stat().st_size,
        "sha256": _sha256(shp),
    }
    print(f"  shp: {shp.relative_to(ROOT)}")

    # 3. write manifest
    with MANIFEST_PATH.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nmanifest -> {MANIFEST_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
