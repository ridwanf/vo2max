# Created by ridwan.fansuri@dana.id on 21/10/26.
"""app/compliance.py — apakah sesi kemarin beneran kena zona?

Dua tingkat keyakinan:
- ok / kurang_keras / kelebihan  -> dihitung dari HR per detik (TCX/FIT import)
- perkiraan                      -> cuma ada avg HR (input manual dari Mi Fitness)
Tidak ada API, jadi tidak ada rate limit dan tidak ada token yang expired.
"""
from .db import connect

from . import metrics


def time_in_zone(hr, tm, lo, hi) -> float:
    total = 0.0
    n = min(len(hr), len(tm))
    for i in range(1, n):
        prev = hr[i - 1]
        if prev is None:
            continue
        dt = tm[i] - tm[i - 1]
        if dt <= 0:
            continue
        if lo <= prev <= hi:
            total += dt
    return total

def classify(work_s: int, in_zone_s: float, above_hi_s: float) -> str:
    if work_s <= 0:
        return "ok" if in_zone_s > 0 else "Not Yet"
    if above_hi_s > 300:          # > 5 menit di atas zona = kebanyakan
        return "Overtrain"
    if in_zone_s >= 0.7 * work_s:  # minimal 70% durasi kerja di zona
        return "ok"
    return "Undertrain"

def _activity_for(con, session_date: str):
    """Run pada tanggal sesi (WIB = UTC+7), ambil yang paling awal."""
    return con.execute(
        """SELECT external_id, avg_hr FROM activities
           WHERE date(datetime(start_utc, '+7 hours')) = ?
           ORDER BY start_utc LIMIT 1""",
        (session_date,),
    ).fetchone()

def check_session(session_id: int) -> dict:
    con = connect()
    s = con.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not s:
        con.close()
        return {"error": "session tidak ada"}

    act = _activity_for(con, s["date"])
    if not act:
        con.close()
        return {"verdict": "belum", "reason": "belum ada run di tanggal ini"}
    if not s["target_hr_low"]:
        con.close()
        return {"verdict": "belum", "reason": "sesi tanpa target HR"}

    st = metrics.streams(act["external_id"])
    hr, tm = st.get("hr") or [], st.get("time") or []

    # Tanpa stream (input manual): cuma bisa menilai dari avg HR.
    if not hr:
        avg = act["avg_hr"]
        if not avg:
            verdict = "belum"
        elif avg < s["target_hr_low"]:
            verdict = "perkiraan_kurang_keras"
        elif avg > s["target_hr_high"]:
            verdict = "perkiraan_kelebihan"
        else:
            verdict = "perkiraan"
        con.execute("UPDATE sessions SET external_id=?, verdict=? WHERE id=?",
                    (act["external_id"], verdict, session_id))
        con.commit()
        con.close()
        return {"verdict": verdict, "basis": "avg_hr", "avg_hr": avg,
                "target": [s["target_hr_low"], s["target_hr_high"]]}

    in_zone = time_in_zone(hr, tm, s["target_hr_low"], s["target_hr_high"])
    above = time_in_zone(hr, tm, s["target_hr_high"] + 1, 250)
    verdict = classify(s["work_s"], in_zone, above)

    con.execute("UPDATE sessions SET external_id=?, verdict=? WHERE id=?",
                (act["external_id"], verdict, session_id))
    con.commit()
    con.close()
    return {"verdict": verdict, "basis": "stream_hr",
            "in_zone_s": round(in_zone), "target_s": s["work_s"],
            "pct": round(100 * in_zone / s["work_s"]) if s["work_s"] else 0}
