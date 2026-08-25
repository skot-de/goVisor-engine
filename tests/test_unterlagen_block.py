"""Der Unterlagen-Block: was die Quelle anbietet ≠ was wir gelesen haben.

⚠ Bis zum 2026-08-25 gab es nur die erste Frage. Gemessen über 18.594 Leads mit laufender
Frist: **5.899 deutsche Leads hatten bei uns den Volltext, und keiner sagte es dem
Nutzer** — 744 zeigten „unknown", 5.155 gar keinen Block, weil weder `documents_url` noch
`source_url` gesetzt war. Umgekehrt zeigten 166 Schweizer Leads „offen", obwohl nichts
abgerufen worden war.

`docs/laender/03-input-dokumente.md` verlangt dafür ausdrücklich ein `gelesen`-Feld:
„Eine abgeleitete Aussage darf nicht aussehen wie eine gelesene."
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _hole_funktion(name: str):
    """Eine einzelne Funktion aus einem Skript holen, ohne das Skript auszufuehren.

    ⚠ Ueber den SYNTAXBAUM, nicht ueber Textgrenzen. Der erste Versuch schnitt von
    `def _unterlagen(` bis zum naechsten Doppel-Leerzeile-Block und griff dabei ueber die
    Funktion hinaus — der Ausschnitt enthielt fremden Code und scheiterte an `_db`.
    `export_web_leads.py` fuehrt beim Import DuckDB-Abfragen aus; ein normaler Import
    kommt hier also nicht in Frage.
    """
    import ast as _ast
    baum = _ast.parse((ROOT / "scripts" / "export_web_leads.py").read_text(encoding="utf-8"))
    knoten = next(k for k in baum.body
                  if isinstance(k, _ast.FunctionDef) and k.name == name)
    raum: dict = {}
    exec(compile(_ast.Module(body=[knoten], type_ignores=[]), "<extrakt>", "exec"), raum)
    return raum[name]


def _unterlagen(felder: dict, volltext: set):
    return _hole_funktion("_unterlagen")(lambda k: felder.get(k), volltext)


def test_volltext_ohne_link_ergibt_trotzdem_einen_block():
    """⚠ Der grösste Einzelfall: 5.155 Leads mit Text und ganz ohne Block."""
    b = _unterlagen({"lead_id": "N1"}, {"N1"})
    assert b is not None and b["gelesen"] is True
    assert b["url"] is None and b["access"] == "unknown"


def test_ohne_link_und_ohne_volltext_gibt_es_nichts_zu_sagen():
    assert _unterlagen({"lead_id": "N1"}, set()) is None


def test_gelesen_ist_unabhaengig_von_access():
    """Die Schweizer Lage: die Quelle sagt „offen", wir haben trotzdem nichts."""
    b = _unterlagen({"lead_id": "N1", "documents_url": "https://simap.ch/x",
                     "has_documents": True}, set())
    assert b["access"] == "offen" and b["gelesen"] is False


def test_deutscher_lead_mit_volltext_sagt_es_jetzt():
    """Die deutsche Lage: die Quelle sagt nichts, wir haben den Text."""
    b = _unterlagen({"lead_id": "N1",
                     "documents_url": "https://evergabe-online.de/x"}, {"N1"})
    assert b["access"] == "unknown", "über die Quelle wissen wir weiterhin nichts"
    assert b["gelesen"] is True, "über uns schon"


def test_kostenpflichtig_und_auf_anfrage_bleiben_erhalten():
    bez = _unterlagen({"lead_id": "N1", "documents_url": "u", "has_documents": True,
                       "documents_paid": True}, set())
    assert bez["access"] == "kostenpflichtig"
    anf = _unterlagen({"lead_id": "N1", "documents_url": "u",
                       "documents_source": "on_request"}, set())
    assert anf["access"] == "auf_anfrage" and anf["wie"] == "on_request"


def test_nur_portallink_wird_als_portal_gefuehrt():
    b = _unterlagen({"lead_id": "N1", "source_url": "https://portal/x"}, {"N1"})
    assert b["source"] == "portal" and b["gelesen"] is True
