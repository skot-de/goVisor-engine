"""subreport: nur endgültige Ergebnisse sperren eine Vergabe für immer.

Bis zum 2026-09-22 galt jeder Satz der Dateiliste als erfasst, auch „leer" und „fehler",
und die Sperrfrist der Warteschlange kam nie zum Zug. 7 von 8 geprüften „0 Dateien"-Fällen
trugen beim zweiten Besuch eine Liste.
"""
import datetime as dt

from govisor import docfetch_queue as q
from govisor.subreport import erledigt


def _satz(lead_id, status):
    return {"lead_id": lead_id, "status": status}


def test_endgueltige_ergebnisse_sind_erledigt():
    alt = [_satz("a", "nur_liste"), _satz("b", "abgelaufen"), _satz("c", "aufgehoben"),
           _satz("d", "gated"), _satz("e", "passwortgeschuetzt")]
    assert erledigt(alt) == {"a", "b", "c", "d", "e"}


def test_leer_und_fehler_kommen_wieder():
    alt = [_satz("x", "leer"), _satz("y", "fehler"), _satz("z", None)]
    assert erledigt(alt) == set()


def test_die_warteschlange_gibt_leer_nach_der_sperrfrist_frei():
    """Ohne diesen Teil hiesse „nicht erledigt" nur, dass der Vorgang JEDE Nacht läuft."""
    heute = dt.date(2026, 9, 22)
    frisch = {"status": "leer", "wann": heute - dt.timedelta(days=1)}
    alt = {"status": "leer", "wann": heute - dt.timedelta(days=q.SPERRE_TAGE)}
    assert q.ueberspringen(frisch, heute=heute)
    assert q.ueberspringen(alt, heute=heute) is None
