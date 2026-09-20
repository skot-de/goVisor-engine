/* „4 von 6 Angaben" — die Zahl, die im Ueberblick steht, GERECHNET statt gelesen.
 *
 * ⚠ WARUM DIESE SONDE DEN ECHTEN CODE FAEHRT. Die Zahl hat sechs Eingaenge, und zwei davon
 * sind Fallen, die man einer Textpruefung nicht ansieht:
 *
 *   1. `regions: null` heisst NICHT „nicht ausgefuellt", sondern „bundesweit taetig"
 *      (`buildProfile` macht aus leerer Eingabe bewusst null). Wer das als Luecke zaehlt,
 *      mahnt eine Angabe an, die der Nutzer laengst gemacht hat.
 *   2. `zielrichtung` traegt eine Vorgabe ('ausgewogen') und ist damit IMMER gesetzt. Waere
 *      sie im Nenner, staende dort eine geschenkte Angabe, und „5 von 7" waere geschoent.
 *
 * ⚠ Und der Grund fuer „4 von 6" statt „67 %": ein Prozentsatz verspricht, dass 100
 * erreichbar ist. Wer keine Buergschaft hat und keine will, kommt nie dorthin.
 */
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const { angabenStand, emptyProfile, buildProfile } =
  await import(join(WEB, "lib", "profileEngine.js"));

let fehler = 0;
const sage = (ok, t) => { if (!ok) fehler++; console.log(`  ${ok ? "✓" : "✗"} ${t}`); };
const voll = (p) => angabenStand(p).voll;

const basis = { cpvFields: ["4521"] };
const alles = { ...basis, regions: ["DE1"], volMin: 1e5, volMax: 2e6,
                maxAlleine: 8e5, buergschaft: 5e5, exclusions: { cpv_aus: ["4522"] } };

sage(angabenStand(null).gesamt === 6, "sechs Angaben im Nenner");
sage(voll(null) === 0, "kein Profil: 0 von 6");
sage(voll(emptyProfile()) === 0, "leeres Profil: 0 von 6");
sage(voll(buildProfile(basis)) === 1, "nur Fachgebiete: 1 von 6");
sage(voll(buildProfile(alles)) === 6, "vollstaendiges Profil: 6 von 6");

/* ⚠ DIE BEIDEN FALLEN, EINZELN GEPRUEFT. */
sage(voll({ ...buildProfile(basis), regionTyp: "bundesweit" }) === 2,
     "bundesweit taetig zaehlt als beantwortet, nicht als Luecke");
sage(voll(buildProfile({ ...basis, regions: ["DE1"] })) === 2,
     "gesetzte Regionen zaehlen genauso");
sage(voll({ ...buildProfile(alles), zielrichtung: "expandieren" }) === 6
     && voll({ ...buildProfile(alles), zielrichtung: "bestand" }) === 6,
     "die Zielrichtung veraendert die Zahl nicht (sie hat eine Vorgabe)");

/* Leere Huellen sind keine Angabe: ein Ausschluss-Objekt ohne Inhalt, eine leere Liste. */
sage(voll(buildProfile({ ...basis, exclusions: { cpv_aus: [], regionen_aus: [] } })) === 1,
     "ein leeres Ausschluss-Objekt zaehlt nicht");
sage(voll(buildProfile({ ...basis, exclusions: { keine_bietergemeinschaft: false } })) === 1,
     "ein ausgeschaltetes Kaestchen zaehlt nicht");
sage(voll(buildProfile({ ...basis, exclusions: { keine_bietergemeinschaft: true } })) === 2,
     "ein gesetztes Kaestchen zaehlt");

/* ⚠ Eine Wertspanne ist EINE Angabe, auch wenn sie aus zwei Feldern besteht — sonst
   zaehlte ein Nutzer mit Ober- und Untergrenze doppelt. */
sage(voll(buildProfile({ ...basis, volMin: 1e5 })) === 2
     && voll(buildProfile({ ...basis, volMin: 1e5, volMax: 2e6 })) === 2,
     "Ober- und Untergrenze sind zusammen eine Angabe");

/* Die offenen Angaben muessen benennbar sein, sonst kann niemand sie nachfragen. */
const offen = angabenStand(buildProfile(basis)).offen;
sage(offen.length === 5 && offen.includes("buerg") && !offen.includes("fach"),
     `die offenen Angaben sind benannt: ${offen.join(", ")}`);

console.log(fehler ? `  ${fehler} Abweichung(en)` : "  Angaben-Zaehlung stimmt");
process.exit(fehler ? 1 : 0);
