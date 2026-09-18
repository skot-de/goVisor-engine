// Eine angemeldete Sitzung fuer Pruefungen — ohne Browser, ohne fremdes Passwort.
//
// WARUM ES DAS GIBT. Mehrere Routen (`/api/leads`, `/api/doc-analysis`, `/api/lead-detail`)
// liegen hinter dem Anmeldetor in `middleware.ts`. Ohne Sitzung antworten sie mit 401 — und
// damit war am 2026-09-17 eine Aenderung an `/api/leads` nicht pruefbar, obwohl sie
// gemessen 48 % Uebertragung gespart haette. Eine Komprimierungsaenderung an der
// wichtigsten Route ungeprueft auszuliefern waere die falsche Wette gewesen: setzt Next
// seinen gzip zusaetzlich darueber, ist die Antwort doppelt kodiert und die Liste fuer
// JEDEN kaputt.
//
// ⚠ DAS COOKIE-FORMAT WIRD NICHT GERATEN. `@supabase/ssr` kodiert die Sitzung
// base64-praefixiert und zerlegt sie bei Bedarf auf mehrere Cookies (`…auth-token.0`,
// `.1`). Jede handgeschriebene Nachbildung waere beim naechsten Bibliotheks-Update falsch
// — und zwar still, mit 401 statt einer Fehlermeldung. Deshalb laesst dieses Skript die
// ECHTE Bibliothek anmelden und faengt ab, welche Cookies sie setzt.
//
// Aufruf:
//     node web/scripts/pruefanmeldung.mjs <email> <passwort>
//   → gibt die Cookie-Zeile aus, die `curl -b` erwartet.
//
// Das Konto legt `scripts/pruefkonto.py` an (und wieder weg).
import { readFileSync } from "node:fs";
import { createServerClient } from "../node_modules/@supabase/ssr/dist/main/index.js";

const env = Object.fromEntries(
  readFileSync(new URL("../.env.local", import.meta.url), "utf8")
    .split("\n").map((z) => z.match(/^\s*([A-Za-z_]+)\s*=\s*"?([^"\n]*)"?/))
    .filter(Boolean).map((m) => [m[1], m[2]]));

const [email, passwort] = process.argv.slice(2);
if (!email || !passwort) {
  console.error("Aufruf: node web/scripts/pruefanmeldung.mjs <email> <passwort>");
  process.exit(2);
}

// Der Cookie-Speicher, den `@supabase/ssr` fuellt. Genau das ist die Ausbeute.
const jar = new Map();
const sb = createServerClient(
  env.NEXT_PUBLIC_SUPABASE_URL, env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  {
    cookies: {
      getAll: () => [...jar].map(([name, value]) => ({ name, value })),
      setAll: (liste) => liste.forEach(({ name, value }) => jar.set(name, value)),
    },
  });

const { data, error } = await sb.auth.signInWithPassword({ email, password: passwort });
if (error) {
  console.error(`  ✖ Anmeldung fehlgeschlagen: ${error.message}`);
  process.exit(1);
}
if (!jar.size) {
  // ⚠ Ohne Cookies ist die Anmeldung wertlos — und das faellt sonst erst beim 401 auf.
  console.error("  ✖ Die Bibliothek hat keine Cookies gesetzt. Format geaendert?");
  process.exit(1);
}
const zeile = [...jar].map(([n, v]) => `${n}=${v}`).join("; ");
if (process.env.LEISE !== "1") {
  console.error(`  angemeldet als ${data.user.email} (${[...jar.keys()].length} Cookie(s))`);
}
console.log(zeile);
