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
import { buildProfile, matchLead, brancheFromProfile } from "../lib/profileEngine.js";

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

// ── ⚠ FALLE 2: DIE NORMALISIERUNG DARF NICHTS WEGWERFEN ───────────────────────
// `buildProfile` kopiert FELDWEISE. Was `emptyProfile` nicht kennt, faellt still heraus —
// und seit `loadProfile` jedes Profil durch die Normalisierung schickt, trifft das echte
// Nutzerdaten. Gemessen am 2026-09-17: `branche` fehlte in der Liste. Ein Profil mit
// `branche: "bau"` kam als `undefined` zurueck, der Explorer fiel auf „it" und zeigte
// **0 von 0** — nach einem Onboarding, das gerade 509 Zuschlaege bestaetigt hatte.
//
// Geprueft wird deshalb nicht „ist `branche` da", sondern die Regel dahinter: jedes Feld,
// das hineingeht, muss auch wieder herauskommen.
const HINEIN = {
  branche: "bau", firma: "Testfirma", entityConfidence: "belegt",
  cpvFields: ["4522"], cpvFields6: ["452210"], cpvLabels: ["Hochbau"],
  cpvWins: { "4522": 7 }, nachbarFields: ["4521"], regions: ["DEA"],
  regionTyp: "nuts1", regionLabels: ["Nordrhein-Westfalen"],
  volMin: 1000, volMax: 2000, maxAlleine: 500, buergschaft: 50,
  capabilities: ["iso_9001"], exclusions: ["x"], zielrichtung: "wachstum",
};
const heraus = buildProfile(HINEIN);
for (const [feld, wert] of Object.entries(HINEIN)) {
  const da = JSON.stringify(heraus[feld]) === JSON.stringify(wert);
  pruefe(`buildProfile behaelt ${feld}`, da);
}

// Und die Ableitung bleibt der Rueckfall, nicht der Vorrang.
pruefe("eine ausdrueckliche Branche schlaegt die CPV-Ableitung",
  brancheFromProfile(buildProfile({ branche: "medizin", cpvFields: ["4522"] })) === "medizin");
pruefe("ohne Angabe wird aus den CPV abgeleitet",
  brancheFromProfile(buildProfile({ cpvFields: ["4522"] })) === "bau");

// ── Auch das leere Profil darf nicht sterben ──────────────────────────────────
let leerOk = true;
try { matchLead(LEAD, buildProfile({})); matchLead(FREMD, buildProfile({})); } catch { leerOk = false; }
pruefe("selbst ein voellig leeres Profil traegt", leerOk);

console.log(fehler ? `\n${fehler} Fehler` : "\nalles gruen");
process.exit(fehler ? 1 : 0);
