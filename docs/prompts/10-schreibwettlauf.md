# Schreibwettlauf beim Profilspeichern

## Was war
Im Onboarding schrieben `saveProfile` und `uebernimmCheck` gleichzeitig auf dasselbe
Profil. Der spaetere Schreiber gewann, die Angaben des Eignungs-Checks gingen
gelegentlich verloren. Sichtbar wurde es als „0 von 7.013".

## Was bereits behoben ist (2026-09-17)
`web/app/onboarding/page.tsx`: die Schreibvorgaenge sind gereiht statt nebenlaeufig,
`fertigstellen()` ist `async`.

    await saveProfile(profile).catch(() => {});
    if (checkAngaben) {
      await uebernimmCheck(checkAngaben).catch(() => {});
      checkVerwerfen();
    }

## Was offen ist
Die Frage, die zu diesem Prompt gefuehrt hat, war: gibt es weitere Stellen, an denen
zwei Vorgaenge gleichzeitig auf dasselbe Profil schreiben? Sie wurde nicht
systematisch beantwortet, sondern nur fuer diese eine Stelle.

## Aufgabe
1. Alle Schreiber auf das Profil auflisten. Bekannte Einstiege:
   `web/app/settings/page.tsx`, `web/app/onboarding/page.tsx`,
   `web/components/explorer/Trefferguete.tsx`, dazu `demo_konto.py` von aussen.
2. Fuer jeden pruefen: kann er zeitlich mit einem anderen zusammenfallen?
3. Wo ja: reihen, oder feldweise zusammenfuehren statt das ganze Profil zu ersetzen.

Ein Lese-Aendere-Schreibe-Zyklus auf ein ganzes Dokument ist die Fehlerklasse. Sie
verschwindet nicht dadurch, dass ein Vorkommen behoben ist.

## Falle
`catch(() => {})` verschluckt Fehler. Das ist hier bewusst, damit ein misslungener
Teilschritt den Trichter nicht abbricht. Es bedeutet aber, dass ein Schreibfehler
still bleibt. Mindestens protokollieren.

## Abnahme
- Eine Liste aller Schreiber im Commit, mit Urteil je Stelle.
- Ein Test je gefundener Kollisionsstelle, der ohne die Reihung rot wird.
