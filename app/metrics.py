# Created by ridwan.fansuri@dana.id on 20/10/26.
"""app/metrics.py — VDOT, best 5K, zona HR, pace target. Tanpa Strava API.

Rumus Daniels & Gilbert:
  VO2(v)     = -4.60 + 0.182258*v + 0.000104*v^2       (v dalam m/menit)
  %VO2max(t) = 0.8 + 0.1894393*e^(-0.012778*t) + 0.2989558*e^(-0.1932605*t)
  VDOT       = VO2(pace lomba) / %VO2max(durasi lomba)

Zona HR pakai Tanaka: HRmax = 208 - 0.7*age.
"""
import json
import math

from .db import connect

ZONES = {"z1": (0.50, 0.60), "z2": (0.60, 0.70), "z3": (0.70, 0.80),
         "z4": (0.80, 0.90), "z5": (0.90, 0.95)}


def vo2_from_velocity(v_m_per_min: float) -> float:
    return -4.60 + 0.182258 * v_m_per_min + 0.000104 * v_m_per_min ** 2


def pct_vo2max(duration_min: float) -> float:
    return (0.8
            + 0.1894393 * math.exp(-0.012778 * duration_min)
            + 0.2989558 * math.exp(-0.1932605 * duration_min))


def vdot(distance_m: float, time_s: float) -> float:
    v = distance_m / (time_s / 60.0)
    return vo2_from_velocity(v) / pct_vo2max(time_s / 60.0)


def velocity_for_pct(vdot_value: float, pct: float) -> float:
    target = pct * vdot_value
    a, b, c = 0.000104, 0.182258, -4.60 - target
    disc = b * b - 4 * a * c
    if disc < 0:
        return 0.0
    return (-b + math.sqrt(disc)) / (2 * a)


def pace_sec_per_km(vdot_value: float, pct: float) -> int:
    v = velocity_for_pct(vdot_value, pct)
    return int(round(60000.0 / v)) if v > 0 else 0


def hr_zones(hr_max: int) -> dict:
    return {k: (round(lo * hr_max), round(hi * hr_max)) for k, (lo, hi) in ZONES.items()}


def target_pace(zone: str, vdot_value: float) -> int:
    pct = {"z2": 0.70, "z3": 0.80, "z4": 0.88, "z5": 0.98}[zone]
    return pace_sec_per_km(vdot_value, pct)


def best_5k(dist, tm):
    """Waktu tercepat 5.000 m di dalam satu run (sliding window)."""
    best = None
    j = 0
    for i, d in enumerate(dist):
        while d - dist[j] > 5000:
            j += 1
        if d - dist[j] >= 5000:
            seg = tm[i] - tm[j]
            if best is None or seg < best:
                best = seg
    return best


def riegel(time_s: float, from_m: float, to_m: float = 5000.0) -> int:
    """Ekstrapolasi waktu lomba (exponent 1.06) — selalu tandai sebagai estimasi."""
    return int(round(time_s * (to_m / from_m) ** 1.06))


def streams(external_id: str) -> dict:
    """HR/time/distance per detik dari streams_cache (hasil import TCX)."""
    con = connect()
    row = con.execute(
        "SELECT hr_json, time_json, dist_json FROM streams_cache WHERE external_id=?",
        (external_id,),
    ).fetchone()
    con.close()
    if not row:
        return {}
    return {
        "hr": json.loads(row["hr_json"]) if row["hr_json"] else [],
        "time": json.loads(row["time_json"]) if row["time_json"] else [],
        "dist": json.loads(row["dist_json"]) if row["dist_json"] else [],
    }


def current_vdot() -> tuple[float, str]:
    """Prioritas: 5K hasil run 30 hari terakhir -> tes manual -> nol."""
    con = connect()
    row = con.execute(
        """SELECT best_5k_s FROM activities
           WHERE best_5k_s IS NOT NULL
             AND start_utc >= datetime('now', '-30 days')
           ORDER BY best_5k_s ASC LIMIT 1"""
    ).fetchone()
    if row:
        con.close()
        return round(vdot(5000, row["best_5k_s"]), 1), "run"

    test = con.execute(
        "SELECT value FROM tests WHERE kind='vo2max' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    con.close()
    if test:
        return float(test["value"]), "test"
    return 0.0, "none"
