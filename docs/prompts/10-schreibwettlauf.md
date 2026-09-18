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


## Nachtrag 2026-09-18 — der Abgleich mit dem Originalauftrag

⚠ **Der Auftrag verlangte einen echten Nebenlaeufigkeitstest, ich hatte nur strukturell
bewiesen.** „Zwei Schreibvorgaenge absichtlich ueberlappen lassen und belegen, dass keiner
den anderen verliert" — mein Waechter prueft „genau ein Schreibweg" und „minimaler Patch".
Beides richtig, beides kein Beleg fuer Verhalten unter Last.

Nachgeholt mit `scripts/pruefe_profil_nebenlaeufig.py`, je 12 Runden gegen die echte
Datenbank, zwei gleichzeitige Schreiber auf VERSCHIEDENE Felder:

    alter Weg (lesen → aendern → ganzen Blob schreiben)    0 von 12 vollstaendig
    merge_profile (atomar)                                12 von 12 vollstaendig

Der alte Weg verliert in JEDER Runde. Das ist die Reproduktion des Fehlers vom 2026-09-17.

### Die drei Wege, wie der Auftrag sie stellt — mit Begruendung der Wahl

**(a) Atomares Update in Postgres — GEWAEHLT.** `merge_profile(jsonb)` mischt in EINER
Anweisung; es gibt kein Fenster mehr. Kein Versionszaehler noetig, keine Wiederholung,
keine zusaetzliche Spalte.

**(b) Optimistische Sperre — verworfen.** Sie braucht eine Wiederholungsschleife im Client
und loest ein Problem, das (a) gar nicht erst entstehen laesst. Bei zwei Schreibern auf
VERSCHIEDENE Felder waere jede Kollision ein unnoetiger zweiter Umlauf.

**(c) Die Felder in Spalten heben — nicht moeglich, gemessen.** Der Auftrag vermutet, der
Blob sei „schlicht ueberfluessig", weil die betroffenen Felder bereits Spalten haben. Das
gilt fuer NEUN Felder:

    firma↔company_name · regions↔regions · regionLabels↔region_labels · volMin↔vol_min
    volMax↔vol_max · branche↔branche · cpvFields↔cpv_fields · cpvLabels↔cpv_labels
    identityId↔identity_id

Aber **21 weitere Felder gibt es nur im Blob**: attributes, branchen, buergschaft,
capabilities, certificates, checkAngaben, confirmedEntities, cpvFields6, cpvWins,
entityConfidence, exclusions, history, maxAlleine, nachbarFields, quelle, rahmen,
references, regionTyp und weitere. Den Blob aufzuloesen hiesse, 21 Spalten anzulegen,
darunter verschachtelte Objekte und Listen (`references`, `certificates`, `history`,
`checkAngaben`). Der Blob ist nicht ueberfluessig — die DOPPELUNG der neun war das
Problem, und die ist behoben: alle Schreiber gehen durch `saveProfile`, das beide Formen
in einem Zug setzt.

### `tests/test_profil_wettlauf.py` — ersetzt, nicht geloescht

Der Auftrag sieht das voraus. Der Test prueft die Reihenfolge im Onboarding; gegen LOST
UPDATES braucht es ihn nicht mehr. Er bewacht aber eine zweite Eigenschaft, die der Merge
NICHT herstellt: ein Schreibvorgang ohne `await` kann schlicht nicht ankommen, wenn die
Seite vorher weiterschaltet. Wer gar nicht schreibt, schreibt auch atomar nicht. Die neue
Begruendung steht in seinem Docstring.
