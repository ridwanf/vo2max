-- schema.sql · SQLite. Jalankan sekali: sqlite3 vo2max.db < schema.sql
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS athlete (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  sex TEXT NOT NULL,
  age INTEGER NOT NULL,
  hr_max INTEGER NOT NULL,
  rhr_baseline REAL,
  start_date TEXT NOT NULL            -- tanggal sesi #1 (Minggu)
);

CREATE TABLE IF NOT EXISTS activities (
  external_id TEXT PRIMARY KEY,       -- nama file TCX/FIT, atau 'manual-2026-10-25'
  source TEXT NOT NULL,               -- 'tcx' | 'fit' | 'manual'
  start_utc TEXT NOT NULL,
  distance_m REAL NOT NULL,
  moving_s INTEGER NOT NULL,
  avg_hr REAL,
  max_hr REAL,
  best_5k_s INTEGER,
  note TEXT
);
CREATE INDEX IF NOT EXISTS idx_act_start ON activities(start_utc);

CREATE TABLE IF NOT EXISTS streams_cache (
  external_id TEXT PRIMARY KEY,
  hr_json TEXT, time_json TEXT, dist_json TEXT,
  fetched_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL, kind TEXT NOT NULL, value REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  week INTEGER NOT NULL, slot INTEGER NOT NULL,
  date TEXT NOT NULL, kind TEXT NOT NULL, main_set TEXT NOT NULL,
  target_hr_low INTEGER, target_hr_high INTEGER,
  target_pace_s INTEGER, work_s INTEGER,
  external_id TEXT, verdict TEXT DEFAULT 'belum',
  UNIQUE(week, slot)
);
