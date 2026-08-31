/* Passwortstärke — EINE Regel für das ganze Produkt.
 *
 * WARUM ES DIESE DATEI GIBT. Am 2026-08-31 standen drei verschiedene Regeln nebeneinander:
 * das Onboarding verlangte 12 Zeichen UND drei Zeichenklassen, das Zurücksetzen 8 Zeichen,
 * die Einstellungen 8 Zeichen. Man konnte also später ein Passwort setzen, mit dem man sich
 * nicht hätte anmelden dürfen — die schwächste Regel gewann, weil sie erreichbar blieb.
 *
 * ⚠ UND DIE STRENGSTE WIDERSPRACH SICH SELBST. Unter dem Feld stand „Länge zählt mehr als
 * Sonderzeichen, eine Passphrase aus vier Wörtern ist sicherer als P@ssw0rt!" — und der
 * Prüfer wies genau diese Passphrase ab, weil ihr die Ziffer fehlte. Eine 29 Zeichen lange
 * Passphrase fiel durch, `Abcdefgh123!` kam durch. Der Code-Kommentar daneben sagte selbst
 * „Länge schlägt Sonderzeichen"; nur die Bedingung darunter tat es nicht.
 *
 * Die Regel folgt jetzt dem, was das Produkt behauptet, und der heutigen Empfehlung
 * (NIST SP 800-63B): Länge zuerst, Zeichenklassen nur dort, wo die Länge sie nicht ersetzt.
 *
 * ⚠ BEWUSST PLAIN JS statt TypeScript — dasselbe wie bei `netzMatch.js`: so kann
 * `scripts/pruefe-passwort.mjs` die Regel unter `node` mit echten Passwoertern durchspielen,
 * statt sie in einer Abschrift nachzubauen. Eine Abschrift geht gruen, waehrend die benutzte
 * Fassung falsch ist.
 *
 * SERVERSEITE, GEMESSEN AM 2026-08-31: Supabase führt eine eigene Passwortregel, und sie
 * steht in keiner Codezeile — sie ist eine Dashboard-Einstellung. Nachgesehen ohne Anmeldung,
 * über eine Registrieranfrage mit einem Passwort, das garantiert scheitert (`abc`):
 *
 *     {"error_code":"weak_password","msg":"Password should be at least 6 characters.",
 *      "weak_password":{"reasons":["length"]}}
 *
 * **Nur `length`, kein `characters`.** `abc` verletzt jede denkbare Zeichenklassen-Regel;
 * wäre eine gesetzt, stünde sie in den Gründen, denn GoTrue meldet alle zutreffenden. Also
 * gilt serverseitig die Voreinstellung: sechs Zeichen, keine Zeichenklassen. Unsere Regel
 * hier ist strenger, und eine Passphrase kommt am Server durch.
 *
 * ⚠ Das bleibt eine EINSTELLUNG und kann sich ohne Codeänderung ändern. Wird im Dashboard
 * „Password Requirements" auf Zeichenklassen gestellt, weist der Server die Passphrase
 * trotzdem ab, und der Nutzer sieht die generische Meldung „Das Passwort erfüllt die
 * Mindestanforderungen nicht" statt des Hinweises hier. Nachprüfen geht mit derselben Sonde,
 * ohne Konto und ohne Mail — die Prüfung scheitert vor dem Anlegen (HTTP 422).
 */

export const MINDESTLAENGE = 12;

/** Ab hier trägt die Länge allein. Vier Wörter à drei Zeichen plus Leerzeichen liegen
 *  darüber — genau der Fall, den der Hinweis unter dem Feld verspricht. */
const LAENGE_STATT_KLASSEN = 16;
const WOERTER_STATT_KLASSEN = 4;

const SCHWACH = ["passwort", "password", "qwertz", "qwerty", "123456", "govisor", "admin",
                 "willkommen", "sommer", "winter"];

/** `mail` ist optional — beim Zurücksetzen kennt die Seite die Adresse nicht.
 *  @param {string} pw
 *  @param {string} [mail]
 *  @returns {{ok: boolean, maengel: string[], stufe: 0|1|2|3}} */
export function pwPruefung(pw, mail = "") {
  const lokal = (mail.split("@")[0] || "").toLowerCase();
  const klassen = [/[a-zäöüß]/, /[A-ZÄÖÜ]/, /\d/, /[^\wäöüßÄÖÜ]/].filter((r) => r.test(pw)).length;
  const woerter = pw.trim().split(/\s+/).filter((w) => w.length >= 3).length;
  const langGenug = pw.length >= LAENGE_STATT_KLASSEN || woerter >= WOERTER_STATT_KLASSEN;

  const maengel = [];
  if (pw.length < MINDESTLAENGE) maengel.push("mindestens 12 Zeichen");
  // Zeichenklassen nur verlangen, wo die Länge sie nicht ersetzt — sonst widerspräche die
  // Regel dem Hinweis, der direkt daneben steht.
  if (!langGenug && klassen < 3) {
    maengel.push("entweder ab 16 Zeichen bzw. vier Wörter, oder Groß- und Kleinbuchstaben plus Ziffern");
  }
  if (SCHWACH.some((w) => pw.toLowerCase().includes(w))) maengel.push("kein gängiges Wort wie „passwort“");
  if (lokal.length >= 3 && pw.toLowerCase().includes(lokal)) maengel.push("nicht die eigene E-Mail-Adresse");
  if (/^(.)\1+$/.test(pw)) maengel.push("nicht nur ein wiederholtes Zeichen");

  // Stufe rein für die Anzeige — die Freigabe hängt allein an `maengel`. Eine lange
  // Passphrase gilt hier als stark, sonst zeigte der Balken „mittel" für genau das,
  // was der Hinweis empfiehlt.
  const stufe = pw.length === 0 ? 0
    : maengel.length ? 1
    : (pw.length >= LAENGE_STATT_KLASSEN || woerter >= WOERTER_STATT_KLASSEN || klassen >= 3) ? 3 : 2;
  return { ok: pw.length > 0 && maengel.length === 0, maengel, stufe };
}
