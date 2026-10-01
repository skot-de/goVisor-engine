// Laufzeittest: Kauf-Pfad der Mehrfachprofile/Seats (0027) — 503-Stub + idempotente Gutschrift.
//
// Teil A (API, eingeloggter Owner): /api/kauf/checkout + /api/kauf/webhook sind ehrliche Stubs,
//   solange Preise/Stripe nicht scharf sind → 503 (kein vorgetaeuschter Erfolg). Dazu die
//   Validierungs-Reihenfolge (400 vor 503) und die Berechtigung (401/403).
// Teil B (Service-RPC): kauf_gutschreiben verbucht GENAU EINMAL je (provider, provider_ref):
//   erster Aufruf 'gutgeschrieben' + Kontingent hoch, zweiter mit gleicher ref 'schon_verbucht'
//   ohne Doppel-Increment; purchases-Ledger haelt je ref eine Zeile. Ungueltige Eingaben werfen.
// Räumt das Testkonto + Org weg. Nur Testdaten (.invalid).
//
// Aufruf:  node web/scripts/test_kauf.mjs [BASIS-URL]
import { readFileSync } from "node:fs";
import { createClient } from "@supabase/supabase-js";
import { createServerClient } from "@supabase/ssr";

const BASIS = (process.argv[2] || "http://127.0.0.1:3000").replace(/\/$/, "");
const env = Object.fromEntries(
  readFileSync(new URL("../.env.local", import.meta.url), "utf8")
    .split("\n").map((z) => z.match(/^\s*([A-Za-z_]+)\s*=\s*"?([^"\n]*)"?/))
    .filter(Boolean).map((m) => [m[1], m[2]]));
const URL_ = env.NEXT_PUBLIC_SUPABASE_URL, ANON = env.NEXT_PUBLIC_SUPABASE_ANON_KEY, SECRET = env.SUPABASE_SECRET_KEY;
const svc = createClient(URL_, SECRET, { auth: { persistSession: false, autoRefreshToken: false } });

let fehler = 0;
const pruef = (ok, name, info = "") => { console.log(`  ${ok ? "✓" : "✖"} ${name}${info ? "  — " + info : ""}`); if (!ok) fehler++; };

async function createUser(email) {
  const p = "T" + Math.random().toString(36).slice(2) + "x9!";
  const { data, error } = await svc.auth.admin.createUser({ email, password: p, email_confirm: true });
  if (error) throw new Error(`createUser: ${error.message}`);
  return { id: data.user.id, email, pw: p };
}
async function up(id) { const { data } = await svc.from("user_profiles").select("org_id").eq("id", id).single(); return data; }
async function org(id) { const { data } = await svc.from("organizations").select("seats_paid, profiles_paid").eq("id", id).single(); return data; }
async function session(email, p) {
  const jar = new Map();
  const client = createServerClient(URL_, ANON, {
    cookies: { getAll: () => [...jar].map(([name, value]) => ({ name, value })), setAll: (l) => l.forEach(({ name, value }) => jar.set(name, value)) },
  });
  const { error } = await client.auth.signInWithPassword({ email, password: p });
  if (error) throw new Error(`login: ${error.message}`);
  return [...jar].map(([n, v]) => `${n}=${v}`).join("; ");
}
const api = (cookie, pfad, opt = {}) => fetch(`${BASIS}${pfad}`, { ...opt, headers: { ...(cookie ? { cookie } : {}), "content-type": "application/json", ...(opt.headers || {}) } });
const ref = () => "test_" + Math.random().toString(36).slice(2);

let A, orgId;
try {
  A = await createUser("rlstest-kauf@govisor.invalid");
  orgId = (await up(A.id)).org_id;
  const cookie = await session(A.email, A.pw);

  // ── Teil A: 503-Stub + Validierung + Authz ───────────────────────────────────────────────
  console.log("  Teil A — API-Stub (503) + Validierung:");
  let r = await api(cookie, "/api/kauf/checkout", { method: "POST", body: JSON.stringify({ art: "seat", menge: 1 }) });
  let j = await r.json();
  pruef(r.status === 503, "checkout seat → 503 (Stripe nicht konfiguriert)", j.error || `status ${r.status}`);
  r = await api(cookie, "/api/kauf/checkout", { method: "POST", body: JSON.stringify({ art: "profile", menge: 2 }) });
  pruef(r.status === 503, "checkout profile → 503");
  r = await api(cookie, "/api/kauf/webhook", { method: "POST", body: "{}" });
  pruef(r.status === 503, "webhook → 503 (Stripe aus)");
  // Validierung GREIFT VOR dem 503: ungueltige art/menge → 400
  r = await api(cookie, "/api/kauf/checkout", { method: "POST", body: JSON.stringify({ art: "foo", menge: 1 }) });
  pruef(r.status === 400, "checkout ungueltige art → 400 (vor 503)");
  r = await api(cookie, "/api/kauf/checkout", { method: "POST", body: JSON.stringify({ art: "seat", menge: 0 }) });
  pruef(r.status === 400, "checkout menge 0 → 400");
  // Authz: ohne Session 401
  r = await api(null, "/api/kauf/checkout", { method: "POST", body: JSON.stringify({ art: "seat", menge: 1 }) });
  pruef(r.status === 401, "checkout ohne Session → 401", `status ${r.status}`);

  // ── Teil B: kauf_gutschreiben idempotent ─────────────────────────────────────────────────
  console.log("\n  Teil B — kauf_gutschreiben (Idempotenz):");
  const basis = await org(orgId);
  pruef(!!basis, "Org-Kontingent gelesen", `seats=${basis.seats_paid} profiles=${basis.profiles_paid}`);
  const refSeat = ref(), refProf = ref();

  let { data: d1, error: e1 } = await svc.rpc("kauf_gutschreiben", { p_org: orgId, p_art: "seat", p_menge: 2, p_provider: "stripe", p_ref: refSeat, p_cents: 1000 });
  pruef(!e1 && d1 === "gutgeschrieben", "1. Aufruf (seat +2) → gutgeschrieben", e1?.message || `data=${d1}`);
  let nach1 = await org(orgId);
  pruef(nach1.seats_paid === basis.seats_paid + 2, "seats_paid +2", `${basis.seats_paid}→${nach1.seats_paid}`);

  let { data: d2, error: e2 } = await svc.rpc("kauf_gutschreiben", { p_org: orgId, p_art: "seat", p_menge: 2, p_provider: "stripe", p_ref: refSeat, p_cents: 1000 });
  pruef(!e2 && d2 === "schon_verbucht", "2. Aufruf (gleiche ref) → schon_verbucht", e2?.message || `data=${d2}`);
  let nach2 = await org(orgId);
  pruef(nach2.seats_paid === nach1.seats_paid, "seats_paid UNVERAENDERT (kein Doppel-Increment)", `seats=${nach2.seats_paid}`);

  let { data: d3, error: e3 } = await svc.rpc("kauf_gutschreiben", { p_org: orgId, p_art: "profile", p_menge: 3, p_provider: "stripe", p_ref: refProf });
  pruef(!e3 && d3 === "gutgeschrieben", "profile +3 → gutgeschrieben", e3?.message);
  let nach3 = await org(orgId);
  pruef(nach3.profiles_paid === basis.profiles_paid + 3, "profiles_paid +3", `${basis.profiles_paid}→${nach3.profiles_paid}`);

  const { count } = await svc.from("purchases").select("id", { count: "exact", head: true }).eq("org_id", orgId);
  pruef(count === 2, "purchases-Ledger: genau 2 Zeilen (je ref eine)", `count=${count}`);

  // Ungueltige Eingaben werfen (RPC raises)
  let { error: eArt } = await svc.rpc("kauf_gutschreiben", { p_org: orgId, p_art: "quatsch", p_menge: 1, p_provider: "stripe", p_ref: ref() });
  pruef(!!eArt, "ungueltige art → Fehler", eArt?.message?.slice(0, 50));
  let { error: eMenge } = await svc.rpc("kauf_gutschreiben", { p_org: orgId, p_art: "seat", p_menge: 0, p_provider: "stripe", p_ref: ref() });
  pruef(!!eMenge, "menge 0 → Fehler", eMenge?.message?.slice(0, 50));
} catch (e) {
  console.error("\n  ✖ Abbruch:", e.message); fehler++;
} finally {
  if (A) { try { await svc.auth.admin.deleteUser(A.id); } catch { /* egal */ } }
  if (orgId) { try { await svc.from("organizations").delete().eq("id", orgId); } catch { /* egal */ } }  // kaskadiert purchases
  console.log("\n  Aufgeraeumt (Konto + Org + purchases geloescht).");
}
console.log(`\n  ${fehler ? "✖ " + fehler + " Fehler" : "✓ alles grün"}`);
process.exit(fehler ? 1 : 0);
