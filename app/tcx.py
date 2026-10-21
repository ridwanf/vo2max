# Created by ridwan.fansuri@dana.id on 20/10/26.
"""app/tcx.py — baca file TCX / FIT jadi array distance, time, heartrate.

Tahan terhadap file yang "kotor": BOM, spasi/newline sebelum deklarasi XML,
file .gz, dan .zip berisi .tcx (banyak export Strava dikirim dalam zip).
GPX dikenali dan ditolak dengan pesan jelas, bukan traceback ET.
"""
import gzip
import io
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def _tag(el) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _child(el, name):
    for c in el:
        if _tag(c) == name:
            return c
    return None


def _text(el, name):
    c = _child(el, name)
    return c.text if c is not None else None


def _iso_to_epoch(s: str) -> float:
    s = s.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _clean_xml(raw: bytes) -> str:
    """Kembalikan teks XML yang aman di-parse, atau lempar ValueError yang jelas."""
    if raw[:2] == b"\x1f\x8b":                      # gzip
        raw = gzip.decompress(raw)

    if raw[:2] == b"PK":                            # zip: ambil .tcx pertama
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".tcx")]
            if not names:
                raise ValueError("zip tidak berisi .tcx (isi: " + ", ".join(z.namelist()[:5]) + ")")
            raw = z.read(names[0])

    text = raw.decode("utf-8-sig", errors="replace")   # utf-8-sig membuang BOM
    i = text.find("<?xml")
    if i > 0:
        text = text[i:]                                 # buang sampah sebelum deklarasi
    elif i < 0:
        j = text.find("<")
        if j < 0:
            raise ValueError("file kosong / bukan XML")
        text = text[j:]

    head = text[:400].lower()
    if "<gpx" in head:
        raise ValueError("ini file GPX, bukan TCX — GPX tidak menyimpan HR per detik dengan rapi")
    if "<html" in head or "<!doctype html" in head:
        raise ValueError("ini halaman HTML (mungkin link download, bukan file-nya)")
    return text


def _root(path: str):
    raw = Path(path).read_bytes()
    return ET.fromstring(_clean_xml(raw))


def parse_tcx(path: str) -> dict:
    """Balikin {'dist': [m], 'time': [s], 'hr': [bpm|None], 'start': iso}."""
    root = _root(path)
    dist, tm, hr, stamps = [], [], [], []

    for tp in root.iter():
        if _tag(tp) != "Trackpoint":
            continue
        t = _text(tp, "Time")
        if not t:
            continue
        d = _text(tp, "DistanceMeters")
        if d is None:
            continue
        bpm = None
        hr_el = _child(tp, "HeartRateBpm")
        if hr_el is not None:
            v = _text(hr_el, "Value")
            bpm = int(float(v)) if v else None
        stamps.append(_iso_to_epoch(t))
        dist.append(float(d))
        hr.append(bpm)

    if not stamps:
        return {"dist": [], "time": [], "hr": [], "start": None}

    t0 = stamps[0]
    return {
        "dist": dist,
        "time": [round(s - t0, 1) for s in stamps],
        "hr": hr,
        "start": datetime.fromtimestamp(t0, timezone.utc).isoformat(),
    }


def parse_fit(path: str) -> dict:
    """Opsional: pip install fitparse."""
    from fitparse import FitFile

    fit = FitFile(path, check_crc=False)
    dist, stamps, hr = [], [], []
    for rec in fit.get_messages("record"):
        vals = {d.name: d.value for d in rec}
        if vals.get("distance") is None or vals.get("timestamp") is None:
            continue
        stamps.append(vals["timestamp"].timestamp())
        dist.append(float(vals["distance"]))
        hr.append(vals.get("heart_rate"))

    if not stamps:
        return {"dist": [], "time": [], "hr": [], "start": None}
    t0 = stamps[0]
    return {
        "dist": dist,
        "time": [round(s - t0, 1) for s in stamps],
        "hr": hr,
        "start": datetime.fromtimestamp(t0, timezone.utc).isoformat(),
    }


def parse_any(path: str) -> dict:
    low = path.lower()
    if low.endswith((".tcx", ".xml", ".gz", ".zip")):
        return parse_tcx(path)              # _clean_xml yang membuka gz/zip
    if low.endswith(".fit"):
        return parse_fit(path)
    head = Path(path).read_bytes()[:4]
    if head[:2] in (b"\x1f\x8b", b"PK"):   # tebak dari magic bytes
        return parse_tcx(path)
    raise ValueError(f"format tidak didukung: {path}")
