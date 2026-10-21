# Created by ridwan.fansuri@dana.id on 21/10/26.
"""app/main.py — FastAPI: login, state, import, manual, check, export.

Tanpa Strava API: data masuk lewat upload TCX/FIT, scan folder, atau input manual.
Auth: satu passphrase -> cookie HttpOnly bertanda tangan (itsdangerous).
"""
import os
import tempfile
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, Depends, UploadFile, File
from itsdangerous import URLSafeTimedSerializer, BadSignature
from pydantic import BaseModel
from starlette.staticfiles import StaticFiles

from . import metrics, ingest, manual, generator, compliance
from app.db import connect

COOKIE = "vo2max_session"
signer = URLSafeTimedSerializer(os.environ["APP_SECRET"], salt="vo2max")
app =FastAPI(title="VO2max")

class LoginIn(BaseModel):
	passphrase: str

class ManualIn(BaseModel):
	date: str
	km: float
	mmss: str
	hr_avg: float | None = None
	hr_max: float | None = None

def athlete(con) -> dict:
	row = con.execute("SELECT * FROM athlete WHERE id=1").fetchone()
	if not row:
		raise HTTPException(status_code=500, detail="athlete not found")
	return dict(row)

def require_login(request: Request) -> bool:
	try:
		signer.loads(request.cookies.get(COOKIE), max_age=90*24*3600)
	except BadSignature:
		raise HTTPException(status_code=401, detail="Please login first")
	return True

@app.post("/api/login")
def login(payload: LoginIn, response: Response):
	if payload.passphrase != os.environ["APP_PASSPHRASE"]:
		raise HTTPException(status_code=401, detail="Invalid passphrase")
	response.set_cookie(COOKIE, signer.dumps("athlete"),
						httponly=True, samesite="lax", secure=True,
						max_age=90*24*3600)
	return {"ok": True}

@app.get("/api/state")
def state(_: bool = Depends(require_login)):
	con = connect()
	a = athlete(con)
	vd, src = metrics.current_vdot()
	zones = metrics.hr_zones(a["hr_max"])
	paces = {z: metrics.target_pace(z, vd) for z in ("z2", "z4", "z5")} if vd else {}
	if vd:
		generator.ensure_session(
			con, date.fromisoformat(a["start_date"]), vd, a["hr_max"]
		)
	session = generator.this_week_session(con, a["start_date"])
	recent = [
		dict(r)
		for r in con.execute(
			"""SELECT external_id, source, start_utc, distance_m, moving_s, avg_hr,
						  best_5k_s, note
				   FROM activities ORDER BY start_utc DESC LIMIT 5"""
		)]
	con.close()
	return {"athlete": a, "vdot": vd, "vdot_source": src,
			"zones": zones, "paces": paces, "session": session, "recent": recent}

@app.post("/api/import")
def import_inbox(_:bool = Depends(require_login)):
	"""SCAN TCX_INBOX"""
	return {"results": ingest.scan(os.environ.get("TCX_INBOX", "data"))}

@app.post("/api/upload")
async def upload(file: UploadFile = File(...), _:bool = Depends(require_login)):
	"""Upload file TCX/FIT from iphone"""
	suffix = Path(file.filename or "x.tcx").suffix
	with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
		tmp.write(await file.read())
		path = tmp.name
	try:
		return ingest.ingest_file(path) | {"filename": file.filename}
	finally:
		os.unlink(path)

@app.post("/api/manual")
def manual_entry(payload: ManualIn, _:bool = Depends(require_login)):
	return manual.add(payload.date, payload.km, manual.parse_mmss(payload.mmss),
	                  payload.hr_avg, payload.hr_max)

@app.post("/api/check/{session_id}")
def check(session_id: int, _:bool = Depends(require_login)):
	return compliance.check_session(session_id)

@app.get("/api/export")
def export_all(_:bool = Depends(require_login)):
	con = connect()
	out = {t: [dict(r) for r in con.execute(f"SELECT * FROM {t}")]
	       for t in ("athlete", "activities", "tests", "sessions")}
	con.close()
	return out

app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__),  "../data"),
                           html=True), name="static")