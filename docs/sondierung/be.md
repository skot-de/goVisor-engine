# Sondierung Belgien

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.** Keine Zeile in `data/gold` oder `data/silver`.
> ⚠ **UND NICHT ABGESCHLOSSEN** — siehe § 3.

**Stand 2026-09-03.** Landschaft aus dem TED-Monatspaket 2026-06.

---

## 1. Mengengerüst — zwei Systeme, sonst nichts

1.309 Ausschreibungen im Juni. Belgien ist das am stärksten konzentrierte Land der
bisherigen Sondierung:

| Portal | Bezüge | Anteil | Linktiefe |
|---|---:|---:|---:|
| `publicprocurement.be` (BOSA, föderal) | 1.226 | **73 %** | 96 % |
| `cloud.3p.eu` | 433 | 26 % | **100 %** |
| `ec.europa.eu` + `webgate.ec.europa.eu` | 135 | — | — |
| Rest (Bahn, Elia, Fluxys, Häfen …) | ~20 | 1 % | |

⚠ Die 135 Bezüge auf `ec.europa.eu` sind **EU-Institutionen**, die von Brüssel aus unter
BE veröffentlichen — kein belgisches Portal. Wer Belgien zählt, zählt sie mit, obwohl sie
nicht dazugehören.

## 2. Was geprüft ist

**Keine robots.txt auf beiden Hauptseiten.** `publicprocurement.be/robots.txt` liefert die
Anwendungshülle (weiches 404), `cloud.3p.eu/robots.txt` ein echtes 404. Nichts untersagt.

**Die Dokumente liegen öffentlich.** Die Vergabeseite der föderalen Plattform zeigt ohne
Anmeldung Titel, Sprachen, Version und Veröffentlichungsdatum jedes Dokuments, dazu einen
Knopf „Alle Dokumente herunterladen".

**Und es gibt eine saubere REST-Oberfläche:**
```
/api/dos/publication-workspaces/<uuid>                → der Vorgang
/api/dos/publication-workspaces/<uuid>/documents      → die Dokumentenliste
/api/dos/publication-workspaces/<uuid>/archive        → alle Dateien als Archiv
```

## 3. ⚠ Warum Belgien offen bleibt

**Die API antwortet seit dem Nachmittag des 2026-09-03 durchgängig mit HTTP 500** — für
zwei verschiedene Vorgänge, für alle drei Endpunkte, mit und ohne Sitzungskeks, und
**auch aus dem Browser heraus**, der wenige Minuten zuvor noch 200 bekommen hatte.

```
{"details":"Error id 3f59ed8c-83fa-4505-8de2-85e4c8ce04c0-353","stack":""}
```

Das ist **keine Schranke, sondern ein Ausfall.** Ein Urteil wäre hier falsch, in beide
Richtungen: „gesperrt" wäre unwahr, „offen" unbelegt.

**Alle Anzeichen sprechen für offen** — keine robots-Sperre, öffentlich sichtbare
Dokumentenliste, ein Sammel-Download-Knopf ohne Anmeldung, eine ordentliche REST-API. Aber
belegt ist es nicht, und in dieser Sondierung zählt nur, was heruntergeladen wurde.

**Nachzuholen**, sobald die Plattform wieder antwortet.

## 4. Ungeprüft

`cloud.3p.eu` (26 %) leitet auf eine Länderauswahl mit Cookie-Banner. Die Länderwahl wäre
ein gewöhnlicher Klick, die Cookie-Zustimmung ist eine Entscheidung, die ich nicht von mir
aus treffe. Die Adressen sind zu 100 % tief (`/Downloads/1/1649/6U/2026`), das Portal
also grundsätzlich aussichtsreich.

## 5. Stand nach sieben Ländern

| Land | Anteil EU | bestätigt skriptfähig |
|---|---:|---|
| DE | 21,2 % | 32 % |
| FR | 15,4 % | **0 %** |
| PL | 14,6 % | 19 % / 35 % |
| ES | 6,7 % | 5 % |
| IT | 4,9 % | 4 % |
| CZ | 4,4 % | **28 %** |
| **BE** | **3,6 %** | **offen (Ausfall)** |

Zusammen **70,8 %** aller EU-Ausschreibungen.
