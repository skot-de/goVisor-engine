// Sieht der Nutzer, dass ein Verfahren AUFGEHOBEN wurde — und warum?
//
// WARUM ES DIESE PRUEFUNG GIBT. Bis zum 2026-10-05 schrieb die Vorgangsakte „Zuschlag"
// an jede Zuschlagsstation, auch wenn das Verfahren aufgehoben worden war: 1.507 von
// 43.114 Stationen (3,5 %). Das ist keine fehlende Angabe, sondern eine FALSCHE — wer
// die Akte liest, schliesst daraus, dass vergeben wurde.
//
// Drei Ausfaelle sind moeglich, und keiner wuerde von selbst auffallen:
//   1. Der Export setzt `aufgehoben` nicht mehr → alles heisst wieder „Zuschlag".
//   2. Die Oberflaeche liest das Merkmal nicht mehr → Daten da, Anzeige falsch.
//   3. Ein Grund hat keine Uebersetzung → englische Nutzer lesen Deutsch.
//
// ⚠ Fall 3 faengt der allgemeine i18n-Waechter NICHT. Er durchsucht den Quelltext nach
// `t("...")`-Literalen; diese Texte kommen aber als DATEN aus `export_vorgaenge.py` und
// landen ueber `t(e.grund)` in der Ansicht. Der Waechter blieb gruen, waehrend en/fr
// deutsche Saetze angezeigt haetten. Deshalb prueft diese Sonde die DATEN gegen die
// Sprachdateien, nicht den Code.
import { readFileSync, readdirSync, existsSync } from "node:fs";

const hier = (p) => new URL(p, import.meta.url);
let fehler = 0;
const klage = (m) => { console.error("  ✗ " + m); fehler++; };

/* ── 1. Die Oberflaeche liest das MERKMAL, nicht den Text ─────────────────────────── */
const tsx = readFileSync(hier("../components/explorer/Vorgangsakte.tsx"), "utf8")
  // ⚠ Kommentare raus, sonst schlaegt die Pruefung an der eigenen Erklaerung an.
  // `(?m)` waere Python; in JS traegt das Literal die m-Flagge selbst.
  .replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
if (!/e\.aufgehoben/.test(tsx)) {
  klage("Vorgangsakte.tsx liest `e.aufgehoben` nicht mehr. Dann faerbt und beschriftet "
      + "die Ansicht ein aufgehobenes Verfahren wie einen Zuschlag.");
}
if (!/e\.grund/.test(tsx)) {
  klage("Vorgangsakte.tsx zeigt `e.grund` nicht mehr an.");
}
// ⚠ Nicht am Label haengen: es laeuft durch die Uebersetzung.
if (/===\s*["']Aufgehoben["']|label\s*===/.test(tsx)) {
  klage("Die Ansicht vergleicht das LABEL statt das Merkmal zu lesen. In der englischen "
      + "Fassung heisst es „Cancelled\" und der Vergleich schlaegt fehl.");
}

/* ── 2. Die Daten tragen es ───────────────────────────────────────────────────────── */
const daten = hier("../data/vorgang/");
if (!existsSync(daten)) {
  console.log("  … web/data/vorgang fehlt — uebersprungen.");
  process.exit(fehler ? 1 : 0);
}
let stationen = 0, aufgehoben = 0, mitGrund = 0;
const gruende = new Set();
for (const f of readdirSync(daten).filter((x) => x.endsWith(".json"))) {
  const b = JSON.parse(readFileSync(new URL(f, daten), "utf8"));
  for (const akte of Object.values(b)) {
    for (const e of akte.verlauf ?? []) {
      if (e.art !== "can") continue;
      stationen++;
      if (!e.aufgehoben) continue;
      aufgehoben++;
      // Ein aufgehobenes Verfahren darf nicht „Zuschlag" heissen.
      if (e.label === "Zuschlag") {
        klage(`Station ${e.datum} ist aufgehoben, traegt aber das Label „Zuschlag".`);
      }
      if (e.grund) { mitGrund++; for (const g of e.grund.split(" · ")) gruende.add(g); }
    }
  }
}
if (!aufgehoben) {
  klage(`${stationen.toLocaleString("de")} Zuschlagsstationen, aber KEINE ist als `
      + `aufgehoben markiert. Gemessen am 2026-10-05: 1.507. Null heisst, dass `
      + `export_vorgaenge.py die quality-Zuordnung verloren hat.`);
}

/* ── 3. Jeder Grund ist uebersetzt ────────────────────────────────────────────────── */
for (const sprache of ["en", "fr"]) {
  const p = hier(`../lib/i18n/messages/flat.${sprache}.json`);
  if (!existsSync(p)) { klage(`flat.${sprache}.json fehlt`); continue; }
  const m = JSON.parse(readFileSync(p, "utf8"));
  const fehlend = [...gruende, "Aufgehoben"].filter((g) => !(g in m));
  if (fehlend.length) {
    klage(`flat.${sprache}.json fehlen ${fehlend.length} Texte, die als DATEN in die `
        + `Ansicht kommen: ${fehlend.slice(0, 4).join(" | ")}. Der allgemeine `
        + `i18n-Waechter sieht sie nicht — er liest nur Literale im Quelltext.`);
  }
}

console.log(`  ${aufgehoben.toLocaleString("de")} von `
          + `${stationen.toLocaleString("de")} Zuschlagsstationen sind aufgehoben `
          + `(${(100 * aufgehoben / Math.max(1, stationen)).toFixed(1)} %), `
          + `${mitGrund.toLocaleString("de")} mit Grund, `
          + `${gruende.size} verschiedene Gruende — alle uebersetzt`);
if (!fehler) console.log("  ✓ Aufhebungen sind sichtbar und nicht als Zuschlag getarnt");
process.exit(fehler ? 1 : 0);
