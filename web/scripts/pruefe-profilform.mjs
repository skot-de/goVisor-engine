/* Ein Profil aus der Datenbank ist NICHT das, was die Engine erwartet.
 *
 *     node web/scripts/pruefe-profilform.mjs
 *
 * Geprüft wird die ECHTE `buildProfile`/`matchLead` aus `lib/profileEngine.js`.
 *
 * ⚠ DER ANLASS, gemessen am 2026-09-11. `loadProfile()` holte den `profile`-jsonb aus
 * Supabase und gab ihn mit `as Profile` zurück — einem Typ mit 18 Pflichtfeldern. Der Cast
 * war eine Behauptung: zurück kam, was jemand hineingeschrieben hatte. Ein per Skript
 * gesetztes Profil trug 5 der 18 Felder. Folge: `matchLead` starb an
 * `p.nachbarFields.includes(...)` beim ERSTEN Rendern der Lead-Liste, und der Nutzer sah
 * „Application error: a client-side exception has occurred" — sonst nichts. Keine halbe
 * Seite, kein Hinweis, kein Weg zurück.
 *
 * Das ist die Fehlerklasse „sieht aus wie eine Aussage über die Welt, ist eine über unsere
 * Leitung": der Typ sagte „vollständig", geprüft hat es niemand.
 */
import { buildProfile, matchLead } from "../lib/profileEngine.js";

let fehler = 0;
const pruefe = (name, bedingung) => {
  if (!bedingung) fehler++;
  console.log(`${bedingung ? "ok  " : "FEHL"}  ${name}`);
};

const LEAD = { cpv: "45220000", nuts: "DEA22", buyer: "Stadt Hamm", wert: 500000 };
// ⚠ Ein Lead AUSSERHALB der eigenen CPV-Felder. Der erste Entwurf nahm 45220000 — das steht
// im Profil, also endet `matchLead` schon bei `cpvFields.includes` und erreicht
// `nachbarFields` nie. Der Test war gruen und pruefte nichts. Erst ein FREMDER CPV laeuft
// in die Zeile, an der die Oberflaeche wirklich gestorben ist.
const FREMD = { cpv: "79000000", nuts: "DEA22", buyer: "Stadt Hamm", wert: 500000 };

// Genau die fünf Felder, die ein von Hand gesetztes Profil trägt.
const SCHMAL = {
  firma: "H. Klostermann Baugesellschaft mbH",
  entityConfidence: "unbestaetigt",
  cpvFields: ["4522", "4523"],
  cpvLabels: ["Ingenieur- und Hochbauarbeiten", "Rohrleitungen"],
  regions: ["DEA"],
};

// ── Die Normalisierung füllt, was fehlt ────────────────────────────────────────
const voll = buildProfile(SCHMAL);
for (const feld of ["cpvFields6", "cpvWins", "nachbarFields", "regionTyp", "regionLabels",
                    "capabilities", "exclusions"]) {
  pruefe(`buildProfile setzt ${feld}`, voll[feld] !== undefined);
}
pruefe("die mitgegebenen Werte bleiben erhalten",
  voll.cpvFields.length === 2 && voll.firma === SCHMAL.firma);

// ── ⚠ DER KERN: ein rohes Profil bringt die Bewertung um ──────────────────────
let rohGestorben = false;
try { matchLead(FREMD, SCHMAL); } catch { rohGestorben = true; }
pruefe("ein ROHES Profil laesst matchLead sterben (deshalb muss normalisiert werden)",
  rohGestorben);

let normalOk = true;
try { matchLead(LEAD, voll); matchLead(FREMD, voll); } catch { normalOk = false; }
pruefe("ein normalisiertes Profil traegt durch matchLead", normalOk);

// ── Auch das leere Profil darf nicht sterben ──────────────────────────────────
let leerOk = true;
try { matchLead(LEAD, buildProfile({})); matchLead(FREMD, buildProfile({})); } catch { leerOk = false; }
pruefe("selbst ein voellig leeres Profil traegt", leerOk);

console.log(fehler ? `\n${fehler} Fehler` : "\nalles gruen");
process.exit(fehler ? 1 : 0);
