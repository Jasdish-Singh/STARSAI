"""Step 1 — Download raw datasets per SDLC §4.2 ingest stage.

Sources: GTFS (5 systems), Toronto CKAN (MCI, 311 x2, poles), OSM Ontario PBF.
Outputs: data/raw/<file> + data/raw/manifest.json (URL, fetched_at, sha256, bytes).
Resumable: skip if file already present and non-empty.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    DATA_RAW,
    GTFS_REQUIRED_FILES,
    GTFS_URLS,
    HTTP_RETRY_BACKOFF,
    HTTP_RETRY_TOTAL,
    HTTP_TIMEOUT_SECONDS,
    HTTP_USER_AGENT,
    OSM_PBF_FILENAME,
    OSM_PBF_URL,
    PULL_DATE,
    TORONTO_CKAN_BASE,
    TORONTO_DATASTORE_DUMP,
    TORONTO_RESOURCES,
    TORONTO_RESOURCE_SHOW,
)

MANIFEST_PATH = DATA_RAW / "manifest.json"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = HTTP_USER_AGENT
    retry = Retry(
        total=HTTP_RETRY_TOTAL,
        backoff_factor=HTTP_RETRY_BACKOFF,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"pull_date": PULL_DATE, "entries": {}}


def _save_manifest(m: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(m, indent=2, sort_keys=True), encoding="utf-8")


def _record(manifest: dict, key: str, *, url: str, path: Path, extra: dict | None = None) -> None:
    manifest["entries"][key] = {
        "url": url,
        "path": str(path.relative_to(DATA_RAW.parent)),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        **(extra or {}),
    }


def _stream_download(sess: requests.Session, url: str, dest: Path, *, label: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    t0 = time.time()
    with sess.get(url, stream=True, timeout=HTTP_TIMEOUT_SECONDS) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        written = 0
        with tmp.open("wb") as f:
            for chunk in r.iter_content(1 << 20):
                if chunk:
                    f.write(chunk)
                    written += len(chunk)
        if total and written != total:
            raise IOError(f"{label}: short read ({written}/{total})")
    tmp.replace(dest)
    dur = time.time() - t0
    mb = dest.stat().st_size / (1 << 20)
    print(f"[OK] {label} -> {dest.name} ({mb:.1f} MB in {dur:.1f}s)")


def download_gtfs(sess: requests.Session, system: str, url: str, manifest: dict) -> bool:
    dest_dir = DATA_RAW / "gtfs" / system
    dest_dir.mkdir(parents=True, exist_ok=True)
    have_all = all((dest_dir / f).exists() for f in GTFS_REQUIRED_FILES)
    if have_all:
        print(f"[SKIP] gtfs/{system} (complete)")
        # Re-record manifest if missing
        if f"gtfs/{system}" not in manifest["entries"]:
            zip_path = dest_dir / "_source.zip"
            if zip_path.exists():
                _record(manifest, f"gtfs/{system}", url=url, path=zip_path,
                        extra={"kind": "gtfs", "system": system})
        return True

    zip_path = dest_dir / "_source.zip"
    try:
        _stream_download(sess, url, zip_path, label=f"gtfs/{system}")
    except Exception as e:
        print(f"[FAIL] gtfs/{system}: {e}")
        return False

    try:
        with zipfile.ZipFile(zip_path) as z:
            members = [m for m in z.namelist() if not m.endswith("/")]
            for m in members:
                target = dest_dir / Path(m).name
                with z.open(m) as src, target.open("wb") as out:
                    out.write(src.read())
    except zipfile.BadZipFile as e:
        print(f"[FAIL] gtfs/{system} bad zip: {e}")
        return False

    missing = [f for f in GTFS_REQUIRED_FILES if not (dest_dir / f).exists()]
    if missing:
        print(f"[WARN] gtfs/{system} missing files: {missing}")
    _record(manifest, f"gtfs/{system}", url=url, path=zip_path,
            extra={"kind": "gtfs", "system": system, "missing": missing})
    return not missing


def download_toronto_resource(sess: requests.Session, filename: str, spec: dict, manifest: dict) -> bool:
    dest = DATA_RAW / "toronto" / filename
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[SKIP] toronto/{filename}")
        if f"toronto/{filename}" not in manifest["entries"]:
            _record(manifest, f"toronto/{filename}",
                    url=spec.get("resolved_url", ""), path=dest, extra=spec)
        return True

    rid = spec["resource_id"]
    kind = spec["kind"]
    if kind == "datastore_csv":
        url = TORONTO_DATASTORE_DUMP.format(resource_id=rid)
    elif kind == "ckan_file":
        meta_url = TORONTO_RESOURCE_SHOW.format(resource_id=rid)
        try:
            r = sess.get(meta_url, timeout=HTTP_TIMEOUT_SECONDS)
            r.raise_for_status()
            meta = r.json()
            url = meta["result"]["url"]
        except Exception as e:
            print(f"[FAIL] toronto/{filename} resource_show: {e}")
            return False
    else:
        print(f"[FAIL] toronto/{filename}: unknown kind {kind!r}")
        return False

    try:
        _stream_download(sess, url, dest, label=f"toronto/{filename}")
    except Exception as e:
        print(f"[FAIL] toronto/{filename}: {e}")
        return False

    extra = {**spec, "resolved_url": url}
    _record(manifest, f"toronto/{filename}", url=url, path=dest, extra=extra)
    return True


def download_osm(sess: requests.Session, manifest: dict) -> bool:
    dest = DATA_RAW / "osm" / OSM_PBF_FILENAME
    if dest.exists() and dest.stat().st_size > 100 * (1 << 20):  # ≥100MB sanity
        print(f"[SKIP] osm/{OSM_PBF_FILENAME} ({dest.stat().st_size / (1<<20):.0f} MB)")
        if f"osm/{OSM_PBF_FILENAME}" not in manifest["entries"]:
            _record(manifest, f"osm/{OSM_PBF_FILENAME}",
                    url=OSM_PBF_URL, path=dest, extra={"kind": "osm_pbf"})
        return True
    try:
        _stream_download(sess, OSM_PBF_URL, dest, label="osm/ontario.pbf")
    except Exception as e:
        print(f"[FAIL] osm: {e}")
        return False
    _record(manifest, f"osm/{OSM_PBF_FILENAME}", url=OSM_PBF_URL, path=dest,
            extra={"kind": "osm_pbf"})
    return True


def main() -> int:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest()
    sess = _session()
    results: dict[str, bool] = {}

    print(f"=== INGEST start (pull_date={PULL_DATE}) ===")

    for system, url in GTFS_URLS.items():
        results[f"gtfs/{system}"] = download_gtfs(sess, system, url, manifest)
        _save_manifest(manifest)

    for filename, spec in TORONTO_RESOURCES.items():
        results[f"toronto/{filename}"] = download_toronto_resource(sess, filename, spec, manifest)
        _save_manifest(manifest)

    results["osm/ontario"] = download_osm(sess, manifest)
    _save_manifest(manifest)

    print("\n=== INGEST summary ===")
    ok = sum(1 for v in results.values() if v)
    fail = sum(1 for v in results.values() if not v)
    for k, v in results.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    print(f"Total: {ok} ok, {fail} fail")
    print(f"Manifest: {MANIFEST_PATH}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
