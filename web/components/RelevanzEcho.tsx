"use client";

import { useSyncExternalStore } from "react";
import {
  abonniereCheckErgebnis, leseCheckErgebnis, leseCheckErgebnisServer,
} from "@/lib/checkErgebnis";

/**
 * Die Relevanz-Spalte der drei Masse.
 *
 * Ohne Profil gibt es keine Relevanzzahl — `relevanz` steht bei allen 30.627 offenen
 * Vorgängen auf „na". Deshalb steht hier normalerweise der Verweis auf den Check darüber.
 * Wer ihn benutzt hat, sieht stattdessen SEIN Ergebnis: keine Behauptung über ihn, sondern
 * die Wiedergabe dessen, was er selbst eingegeben hat.
 */
export function RelevanzEcho() {
  const e = useSyncExternalStore(
    abonniereCheckErgebnis, leseCheckErgebnis, leseCheckErgebnisServer);

  if (!e) {
    return (
      <p>
        Der Abgleich eurer Nachweise mit dem, was in den Unterlagen verlangt wird. Diese Zahl
        gibt es nur mit Profil, deshalb steht hier keine: probiert sie oben im{" "}
        <a href="#check">Eignungs-Check</a> aus, ohne Anmeldung.
      </p>
    );
  }
  return (
    <p>
      <b>Ihr habt gerade {e.erfuellt} von {e.von}</b> üblichen Vorgaben erfüllt, in{" "}
      {e.fachLabel}.{" "}
      {/* Dieselbe Wendung wie im Check selbst („Eure grösste Lücke ist …"): „am häufigsten
          fehlt" wäre falsch, denn bei den Schwellen fehlt nichts, es liegt nur unter dem
          Üblichen. */}
      {e.luecke
        ? <>Die grösste Lücke: {e.luecke}. </>
        : <>Von dem, was dort belegt ist, erfüllt ihr alles. </>}
      Drinnen rechnet goVisor das je Vorgang statt als Zusammenfassung, mit euren echten
      Nachweisen. <a href="#check">Noch einmal ansehen</a>.
    </p>
  );
}
