// Stellt der Einheiten-Schritt eine Frage — oder kostet er nur einen Klick?
//
// WARUM ES DIESE PRUEFUNG GIBT. Schritt 3 des Onboardings fragt „Gehoeren diese Einheiten
// zu euch?" und zeigt die gefundenen Firmeneinheiten zur Bestaetigung. Bei EINER Einheit
// ist das keine Frage, sondern eine Liste mit einem Eintrag, den man anhaken soll, um
// weiterzukommen — mitten im Trichter.
//
// Gemessen am 2026-09-17 ueber 37.946 Firmen:
//     1 Einheit   30.174   79,5 %
//     2 Einheiten  4.584   12,1 %
//     3 Einheiten  1.656    4,4 %
//     4 Einheiten    646    1,7 %
//     5 und mehr     886    2,3 %
//
// ⚠ ZWEI DINGE, DIE DIESE SONDE FESTHAELT.
//
// 1. UEBERSPRINGEN NUR BEI BELEGTER EINHEIT. Ist die eine Einheit blosse Selbstauskunft,
//    traegt der Schritt eine Warnung („diese Zuschlaege zaehlen als eure Historie").
//    Sie stillschweigend zu uebergehen hiesse, eine Zustimmung anzunehmen, die niemand
//    gegeben hat — der Zustand, den die Plausibilitaetsbremse vom 2026-08-21 abgeschafft
//    hat. Von den 30.174 Ein-Einheit-Firmen sind 30.172 belegt und 2 nicht; die Ausnahme
//    kostet fast nichts.
//
// 2. EINE REGEL FUER BEIDE WEGE. In diesen Bildschirm fuehren der normale Pfad und der
//    Token-Pfad. Auf dem Token-Pfad stand `anzahl > 1` ohne Belegpruefung — zwei Regeln
//    fuer dieselbe Frage, bereits auseinandergelaufen, als diese Sonde entstand.
import { readFileSync, existsSync } from "node:fs";

const web = new URL("../", import.meta.url);
let fehler = 0;
const klage = (m) => { console.error("  ✗ " + m); fehler++; };

const seite = readFileSync(new URL("app/onboarding/page.tsx", web), "utf8");

/* ── 1. Die ECHTE Regel gegen die Faelle fahren ───────────────────────────────────── */
const a = seite.indexOf("function hatEtwasZuEntscheiden");
if (a < 0) {
  klage("`hatEtwasZuEntscheiden` fehlt — die Regel steht wieder verstreut im Ablauf.");
} else {
  const js = seite.slice(a, seite.indexOf("\n}", a) + 3)
    .replace("(ms: Member[]): boolean", "(ms)");
  const regel = new Function(`${js}\nreturn hatEtwasZuEntscheiden;`)();
  const FAELLE = [
    ["keine Einheit",            [],                                              false],
    ["eine, belegt",             [{ conf: "belegt" }],                            false],
    ["eine, Selbstauskunft",     [{ conf: "unsicher" }],                          true],
    ["zwei, beide belegt",       [{ conf: "belegt" }, { conf: "belegt" }],        true],
    ["zwei, eine unsicher",      [{ conf: "belegt" }, { conf: "unsicher" }],      true],
  ];
  for (const [name, ms, erwartet] of FAELLE) {
    const ist = regel(ms);
    if (ist !== erwartet) {
      klage(`\`${name}\`: Schritt wird ${ist ? "gezeigt" : "uebersprungen"}, erwartet `
          + `${erwartet ? "gezeigt" : "uebersprungen"}.`
          + (name.includes("Selbstauskunft")
             ? " Die Warnung zur Selbstauskunft darf nie uebersprungen werden."
             : ""));
    }
  }
}

/* ── 2. BEIDE Wege benutzen sie ───────────────────────────────────────────────────── */
const code = seite.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
// ⚠ `[^)]` REICHT NICHT: die Bedingung ist selbst ein Funktionsaufruf
// (`hatEtwasZuEntscheiden(ms)`) und enthaelt eine Klammer. Die erste Fassung dieser
// Pruefung fand deshalb NULL Wege und meldete, beide seien verschwunden.
const spruenge = [...code.matchAll(/geheZu\(([\s\S]{0,90}?)\?\s*"(\w+)"\s*:\s*"(\w+)"\)/g)];
const zuProfil = spruenge.filter((m) => m[2] === "profil" || m[3] === "profil");
if (zuProfil.length < 2) {
  klage(`Nur ${zuProfil.length} Weg(e) entscheiden ueber den Einheiten-Schritt — es gibt `
      + "zwei (normaler Pfad und Token-Pfad). Einer wurde entfernt oder entscheidet nicht mehr.");
}
for (const m of zuProfil) {
  if (!/hatEtwasZuEntscheiden\s*\(/.test(m[1])) {
    klage(`Ein Weg in den Einheiten-Schritt prueft mit \`${m[1].trim()}\` statt mit `
        + "`hatEtwasZuEntscheiden`. Genau so liefen die beiden Wege schon einmal auseinander.");
  }
}

/* ── 3. Gegen die echten Daten: lohnt es sich ueberhaupt? ─────────────────────────── */
const lief = new URL("data/suppliers.json", web);
if (existsSync(lief)) {
  const roh = JSON.parse(readFileSync(lief, "utf8"));
  const arr = Array.isArray(roh) ? roh : Object.values(roh);
  let eins = 0, einsBelegt = 0, ges = 0;
  for (const s of arr) {
    if (!s || !Array.isArray(s.members)) continue;
    ges++;
    if (s.members.length !== 1) continue;
    eins++;
    if (s.members[0]?.conf === "belegt") einsBelegt++;
  }
  console.log(`  ${ges.toLocaleString("de")} Firmen, ${eins.toLocaleString("de")} mit EINER Einheit `
            + `(${(100 * eins / ges).toFixed(1)} %), davon ${einsBelegt.toLocaleString("de")} belegt`);
  console.log(`  → ${(100 * einsBelegt / ges).toFixed(1)} % sehen den Schritt nicht mehr`);
  // ⚠ Faellt der Anteil stark, ist die Abkuerzung ihren Aufwand nicht mehr wert — dann
  //    gehoert sie geprueft, nicht stillschweigend weitergeschleppt.
  if (einsBelegt / ges < 0.4) {
    klage(`Nur ${(100 * einsBelegt / ges).toFixed(1)} % profitieren noch. Die Abkuerzung `
        + "war fuer 79,5 % gebaut — die Datenlage hat sich verschoben, bitte neu bewerten.");
  }
}

console.log(fehler ? `\n✗ ${fehler} Befund(e)` : "\n✓ Der Schritt erscheint genau dann, wenn er etwas fragt");
process.exit(fehler ? 1 : 0);
