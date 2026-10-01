// Laufzeittest: Testphase (Preismodell v1.9 §3a, Migration 0034 + /api/testphase).
//
//   T1 Signup → Testphase: eine Selbst-Registrierung landet auf tier='trial' + trial_ends_at
//      ~28 Tage (handle_new_user, 0034).
//   T2 /api/testphase: trial=true, tage_rest ~28, genutzt=0, limit_free=3.
//   T3 Nutzungszahl: ein aufgeschlossener Vorgang → genutzt=1.
//   T4 T−7-Fenster: trial_ends_at auf +5 Tage → tage_rest=5 (der Hinweis wird „bald").
//   T5 Eingeladener bekommt KEINE eigene Trial-Org, sondern tritt der bestehenden bei.
// Räumt Konten + Orgs weg. Nur Testdaten (.invalid).
//
// Aufruf:  node web/scripts/test_testphase.mjs [BASIS-URL]
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
const mkUser = async (email) => { const p = "T" + Math.random().toString(36).slice(2) + "x9!";
  const { data, error } = await svc.auth.admin.createUser({ email, password: p, email_confirm: true });
  if (error) throw new Error(`createUser ${email}: ${error.message}`); return { id: data.user.id, email, pw: p }; };
const up = async (id) => (await svc.from("user_profiles").select("org_id, active_profile_id").eq("id", id).single()).data;
async function cookie(email, p) {
  const jar = new Map();
  const c = createServerClient(URL_, ANON, { cookies: {
    getAll: () => [...jar].map(([name, value]) => ({ name, value })),
    setAll: (l) => l.forEach(({ name, value }) => jar.set(name, value)) } });
  const { error } = await c.auth.signInWithPassword({ email, password: p });
  if (error) throw new Error(`login ${email}: ${error.message}`);
  return [...jar].map(([n, v]) => `${n}=${v}`).join("; ");
}
const tp = (ck) => fetch(`${BASIS}/api/testphase`, { headers: { cookie: ck } }).then((r) => r.json());

const users = [], orgs = new Set();
try {
  // ── T1: Signup → Testphase ───────────────────────────────────────────────────────────────
  console.log("  T1 — Signup landet in der Testphase:");
  const A = await mkUser("rlstest-tp-a@govisor.invalid"); users.push(A.id);
  const upA = await up(A.id); const OA = upA.org_id; orgs.add(OA);
  const { data: org } = await svc.from("organizations").select("tier, trial_ends_at").eq("id", OA).single();
  const tage = org.trial_ends_at ? Math.ceil((Date.parse(org.trial_ends_at) - Date.now()) / 86400000) : 0;
  pruef(org.tier === "trial", "Org-Stufe = trial", `tier=${org.tier}`);
  pruef(tage >= 27 && tage <= 28, "trial_ends_at ~28 Tage", `tage=${tage}`);

  // ── T2: /api/testphase ───────────────────────────────────────────────────────────────────
  console.log("\n  T2 — /api/testphase:");
  const ckA = await cookie(A.email, A.pw);
  let s = await tp(ckA);
  pruef(s.trial === true && s.tage_rest >= 27 && s.genutzt === 0 && s.limit_free === 3,
    "trial=true, ~28 Tage, 0 genutzt, Limit 3", `${JSON.stringify(s)}`);

  // ── T3: Nutzungszahl ─────────────────────────────────────────────────────────────────────
  await svc.from("vorgang_freigaben").insert({ org_id: OA, art: "lead", ref: "T", durch: A.id });
  s = await tp(ckA);
  pruef(s.genutzt === 1, "T3 — ein Vorgang → genutzt=1", `genutzt=${s.genutzt}`);

  // ── T4: T−7-Fenster ──────────────────────────────────────────────────────────────────────
  await svc.from("organizations").update({ trial_ends_at: new Date(Date.now() + 5 * 86400000).toISOString() }).eq("id", OA);
  s = await tp(ckA);
  pruef(s.tage_rest === 5, "T4 — trial_ends_at +5 Tage → tage_rest=5 (Hinweis wird bald)", `tage_rest=${s.tage_rest}`);

  // ── T5: Eingeladener bekommt keine eigene Trial-Org ──────────────────────────────────────
  console.log("\n  T5 — Eingeladener tritt bei (keine eigene Trial-Org):");
  await svc.from("organizations").update({ tier: "analyse" }).eq("id", OA);   // Einladung erlauben (trial = 1 Sitz)
  await svc.from("pending_invites").insert({ org_id: OA, email: "rlstest-tp-inv@govisor.invalid", role: "member", invited_by: A.id });
  const INV = await mkUser("rlstest-tp-inv@govisor.invalid"); users.push(INV.id);
  const upI = await up(INV.id);
  pruef(upI.org_id === OA, "Eingeladener landet in OA (keine neue Org)", `org=${upI.org_id === OA ? "OA" : upI.org_id}`);
  if (upI.org_id && upI.org_id !== OA) orgs.add(upI.org_id);
} catch (e) {
  console.error("\n  ✖ Abbruch:", e.message); fehler++;
} finally {
  for (const id of users) { try { await svc.auth.admin.deleteUser(id); } catch { /* egal */ } }
  for (const o of orgs) { try { await svc.from("organizations").delete().eq("id", o); } catch { /* egal */ } }
  console.log("\n  Aufgeraeumt (Konten + Orgs geloescht).");
}
console.log(`\n  ${fehler ? "✖ " + fehler + " Fehler" : "✓ alles grün"}`);
process.exit(fehler ? 1 : 0);
