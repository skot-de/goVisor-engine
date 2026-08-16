/**
 * Wer darf die internen Seiten sehen — EINE Quelle für Middleware und Oberfläche.
 *
 * **Warum nicht zwei Prüfungen.** Die Sperre sitzt in der Middleware, die Anzeige des
 * Menüeintrags braucht dieselbe Antwort. Zwei getrennte Implementierungen derselben Regel
 * laufen beim ersten Nachziehen auseinander — und zwar in die gefährliche Richtung: die
 * Anzeige sagt „nein", die Sperre denkt „ja".
 *
 * **Warum Umgebungsvariable und nicht Datenbank-Rolle.** Für eine Person ist ein
 * Rollenmodell mehr Angriffsfläche als Nutzen. Ein Datenbankfeld kann man versehentlich
 * setzen; eine Vercel-Umgebungsvariable nicht.
 */
export const ADMINS = (process.env.ADMIN_EMAILS ?? "sk@skot.de")
  .split(",").map((x) => x.trim().toLowerCase()).filter(Boolean);

/** FAIL-CLOSED: ohne konfigurierte Adresse kommt niemand rein — auch nicht „alle". */
export function istAdmin(email: string | null | undefined): boolean {
  if (!ADMINS.length || !email) return false;
  return ADMINS.includes(email.toLowerCase());
}
