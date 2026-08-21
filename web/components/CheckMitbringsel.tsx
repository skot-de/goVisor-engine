"use client";

import { useSyncExternalStore } from "react";
import {
  abonniereCheckErgebnis, leseCheckErgebnis, leseCheckErgebnisServer,
} from "@/lib/checkErgebnis";

/**
 * Was der Besucher aus dem Eignungs-Check mitbringt, hier am Anfang der Anmeldung.
 *
 * **Warum das den Übergang weicher macht.** Auf der Startseite darf man etwas tun und
 * bekommt ein Ergebnis; im nächsten Bild stand bisher ein leeres Anmeldeformular, das so
 * tat, als sei nichts gewesen. Wer hier seine eigene Auswahl wiederfindet („Bau und
 * Handwerk, überall, 9 von 11 erfüllt, 188 passende offene Vergaben"), erlebt den Schritt
 * als Fortsetzung statt als Schranke — und er sieht, wofür er das Konto anlegt.
 *
 * **Nur was er selbst eingegeben hat.** Der Wert kommt aus dem Modulspeicher derselben
 * Sitzung (`lib/checkErgebnis.ts`), nicht aus einer Datenbank, einem Cookie oder einem
 * URL-Parameter. Wer die Anmeldung direkt aufruft oder neu lädt, sieht diesen Kasten nicht
 * — dann steht dort nichts, statt etwas Erfundenem.
 */
export function CheckMitbringsel() {
  const e = useSyncExternalStore(
    abonniereCheckErgebnis, leseCheckErgebnis, leseCheckErgebnisServer);
  if (!e) return null;

  return (
    <div className="mitbringsel">
      <p className="mitbringsel-kopf">Aus eurem Eignungs-Check</p>
      <ul>
        <li><span>Fachgebiet</span><b>{e.fachLabel}</b></li>
        <li><span>Region</span><b>{e.regionLabel}</b></li>
        <li><span>Übliche Vorgaben erfüllt</span><b>{e.erfuellt} von {e.von}</b></li>
        {e.offeneTreffer > 0 ? (
          <li><span>Passende offene Vergaben</span><b>{e.offeneTreffer.toLocaleString("de-DE")}</b></li>
        ) : null}
      </ul>
      <p className="mitbringsel-fuss">
        {e.offeneTreffer > 0
          ? "Legt das Konto an, dann seht ihr sie mit Frist, Unterlagen und Anforderungen."
          : "Legt das Konto an, dann rechnen wir das je Vorgang statt als Zusammenfassung."}
        {e.luecke ? ` Eure grösste Lücke, ${e.luecke}, tragt ihr im Profil nach.` : ""}
      </p>
    </div>
  );
}
