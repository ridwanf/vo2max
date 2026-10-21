# Created by ridwan.fansuri@dana.id on 20/10/26.
import os

from .db import connect

con = connect()
con.execute(
	"""INSERT OR REPLACE INTO athlete (id, sex, age, hr_max, rhr_baseline, start_date) 
	VALUES (1, ?,?,?,?,?)""",
	(
		os.environ.get("ATHLETE_SEX", "m"),
		int(os.environ.get("ATHLETE_AGE", 38)),
		int(os.environ.get("ATHLETE_HRMAX", 181)),
		float(os.environ["ATHLETE_RHR"]) if os.environ.get("ATHLETE_RHR") else None,
		os.environ.get("PROGRAM_START", "2026-10-25"),
	),
)
con.commit()
print(dict(con.execute("SELECT * FROM athlete").fetchone()))

