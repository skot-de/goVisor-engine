/* Faehrt den ECHTEN `leadStatus.ts`, nicht seinen Quelltext.
 *
 * ⚠ WARUM DER AUFWAND. Eine Wortpruefung haette hier den teuersten Fehler nicht gesehen:
 * `upsert(..., { onConflict, ignoreDuplicates: true })` sieht genau so richtig aus wie die
 * Fassung ohne das Flag — die beiden Nachbarmodule (`watchlist.ts`, `ausgeblendet.ts`)
 * fahren es sogar, und zwar zu Recht, weil dort die EXISTENZ der Zeile die Aussage ist.
 * Hier ist es der WERT. Mit dem Flag kaeme das erste Setzen an und jede Aenderung danach
 * nicht mehr — ein Fehler, der beim Ausprobieren funktioniert und erst beim zweiten Klick
 * auftritt, den niemand testet.
 *
 * Das Modul ist TypeScript und importiert den Supabase-Client. Also: mit `tsc` allein
 * uebersetzen (`--noResolve`, der Import bleibt stehen), einen Attrappen-Client danebenlegen
 * und die Aufrufe mitschreiben. */
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync, readFileSync, existsSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const T = mkdtempSync(join(tmpdir(), "gv-leadstatus-"));
let fehler = 0;
const sage = (ok, text) => { if (!ok) fehler++; console.log(`  ${ok ? "✓" : "✗"} ${text}`); };

try {
  /* tsc meldet den nicht aufloesbaren `./client`-Import als Fehler und schreibt die Datei
     TROTZDEM. Den Ausgang deshalb nicht bewerten — die echte Typpruefung des Projekts
     laeuft ohnehin ueber `npx tsc --noEmit` im ganzen Baum. */
  try {
    execFileSync("npx", ["tsc", "lib/supabase/leadStatus.ts", "--outDir", T,
      "--module", "es2020", "--target", "es2020", "--noResolve", "--skipLibCheck"],
      { cwd: WEB, stdio: "pipe" });
  } catch { /* s. o. */ }
  if (!existsSync(join(T, "leadStatus.js"))) {
    console.log("  ✗ leadStatus.ts liess sich nicht uebersetzen");
    process.exit(1);
  }

  writeFileSync(join(T, "client.js"), `
    export const rufe = [];
    const tisch = (name) => ({
      upsert: (zeile, opt) => { rufe.push({art:"upsert", name, zeile, opt}); return Promise.resolve({}); },
      delete: () => { const d = {art:"delete", name, eq:{}}; rufe.push(d);
        const kette = { eq: (k,v) => { d.eq[k]=v; return kette; }, then: (f)=>f({}) };
        return kette; },
      select: () => ({ eq: () => Promise.resolve({ data: [
        {lead_id:"L1", status:"pruefung"}, {lead_id:"L2", status:"verworfen"}] }) }),
    });
    export const createClient = () => ({
      auth: { getUser: async () => ({ data: { user: { id: "U1" } } }) },
      from: (name) => tisch(name),
    });
  `);

  /* ⚠ node/ESM loest `./client` nicht auf — die Endung ist Pflicht. tsc laesst den
     Bezeichner unveraendert stehen, weil er im Next-Bau vom Bundler aufgeloest wird. */
  const js = join(T, "leadStatus.js");
  writeFileSync(js, readFileSync(js, "utf8").replace('./client', './client.js'));

  const mod = await import(js);
  const { rufe: gesehen } = await import(join(T, "client.js"));

  // 1 ── Setzen schreibt, und zwar ueberschreibend.
  await mod.syncLeadStatus("L1", "pruefung", { titel: "Sanierung", buyer: "Stadt Ulm" });
  const u = gesehen.find((r) => r.art === "upsert");
  sage(!!u, "Setzen schreibt in die Datenbank");
  sage(u && u.name === "user_lead_status", `Tabelle ist user_lead_status (war: ${u && u.name})`);
  sage(u && u.zeile.status === "pruefung", "der Status steht in der Zeile");
  sage(u && u.zeile.titel === "Sanierung" && u.zeile.buyer_name === "Stadt Ulm",
       "Titel und Kaeufer gehen mit (sonst ist die Zeile nach der Frist nicht mehr deutbar)");
  sage(u && u.opt && u.opt.onConflict === "user_id,lead_id",
       "onConflict steht auf dem Paar aus Nutzer und Vorgang");
  sage(u && u.opt && !u.opt.ignoreDuplicates,
       "KEIN ignoreDuplicates — sonst verpufft jede Aenderung nach der ersten");

  // 2 ── Zuruecknehmen loescht.
  gesehen.length = 0;
  await mod.syncLeadStatus("L1", null);
  const d = gesehen.find((r) => r.art === "delete");
  sage(!!d, "Zuruecksetzen loescht die Zeile");
  sage(d && d.eq.user_id === "U1" && d.eq.lead_id === "L1",
       "geloescht wird genau die eigene Zeile dieses Vorgangs");

  // 3 ── Ein unbekannter Wert darf nicht bis zur Datenbank laufen.
  gesehen.length = 0;
  await mod.syncLeadStatus("L1", "quatsch");
  sage(gesehen.length === 0,
       "ein unbekannter Status wird abgefangen (der Check-Constraint wuerde ihn ablehnen, "
       + "und der Nutzer saehe nichts davon)");

  // 4 ── Laden gibt die Zuordnung zurueck.
  const m = await mod.loadLeadStatus();
  sage(m instanceof Map && m.get("L1") === "pruefung" && m.get("L2") === "verworfen",
       `Laden liefert lead_id → status (${m && m.size} Eintraege)`);
} finally {
  rmSync(T, { recursive: true, force: true });
}

if (fehler) { console.log(`\n⛔ ${fehler} Befund(e)`); process.exit(1); }
console.log("\n✓ Der Lead-Status geht wirklich in die Datenbank und wieder zurueck");
