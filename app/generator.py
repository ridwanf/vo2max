# Created by ridwan.fansuri@dana.id on 21/10/26.
"""app/generator.py — 8 sesi mingguan dari template + pace/HR dari VDOT.

Kenapa disimpan ke tabel sessions, bukan dihitung tiap request:
kalau VDOT berubah di tengah program, sesi yang sudah lewat jangan ikut berubah.
Generate sekali (ensure_sessions), sesudah itu cuma dibaca.
"""

from datetime import date, timedelta, datetime

TEMPLATE = [
    {
        "week": 1,
        "kind": "interval",
        "reps": 4,
        "work_s": 180,
        "rec_s": 120,
        "zone": "z4",
    },
    {
        "week": 2,
        "kind": "interval",
        "reps": 5,
        "work_s": 180,
        "rec_s": 120,
        "zone": "z4",
    },
    {
        "week": 3,
        "kind": "interval",
        "reps": 4,
        "work_s": 240,
        "rec_s": 120,
        "zone": "z4",
    },
    {"week": 4, "kind": "deload", "reps": 3, "work_s": 180, "rec_s": 180, "zone": "z4"},
    {
        "week": 5,
        "kind": "interval",
        "reps": 4,
        "work_s": 240,
        "rec_s": 180,
        "zone": "z5",
    },
    {
        "week": 6,
        "kind": "interval",
        "reps": 5,
        "work_s": 240,
        "rec_s": 180,
        "zone": "z5",
    },
    {
        "week": 7,
        "kind": "interval",
        "reps": 4,
        "work_s": 240,
        "rec_s": 180,
        "zone": "z5",
    },
    {"week": 8, "kind": "test", "reps": 0, "work_s": 0, "rec_s": 0, "zone": "z5"},
]


def describe(t: dict, pace_s: int) -> str:
    if t["kind"] == "test":
        return "TES 5K all-out · warm-up 12' + 2x(30\" keras/30\" jog) · cool-down 8'"
    mins, secs = divmod(t["work_s"], 60)
    work = f"{mins}'" if secs == 0 else f"{mins}'{secs:02d}\""
    rec = f"{t['rec_s'] // 60}"
    pace = f" · pace {pace_s // 60}:{pace_s % 60:02d}/km" if pace_s else ""
    label = "DELOAD " if t["kind"] == "deload" else ""
    return f"{label}{t['reps']} x ({work} {t['zone'].upper()} + {rec} jog){pace}"


def ensure_sessions(
    con, start: date, vdot_value: float, hr_max: int, paces: dict
) -> None:
    """Insert Table sessions"""
    for t in TEMPLATE:
        row = con.execute(
            "SELECT id FROM sessions WHERE week=? and slot=1", (t["week"],)
        ).fetchone()
        if row:
            continue
        lo, hi = {
            "z4": (round(0.80 * hr_max), round(0.90 * hr_max)),
            "z5": (round(0.90 * hr_max), round(0.95 * hr_max)),
        }[t["zone"]]
        con.execute(
            """INSERT INTO sessions (week, slot, date, kind, main_set,
									 target_hr_low, target_hr_high, target_pace_s, work_s)
			   VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?)""",
            (
                t["week"],
                (start + timedelta(days=7 * (t["week"] - 1))).isoformat(),
                t["kind"],
                describe(t, paces.get(t["zone"], 0)),
                lo,
                hi,
                paces.get(t["zone"], 0),
                t["reps"] * t["work_s"],
            ),
        )
        con.commit()
def week_index(start: date, today: date | None = None) -> int:
    today = today or datetime.now().date()
    return max(1, min(8, (today - start).days // 7 + 1))

def this_week_session(con, start_iso: str, today: date | None = None) -> dict | None:
    start = date.fromisoformat(start_iso)
    week = week_index(start, today)
    row = con.execute("SELECT * FROM sessions WHERE week=? AND slot=1", (week,)).fetchone()
    return dict(row) if row else None