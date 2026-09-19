"""goVisor data engine."""

__version__ = "0.1.0"

# ── openpyxls Darstellungs-Warnungen ────────────────────────────────────────────────────
#
# ⚠ WARUM HIER UND NICHT AN DEN VIER LADEAUFRUFEN. Der erste Versuch legte je einen
# `catch_warnings`-Block um `load_workbook` — und senkte den Laerm gemessen von 6 auf 4
# Zeilen, also fast gar nicht. Der Grund: `read_only=True` liest VERZOEGERT. `load_workbook`
# kehrt sofort zurueck, die Blaetter werden erst beim Iterieren geparst, und genau dort
# entstehen die Meldungen — laengst ausserhalb des Blocks.
#
# ⚠ UND KEIN PAUSCHALES `filterwarnings("ignore")`. Der Filter zielt auf das MODUL: nur was
# aus `openpyxl.*` kommt, wird stumm. Warnungen aus unserem eigenen Code gehen weiter durch,
# und Fehler werfen ohnehin.
#
# Gemessen im Nachtlauf 2026-09-06: 196 Zeilen, davon 189-mal „Print area cannot be set to
# Defined name", dazu Slicer, WMF-Bilder, Conditional-Formatting-Erweiterungen. Alle
# betreffen AUSSEHEN. Wir laden mit `data_only=True` und lesen Zellwerte — keine dieser
# Meldungen kann ein Ergebnis veraendern.
import warnings as _warnings

# ⚠ `module` wird als Regex mit `match` gegen den Modulnamen geprueft, also als PRAEFIX.
# „openpyxl" trifft damit auch `openpyxl.worksheet._reader`; ein `openpyxl\..*` haette
# das Paket selbst NICHT getroffen. `scripts/extract_criteria.py` fuehrt seit jeher
# dieselbe Zeile — sie war der Hinweis, dass die Praefix-Form die richtige ist.
_warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


# ── pypdfs Reparatur-Meldungen ──────────────────────────────────────────────────────────
#
# ⚠ GEMESSEN AM 2026-09-19, und die Zahl ist der ganze Grund: `govisor-analyse.log` war
# 166 MB gross, und **95,3 % davon waren vier pypdf-Saetze**.
#
#     Ignoring wrong pointing object      1.945.923 Zeilen
#     Unexpected escaped string           1.565.143
#     Multiple definitions in dictionary    204.401
#     incorrect startxref                     4.879
#     ────────────────────────────────────────────
#     von insgesamt                       3.903.758
#
# Das ist nicht nur Platz. Es hat an diesem Tag eine Diagnose aktiv behindert: die letzte
# echte Fortschrittszeile des Arbeiters lag auf Position 3.903.111 von 3.903.758 — die
# Erklaerung fuer einen zwoelfstuendigen Leerlauf stand hinter 1,5 Millionen Zeilen
# Rauschen. Ein Log, in dem man den Befund nicht mehr findet, ist kein Log.
#
# ⚠ WARUM `logging` UND NICHT `warnings` WIE BEI OPENPYXL DARUEBER. pypdf schickt diese
# Meldungen durch `pypdf._utils.logger_warning()`, nicht durch `warnings.warn()`. Ein
# `filterwarnings` haette hier nichts getan — die beiden Mechanismen sind getrennt.
#
# ⚠ UND WARUM DAS NICHTS VERDECKT. pypdf trennt seine drei Stufen ausdruecklich: eine
# Ausnahme heisst „Daten verloren", `warnings.warn` heisst „der Aufrufer sollte etwas
# aendern", und `logger_warning` heisst „ein Sonderfall, den die Bibliothek SELBST
# behandelt hat". Genau diese dritte Stufe wird hier stumm. ERROR und CRITICAL gehen
# weiter durch, und ein PDF, das sich nicht lesen laesst, wirft ohnehin.
import logging as _logging

_logging.getLogger("pypdf").setLevel(_logging.ERROR)
