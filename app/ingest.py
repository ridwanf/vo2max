"""app/ingest.py — import semua TCX/FIT dari folder + hitung ringkasan.

Dipakai dua cara:
  python -m app.ingest                 # scan TCX_INBOX
  python -m app.ingest --file x.tcx    # satu file

Idempotent: external_id = nama file. File yang sama di-import ulang cuma
meng-update row, bukan menambah. streams_cache menyimpan HR per detik supaya
compliance tidak perlu parsing ulang.
"""
import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from . import metrics, tcx
from .db import PROJECT_ROOT, connect


def resolve_inbox(raw: str) -> Path:
    """Path relatif dihitung dari root project, bukan dari CWD."""
    p = Path(os.path.expanduser(raw))
    return (PROJECT_ROOT / p).resolve() if not p.is_absolute() else p.resolve()


def _summary(dist, tm, hr):
    moving = int(round(tm[-1])) if tm else 0
    vals = [h for h in hr if h]
    avg = round(sum(vals) / len(vals), 1) if vals else None
    mx = max(vals) if vals else None
    return moving, avg, mx


def ingest_file(path: str, external_id: str | None = None) -> dict:
    ext_id = external_id or Path(path).stem
    parsed = tcx.parse_any(path)
    if not parsed["dist"]:
        return {"external_id": ext_id,
                "error": "TCX tidak punya DistanceMeters maupun Position — "
                         "export ulang dari Strava (⋯ → Export TCX)"}

    moving, avg_hr, max_hr = _summary(parsed["dist"], parsed["time"], parsed["hr"])
    source = "fit" if path.lower().endswith(".fit") else "tcx"
    best5k = metrics.best_5k(parsed["dist"], parsed["time"])
    note = None
    if best5k is None and parsed["dist"][-1] >= 4800:
        # run hampir 5 km (jarak GPS sering 4,95-4,99 km): ekstrapolasi Riegel
        best5k = metrics.riegel(moving, parsed["dist"][-1])
        note = "estimate"

    con = connect()
    con.execute(
        """INSERT INTO activities (external_id, source, start_utc, distance_m, moving_s,
                                   avg_hr, max_hr, best_5k_s, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(external_id) DO UPDATE SET
             start_utc=excluded.start_utc, distance_m=excluded.distance_m,
             moving_s=excluded.moving_s, avg_hr=excluded.avg_hr,
             max_hr=excluded.max_hr, best_5k_s=excluded.best_5k_s,
             note=excluded.note""",
        (ext_id, source, parsed["start"], parsed["dist"][-1], moving, avg_hr, max_hr, best5k, note),
    )
    con.execute(
        """INSERT INTO streams_cache (external_id, hr_json, time_json, dist_json, fetched_utc)
           VALUES (?, ?, ?, ?, datetime('now'))
           ON CONFLICT(external_id) DO UPDATE SET
             hr_json=excluded.hr_json, time_json=excluded.time_json,
             dist_json=excluded.dist_json""",
        (ext_id, json.dumps(parsed["hr"]), json.dumps(parsed["time"]), json.dumps(parsed["dist"])),
    )
    con.commit()
    con.close()
    return {
        "external_id": ext_id,
        "distance_km": round(parsed["dist"][-1] / 1000, 2),
        "moving_s": moving,
        "avg_hr": avg_hr,
        "best_5k_s": best5k,
    }


def scan(inbox: str) -> list[dict]:
    root = resolve_inbox(inbox)
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return [{"info": f"folder dibuat, masih kosong: {root}"}]
    if not root.is_dir():
        return [{"error": f"bukan folder: {root}"}]
    out = []
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.name.startswith("."):
            continue
        if f.suffix.lower() not in (".tcx", ".fit", ".gz", ".zip"):
            continue
        try:
            out.append(ingest_file(str(f)))
        except Exception as e:                       # file rusak jangan stop batch
            out.append({"file": f.name, "error": str(e)})
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--inbox", default=os.environ.get("TCX_INBOX", "data"))
    args = ap.parse_args()
    results = [ingest_file(args.file)] if args.file else scan(args.inbox)
    for r in results:
        print(r)
    print(f"total: {len(results)} · folder: {resolve_inbox(args.inbox)}")
