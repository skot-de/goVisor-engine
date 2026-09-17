// Wie viele Stellen schreiben das Profil — und schreiben sie dasselbe?
//
// WARUM ES DIESE PRUEFUNG GIBT. `user_profiles` haelt dieselben Angaben ZWEIMAL: als
// Spalten (`vol_min`, `vol_max`, `regions`, `branche`, `company_name`) und im
// `profile`-jsonb (`volMin`, `volMax`, `regions`, `branche`, `firma`). Gelesen wird fuer
// die Passung ausschliesslich der Blob (`loadProfile`); die Spalten liest nur `/settings`
// selbst, um sein eigenes Formular zu fuellen.
//
// Bis zum 2026-09-17 schrieb `/settings` ueber `saveProfileFields` NUR die Spalten. Wer
// dort seine Wertspanne aenderte, schrieb also in Felder, die kein Treffer je ansieht —
// waehrend die Seite meldete: „Profil gespeichert, wirkt beim naechsten Laden auf die
// Relevanz."
//
// Nachgewiesen an der Datenbank, nicht nur am Quelltext: ein Profil trug in den Spalten
// 2.000.000 / 10.000.000 und im Blob null / null.
//
// ⚠ DIE EIGENSCHAFT, DIE HIER GEPRUEFT WIRD: es gibt GENAU EINEN Schreibweg auf
// `user_profiles`. Zwei Schreiber auf dieselbe Angabe laufen auseinander — das ist keine
// Prognose, es ist hier bereits gemessen worden. Ein zweiter Weg, der „auch das Richtige
// tut", ist kein Gegenargument: der erste tat anfangs auch das Richtige.
import { readFileSync, readdirSync } from "node:fs";

const web = new URL("../", import.meta.url);
let fehler = 0;
const klage = (m) => { console.error("  ✗ " + m); fehler++; };

function dateien(ordner, raus = []) {
  for (const e of readdirSync(ordner, { withFileTypes: true })) {
    if (e.isDirectory()) {
      if (!["node_modules", ".next", "scripts"].includes(e.name)) {
        dateien(new URL(e.name + "/", ordner), raus);
      }
    } else if (/\.(ts|tsx)$/.test(e.name)) raus.push(new URL(e.name, ordner));
  }
  return raus;
}

/* ── 1. Genau EINE Stelle schreibt den `profile`-Blob ─────────────────────────────── */
// Spalten-Updates sind unkritisch: sie sind einwertig, „der letzte gewinnt" ist dort die
// richtige Regel, und ohne Lesen entsteht kein Fenster. Der BLOB dagegen wurde gelesen,
// im Client veraendert und ganz zurueckgeschrieben — zwei solche Schreiber loeschen sich
// gegenseitig. Genau das ist am 2026-09-17 im Onboarding passiert („0 von 7.013").
const blobSchreiber = [], spaltenSchreiber = [];
for (const p of dateien(web)) {
  const text = readFileSync(p, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
  const name = String(p).split("/web/")[1];
  // ⚠ NACHSCHAU, NICHT VERBRAUCH. Mit `([\s\S]{0,160})` frisst der erste Treffer 160
  // Zeichen und damit womoeglich den naechsten `from("user_profiles")` — in genau dieser
  // Datei standen zwei Aufrufe 90 Zeichen auseinander, und die Sonde meldete „0 Schreiber".
  for (const m of text.matchAll(/from\(\s*["'`]user_profiles["'`]\s*\)\s*\.\s*(\w+)\((?=([\s\S]{0,160}))/g)) {
    if (!["update", "upsert", "insert"].includes(m[1])) continue;
    (/\bprofile\b\s*[,:}]/.test(m[2]) ? blobSchreiber : spaltenSchreiber).push(`${name} → .${m[1]}()`);
  }
}
if (blobSchreiber.length !== 1) {
  klage(`${blobSchreiber.length} Stellen schreiben den \`profile\`-Blob statt einer:\n      `
      + blobSchreiber.join("\n      ")
      + "\n      Zwei Lese-Aendere-Schreibe-Zyklen auf dasselbe Dokument loeschen sich "
      + "gegenseitig. Der eine Weg ist `lib/supabase/profilBlob.ts`.");
} else {
  console.log(`  Blob-Schreiber : ${blobSchreiber[0]}`);
  console.log(`  Spalten-Schreiber: ${spaltenSchreiber.length} (unkritisch, kein Lesezyklus)`);
}

/* ── 1b. Der eine Weg mischt, statt zu ersetzen ───────────────────────────────────── */
const blobModul = readFileSync(new URL("lib/supabase/profilBlob.ts", web), "utf8");
if (!/\.rpc\(\s*["'`]merge_profile["'`]/.test(blobModul)) {
  klage("`profilBlob.ts` ruft `merge_profile` nicht auf — der Merge liegt wieder im "
      + "Client, samt Fenster.");
}
// Der Rueckfall darf nicht still sein: ohne Migration ist das Fenster wieder offen, und
// das muss im Protokoll stehen. Sonst heisst es spaeter „wir haben das doch behoben".
const rueckfall = blobModul.slice(blobModul.indexOf("funktionFehlt(error)"));
if (!/console\.(error|warn)/.test(rueckfall)) {
  klage("Der Rueckfall auf Lesen-Aendern-Schreiben meldet sich nicht. Ein stiller "
      + "Rueckfall sieht aus wie ein behobener Fehler.");
}

/* ── 2. Jede doppelt gehaltene Angabe wird in BEIDEN Formen geschrieben ───────────── */
// Sonst entsteht die Spaltung wieder — nur innerhalb derselben Funktion.
const auth = readFileSync(new URL("lib/supabase/auth.ts", web), "utf8");
const block = auth.slice(auth.indexOf("export async function saveProfile("),
                        auth.indexOf("/* user_profiles.profile-Blob"));
const DOPPELT = [
  ["company_name", "firma"], ["regions", "regions"], ["region_labels", "regionLabels"],
  ["vol_min", "volMin"], ["vol_max", "volMax"], ["branche", "branche"],
];
for (const [spalte, feld] of DOPPELT) {
  if (!new RegExp(`\\b${spalte}\\s*:`).test(block)) {
    klage(`\`saveProfile\` schreibt die Spalte \`${spalte}\` nicht mehr — /settings zeigt `
        + "dann einen anderen Stand als die Passung benutzt.");
  }
  if (!new RegExp(`\\b${feld}\\b`).test(block)) {
    klage(`\`saveProfile\` liest das Profilfeld \`${feld}\` nicht — die Spalte \`${spalte}\` `
        + "bekaeme einen Wert, der aus nichts stammt.");
  }
}

/* ── 3. Der Blob wandert vollstaendig mit ─────────────────────────────────────────── */
// `profile: blob` ist die Zeile, die die Passung fuettert. Faellt sie weg, schreibt die
// Anwendung nur noch Spalten — und das ist wortwoertlich der behobene Fehler.
if (!/mischeProfilBlob\s*\(/.test(block)) {
  klage("`saveProfile` ruft `mischeProfilBlob` nicht auf. `loadProfile` liest "
      + "ausschliesslich den Blob — die Passung saehe ab sofort gar kein Profil.");
}

/* ── 4. /settings geht ueber den einen Weg ────────────────────────────────────────── */
const konto = readFileSync(new URL("lib/supabase/account.ts", web), "utf8")
  .replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
// ⚠ NICHT bis zum ersten „\n}" schneiden: die Typsignatur `Partial<{ … }>` endet selbst
// so, und der Rumpf begaenne dann gar nicht. Bis zum naechsten `export` ist robust.
const ab = konto.indexOf("export async function saveProfileFields");
const weiter = konto.indexOf("\nexport ", ab + 10);
const sf = konto.slice(ab, weiter < 0 ? konto.length : weiter);
if (!/\bsaveProfile\s*\(/.test(sf)) {
  klage("`saveProfileFields` ruft `saveProfile` nicht auf — /settings schreibt wieder an "
      + "der Passung vorbei.");
}

/* ── 5. Der Patch ist wirklich minimal ───────────────────────────────────────────── */
// ⚠ WENN `geaenderteFelder` DEN GANZEN BLOB ZURUECKGIBT, wird aus dem Merge wieder ein
// Ueberschreiben — und zwar still: die Datenbankfunktion arbeitet korrekt, der Aufruf ist
// da, der Waechter oben bleibt gruen. Nur haette der andere Schreiber wieder verloren.
// Deshalb faehrt diese Pruefung die ECHTE Funktion, nicht ihre Beschreibung.
{
  const quelle = blobModul.slice(blobModul.indexOf("export function geaenderteFelder"));
  const js = quelle.slice(0, quelle.indexOf("\n}") + 3)
    .replace("export function", "function")
    // Nur die Annotationen dieser einen Funktion — bewusst eng gefasst.
    .replace(/vorher: Record<string, unknown>, nachher: Record<string, unknown>,/, "vorher, nachher")
    .replace(/\)\s*:\s*Record<string, unknown>\s*\{/, ") {")
    .replace(/const patch: Record<string, unknown> = \{\};/, "const patch = {};");
  const geaenderteFelder = new Function(`${js}\nreturn geaenderteFelder;`)();

  const vorher = { firma: "A", regions: ["DEA"], stammdaten: { x: 1 }, history: [] };
  const nachher = { firma: "A", regions: ["DEA", "DE2"], stammdaten: { x: 1 }, history: [] };
  const patch = geaenderteFelder(vorher, nachher);
  const keys = Object.keys(patch);
  if (keys.length !== 1 || keys[0] !== "regions") {
    klage(`\`geaenderteFelder\` liefert ${JSON.stringify(keys)} statt nur ["regions"]. `
        + "Ein zu grosser Patch macht aus dem Merge wieder ein Ueberschreiben.");
  }
  // Ein entferntes Feld muss als `null` im Patch stehen — sonst bliebe es stehen.
  const weg = geaenderteFelder({ a: 1, b: 2 }, { a: 1 });
  if (!("b" in weg) || weg.b !== null) {
    klage("`geaenderteFelder` meldet ein entferntes Feld nicht als `null` — es bliebe "
        + "im Blob stehen, weil der Merge nur Genanntes anfasst.");
  }
  // Nichts geaendert = leerer Patch = kein Schreibzugriff.
  if (Object.keys(geaenderteFelder(vorher, { ...vorher })).length) {
    klage("`geaenderteFelder` meldet Aenderungen, wo keine sind — jeder Aufruf schriebe.");
  }
}

console.log(fehler ? `\n✗ ${fehler} Befund(e)` : "\n✓ Ein Schreibweg, beide Formen bedient");
process.exit(fehler ? 1 : 0);
