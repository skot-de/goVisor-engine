// Stellt der Einheiten-Schritt eine Frage, wo es nichts zu fragen gibt?
//
// WARUM ES DIESE PRUEFUNG GIBT. Schritt 3 des Onboardings fragt „Gehoeren diese Einheiten
// zu euch?". Bei EINER Einheit ist das keine Frage, sondern eine Liste mit einem Eintrag,
// ueber den in Schritt 2 gerade entschieden wurde, und darueber ein Ja/Nein mit nur einer
// Antwort.
//
// ⚠ DER SCHRITT WIRD NICHT UEBERSPRUNGEN — und das ist der Kern. Eine erste Fassung vom
// 2026-09-17 sprang bei einer belegten Einheit direkt zu „fertig". Das war die falsche
// Loesung: der Schritt traegt die Zusage „Mit der Bestaetigung merken wir uns diese
// Einheiten als eure Identitaet. {n} Siege fliessen in euer Profil." Das ist die Stelle,
// an der aus „wir kennen euch" ein Profil wird; sie wegzulassen waere schlechter als eine
// unpassende Ueberschrift.
//
// Gemessen am 2026-09-18, zwei Grundmengen — beide richtig, verschiedene Fragen:
//
//     alle DE-Identitaeten (entity_identity.parquet)  304.994 · 96,9 % mit EINER Einheit
//     Firmen, die das Onboarding findet (suppliers)    37.948 · 79,5 % mit EINER Einheit
//
// Die zweite ist die einschlaegige: Schritt 3 erreicht nur, wer in Schritt 2 einen Treffer
// aus `suppliers.json` bestaetigt hat.
import { readFileSync, existsSync } from "node:fs";

const web = new URL("../", import.meta.url);
let fehler = 0;
const klage = (m) => { console.error("  ✗ " + m); fehler++; };

const seite = readFileSync(new URL("app/onboarding/page.tsx", web), "utf8");

/* ── 1. Die ECHTE Regel gegen die Faelle fahren ───────────────────────────────────── */
const a = seite.indexOf("function istEineFrage");
if (a < 0) {
  klage("`istEineFrage` fehlt — die Regel steht wieder verstreut im Ablauf.");
} else {
  const js = seite.slice(a, seite.indexOf("\n}", a) + 3).replace("(ms: Member[]): boolean", "(ms)");
  const regel = new Function(`${js}\nreturn istEineFrage;`)();
  const FAELLE = [
    ["keine Einheit",        [],                                        true],
    ["eine, belegt",         [{ conf: "belegt" }],                      false],
    ["eine, Selbstauskunft", [{ conf: "unsicher" }],                    false],
    ["zwei",                 [{ conf: "belegt" }, { conf: "belegt" }],  true],
  ];
  for (const [name, ms, erwartet] of FAELLE) {
    const ist = regel(ms);
    if (ist !== erwartet) {
      klage(`\`${name}\`: ${ist ? "Frage" : "Aussage"}, erwartet ${erwartet ? "Frage" : "Aussage"}.`
          + (ms.length === 1 ? " Bei einer Einheit gibt es nichts zu fragen." : ""));
    }
  }
}

/* ── 1b. DER SCHRITT WIRD UEBERSPRUNGEN — ABER NUR BEI BELEGTER EINHEIT───────────── */
// ⚠ DIESE REGEL IST AM 2026-09-18 ZWEIMAL GEKIPPT. Vormittags wurde der Sprung entfernt,
// weil ein Arbeitsauftrag verlangte, den Schritt zu ERHALTEN: er traegt die Zusage „{n}
// Siege fliessen in euer Profil". Nachmittags hat Sven an einem Bildschirm mit genau einer
// Einheit entschieden: „hat die seite keinen mehrwert, sondern kostet nur zeit und ein
// klick". Beides stimmt — aufgeloest ist es dadurch, dass die Zusage auch auf dem
// Abschlussbildschirm steht („Siege im Profil"), den der Sprung ansteuert. Verloren geht
// sie nicht, sie kommt eine Seite spaeter.
//
// ⚠ DIE AUSNAHME IST DER TEIL, DER ZAEHLT. Ist die eine Einheit blosse Selbstauskunft,
// traegt der Schritt eine Warnung; sie stillschweigend zu uebergehen hiesse, eine
// Zustimmung anzunehmen, die niemand gegeben hat. Wer `darfUeberspringen` auf
// `ms.length === 1` verkuerzt, faellt hier durch.
const code0 = seite.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
const b = code0.indexOf("function darfUeberspringen");
if (b < 0) {
  klage("`darfUeberspringen` fehlt — der Schritt wird wieder immer gezeigt, auch wo es "
      + "nichts zu entscheiden gibt.");
} else {
  const rumpf = code0.slice(b, code0.indexOf("}", b));
  if (!/conf\s*===\s*"belegt"/.test(rumpf)) {
    klage("`darfUeberspringen` prueft die Beleglage nicht. Dann wird auch bei blosser "
        + "Selbstauskunft uebersprungen — samt der Warnung, die dort haengt.");
  }
  if (!/length\s*===\s*1/.test(rumpf)) {
    klage("`darfUeberspringen` prueft die Anzahl nicht. Bei mehreren Einheiten ist die "
        + "Frage eine echte und darf nicht entfallen.");
  }
  /* ⚠ Die Funktion HIER herausschneiden, nicht `js` von oben leihen: das ist im
     else-Zweig von Abschnitt 1 gebunden und hier nicht sichtbar. Beim ersten Versuch
     war genau das der Fehler — und er blieb unbemerkt, weil dieser ganze Block in
     einem nicht geschlossenen `/*` steckte und gar nicht lief. */
  const q = seite.indexOf("function darfUeberspringen");
  const js2 = seite.slice(q, seite.indexOf("\n}", q) + 3).replace("(ms: Member[]): boolean", "(ms)");
  const regel2 = new Function(`${js2}\nreturn darfUeberspringen;`)();
  const SPRUNG = [
    ["eine belegte Einheit",        [{ name: "A", conf: "belegt",   method: "x", wins: 5 }], true],
    ["eine unsichere Einheit",      [{ name: "A", conf: "unsicher", method: "x", wins: 5 }], false],
    ["zwei belegte Einheiten",      [{ name: "A", conf: "belegt",   method: "x", wins: 5 },
                                     { name: "B", conf: "belegt",   method: "x", wins: 2 }], false],
    ["keine Einheit",               [], false],
  ];
  for (const [name, ms, erwartet] of SPRUNG) {
    if (regel2(ms) !== erwartet) {
      klage(`darfUeberspringen(${name}) = ${regel2(ms)}, erwartet ${erwartet}`);
    }
  }
}

/* ── 1c. Die Aussage verspricht nichts, was das Produkt nicht kann ────────────────── */
// ⚠ Geprueft am 2026-09-18: eine Einheit laesst sich NICHT nachtraeglich ergaenzen.
// `EntityKorrektur` unter „Unternehmen" ERSETZT die Zuordnung, sie fuegt nichts hinzu.
if (/ergänzen|ergaenzen|hinzufügen|hinzufuegen/.test(seite.slice(seite.indexOf("Das ist euer Bestand"),
                                                                seite.indexOf("Das ist euer Bestand") + 900))) {
  klage("Der Text verspricht, eine Einheit spaeter zu ergaenzen. Das kann das Produkt "
      + "nicht — `EntityKorrektur` ersetzt die Zuordnung, sie ergaenzt keine Einheit.");
}

/* ── 2. BEIDE WEGE BENUTZEN DIESELBE REGEL────────────────────────────────────────── */
// In den Bildschirm fuehren der normale Pfad und der Token-Pfad. ⚠ Auf dem Token-Pfad
// stand einmal `anzahl > 1` ohne Belegpruefung — zwei Wege in denselben Bildschirm mit
// zwei Regeln laufen auseinander, und zwar unbemerkt, weil der andere Weg funktioniert.
const wege = [...code0.matchAll(/geheZu\(\s*darfUeberspringen\([^)]*\)\s*\?/g)].length;
if (wege < 2) {
  klage(`Nur ${wege} Weg(e) entscheiden ueber \`darfUeberspringen\` — es gibt zwei `
      + "(normaler Pfad und Token-Pfad). Der andere springt nach eigener Regel.");
}
if ([...code0.matchAll(/geheZu\("profil"\)/g)].length > 0) {
  klage("Ein Weg fuehrt unbedingt in den Einheiten-Schritt, ohne die Regel zu fragen.");
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
  console.log(`  → ${(100 * eins / ges).toFixed(1)} % sparen den Klick; der Rest entscheidet wirklich etwas`);
  // ⚠ Faellt der Anteil stark, ist die Abkuerzung ihren Aufwand nicht mehr wert — dann
  //    gehoert sie geprueft, nicht stillschweigend weitergeschleppt.
  if (eins / ges < 0.4) {
    klage(`Nur ${(100 * eins / ges).toFixed(1)} % sehen noch eine Ein-Einheit-Liste. Die `
        + "Unterscheidung war fuer 79,5 % gebaut; die Datenlage hat sich verschoben.");
  }
}

console.log(fehler ? `\n✗ ${fehler} Befund(e)`
                   : "\n✓ Der Schritt entfaellt, wo er nichts fragt — und bleibt, wo er warnt");
process.exit(fehler ? 1 : 0);
