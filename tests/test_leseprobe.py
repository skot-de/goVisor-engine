"""Die Leseprobe ist das Erste, was ein Fremder von goVisor liest.

⚠ Warum es diese Datei gibt: beim Bauen am 2026-09-01 sind drei Dinge auf die öffentliche
Seite gerutscht, die dort nichts zu suchen haben — ein falsches Bundesland, ein beschädigter
Name und ein geschätzter Wert, der wie ein belegter aussah. Keines davon war ein Denkfehler;
alle drei kamen aus Daten, die anderswo unauffällig sind.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DATEI = WURZEL / "web" / "data" / "landing.json"
QUELLE = (WURZEL / "scripts" / "export_landing.py").read_text(encoding="utf-8")


def _probe() -> dict:
    return json.loads(DATEI.read_text(encoding="utf-8")).get("leseprobe", {})


def test_es_gibt_eine_leseprobe():
    p = _probe()
    assert p, "keine Leseprobe in landing.json — der Export hat sie nicht gebaut"
    assert len(p) >= 5, f"nur {len(p)} Fachgebiete"


def test_keine_abgelaufene_frist():
    """⚠ Die Datei wird nachts gebaut und trägt Vorrat. Ein Vorgang, auf den sich niemand
    mehr bewerben kann, ist auf der Startseite schlimmer als gar keiner."""
    heute = date.today()
    for fach, eintraege in _probe().items():
        for x in eintraege:
            frist = datetime.strptime(x["f"], "%d.%m.%Y").date()
            assert frist >= heute, f"{fach}: Frist {x['f']} ist vorbei"


def test_ein_wert_ohne_herkunft_wird_nicht_gezeigt():
    """⚠ Unter den offenen Vergaben ist derzeit KEIN Auftragswert belegt — alles sind
    CPV-Median-Schätzungen, „383.180 €" allein 2.752-mal. Ohne `vs` daneben wäre das eine
    erfundene Zahl mit zwei Nachkommastellen Glaubwürdigkeit."""
    for fach, eintraege in _probe().items():
        for x in eintraege:
            if x.get("v"):
                assert x.get("vs") in ("echt", "schaetz"), f"{fach}: Wert ohne Herkunft"


def test_der_bonn_klumpen_bleibt_draussen():
    """⚠ 391 DE-Leads tragen `DEA22` (Bonn), obwohl der Käufer woanders sitzt — und wir
    führen den Wert als „amtlich". Solange das in der Pipeline nicht repariert ist, hält
    diese Tür zu. Sichtbar geworden an „Lutherstadt Wittenberg | Nordrhein-Westfalen"."""
    assert 'nuts == "DEA22"' in QUELLE
    assert '"Bonn" not in kaeufer' in QUELLE


def test_die_frist_kommt_aus_dem_richtigen_feld():
    """⚠ Die erste Fassung filterte auf `endTage` — das ist `days_to_expiry`, also das
    VERTRAGSENDE fürs Auslauf-Radar, nicht die Angebotsfrist. Sie hätte auslaufende Verträge
    als „jetzt bewerben" ausgegeben. Aufgefallen nur daran, dass jeder gewählte Vorgang die
    Frist „heute" trug."""
    block = QUELLE[QUELLE.index("def leseprobe("):QUELLE.index("def eignungs_check(")]
    assert 'frist.get("tage")' in block
    # ⚠ Auf die BENUTZUNG prüfen, nicht auf das Wort: die Warnung im Docstring nennt
    # `endTage` ja gerade, um davor zu warnen. Ein Test, der Text statt Code liest, ist in
    # diesem Projekt schon dreimal an der eigenen Begründung hängengeblieben.
    assert 'l.get("endTage")' not in block, "filtert wieder auf das Vertragsende"


def test_breite_statt_zufall():
    """Höchstens zwei je Region und einer je Fristtag. Ohne die Bremsen stand fünfmal
    dieselbe Grossstadt untereinander, und alle fünf trugen dasselbe Datum."""
    for fach, eintraege in _probe().items():
        raeume: dict[str, int] = {}
        tage: dict[str, int] = {}
        for x in eintraege:
            raum = x.get("r") or x.get("l") or "?"
            raeume[raum] = raeume.get(raum, 0) + 1
            tage[x["f"]] = tage.get(x["f"], 0) + 1
        assert max(raeume.values()) <= 2, f"{fach}: {max(raeume, key=raeume.get)} kommt zu oft"
        assert max(tage.values()) <= 1, f"{fach}: mehrere Vorgänge am selben Fristtag"


def test_kein_kaeufername_traegt_seine_anschrift():
    """⚠ Das Feld heisst `buyerShort` und ist es nicht. Gemessen am 2026-09-01: „Gemeinde
    Motten, Fuldaer Str. 11, 97786 Motten, Tel.: +49 974891910, Fax: +49 97" — bei 80
    Zeichen gekappt, mitten in der Faxnummer. Im Explorer faellt das nicht auf, auf der
    ersten Seite, die ein Fremder liest, schon."""
    for fach, eintraege in _probe().items():
        for x in eintraege:
            for teil in x["k"].split(", ")[1:]:
                assert not re.search(r"\d|Tel\.|Fax|E-Mail", teil, re.I), \
                    f"{fach}: Anschrift im Namen — {x['k']}"


def test_nur_oeffentliche_felder():
    """Was hier steht, ist ohnehin in jeder Bekanntmachung öffentlich. Bewertung, Passung,
    Strategie und Dokumentanalyse sind die Arbeit, für die man sich anmeldet — sie dürfen
    nicht aus Versehen mitwandern."""
    erlaubt = {"t", "k", "r", "l", "f", "d", "v", "vs"}
    for fach, eintraege in _probe().items():
        for x in eintraege:
            assert set(x) <= erlaubt, f"{fach}: unerwartete Felder {set(x) - erlaubt}"


def test_die_seite_wirft_abgelaufenes_nochmal_raus():
    """Zwei Wälle: der Export nimmt nur laufende Fristen auf, und die Seite prüft beim
    Anzeigen erneut. Fällt der Tageslauf aus, trägt der zweite Wall."""
    tsx = (WURZEL / "web" / "components" / "EignungsCheck.tsx").read_text(encoding="utf-8")
    assert "alsDatum" in tsx and "heute" in tsx
    # ⚠ Deutsche Schreibweise: `new Date("08.09.2026")` ist ungültig, und dann wäre JEDER
    # Vorgang abgelaufen — die Leseprobe verschwände lautlos.
    assert re.search(r"\(\\d\{2\}\)\\\.", tsx) or "\\d{2})\\." in tsx
