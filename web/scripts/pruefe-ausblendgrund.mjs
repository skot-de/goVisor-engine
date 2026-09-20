/* Faehrt den ECHTEN `ausgeblendet.ts` und prueft, ob der Grund ankommt.
 *
 * ⛔ DER ANLASS: er kam bis zum 2026-09-20 NIE an. Der Ablauf ist zweistufig — der Klick
 * auf das Kreuz legt die Zeile ohne Grund an, die Antwort in der Rueckfrage reicht ihn
 * nach. Mit `ignoreDuplicates: true` wurde die zweite Schreibung zu `ON CONFLICT DO
 * NOTHING` und verpuffte. Die ganze Rueckfrage war wirkungslos, ohne Fehlermeldung.
 *
 * ⚠ EINE WORTPRUEFUNG HAETTE DAS NICHT GESEHEN. `upsert(..., {onConflict, ignoreDuplicates})`
 * sieht genau so richtig aus wie die Fassung ohne das Flag; in den Nachbarmodulen ist es
 * sogar richtig. Nur die REIHENFOLGE zweier Aufrufe macht den Unterschied, und die sieht
 * man erst, wenn man sie ausfuehrt.
 */
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync, readFileSync, existsSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const T = mkdtempSync(join(tmpdir(), "gv-grund-"));
let fehler = 0;
const sage = (ok, t) => { if (!ok) fehler++; console.log(`  ${ok ? "✓" : "✗"} ${t}`); };

try {
  try {
    execFileSync("npx", ["tsc", "lib/supabase/ausgeblendet.ts", "--outDir", T,
      "--module", "es2020", "--target", "es2020", "--noResolve", "--skipLibCheck"],
      { cwd: WEB, stdio: "pipe" });
  } catch { /* der nicht aufloesbare ./client-Import ist erwartet */ }
  const js = join(T, "ausgeblendet.js");
  if (!existsSync(js)) { console.log("  ✗ liess sich nicht uebersetzen"); process.exit(1); }
  writeFileSync(js, readFileSync(js, "utf8").replace("./client", "./client.js"));

  /* Attrappe mit einer ZEILENSEMANTIK, nicht nur einem Aufrufprotokoll: nur so faellt auf,
     dass ein `upsert` mit ignoreDuplicates die vorhandene Zeile unveraendert laesst. */
  writeFileSync(join(T, "client.js"), `
    export const tabelle = new Map();   // "user|lead" → Zeile
    export const rufe = [];
    const schluessel = (z) => z.user_id + "|" + z.lead_id;
    const tisch = () => ({
      upsert: (z, opt) => { rufe.push({art:"upsert", opt});
        const k = schluessel(z);
        if (tabelle.has(k) && opt && opt.ignoreDuplicates) return Promise.resolve({});
        tabelle.set(k, { ...(tabelle.get(k) || {}), ...z });
        return Promise.resolve({}); },
      update: (felder) => { rufe.push({art:"update", felder});
        const w = {};
        const kette = { eq: (k,v) => { w[k]=v; return kette; },
          then: (f) => { const k = w.user_id + "|" + w.lead_id;
            if (tabelle.has(k)) tabelle.set(k, { ...tabelle.get(k), ...felder });
            return f({}); } };
        return kette; },
      delete: () => { const w = {};
        const kette = { eq: (k,v) => { w[k]=v; return kette; },
          then: (f) => { tabelle.delete(w.user_id + "|" + w.lead_id); return f({}); } };
        return kette; },
      select: () => ({ eq: () => Promise.resolve({ data: [...tabelle.values()] }) }),
    });
    export const createClient = () => ({
      auth: { getUser: async () => ({ data: { user: { id: "U1" } } }) },
      from: () => tisch(),
    });
  `);

  const mod = await import(js);
  const { tabelle, rufe } = await import(join(T, "client.js"));
  const zeile = () => tabelle.get("U1|L1");

  // 1 ── Der Klick auf das Kreuz legt die Zeile an, noch ohne Grund.
  await mod.syncAusgeblendet("L1", true, { titel: "Sanierung", buyer: "Stadt Ulm" });
  sage(!!zeile(), "Ausblenden legt die Zeile an");
  sage(zeile() && zeile().titel === "Sanierung" && zeile().buyer_name === "Stadt Ulm",
       "Titel und Kaeufer stehen drin (sonst ist die Zeile spaeter nicht deutbar)");
  sage(zeile() && zeile().grund == null, "noch kein Grund — er kommt erst mit der Antwort");

  // 2 ── ⛔ DER FALL, DER IMMER GESCHEITERT IST.
  await mod.syncAusgeblendet("L1", true, { titel: "Sanierung", buyer: "Stadt Ulm",
                                           grund: "Entfernung" });
  sage(zeile() && zeile().grund === "Entfernung",
       `der nachgereichte Grund kommt an (ist: ${JSON.stringify(zeile() && zeile().grund)})`);

  // 3 ── Erneutes Ausblenden darf einen vorhandenen Grund NICHT loeschen.
  await mod.syncAusgeblendet("L1", true, { titel: "Sanierung", buyer: "Stadt Ulm" });
  sage(zeile() && zeile().grund === "Entfernung",
       "erneutes Ausblenden ueberschreibt den Grund nicht mit null");

  // 4 ── Wiedereinblenden raeumt die Zeile.
  await mod.syncAusgeblendet("L1", false);
  sage(!zeile(), "Wiedereinblenden loescht die Zeile");

  // 5 ── Der Grund geht als UPDATE, nicht als UPSERT.
  const artZumGrund = rufe.filter((r) => r.art === "update").length;
  sage(artZumGrund >= 1,
       "der Grund wird per update geschrieben (ein upsert mit ignoreDuplicates verpufft)");
} finally {
  rmSync(T, { recursive: true, force: true });
}

if (fehler) { console.log(`\n⛔ ${fehler} Befund(e)`); process.exit(1); }
console.log("\n✓ Der Grund kommt an, und ein zweiter Klick loescht ihn nicht");
