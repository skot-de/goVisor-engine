# Weiterentwicklung

Was goVisor werden koennte, getrennt von dem, was es ist. Alles hier ist **Vorschlag oder
Recherche**, nichts davon ist gebaut, sofern es nicht ausdruecklich dabeisteht.

⚠ **Warum die Trennung eigene Ordner braucht.** In diesem Projekt sind schon mehrfach
Momentaufnahmen als Auskunft gelesen worden (s. den Kopf von `CLAUDE.md`). Ein Vorschlag, der
neben einer Messung liegt, wird irgendwann wie eine Messung zitiert. Deshalb: hier steht das
Kuenftige, in `docs/` daneben das Geltende, in `docs/laender/` das Geprueft-Geltende.

## Was hier liegt

| Blatt | Art | Stand | Kurz |
|---|---|---|---|
| [angebotsmodul-bauplan.md](angebotsmodul-bauplan.md) | Bauplan | 2026-09-15 | Die Verfahrensakte als Anker eines Angebotsmoduls. Fuenf Stufen, jede mit Abbruchbedingung. **Zuarbeit `build_anlaufvergleich.py` ist gebaut.** |
| [mappe-an-der-kette.md](mappe-an-der-kette.md) | Konzept | 2026-09-15 | Die Angebotsmappe haengt an der Kette statt am Kalender. Drei Zustaende, davon einer (Vorwarnung) ohne Wettbewerbsentsprechung. |
| [betriebskosten.md](betriebskosten.md) | Rechnung | 2026-09-15 | Was der Betrieb kostet, gemessen. Listenpreise am 11.09.2026 nachgeschlagen. |
| [preisstufen-vorschlag.md](preisstufen-vorschlag.md) | Vorschlag | 2026-09-15 | Drei Pakete, geschnitten nach Tiefe der Antwort. ⚠ Die Betraege sind **nicht** gemessen. |
| [kurzprofil-partner.md](kurzprofil-partner.md) | Unterlage | 2026-09-15 | Kurzprofil fuer Partner- und Investorengespraeche. |

## Regeln fuer dieses Verzeichnis

1. **Jede Zahl mit Datum.** Gleiche Regel wie in der Laender-Bibel. Ohne Datum ist eine Zahl
   hier wertlos, weil der Bestand taeglich waechst.
2. **Gemessen und geschaetzt nie ohne Kennzeichnung mischen.** Wo etwas hergeleitet ist, steht
   „Vorschlag" oder „Annahme" daneben. Die Paketpreise sind das Musterbeispiel: der
   Marktkorridor ist belegt, die drei Betraege darin sind gesetzt.
3. **Was gebaut wird, wandert hinaus.** Sobald ein Vorhaben umgesetzt ist, gehoert die
   Begruendung nach `docs/entscheidungen-und-kontext.md` und die Mechanik in den Code. Ein
   Bauplan, der eine gebaute Sache beschreibt, veraltet still.
4. **Gerenderte Blaetter sind Kopien, nicht Quellen.** Die Artifact-Adressen stehen in den
   Dateien; die Datei gewinnt bei jeder Abweichung.
