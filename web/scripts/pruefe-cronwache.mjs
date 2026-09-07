/* Die Regel, die entscheidet, wer den Cron-Endpunkt auslösen darf.
 *
 *     node web/scripts/pruefe-cronwache.mjs
 *
 * Geprüft wird die ECHTE Funktion aus `lib/cronWache.js`, keine Abschrift.
 *
 * Warum überhaupt ein Test: `/api/alerts/run` verschickt E-Mails an alle Nutzer mit
 * Beobachtungen und setzt danach die `*_sent`-Flags. Wer ihn auslösen kann, kann fremde
 * Hinweise VERBRAUCHEN — sie gelten als zugestellt und kommen nie wieder. Bis zum
 * 2026-09-07 hing die einzige Absicherung dieser Regel an einem Wort in einer Datei.
 */
import { cronUrteil, DURCH, UNKONFIGURIERT, ABGELEHNT } from "../lib/cronWache.js";

let fehler = 0;
const pruefe = (name, bedingung) => {
  if (!bedingung) fehler++;
  console.log(`${bedingung ? "ok  " : "FEHL"}  ${name}`);
};
/** Kopfzeilen als einfache Abbildung, so wie `req.headers.get` sie liefert (fehlt = null). */
const kopf = (o) => (n) => (n in o ? o[n] : null);

const S = "geheim-123";

// ── ⚠ FALLE 1: OHNE GEHEIMNIS ZUMACHEN, NICHT AUFMACHEN ────────────────────────
// Der historische Fehler. `if (secret) {…}` liess bei fehlender Variable JEDEN durch.
pruefe("kein Geheimnis → unkonfiguriert (nicht durch!)",
  cronUrteil(undefined, kopf({})) === UNKONFIGURIERT);
pruefe("kein Geheimnis, aber ein Kopf → immer noch unkonfiguriert",
  cronUrteil(undefined, kopf({ "x-cron-secret": "irgendwas" })) === UNKONFIGURIERT);

// ── ⚠ FALLE 2: DER LEERE STRING IST KEIN GEHEIMNIS ─────────────────────────────
// `CRON_SECRET=` im Deployment ergibt "". Zählte das als gesetzt, käme jeder Aufrufer
// ohne Kopfzeile durch, denn `null === ""` ist zwar falsch — aber `"" === ""` ist wahr,
// sobald jemand die Kopfzeile leer mitschickt.
pruefe("leeres Geheimnis → unkonfiguriert",
  cronUrteil("", kopf({})) === UNKONFIGURIERT);
pruefe("leeres Geheimnis + leere Kopfzeile → NICHT durch",
  cronUrteil("", kopf({ "x-cron-secret": "" })) === UNKONFIGURIERT);

// ── Die beiden erlaubten Wege ──────────────────────────────────────────────────
pruefe("eigener Kopf mit dem Geheimnis → durch",
  cronUrteil(S, kopf({ "x-cron-secret": S })) === DURCH);
pruefe("Vercel-Cron schickt `Authorization: Bearer …` → durch",
  cronUrteil(S, kopf({ authorization: `Bearer ${S}` })) === DURCH);

// ── Was abgelehnt gehört ───────────────────────────────────────────────────────
pruefe("gar kein Kopf → abgelehnt", cronUrteil(S, kopf({})) === ABGELEHNT);
pruefe("falsches Geheimnis → abgelehnt",
  cronUrteil(S, kopf({ "x-cron-secret": "falsch" })) === ABGELEHNT);
pruefe("das Geheimnis ohne `Bearer ` → abgelehnt",
  cronUrteil(S, kopf({ authorization: S })) === ABGELEHNT);
pruefe("Praefix des Geheimnisses → abgelehnt",
  cronUrteil(S, kopf({ "x-cron-secret": S.slice(0, -1) })) === ABGELEHNT);
pruefe("Geheimnis mit angehaengtem Zeichen → abgelehnt",
  cronUrteil(S, kopf({ "x-cron-secret": S + "x" })) === ABGELEHNT);

// ⚠ FALLE 3: kein `kopf` uebergeben. Ein Aufrufer, der die Kopfzeilen vergisst, darf nicht
// deshalb durchkommen, weil der Vergleich an `undefined === undefined` haengenbleibt.
pruefe("ohne Kopf-Zugriff → abgelehnt", cronUrteil(S, null) === ABGELEHNT);

console.log(fehler ? `\n${fehler} Fehler` : "\nalles gruen");
process.exit(fehler ? 1 : 0);
