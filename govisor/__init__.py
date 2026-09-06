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
