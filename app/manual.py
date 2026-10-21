# Created by ridwan.fansuri@dana.id on 20/10/26.
"""app/manual.py — input hasil run dari Mi Fitness tanpa file.

Dipakai kalau malas export TCX: buka Mi Fitness, lihat ringkasan run, isi 3 angka.
best_5k_s diisi hasil ekstrapolasi Riegel dan ditandai note='estimate', jadi
VDOT dari data manual tetap bisa dipakai tapi jelas bukan hasil lomba.

  python -m app.manual --date 2026-10-25 --km 5.0 --mmss 39:10 --hr-avg 158 --hr-max 171
"""
import argparse
from datetime import datetime, timedelta, timezone

from . import metrics
from .db import connect

WIB = timezone(timedelta(hours=7))


def parse_mmss(s: str) -> int:
    parts = [int(p) for p in s.split(":")]
    secs = 0
    for p in parts:
        secs = secs * 60 + p
    return secs


def add(date_str: str, distance_km: float, time_s: int,
        avg_hr=None, max_hr=None, note="estimate") -> dict:
    distance_m = distance_km * 1000
    best = None
    if distance_m >= 2000:
        best = metrics.riegel(time_s, distance_m)
    start = (datetime.fromisoformat(date_str + "T06:00:00")
             .replace(tzinfo=WIB).astimezone(timezone.utc).isoformat())
    ext_id = f"manual-{date_str}"

    con = connect()
    con.execute(
        """INSERT INTO activities (external_id, source, start_utc, distance_m, moving_s,
                                   avg_hr, max_hr, best_5k_s, note)
           VALUES (?, 'manual', ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(external_id) DO UPDATE SET
             distance_m=excluded.distance_m, moving_s=excluded.moving_s,
             avg_hr=excluded.avg_hr, max_hr=excluded.max_hr,
             best_5k_s=excluded.best_5k_s, note=excluded.note""",
        (ext_id, start, distance_m, time_s, avg_hr, max_hr, best, note),
    )
    con.commit()
    con.close()
    return {"external_id": ext_id, "distance_km": distance_km, "time_s": time_s,
            "best_5k_s": best, "note": note}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYY-MM-DD (WIB)")
    ap.add_argument("--km", type=float, required=True)
    ap.add_argument("--mmss", required=True, help="waktu total, misal 39:10")
    ap.add_argument("--hr-avg", type=float)
    ap.add_argument("--hr-max", type=float)
    a = ap.parse_args()
    print(add(a.date, a.km, parse_mmss(a.mmss), a.hr_avg, a.hr_max))
