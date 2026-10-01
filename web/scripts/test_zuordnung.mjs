// Laufzeittest: Nutzer × Profil-Zuordnung (Preismodell v1.9 §7.1, Migration 0033).
//
// Owner A (Org auf tier='analyse', damit Mehrfachprofile erlaubt sind — die free-Grenze aus
// 0032 waere sonst hart 1), ein Mitglied M in derselben Org, ein Fremder Z in anderer Org.
//   T1 Auto-Zuordnung: A legt P2/P3 an → A ist allen dreien zugeordnet (Fallback wird beim
//      ersten Anlegen festgeschrieben, nicht gekappt).
//   T2 Umschalten A auf ein zugeordnetes Profil.
//   T3 Einschraenkung: Owner ordnet M nur P2 zu → M nutzbar NUR P2; aktives Profil zieht nach;
//      Umschalten auf nicht-zugeordnetes → 403.
//   T4 RLS: jeder sieht nur die EIGENEN Zuordnungen.
//   T5 Fremd-Org: Zuordnen ueber Org-Grenze → 400.
//   T6 Entzug: aktives → 409, letztes → geschuetzt, nicht-aktives → ok.
// Räumt Konten + Orgs weg. Nur Testdaten (.invalid).
//
// Aufruf:  node web/scripts/test_zuordnung.mjs [BASIS-URL]
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
const up = async (id) => (await svc.from("user_profiles").select("org_id, active_profile_id, role").eq("id", id).single()).data;
async function session(email, p) {
  const jar = new Map();
  const client = createServerClient(URL_, ANON, { cookies: {
    getAll: () => [...jar].map(([name, value]) => ({ name, value })),
    setAll: (l) => l.forEach(({ name, value }) => jar.set(name, value)) } });
  const { error } = await client.auth.signInWithPassword({ email, password: p });
  if (error) throw new Error(`login ${email}: ${error.message}`);
  return { client, cookie: [...jar].map(([n, v]) => `${n}=${v}`).join("; ") };
}
const api = (cookie, pfad, opt = {}) => fetch(`${BASIS}${pfad}`, { ...opt, headers: { cookie, "content-type": "application/json", ...(opt.headers || {}) } });

const users = [], orgs = new Set();
try {
  const A = await mkUser("rlstest-zu-a@govisor.invalid"); users.push(A.id);
  const upA = await up(A.id); const OA = upA.org_id; orgs.add(OA);
  await svc.from("organizations").update({ tier: "analyse" }).eq("id", OA);   // Mehrfachprofile erlauben
  const P1 = (await svc.from("profiles").select("id").eq("org_id", OA).single()).data.id;
  const sA = await session(A.email, A.pw);

  // Mitglied M in dieselbe Org ziehen
  const M = await mkUser("rlstest-zu-m@govisor.invalid"); users.push(M.id);
  const OM = (await up(M.id)).org_id;
  await svc.from("user_profiles").update({ org_id: OA, role: "member", active_profile_id: P1 }).eq("id", M.id);
  await svc.from("organizations").delete().eq("id", OM);   // Solo-Org von M weg
  const sM = await session(M.email, M.pw);

  // Fremder Z in eigener Org
  const Z = await mkUser("rlstest-zu-z@govisor.invalid"); users.push(Z.id);
  const upZ = await up(Z.id); orgs.add(upZ.org_id);
  const PZ = (await svc.from("profiles").select("id").eq("org_id", upZ.org_id).single()).data.id;

  // ── T1: Auto-Zuordnung beim Anlegen (A) ──────────────────────────────────────────────────
  console.log("  T1 — Auto-Zuordnung (A legt P2/P3 an):");
  let r = await api(sA.cookie, "/api/profil", { method: "POST", body: JSON.stringify({ name: "P2" }) });
  pruef(r.ok, "P2 angelegt", (await r.json()).error || "");
  r = await api(sA.cookie, "/api/profil", { method: "POST", body: JSON.stringify({ name: "P3" }) });
  pruef(r.ok, "P3 angelegt");
  r = await api(sA.cookie, "/api/profil"); let j = await r.json();
  pruef(j.profiles.length === 3 && j.profiles.every((p) => p.nutzbar), "A: alle 3 Profile nutzbar (Fallback festgeschrieben)",
    `nutzbar: ${j.profiles.filter((p) => p.nutzbar).length}/3`);
  const P2 = j.profiles.find((p) => p.name === "P2").id, P3 = j.profiles.find((p) => p.name === "P3").id;
  const { count: zuA } = await svc.from("user_profile_assignments").select("profile_id", { count: "exact", head: true }).eq("user_id", A.id);
  pruef(zuA === 3, "A hat 3 Zuordnungen in der DB", `count=${zuA}`);

  // ── T2: Umschalten auf zugeordnetes Profil ───────────────────────────────────────────────
  r = await api(sA.cookie, "/api/profil/wechseln", { method: "POST", body: JSON.stringify({ profile_id: P2 }) });
  pruef(r.status === 200, "T2 — A schaltet auf P2 (zugeordnet)");

  // ── T3: Einschraenkung M auf P2 ──────────────────────────────────────────────────────────
  console.log("\n  T3 — Owner ordnet M nur P2 zu:");
  r = await api(sA.cookie, "/api/org/zuordnung", { method: "POST", body: JSON.stringify({ user_id: M.id, profile_id: P2 }) });
  pruef(r.ok, "Zuordnung M→P2 gesetzt", (await r.json()).error || "");
  const upM = await up(M.id);
  pruef(upM.active_profile_id === P2, "M aktives Profil zog auf P2 nach (war P1, nicht mehr zugeordnet)", `aktiv=${upM.active_profile_id === P2 ? "P2" : upM.active_profile_id}`);
  r = await api(sM.cookie, "/api/profil"); j = await r.json();
  const nP2 = j.profiles.find((p) => p.id === P2)?.nutzbar, nP1 = j.profiles.find((p) => p.id === P1)?.nutzbar, nP3 = j.profiles.find((p) => p.id === P3)?.nutzbar;
  pruef(nP2 === true && nP1 === false && nP3 === false, "M sieht nur P2 als nutzbar", `P1=${nP1} P2=${nP2} P3=${nP3}`);
  r = await api(sM.cookie, "/api/profil/wechseln", { method: "POST", body: JSON.stringify({ profile_id: P3 }) });
  pruef(r.status === 403, "M: Umschalten auf nicht-zugeordnetes P3 → 403", `status ${r.status}`);
  r = await api(sM.cookie, "/api/profil/wechseln", { method: "POST", body: JSON.stringify({ profile_id: P2 }) });
  pruef(r.status === 200, "M: Umschalten auf zugeordnetes P2 → ok");

  // ── T4: RLS ──────────────────────────────────────────────────────────────────────────────
  console.log("\n  T4 — RLS (nur eigene Zuordnungen):");
  const { data: sichtM } = await sM.client.from("user_profile_assignments").select("user_id, profile_id");
  pruef((sichtM?.length ?? 0) === 1 && sichtM.every((x) => x.user_id === M.id), "M sieht nur eigene Zuordnung (1)", `${sichtM?.length}`);
  const { data: sichtA } = await sA.client.from("user_profile_assignments").select("user_id");
  pruef((sichtA?.length ?? 0) === 3 && sichtA.every((x) => x.user_id === A.id), "A sieht nur eigene (3)", `${sichtA?.length}`);

  // ── T5: Fremd-Org ────────────────────────────────────────────────────────────────────────
  console.log("\n  T5 — Fremd-Org abgewiesen:");
  r = await api(sA.cookie, "/api/org/zuordnung", { method: "POST", body: JSON.stringify({ user_id: Z.id, profile_id: P2 }) });
  pruef(r.status === 400, "A ordnet fremden Nutzer Z zu → 400", `status ${r.status}`);
  r = await api(sA.cookie, "/api/org/zuordnung", { method: "POST", body: JSON.stringify({ user_id: M.id, profile_id: PZ }) });
  pruef(r.status === 400, "A ordnet fremdes Profil (PZ) zu → 400", `status ${r.status}`);

  // ── T6: Entzug-Schutz ────────────────────────────────────────────────────────────────────
  console.log("\n  T6 — Entzug:");
  await api(sA.cookie, "/api/org/zuordnung", { method: "POST", body: JSON.stringify({ user_id: M.id, profile_id: P1 }) }); // M: {P2,P1}, aktiv P2
  r = await api(sA.cookie, `/api/org/zuordnung?user_id=${M.id}&profile_id=${P1}`, { method: "DELETE" });
  pruef(r.status === 200, "nicht-aktives P1 entziehen → ok", `status ${r.status}`);
  r = await api(sA.cookie, `/api/org/zuordnung?user_id=${M.id}&profile_id=${P2}`, { method: "DELETE" });
  pruef(r.status === 409, "aktives P2 entziehen → 409", `status ${r.status}`);
} catch (e) {
  console.error("\n  ✖ Abbruch:", e.message); fehler++;
} finally {
  for (const id of users) { try { await svc.auth.admin.deleteUser(id); } catch { /* egal */ } }
  for (const o of orgs) { try { await svc.from("organizations").delete().eq("id", o); } catch { /* egal */ } }
  console.log("\n  Aufgeraeumt (Konten + Orgs geloescht).");
}
console.log(`\n  ${fehler ? "✖ " + fehler + " Fehler" : "✓ alles grün"}`);
process.exit(fehler ? 1 : 0);
