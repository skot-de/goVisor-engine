"""Welche Länder die Pipeline BAUT — die eine Stelle.

⚠ **Abgrenzung zu `govisor/countries.py`.** Die führt das *Vokabular*: 31 Länder mit
Alpha-2, Alpha-3 und Name, damit Ingest und Parser die TED-Codes auflösen können. Sie sagt
NICHT, für welche Länder die Pipeline etwas baut — das waren bis zum 2026-09-04 eigene
`LAENDER`-Tupel in einem Dutzend Dateien, plus 21 Wertetabellen daneben. `countries.py`
kennt Bulgarien; gebaut wird es deshalb noch lange nicht.

⚠ **WARUM AUSDRÜCKLICH UND NICHT ABGELEITET.** Es wäre verlockend, `AKTIV` aus
`data/gold/*/lead_export.parquet` zu lesen — der Wächter tut genau das. Für Code, der
etwas BAUT, ist das aber zirkulär: Luxemburg hätte nie Gold bekommen, weil es kein Gold
hatte. Deshalb ist diese Liste eine **Erklärung** („dieses Land wollen wir bauen"), und die
abgeleitete Liste in `scripts/pruefe_laender_tabellen.py` ist die **Gegenprobe** („dieses
Land ist tatsächlich gebaut"). Laufen sie auseinander, sagt es
`tests/test_laender.py::test_erklaerung_und_bestand_stimmen_ueberein`.

⚠ **Was hier NICHT hineingehört** — drei Listen, die aussehen wie diese und etwas anderes
meinen. Sie stehen mit Begründung in `pruefe_laender_tabellen.BEWUSST_UNVOLLSTAENDIG`:

  · `web/lib/staaten.ts`            das öffentliche VERSPRECHEN. Hinkt absichtlich hinterher.
  · `analyze_docs.LAND_PRIO`        eine REIHENFOLGE, keine Zugehörigkeit.
  · `daily_leads.sh:_IXLAENDER`     welche Länder DOKUMENTE haben (AT/CH: 0 %).

⚠ **Und was eine Liste grundsätzlich nicht kann:** sie erfindet `DE=5, AT=4` nicht. Die
Wertetabellen (`gold._REGION_STELLEN`, `_PLZ_STELLEN`, `locales.LOCALES` …) tragen
Länderwissen, das jemand messen muss. Diese Liste macht ein Fehlen nur LAUT — dafür ist der
Wächter da.
"""
from __future__ import annotations

# Reihenfolge = Anzeige- und Bearbeitungsreihenfolge (Bestand absteigend).
AKTIV: tuple[str, ...] = ("DE", "AT", "CH", "LU")

# Angefangen und liegengeblieben — MIT Begründung, damit „fehlt" nicht wie „vergessen"
# aussieht. Wer eines davon aufnimmt, verschiebt es nach AKTIV und arbeitet
# `docs/laender/15-eintragungsliste.md` ab.
#
# ⚠ DIESER EINTRAG IST KEINE FORMALIE. Beide standen hier, während ihre Gold-Tabellen
# trotzdem jede Nacht neu entstanden — `build_vorgaenge` nahm seine Länder aus SILBER
# statt aus dieser Liste. Ein Land aus `AKTIV` zu nehmen genügt also nicht, solange
# irgendein Schritt den Bestand fragt statt die Entscheidung.
UNVOLLSTAENDIG: dict[str, str] = {
    "PL": "Am 2026-09-07 zurückgebaut: Gold gelöscht, Silber (1,9 GB, 326.485 Sätze) bleibt. "
          "Vorher war es eine Baustelle, die wie ein Land aussah — `build_vorgaenge` legte "
          "aus Silber heraus Gold-Tabellen an, und damit galt PL in Sonden, Exporten und "
          "der Vorgangsakte als aufgenommen. Wer es aufnehmen will, fängt bei der "
          "Gold-Kette an; die Rohdaten liegen bereit.",
    "EU": "Am 2026-09-07 zurückgebaut, gleiche Geschichte. Kein Land, sondern die "
          "Sammelablage für Bekanntmachungen ohne eindeutiges Land — 135 Stück. Sie hier "
          "als Land zu führen hat mehr Verwirrung gestiftet als Nutzen gebracht.",
}


def ist_aktiv(code: str) -> bool:
    return (code or "").upper() in AKTIV
