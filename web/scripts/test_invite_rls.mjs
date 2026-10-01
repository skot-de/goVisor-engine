// Laufzeittest: Invite-Kreis der Mehrfachprofile/Seats (0026) in der App.
//
// Prueft gegen den laufenden Dev-Server:
//   T1 Einladen:  Owner A (seats_paid=2) laedt X ein (POST /api/org/mitglieder) → X landet in
//                 As ORG (role member, aktives Profil = As Org-Profil), Einladung eingeloest —
//                 NICHT in einer Solo-Org. (handle_new_user, 0026)
//   T2 Seat:      3. Person Y einladen → 409 (belegt = Mitglieder + offene Einladungen >= 2).
//   T3 Solo:      Ein Signup OHNE Einladung bekommt eine EIGENE Org (nicht As).
//   T4 Authz/RLS: ein Mitglied (X) darf nicht einladen → 403; Team-Liste ist auf die Org gescopet.
// Räumt alle Testkonten + Orgs weg. Nur Testdaten (.invalid).
//
// Aufruf:  node web/scripts/test_invite_rls.mjs [BASIS-URL]
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

const OWNER = "rlstest-owner@govisor.invalid";
const INV = "rlstest-invitee@govisor.invalid";
const THIRD = "rlstest-third@govisor.invalid";
const SOLO = "rlstest-solo@govisor.invalid";

let fehler = 0;
const pruef = (ok, name, info = "") => { console.log(`  ${ok ? "✓" : "✖"} ${name}${info ? "  — " + info : ""}`); if (!ok) fehler++; };
const pw = () => "T" + Math.random().toString(36).slice(2) + "x9!";

async function createUser(email) {
  const p = pw();
  const { data, error } = await svc.auth.admin.createUser({ email, password: p, email_confirm: true });
  if (error) throw new Error(`createUser ${email}: ${error.message}`);
  return { id: data.user.id, email, pw: p };
}
async function findUser(email) {
  const { data } = await svc.auth.admin.listUsers({ page: 1, perPage: 200 });
  return data.users.find((u) => (u.email || "").toLowerCase() === email.toLowerCase()) || null;
}
async function up(id) { const { data } = await svc.from("user_profiles").select("org_id, active_profile_id, role, email").eq("id", id).single(); return data; }
async function weg(id) { try { await svc.auth.admin.deleteUser(id); } catch { /* egal */ } }
async function orgWeg(id) { if (id) { try { await svc.from("organizations").delete().eq("id", id); } catch { /* egal */ } } }

async function session(email, p) {
  const jar = new Map();
  const client = createServerClient(URL_, ANON, {
    cookies: { getAll: () => [...jar].map(([name, value]) => ({ name, value })), setAll: (l) => l.forEach(({ name, value }) => jar.set(name, value)) },
  });
  const { error } = await client.auth.signInWithPassword({ email, password: p });
  if (error) throw new Error(`login ${email}: ${error.message}`);
  return [...jar].map(([n, v]) => `${n}=${v}`).join("; ");
}
const api = (cookie, pfad, opt = {}) => fetch(`${BASIS}${pfad}`, { ...opt, headers: { cookie, "content-type": "application/json", ...(opt.headers || {}) } });

const aufraeumen = [];      // user-ids
const orgsWeg = new Set();  // org-ids
try {
  console.log("  Setup: Owner A (seats_paid=2) …");
  const A = await createUser(OWNER); aufraeumen.push(A.id);
  const upA = await up(A.id); orgsWeg.add(upA.org_id);
  pruef(upA.role === "owner" && !!upA.org_id, "A ist owner einer Org");
  await svc.from("organizations").update({ seats_paid: 2 }).eq("id", upA.org_id);
  const cookieA = await session(A.email, A.pw);

  // ── T1: Einladen ───────────────────────────────────────────────────────────────────────
  console.log("\n  T1 — Einladen (X → As Org):");
  let r = await api(cookieA, "/api/org/mitglieder"); let j = await r.json();
  pruef(r.status === 200 && j.team && j.mitglieder.length === 1 && j.role === "owner", "GET Team: 1 Mitglied (owner)");
  r = await api(cookieA, "/api/org/mitglieder", { method: "POST", body: JSON.stringify({ email: INV }) });
  j = await r.json();
  pruef(r.status === 200 && j.ok, "POST Einladung X", j.warnung || j.error || "");

  // X kann vom Auth-Invite schon existieren; sonst Signup simulieren (Kreis ist dieselbe RPC).
  let xUser = await findUser(INV);
  let weg_pfad = xUser ? "Auth-Invite legte X an" : "Signup simuliert";
  if (!xUser) { const x = await createUser(INV); xUser = { id: x.id }; }
  aufraeumen.push(xUser.id);
  const upX = await up(xUser.id);
  pruef(!!upX && upX.org_id === upA.org_id, "X landet in As ORG (nicht Solo)", `${weg_pfad}; org ${upX?.org_id?.slice(0,8)}`);
  pruef(upX?.role === "member", "X hat Rolle member", `role=${upX?.role}`);
  pruef(!!upX?.active_profile_id, "X hat ein aktives Profil (As Org-Profil)");
  const { data: invRow } = await svc.from("pending_invites").select("status").eq("org_id", upA.org_id).eq("email", INV).order("created_at", { ascending: false }).limit(1).single();
  pruef(invRow?.status === "eingeloest", "Einladung als eingeloest markiert", `status=${invRow?.status}`);
  r = await api(cookieA, "/api/org/mitglieder"); j = await r.json();
  pruef(j.mitglieder.length === 2 && j.einladungen.length === 0, "GET Team: jetzt 2 Mitglieder, 0 offene");

  // ── T2: Seat-Grenze ──────────────────────────────────────────────────────────────────────
  console.log("\n  T2 — Seat-Grenze (3. Person):");
  r = await api(cookieA, "/api/org/mitglieder", { method: "POST", body: JSON.stringify({ email: THIRD }) });
  j = await r.json();
  pruef(r.status === 409, "3. Einladung abgewiesen (409)", j.error || `status ${r.status}`);
  const nochDa = await findUser(THIRD);
  if (nochDa) { aufraeumen.push(nochDa.id); const u = await up(nochDa.id); if (u?.org_id) orgsWeg.add(u.org_id); }
  pruef(!nochDa, "3. Person wurde nicht angelegt");

  // ── T3: Solo ohne Einladung ──────────────────────────────────────────────────────────────
  console.log("\n  T3 — Signup ohne Einladung → Solo-Org:");
  const Z = await createUser(SOLO); aufraeumen.push(Z.id);
  const upZ = await up(Z.id); orgsWeg.add(upZ.org_id);
  pruef(!!upZ.org_id && upZ.org_id !== upA.org_id && upZ.role === "owner", "Z bekommt eigene Org (owner)", `org ${upZ.org_id?.slice(0,8)}`);

  // ── T4: Authz — Mitglied darf nicht einladen ─────────────────────────────────────────────
  console.log("\n  T4 — Authz (Mitglied X darf nicht einladen):");
  const neuesPw = pw();
  await svc.auth.admin.updateUserById(xUser.id, { password: neuesPw, email_confirm: true });
  const cookieX = await session(INV, neuesPw);
  r = await api(cookieX, "/api/org/mitglieder", { method: "POST", body: JSON.stringify({ email: "irgendwer@govisor.invalid" }) });
  j = await r.json();
  pruef(r.status === 403, "X (member): Einladen verweigert (403)", j.error || `status ${r.status}`);
  r = await api(cookieX, "/api/org/mitglieder"); j = await r.json();
  pruef(j.team === true && j.mitglieder.length === 2 && j.role === "member", "X sieht Team seiner Org (als member)");
} catch (e) {
  console.error("\n  ✖ Abbruch:", e.message); fehler++;
} finally {
  for (const id of aufraeumen) await weg(id);
  for (const o of orgsWeg) await orgWeg(o);
  console.log("\n  Aufgeraeumt (Konten + Orgs geloescht).");
}
console.log(`\n  ${fehler ? "✖ " + fehler + " Fehler" : "✓ alles grün"}`);
process.exit(fehler ? 1 : 0);
