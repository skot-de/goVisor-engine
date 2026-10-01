// Laufzeittest: Vorgangs-Kontingent (Preismodell v1.9 §4.3, Migration 0029) + RPC-Haertung (0030).
//
// Teil A (Service-RPC, wie die App ruft): vorgang_freischalten mit p_limit=3 → 3× freigeschaltet,
//   4. → limit_erreicht; erneutes Oeffnen → schon_frei (dauerhaft, kein Verbrauch); ein Eintrag
//   aus dem Vormonat zaehlt NICHT aufs Monatslimit (Monatsfenster); p_limit=null → unbegrenzt.
// Teil B (Sicherheit): ein authentifizierter Client darf die RPC NICHT direkt rufen (0030) —
//   sonst waere das Limit client-seitig umgehbar.
// Teil C (API, Session): GET/POST /api/kontingent; solange die Paywall aus ist, ist das Limit null
//   (unbegrenzt) und der Zaehler zaehlt hoch.
// Teil D (RLS): B sieht die Freigaben von A nicht.
// Räumt Konten + Orgs weg (kaskadiert vorgang_freigaben). Nur Testdaten (.invalid).
//
// Aufruf:  node web/scripts/test_kontingent.mjs [BASIS-URL]
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
const frei = (org, art, ref, limit, durch) => svc.rpc("vorgang_freischalten", { p_org: org, p_art: art, p_ref: ref, p_limit: limit, p_durch: durch });

async function createUser(email) {
  const p = "T" + Math.random().toString(36).slice(2) + "x9!";
  const { data, error } = await svc.auth.admin.createUser({ email, password: p, email_confirm: true });
  if (error) throw new Error(`createUser: ${error.message}`);
  return { id: data.user.id, email, pw: p };
}
async function up(id) { const { data } = await svc.from("user_profiles").select("org_id").eq("id", id).single(); return data; }
async function sessionClient(email, p) {
  const jar = new Map();
  const client = createServerClient(URL_, ANON, {
    cookies: { getAll: () => [...jar].map(([name, value]) => ({ name, value })), setAll: (l) => l.forEach(({ name, value }) => jar.set(name, value)) },
  });
  const { error } = await client.auth.signInWithPassword({ email, password: p });
  if (error) throw new Error(`login: ${error.message}`);
  return { client, cookie: [...jar].map(([n, v]) => `${n}=${v}`).join("; ") };
}
const api = (cookie, pfad, opt = {}) => fetch(`${BASIS}${pfad}`, { ...opt, headers: { cookie, "content-type": "application/json", ...(opt.headers || {}) } });

let A, B;
try {
  A = await createUser("rlstest-vorgang-a@govisor.invalid");
  B = await createUser("rlstest-vorgang-b@govisor.invalid");
  const orgA = (await up(A.id)).org_id, orgB = (await up(B.id)).org_id;

  // ── Teil A: Limit + Dauerhaftigkeit + Monatsfenster ──────────────────────────────────────
  console.log("  Teil A — Limit/Dauerhaftigkeit (Service-RPC, limit=3):");
  for (const n of [1, 2, 3]) {
    const { data } = await frei(orgA, "lead", "L" + n, 3, A.id);
    pruef(data === "freigeschaltet", `L${n} → freigeschaltet`, `data=${data}`);
  }
  let { data: l4 } = await frei(orgA, "lead", "L4", 3, A.id);
  pruef(l4 === "limit_erreicht", "L4 → limit_erreicht (3/Monat voll)", `data=${l4}`);
  let { data: wieder } = await frei(orgA, "lead", "L1", 3, A.id);
  pruef(wieder === "schon_frei", "L1 erneut → schon_frei (dauerhaft, kein Verbrauch)", `data=${wieder}`);
  let { data: firmaVoll } = await frei(orgA, "firma", "F1", 3, A.id);
  pruef(firmaVoll === "limit_erreicht", "Firma bei vollem Limit → limit_erreicht (eine Zahl, eine Einheit)");

  // Vormonats-Eintrag zaehlt nicht aufs Monatslimit
  const vormonat = new Date(); vormonat.setUTCDate(1); vormonat.setUTCHours(0,0,0,0); vormonat.setUTCDate(vormonat.getUTCDate() - 5);
  await svc.from("vorgang_freigaben").insert({ org_id: orgA, art: "lead", ref: "ALT", freigeschaltet_am: vormonat.toISOString(), durch: A.id });
  const { count: diesenMonat } = await svc.from("vorgang_freigaben").select("id", { count: "exact", head: true })
    .eq("org_id", orgA).gte("freigeschaltet_am", new Date(Date.UTC(new Date().getUTCFullYear(), new Date().getUTCMonth(), 1)).toISOString());
  pruef(diesenMonat === 3, "Vormonats-Eintrag zaehlt nicht auf diesen Monat", `diesen Monat=${diesenMonat}`);
  let { data: altWieder } = await frei(orgA, "lead", "ALT", 3, A.id);
  pruef(altWieder === "schon_frei", "Vormonats-Vorgang weiterhin offen (schon_frei)");

  console.log("\n  Teil A — unbegrenzt (limit=null):");
  let { data: ohne } = await frei(orgA, "lead", "L99", null, A.id);
  pruef(ohne === "freigeschaltet", "limit=null → freigeschaltet trotz vollem Monat");

  // ── Teil B: Sicherheit — authed Client darf die RPC NICHT rufen (0030) ────────────────────
  console.log("\n  Teil B — RPC client-gesperrt (0030):");
  const sA = await sessionClient(A.email, A.pw);
  const { error: rpcErr } = await sA.client.rpc("vorgang_freischalten", { p_org: orgA, p_art: "lead", p_ref: "HACK", p_limit: 9999, p_durch: A.id });
  pruef(!!rpcErr, "authed Client: direkter RPC-Aufruf abgewiesen", rpcErr ? rpcErr.message.slice(0, 50) : "DURCHGELASSEN!");
  const { data: hackRow } = await svc.from("vorgang_freigaben").select("id").eq("org_id", orgA).eq("ref", "HACK");
  pruef((hackRow?.length ?? 0) === 0, "kein 'HACK'-Eintrag angelegt (Umgehung verhindert)");

  // ── Teil C: API-Pfad (Paywall aus → unbegrenzt, Zaehler zaehlt) ───────────────────────────
  console.log("\n  Teil C — API /api/kontingent (Session):");
  let r = await api(sA.cookie, "/api/kontingent"); let j = await r.json();
  pruef(r.status === 200 && j.limit === null, "GET stand: limit=null (Paywall aus = unbegrenzt)", `verbraucht=${j.verbraucht}`);
  const vorher = j.verbraucht;
  r = await api(sA.cookie, "/api/kontingent", { method: "POST", body: JSON.stringify({ art: "lead", ref: "API1" }) });
  j = await r.json();
  pruef(r.status === 200 && j.ok && j.status === "freigeschaltet", "POST lead API1 → freigeschaltet", j.error || j.status);
  pruef(j.stand.verbraucht === vorher + 1, "Zaehler +1", `${vorher}→${j.stand.verbraucht}`);
  r = await api(sA.cookie, "/api/kontingent", { method: "POST", body: JSON.stringify({ art: "lead", ref: "API1" }) });
  j = await r.json();
  pruef(j.status === "schon_frei", "POST API1 erneut → schon_frei (kein Doppelverbrauch)");

  // ── Teil D: RLS ──────────────────────────────────────────────────────────────────────────
  console.log("\n  Teil D — RLS:");
  const sB = await sessionClient(B.email, B.pw);
  const { data: sichtB } = await sB.client.from("vorgang_freigaben").select("id,org_id");
  pruef((sichtB?.length ?? 0) === 0 && orgB !== orgA, "B sieht keine Freigaben (schon gar nicht As)", `B sieht ${sichtB?.length ?? 0}`);
  const { data: sichtA } = await sA.client.from("vorgang_freigaben").select("id,org_id");
  pruef((sichtA?.length ?? 0) > 0 && sichtA.every((x) => x.org_id === orgA), "A sieht nur eigene Org-Freigaben", `A sieht ${sichtA?.length}`);
} catch (e) {
  console.error("\n  ✖ Abbruch:", e.message); fehler++;
} finally {
  for (const k of [A, B]) {
    if (!k) continue;
    const u = await up(k.id).catch(() => null);
    try { await svc.auth.admin.deleteUser(k.id); } catch { /* egal */ }
    if (u?.org_id) { try { await svc.from("organizations").delete().eq("id", u.org_id); } catch { /* egal */ } }
  }
  console.log("\n  Aufgeraeumt (Konten + Orgs geloescht).");
}
console.log(`\n  ${fehler ? "✖ " + fehler + " Fehler" : "✓ alles grün"}`);
process.exit(fehler ? 1 : 0);
