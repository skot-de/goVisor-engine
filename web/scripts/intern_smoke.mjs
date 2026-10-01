// Laufzeit-Smoke-Test der internen Seiten (/intern) MIT Admin-Session — ohne Browser.
//
// WARUM. Alle /intern-Seiten + /api/intern-Routen liegen hinter dem Admin-Tor der Middleware
// (istAdmin + 404 statt 403). Ohne eingeloggte Admin-Session sind sie von Hand nicht pruefbar;
// genau deshalb blieb die ganze Bereichs-Arbeit bisher nur an der Datenschicht belegt. Dieses
// Skript meldet ein Wegwerf-ADMIN-Konto an (scripts/pruefkonto_admin.py) und ruft jede Route
// mit der echten Session ab — Lesepfade, keine schreibenden Aktionen.
//
// ⚠ COOKIE NICHT GERATEN: dieselbe Mechanik wie pruefanmeldung.mjs — die echte
// @supabase/ssr-Bibliothek setzt die Cookies, wir fangen sie ab.
//
// Aufruf:  node web/scripts/intern_smoke.mjs [BASIS-URL]
//   Standard-Basis http://127.0.0.1:3000 ; Konto/Passwort aus .secrets/pruefkonto_admin.txt.
import { readFileSync } from "node:fs";
import { createServerClient } from "../node_modules/@supabase/ssr/dist/main/index.js";

const BASIS = (process.argv[2] || "http://127.0.0.1:3000").replace(/\/$/, "");
const ADRESSE = process.env.INTERN_TEST_EMAIL || "pruef-admin@govisor.invalid";

const env = Object.fromEntries(
  readFileSync(new URL("../.env.local", import.meta.url), "utf8")
    .split("\n").map((z) => z.match(/^\s*([A-Za-z_]+)\s*=\s*"?([^"\n]*)"?/))
    .filter(Boolean).map((m) => [m[1], m[2]]));

let passwort;
try { passwort = readFileSync(new URL("../../.secrets/pruefkonto_admin.txt", import.meta.url), "utf8").trim(); }
catch { console.error("  ✖ .secrets/pruefkonto_admin.txt fehlt — erst: python3 scripts/pruefkonto_admin.py"); process.exit(2); }

const jar = new Map();
const sb = createServerClient(env.NEXT_PUBLIC_SUPABASE_URL, env.NEXT_PUBLIC_SUPABASE_ANON_KEY, {
  cookies: {
    getAll: () => [...jar].map(([name, value]) => ({ name, value })),
    setAll: (liste) => liste.forEach(({ name, value }) => jar.set(name, value)),
  },
});
const { data, error } = await sb.auth.signInWithPassword({ email: ADRESSE, password: passwort });
if (error) { console.error(`  ✖ Anmeldung fehlgeschlagen: ${error.message}`); process.exit(1); }
if (!jar.size) { console.error("  ✖ keine Cookies gesetzt (Format geaendert?)"); process.exit(1); }
const COOKIE = [...jar].map(([n, v]) => `${n}=${v}`).join("; ");
console.log(`  angemeldet als ${data.user.email}\n`);

// GET-Routen (nur lesen). shape: optionaler Pruefer auf dem JSON.
const APIS = [
  ["betrieb", "/api/intern/betrieb"],
  ["konten", "/api/intern/konten", (j) => Array.isArray(j.orgs)],
  ["qualitaet", "/api/intern/qualitaet?country=DE"],
  ["qualitaet+merges", "/api/intern/qualitaet?country=DE&merges=5", (j) => Array.isArray(j.merge_liste)],
  ["kosten", "/api/intern/kosten"],
  ["kuratierung-index", "/api/intern/kuratierung?country=DE", (j) => Array.isArray(j.arten)],
  ["kuratierung-datei", "/api/intern/kuratierung?kind=hosts_gesperrt", (j) => Array.isArray(j.zeilen)],
  ["zielliste", "/api/intern/zielliste?limit=5", (j) => Array.isArray(j.zeilen)],
  ["outreach", "/api/intern/outreach", (j) => "cooldown" in j || "trefferquote" in j],
];
const SEITEN = ["/intern", "/intern/betrieb", "/intern/konten", "/intern/qualitaet",
  "/intern/kosten", "/intern/kuratierung", "/intern/vertrieb"];

let fehler = 0;
const zeile = (ok, name, info) => { console.log(`  ${ok ? "✓" : "✖"} ${name.padEnd(22)} ${info}`); if (!ok) fehler++; };

// 1) Gate NEGATIV: ohne Cookie muss /api/intern/betrieb 404 sein (Middleware).
{
  const r = await fetch(`${BASIS}/api/intern/betrieb`).catch(() => null);
  zeile(r?.status === 404, "gate(ohne session)", `erwartet 404 → ${r?.status ?? "kein Server?"}`);
  if (!r) { console.error("\n  ✖ Server nicht erreichbar auf " + BASIS); process.exit(1); }
}

// 2) APIs MIT Session
console.log("\n  APIs (mit Admin-Session):");
for (const [name, pfad, shape] of APIS) {
  try {
    const r = await fetch(`${BASIS}${pfad}`, { headers: { cookie: COOKIE } });
    const txt = await r.text();
    let j = null; try { j = JSON.parse(txt); } catch { /* HTML? */ }
    const okStatus = r.status === 200;
    const okJson = j !== null && !j.error && !j.fehler;
    const okShape = !shape || (j && shape(j));
    zeile(okStatus && okJson && okShape, name,
      `${r.status}${j?.error ? " error:" + j.error : ""}${j?.fehler ? " fehler:" + String(j.fehler).slice(0, 60) : ""}${okStatus && okJson && !okShape ? " (shape?)" : ""}`);
  } catch (e) { zeile(false, name, String(e.message).slice(0, 60)); }
}

// 3) Seiten (HTML, dürfen NICHT 404 sein → Gate offen)
console.log("\n  Seiten (HTML, 200 = Gate offen):");
for (const pfad of SEITEN) {
  try {
    const r = await fetch(`${BASIS}${pfad}`, { headers: { cookie: COOKIE } });
    zeile(r.status === 200, pfad, `${r.status}`);
  } catch (e) { zeile(false, pfad, String(e.message).slice(0, 60)); }
}

console.log(`\n  ${fehler ? "✖ " + fehler + " Fehler" : "✓ alles grün"}`);
process.exit(fehler ? 1 : 0);
