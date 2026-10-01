// Scharf-Test der Paywall — LOKAL (PAYWALL_ENFORCED=true muss gesetzt + Server neu gestartet
// sein). Misst BEIDE Seiten gegen drei echte Stufen, ohne die 13 echten Konten anzufassen:
//   Gate (mein Mengen-Kontingent, §4.3):  free → Limit 3,  analyse/strategie → unbegrenzt
//   Redaktion §3.2 darfAnalyse (Markt):   free redigiert (nAwards 0, dominatoren []),
//                                         analyse/strategie voll (echte Zahlen)
//   Redaktion §3.6 darfStrategie:         free + analyse redigiert (faehigkeiten gated),
//                                         strategie voll
// Legt drei Wegwerf-Konten an (free/analyse/strategie), raeumt sie weg. Nur Testdaten.
//
// Aufruf:  node web/scripts/test_paywall_scharf.mjs [BASIS-URL]
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
const up = async (id) => (await svc.from("user_profiles").select("org_id").eq("id", id).single()).data;
async function cookie(email, p) {
  const jar = new Map();
  const c = createServerClient(URL_, ANON, { cookies: {
    getAll: () => [...jar].map(([name, value]) => ({ name, value })),
    setAll: (l) => l.forEach(({ name, value }) => jar.set(name, value)) } });
  const { error } = await c.auth.signInWithPassword({ email, password: p });
  if (error) throw new Error(`login ${email}: ${error.message}`);
  return [...jar].map(([n, v]) => `${n}=${v}`).join("; ");
}
const get = (ck, pfad) => fetch(`${BASIS}${pfad}`, { headers: { cookie: ck } }).then((r) => r.json());

const users = [], orgs = new Set();
try {
  // Vorbedingung: Paywall muss AN sein, sonst liefert getTier immer 'strategie'.
  const probe = await mkUser("rlstest-pw-probe@govisor.invalid"); users.push(probe.id);
  const op = await up(probe.id); orgs.add(op.org_id);
  await svc.from("organizations").update({ tier: "free" }).eq("id", op.org_id);
  const ckProbe = await cookie(probe.email, probe.pw);
  const kp = await get(ckProbe, "/api/kontingent");
  if (kp.limit === null) {
    console.error("\n  ⛔ PAYWALL_ENFORCED ist AUS (free-Konto bekommt limit=null). Erst setzen + Server neu starten.");
    process.exit(2);
  }
  pruef(kp.limit === 3, "Vorbedingung: Paywall AN (free → Limit 3)", `limit=${kp.limit}`);

  // Drei Stufen
  const stufen = {};
  for (const [name, tier] of [["free", "free"], ["ana", "analyse"], ["str", "strategie"]]) {
    const u = await mkUser(`rlstest-pw-${name}@govisor.invalid`); users.push(u.id);
    const o = await up(u.id); orgs.add(o.org_id);
    await svc.from("organizations").update({ tier }).eq("id", o.org_id);
    stufen[name] = { u, ck: await cookie(u.email, u.pw) };
  }

  // ── Gate (Mengen-Kontingent) ─────────────────────────────────────────────────────────────
  console.log("\n  Gate — Vorgangs-Kontingent:");
  pruef((await get(stufen.free.ck, "/api/kontingent")).limit === 3, "free → Limit 3");
  pruef((await get(stufen.ana.ck, "/api/kontingent")).limit === null, "analyse → unbegrenzt");
  pruef((await get(stufen.str.ck, "/api/kontingent")).limit === null, "strategie → unbegrenzt");

  // ── Redaktion §3.2 (darfAnalyse) — Lead-Detail Markt ─────────────────────────────────────
  console.log("\n  Redaktion §3.2 (Markt) — Lead 19277520/bau (nAwards 8883):");
  const detail = async (ck) => (await get(ck, "/api/lead-detail?branche=bau&id=19277520"))?.detail?.marktSegment
    ?? (await get(ck, "/api/lead-detail?branche=bau&id=19277520"))?.marktSegment;
  const mFree = await detail(stufen.free.ck), mAna = await detail(stufen.ana.ck), mStr = await detail(stufen.str.ck);
  pruef(mFree && mFree.nAwards === 0 && (mFree.dominatoren || []).length === 0, "free: Markt redigiert (nAwards 0, dominatoren [])", `nAwards=${mFree?.nAwards}`);
  pruef(mAna && mAna.nAwards > 0, "analyse: Markt voll", `nAwards=${mAna?.nAwards}`);
  pruef(mStr && mStr.nAwards > 0, "strategie: Markt voll", `nAwards=${mStr?.nAwards}`);

  // ── Redaktion §3.6 (darfStrategie) — Strategie-Bereich ───────────────────────────────────
  console.log("\n  Redaktion §3.6 (Strategie-Bereich):");
  const ersterBranch = (m) => (m && typeof m === "object") ? m[Object.keys(m)[0]] : null;
  const gated = (m) => { const b = ersterBranch(m); return !!b && b.faehigkeiten && b.faehigkeiten.gated === true; };
  const sFree = ersterBranch(await get(stufen.free.ck, "/api/strategie?ctx=provider")) ? await get(stufen.free.ck, "/api/strategie?ctx=provider") : null;
  const sAna = await get(stufen.ana.ck, "/api/strategie?ctx=provider");
  const sStr = await get(stufen.str.ck, "/api/strategie?ctx=provider");
  if (!ersterBranch(sStr)) {
    pruef(true, "Strategie-Daten leer — Schwelle nicht beobachtbar (uebersprungen)", "kein Branch");
  } else {
    pruef(gated(sFree), "free: Strategie gated");
    pruef(gated(sAna), "analyse: Strategie weiterhin gated (§3.6 = ++)");
    pruef(!gated(sStr), "strategie: Strategie voll");
  }
} catch (e) {
  console.error("\n  ✖ Abbruch:", e.message); fehler++;
} finally {
  for (const id of users) { try { await svc.auth.admin.deleteUser(id); } catch { /* egal */ } }
  for (const o of orgs) { try { await svc.from("organizations").delete().eq("id", o); } catch { /* egal */ } }
  console.log("\n  Aufgeraeumt (Konten + Orgs geloescht).");
}
console.log(`\n  ${fehler ? "✖ " + fehler + " Fehler" : "✓ alles grün"}`);
process.exit(fehler ? 1 : 0);
