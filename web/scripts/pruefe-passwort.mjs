/* Prueft die Passwortregel gegen das, was die Oberflaeche daneben verspricht.
 *     node web/scripts/pruefe-passwort.mjs
 *
 * Der Fall, der das noetig macht: bis zum 2026-08-31 stand unter dem Feld „Länge zählt mehr
 * als Sonderzeichen, eine Passphrase aus vier Wörtern ist sicherer als P@ssw0rt!" — und der
 * Pruefer wies genau diese Passphrase ab, weil ihr die Ziffer fehlte. Eine 29 Zeichen lange
 * Passphrase fiel durch, `Abcdefgh123!` kam durch. Der Code-Kommentar daneben sagte selbst
 * „Länge schlägt Sonderzeichen"; nur die Bedingung darunter tat es nicht.
 *
 * Das ist die unangenehme Sorte Fehler: Hinweis und Regel sind je fuer sich vertretbar, und
 * nur zusammen ergeben sie einen Widerspruch. Kein Test schlaegt an, weil beide Seiten tun,
 * was dasteht. Hier wird deshalb die BEHAUPTUNG geprueft, nicht die Bedingung. */

import { pwPruefung, MINDESTLAENGE } from "../lib/passwort.js";

let fehler = 0;
const nicht = (b, t) => { if (!b) { console.error("  ✗ " + t); fehler++; } };
const geht = (pw, mail) => pwPruefung(pw, mail).ok;

// ── Was der Hinweis verspricht, muss durchkommen ──────────────────────────────
nicht(geht("korrekt pferd batterie klammer"), "vier Woerter muessen reichen — genau das verspricht der Hinweis");
nicht(geht("vier woerter lange passphrase"), "Passphrase in Kleinschrift muss reichen");
nicht(geht("dieser satz ist lang genug"), "langer Satz ohne Ziffern muss reichen");

// ── Und das Gegenstueck: kurz bleibt kurz, egal wie bunt ──────────────────────
nicht(!geht("P@ssw0rt!"), "9 Zeichen duerfen nicht reichen, auch mit Sonderzeichen");
nicht(!geht("Ab1!"), "vier Zeichen duerfen nie reichen");
nicht(!geht("kurz und bunt1"[0].repeat(11)), "ein wiederholtes Zeichen ist kein Passwort");

// ── Die klassische Variante muss weiter funktionieren ─────────────────────────
nicht(geht("Abcdefgh123!"), "12 Zeichen mit drei Klassen muessen weiter reichen");

// ── Kurz UND einklassig bleibt draussen: die Laenge ersetzt die Klassen erst ab 16 ──
nicht(!geht("abcdefghijklmn"), "14 Zeichen einklassig ohne Wortstruktur duerfen nicht reichen");
nicht(geht("abcdefghijklmnopq"), "17 Zeichen duerfen ohne Klassen reichen");

// ── Die uebrigen Riegel duerfen nicht verlorengehen ───────────────────────────
nicht(!geht("passwort passwort passwort"), "gaengige Woerter bleiben gesperrt");
nicht(!geht("martin martin martin", "martin@firma.de"), "die eigene Adresse bleibt gesperrt");

// ── Mindestlaenge ist EINE Zahl fuers ganze Produkt ───────────────────────────
nicht(MINDESTLAENGE === 12, `Mindestlaenge sollte 12 sein, ist ${MINDESTLAENGE}`);
nicht(!geht("Ab1!" + "x".repeat(MINDESTLAENGE - 5)), "unter der Mindestlaenge muss es scheitern");

// ── Der Balken darf eine Passphrase nicht als „mittel" abwerten ───────────────
nicht(pwPruefung("korrekt pferd batterie klammer").stufe === 3,
      "eine Passphrase muss als stark angezeigt werden, sonst widerspricht der Balken dem Hinweis");

if (fehler) { console.error(`\n${fehler} Abweichung(en).`); process.exit(1); }
console.log("Passwortregel: Hinweis und Pruefung stimmen ueberein.");
