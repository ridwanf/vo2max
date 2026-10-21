// static/app.js — render sesi + import TCX + input manual
const $ = (id) => document.getElementById(id);
const CACHE_KEY = "vo2max:lastState";

async function api(path, opts = {}) {
  const r = await fetch(path, { credentials: "same-origin", ...opts });
  if (r.status === 401) throw new Error("unauth");
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

const fmtPace = (s) => (s ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}/km` : "—");

function render(s) {
  const ses = s.session;
  $("setText").textContent = ses ? ses.main_set : "Belum ada sesi";
  $("hrRange").textContent = ses && ses.target_hr_low ? `${ses.target_hr_low}–${ses.target_hr_high}` : "—";
  $("paceText").textContent = ses ? fmtPace(ses.target_pace_s) : "—";
  $("vdot").textContent = s.vdot ? s.vdot.toFixed(1) : "—";
  $("recent").innerHTML = (s.recent || []).map((a) => {
    const km = (a.distance_m / 1000).toFixed(2);
    const min = Math.round(a.moving_s / 60);
    const bpm = a.avg_hr ? ` · ${Math.round(a.avg_hr)} bpm` : "";
    const src = a.source === "manual" ? "manual" : a.source;
    return `<li><span>${new Date(a.start_utc).toLocaleDateString("id-ID")}</span>` +
           `<span>${km} km · ${min}'${bpm} · ${src}</span></li>`;
  }).join("");
  localStorage.setItem(CACHE_KEY, JSON.stringify(s));
}

async function loadState() {
  try {
    const s = await api("/api/state");
    $("login").classList.add("hidden");
    $("app").classList.remove("hidden");
    render(s);
  } catch (e) {
    if (e.message === "unauth") {
      $("login").classList.remove("hidden");
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) { $("app").classList.remove("hidden"); render(JSON.parse(cached)); }
    } else console.error(e);
  }
}

$("btnLogin").onclick = async () => {
  await api("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ passphrase: $("pass").value }),
  });
  loadState();
};

$("file").onchange = async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append("file", f);
  const r = await api("/api/upload", { method: "POST", body: fd });
  alert(`Masuk: ${r.external_id} · ${r.distance_km} km · best5K ${r.best_5k_s || "-"}s`);
  loadState();
};

$("btnImport").onclick = async () => {
  $("btnImport").textContent = "Mengimport…";
  const r = await api("/api/import", { method: "POST" });
  $("btnImport").textContent = "Import folder di server";
  alert(`${r.results.length} file diproses`);
  loadState();
};

$("btnManual").onclick = async () => {
  await api("/api/manual", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      date: $("mDate").value, km: Number($("mKm").value),
      mmss: $("mTime").value, hr_avg: Number($("mHr").value) || null,
    }),
  });
  loadState();
};

$("btnCheck").onclick = async () => {
  const s = JSON.parse(localStorage.getItem(CACHE_KEY) || "{}");
  if (!s.session) return;
  const r = await api(`/api/check/${s.session.id}`, { method: "POST" });
  alert(`Verdict: ${r.verdict}${r.pct !== undefined ? ` · ${r.in_zone_s}s dari ${r.target_s}s (${r.pct}%)` : ""}`);
};

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");
loadState();
