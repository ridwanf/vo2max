# Created by ridwan.fansuri@dana.id on 20/10/26.
import os
import sqlite3

DB_PATH = os.environ.get("VO2MAX_DB", os.path.expanduser("db/vo2max.db"))
SCHEMA = os.path.join(os.path.dirname(__file__),".." ,"schema.sql")

def connect() -> sqlite3.Connection:
	os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
	con = sqlite3.connect(DB_PATH)
	con.row_factory = sqlite3.Row
	con.execute("PRAGMA journal_mode=WAL")
	return con

def init() -> None:
	con = connect()
	with open(SCHEMA) as fh:
		con.executescript(fh.read())
	con.commit()
	con.close()

if __name__ == "__main__":
	init()
	print("scheme ok ->", DB_PATH)