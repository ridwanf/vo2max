"""app/db.py — koneksi SQLite + schema bootstrap.

Lokasi DB: env VO2MAX_DB (default db/vo2max.db, relatif root project).
connect() mengecek tabel `activities`; kalau belum ada, schema.sql dijalankan
otomatis supaya urutan "lupa python -m app.db" tidak bikin 'no such table'.
"""
import os
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_path(raw: str) -> Path:
    """Path relatif dihitung dari root project, bukan dari CWD."""
    q = Path(os.path.expanduser(raw))
    return q.resolve() if q.is_absolute() else (PROJECT_ROOT / q).resolve()


DB_PATH = resolve_path(os.environ.get("VO2MAX_DB", "db/vo2max.db"))

_SCHEMA_CANDIDATES = [
    PROJECT_ROOT / "schema.sql",
    Path(__file__).resolve().parent / "schema.sql",
    DB_PATH.parent / "schema.sql",
]


def _schema_text() -> str:
    for p in _SCHEMA_CANDIDATES:
        if p.is_file():
            return p.read_text()
    dicari = "\n  ".join(str(p) for p in _SCHEMA_CANDIDATES)
    raise FileNotFoundError("schema.sql tidak ditemukan. Dicari di:\n  " + dicari)


def _has_schema(con: sqlite3.Connection) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='activities'"
    ).fetchone() is not None


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    if not _has_schema(con):
        con.executescript(_schema_text())
        con.commit()
    return con


def init() -> None:
    con = connect()
    con.close()


if __name__ == "__main__":
    init()
    con = connect()
    tabel = [r["name"] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    con.close()
    print("DB    :", DB_PATH)
    print("Tabel :", ", ".join(tabel))
