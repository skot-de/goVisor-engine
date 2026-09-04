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
UNVOLLSTAENDIG: dict[str, str] = {
    "PL": "326.485 Sätze in Silber, kein Gold. KEINE Entscheidung, sondern eine Baustelle.",
    "EU": "Sammelablage für Bekanntmachungen ohne eindeutiges Land — kein Land, sondern ein Rest.",
}


def ist_aktiv(code: str) -> bool:
    return (code or "").upper() in AKTIV
