"""Aktivierung C: die Frage nach abgelaufener Frist, und dass die Antwort ankommt.

⚠ Zwei Dinge waren vorher falsch, und das zweite ist das schwerere. Erstens stand an einem
abgelaufenen Vorgang weiter „Ich bewerbe mich →". Zweitens schrieben die Cockpit-Handler
NIRGENDWOHIN: der Kommentar versprach „#11-Meldung serverseitig", `reportOutcome` wurde von
dort aber nie gerufen. Die Moat-Tabelle gab es seit Ticket #11, angeschlossen war sie nicht.
"""
from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
CK = (WEB / "components" / "explorer" / "Cockpit.tsx").read_text(encoding="utf-8")
SHELL = (WEB / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8")
OUT = (WEB / "lib" / "supabase" / "outcomes.ts").read_text(encoding="utf-8")


def test_die_frage_haengt_an_den_verwaisten_merkzetteln():
    """⚠ MEIN ERSTER VERSUCH WAR TOTER CODE. Die Bedingung lautete `frist.tage < 0` — und
    `frist.tage` wird im Frontend NIE negativ (gemessen 2026-09-01 über 10.536 Leads mit
    Frist: Minimum 0). Der Grund steht in `export_web_leads.py`: offene Ausschreibungen mit
    abgelaufener echter Frist fliegen aus dem Export, „nicht mehr biet-bar".

    Damit verschwand ein gemerkter Vorgang am Tag nach der Frist spurlos, und genau dann
    stellt sich die wertvollste Frage. Sie hängt jetzt an der Merkliste, nicht am Lead."""
    assert "verwaist" in CK and "Habt ihr mitgeboten?" in CK
    stelle = CK[CK.index("verwaist.map("):CK.index("{beob.length ?")]
    assert "Habt ihr mitgeboten?" in stelle


def test_kein_toter_zweig_auf_negative_tage():
    """Eine Bedingung, die nie wahr wird, sieht aus wie eine Funktion und ist keine."""
    assert "frist?.tage ?? 0) < 0" not in CK


def test_die_merkliste_behaelt_ihren_inhalt():
    """⚠ Ohne Titel und Käufer bleibt nach dem Ablauf eine Zeile ohne Inhalt, und die Frage
    lässt sich nicht stellen. `user_outcomes` macht es seit Ticket #11 genauso."""
    wl = (WEB / "lib" / "supabase" / "watchlist.ts").read_text(encoding="utf-8")
    assert "titel: ctx?.titel" in wl and "buyer_name: ctx?.buyer" in wl
    assert "export async function loadWatchlist" in wl
    assert "syncWatchlist(id, !!l.merk, {" in SHELL, "der Kontext wird nicht mitgegeben"


def test_der_grund_kommt_erst_nach_nein():
    """Regel 3 des Papiers: ein Klick, kein Formular. Sechs Gründe sofort anzuzeigen wäre
    genau das Formular."""
    assert "grundFuer" in CK
    # Der Auslöser sitzt an der verwaisten Merkzeile, nicht am Lead — deshalb `v.lead_id`.
    assert "setGrundFuer(v.lead_id)" in CK
    assert "setGrundFuer(null)" in CK, "nach der Antwort muss die Auswahl zugehen"


def test_die_gruende_sind_die_der_tabelle():
    """⚠ Kein siebter Grund. Was hier steht, muss `dismiss_reason` entgegennehmen können,
    sonst sammeln wir Werte, die niemand auswerten kann."""
    erlaubt = set(re.findall(r'"(\w+)"', re.search(r"DismissReason = ([^;]+);", OUT).group(1)))
    gefragt = set(re.findall(r'\["(\w+)",', CK[CK.index("const GRUENDE"):CK.index("];", CK.index("const GRUENDE"))]))
    assert gefragt <= erlaubt, f"unbekannte Gründe: {gefragt - erlaubt}"


def test_die_antwort_wird_wirklich_geschrieben():
    """⚠ Das eigentliche Loch. Ohne diesen Aufruf ist die ganze Aktivierung eine Geste."""
    assert "ckMitgeboten" in SHELL
    stelle = SHELL[SHELL.index("async function ckMitgeboten"):]
    stelle = stelle[:stelle.index("\n  }")]
    assert "reportOutcome" in stelle


def test_der_lokale_stand_folgt_dem_fernen():
    """⚠ Scheitert das Schreiben, darf die Oberfläche nicht so tun, als sei die Antwort
    angekommen. Eine Meldung, die niemand hat, ist schlimmer als eine, die fehlt."""
    stelle = SHELL[SHELL.index("async function ckMitgeboten"):]
    stelle = stelle[:stelle.index("\n  }")]
    assert "if (!r.ok) return;" in stelle
    assert stelle.index("reportOutcome") < stelle.index("if (!r.ok)")
