// Laufzeittest: Profil-Wechsel + RLS-Isolation der Mehrfachprofile (0024-0027) in der App.
//
// Legt ZWEI Wegwerf-Konten in GETRENNTEN Orgs an (handle_new_user → je Org+Profil+owner),
// hebt As Profil-Kontingent auf 2, und prueft dann gegen den laufenden Dev-Server:
//   T1 Wechsel: A legt 2. Profil an (POST /api/profil), listet, schaltet um (/api/profil/wechseln),
//               GET zeigt das neue aktive Profil.
//   T2 RLS:     A sieht nur As Profile, B nur Bs (authentifizierter DB-Client, echte RLS);
//               B kann NICHT auf As Profil umschalten (API 404, weil RLS es verbirgt);
//               B kann As Profil per Kennung nicht lesen.
// Räumt die Konten am Ende wieder weg. Nur Testdaten (.invalid, kein Mailversand).
//
// Aufruf:  node web/scripts/test_profil_rls.mjs [BASIS-URL]
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

async function anlegen(email) {
  const pw = "T" + Math.random().toString(36).slice(2) + "x9!";
  const { data, error } = await svc.auth.admin.createUser({ email, password: pw, email_confirm: true });
  if (error) throw new Error(`createUser ${email}: ${error.message}`);
  return { id: data.user.id, email, pw };
}
async function weg(id) { try { await svc.auth.admin.deleteUser(id); } catch { /* egal */ } }

async function session(email, pw) {
  const jar = new Map();
  const client = createServerClient(URL_, ANON, {
    cookies: { getAll: () => [...jar].map(([name, value]) => ({ name, value })), setAll: (l) => l.forEach(({ name, value }) => jar.set(name, value)) },
  });
  const { data, error } = await client.auth.signInWithPassword({ email, password: pw });
  if (error) throw new Error(`login ${email}: ${error.message}`);
  const cookie = [...jar].map(([n, v]) => `${n}=${v}`).join("; ");
  return { client, cookie, userId: data.user.id };
}
const api = (cookie, pfad, opt = {}) => fetch(`${BASIS}${pfad}`, { ...opt, headers: { cookie, "content-type": "application/json", ...(opt.headers || {}) } });

let A, B;
try {
  console.log("  Setup: zwei Wegwerf-Konten in getrennten Orgs …");
  A = await anlegen("rlstest-a@govisor.invalid");
  B = await anlegen("rlstest-b@govisor.invalid");

  // org_ids (service, bypass RLS) + As Kontingent auf 2 heben (simuliert gekauftes 2. Profil)
  const { data: upA } = await svc.from("user_profiles").select("org_id, active_profile_id").eq("id", A.id).single();
  const { data: upB } = await svc.from("user_profiles").select("org_id, active_profile_id").eq("id", B.id).single();
  A.org = upA?.org_id; B.org = upB?.org_id;   // fuer den Teardown merken (Org kaskadiert NICHT beim User-Delete)
  pruef(!!upA?.org_id && !!upB?.org_id && upA.org_id !== upB.org_id, "getrennte Orgs angelegt",
    `A=${upA?.org_id?.slice(0, 8)} B=${upB?.org_id?.slice(0, 8)}`);
  pruef(!!upA?.active_profile_id, "A hat aktives Profil aus handle_new_user");
  await svc.from("organizations").update({ profiles_paid: 2 }).eq("id", upA.org_id);

  const sA = await session(A.email, A.pw);
  const sB = await session(B.email, B.pw);

  // ── T1: Profil-Wechsel (A) ──────────────────────────────────────────────────────────────
  console.log("\n  T1 — Profil-Wechsel (A):");
  let r = await api(sA.cookie, "/api/profil"); let j = await r.json();
  pruef(r.status === 200 && j.mehrfach === true && j.profiles.length === 1, "GET /api/profil: 1 Profil",
    `limit=${j.limit}`);
  r = await api(sA.cookie, "/api/profil", { method: "POST", body: JSON.stringify({ name: "Zweitprofil" }) });
  j = await r.json();
  pruef(r.status === 200 && j.ok, "POST 2. Profil angelegt (Kontingent 2)", j.error || "");
  r = await api(sA.cookie, "/api/profil"); j = await r.json();
  const neu = j.profiles.find((p) => p.name === "Zweitprofil");
  const altAktiv = j.profiles.find((p) => p.active);
  pruef(j.profiles.length === 2 && !!neu, "GET: jetzt 2 Profile");
  r = await api(sA.cookie, "/api/profil/wechseln", { method: "POST", body: JSON.stringify({ profile_id: neu.id }) });
  j = await r.json();
  pruef(r.status === 200 && j.active_profile_id === neu.id, "Wechsel auf Zweitprofil");
  r = await api(sA.cookie, "/api/profil"); j = await r.json();
  const nunAktiv = j.profiles.find((p) => p.active);
  pruef(nunAktiv?.id === neu.id && nunAktiv?.id !== altAktiv?.id, "GET: aktives Profil ist jetzt das neue",
    `${altAktiv?.name} → ${nunAktiv?.name}`);

  // ── T2: RLS-Isolation ───────────────────────────────────────────────────────────────────
  console.log("\n  T2 — RLS-Isolation:");
  const { data: profA } = await sA.client.from("profiles").select("id,org_id");
  const { data: profB } = await sB.client.from("profiles").select("id,org_id");
  pruef((profA?.length === 2) && profA.every((p) => p.org_id === upA.org_id), "A sieht nur As Org-Profile (2)",
    `sichtbar: ${profA?.length}`);
  pruef((profB?.length === 1) && profB.every((p) => p.org_id === upB.org_id), "B sieht nur Bs Org-Profil (1)",
    `sichtbar: ${profB?.length}`);
  const aIds = new Set((profA || []).map((p) => p.id));
  pruef(!(profB || []).some((p) => aIds.has(p.id)), "Bs Sicht enthält KEIN Profil von A");
  // B liest As Profil per Kennung → leer (RLS verbirgt)
  const { data: leck } = await sB.client.from("profiles").select("id").eq("id", neu.id);
  pruef((leck?.length ?? 0) === 0, "B kann As Profil nicht per Kennung lesen");
  // B schaltet per API auf As Profil um → 404 (nicht sichtbar)
  r = await api(sB.cookie, "/api/profil/wechseln", { method: "POST", body: JSON.stringify({ profile_id: neu.id }) });
  pruef(r.status === 404, "B: Umschalten auf As Profil wird abgewiesen (404)", `status ${r.status}`);
  // Bs aktives Profil blieb unveraendert
  const { data: upBnachher } = await svc.from("user_profiles").select("active_profile_id").eq("id", B.id).single();
  pruef(upBnachher?.active_profile_id === upB.active_profile_id, "Bs aktives Profil unveraendert");
} catch (e) {
  console.error("\n  ✖ Abbruch:", e.message); fehler++;
} finally {
  // User zuerst (kaskadiert user_profiles), dann die Org (kaskadiert profiles) — sonst Waisen.
  for (const k of [A, B]) {
    if (!k) continue;
    await weg(k.id);
    if (k.org) { try { await svc.from("organizations").delete().eq("id", k.org); } catch { /* egal */ } }
  }
  console.log("\n  Aufgeraeumt (Testkonten + Orgs geloescht).");
}
console.log(`\n  ${fehler ? "✖ " + fehler + " Fehler" : "✓ alles grün"}`);
process.exit(fehler ? 1 : 0);
