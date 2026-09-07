"""Kennzahl 3 — Fingerabdruck der Vergabestelle.

Was verlangt DIESE Stelle fast immer, das andere selten verlangen? „Landeshauptstadt München:
Mindestumsatz in 11 von 11, marktweit 10 %." Wer das vor dem Öffnen der Unterlagen weiss,
legt den Nachweis bereit, statt ihn nachzureichen.
"""
from __future__ import annotations

import json
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DATEI = WURZEL / "web" / "data" / "stellenprofil.json"
EXPORT = (WURZEL / "scripts" / "export_stellenprofil.py").read_text(encoding="utf-8")
CORE = (WURZEL / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8")


def _daten() -> dict:
    return json.loads(DATEI.read_text(encoding="utf-8")) if DATEI.exists() else {}


def test_nur_seltene_arten_tragen_einen_fingerabdruck():
    """⚠ `einzureichendes_dokument` steht in 92 % aller Vorgänge. Dass eine Stelle es immer
    verlangt, ist keine Eigenschaft der Stelle, sondern des Verfahrens."""
    assert "MARKT_MAX = 0.25" in EXPORT
    for k, p in (_daten().get("markt") or {}).items():
        assert p < 25, f"{k}: {p} % marktweit — das ist Routine, kein Abdruck"


def test_mindestens_fuenf_verfahren():
    """⚠ Bei dreien ist „3 von 3" rechnerisch auffällig und trotzdem dünn. Die Übergabe nimmt
    drei; das wären 143 Abdrücke statt 54. Ein Muster aus drei Fällen sieht aus wie eines aus
    achtzehn."""
    assert "MIND_VERFAHREN = 5" in EXPORT
    for stelle, eintraege in (_daten().get("stellen") or {}).items():
        for e in eintraege:
            assert e["n"] >= 5, f"{stelle}: Abdruck aus {e['n']} Verfahren"
            assert e["k"] >= e["n"] * 0.8, f"{stelle}: {e['k']}/{e['n']} ist nicht „fast immer“"


def test_die_marktrate_steht_daneben():
    """⚠ „11 von 11" allein ist eine Zählung. Erst der Marktvergleich macht daraus eine
    Aussage — und er ist der Grund, warum die Zeile überhaupt dasteht."""
    block = CORE[CORE.index("function renderStellenprofil"):CORE.index("/* KENNZAHL 2")]
    assert "marktweit {p} %" in block
    for eintraege in (_daten().get("stellen") or {}).values():
        for e in eintraege:
            assert "markt" in e


def test_er_steht_beim_kaeufer():
    """Es ist eine Aussage über die STELLE, die auch für ihre nächste Ausschreibung gilt —
    nicht über diesen einen Vorgang."""
    assert "${renderStellenprofil(l)}" in CORE
    stelle = CORE.index("${renderStellenprofil(l)}")
    # ⚠ Weites Fenster: zwischen Überschrift und Abdruck steht der Beobachten-Schalter
    # (Aktivierung D). Ein zu enges Fenster prüft die Nachbarschaft, nicht die Zugehörigkeit.
    umfeld = CORE[stelle - 1200:stelle]
    assert "Ist der Käufer aktiv?" in umfeld


def test_hoechstens_drei_zeilen():
    api = (WURZEL / "web" / "app" / "api" / "lead-detail" / "route.ts").read_text(encoding="utf-8")
    assert "abdruck.slice(0, 3)" in api


def test_der_schluessel_ist_dokumentiert_schwach():
    """⚠ Der Käufername ist der Schlüssel, weil `lead_export` keine Entitäts-Kennung trägt.
    Zwei Schreibweisen derselben Stelle zählen getrennt. Das macht den Abdruck schwächer, nie
    falsch — und wer das nicht weiss, sucht später den Fehler an der falschen Stelle."""
    assert "KÄUFERNAME" in EXPORT.upper()
    assert "schwächer, nie falsch" in EXPORT


def test_gefiltert_wird_auf_derselben_zahl_die_ausgegeben_wird():
    """⚠ DIE GRENZE UND DIE ANZEIGE MUESSEN DIESELBE ZAHL MEINEN.

    Bis zum 2026-09-07 zog das SQL die Grenze am genauen Anteil (`v < ges * MARKT_MAX`) und
    die Ausgabe rundete danach auf ganze Prozent. Dazwischen liegt ein halber Prozentpunkt:
    eine Art mit 24,7 % kam durch und stand in der Oberflaeche als „marktweit 25 %" — neben
    einer Regel, die „unter 25 %" verspricht. `DE:referenz_anzahl` ist genau dort
    hineingewachsen; der Test darueber wurde rot, und die Zahl war nicht einmal falsch.

    ⚠ Und die Grenze gehoert nach Python: DuckDB rundet 24,5 auf, Python ab
    (round-half-to-even). Wer an zwei Stellen rundet, bekommt zwei Wahrheiten.

    Geprueft wird der ZUSAMMENHANG ueber den Syntaxbaum, nicht ein Wort: der Ausdruck, der
    gegen `MARKT_MAX` verglichen wird, muss derselbe sein, der nach `raus["markt"]` geht.
    """
    import ast
    baum = ast.parse(EXPORT)

    verglichen = {
        ast.unparse(k.left)
        for k in ast.walk(baum) if isinstance(k, ast.Compare)
        if any("MARKT_MAX" in ast.unparse(c) for c in k.comparators)
    }
    assert verglichen, "die Grenze MARKT_MAX wird nirgends in Python verglichen"

    def _geht_nach_markt(ziel) -> bool:
        """`raus["markt"][…] = …` — strukturell, nicht als Text.

        ⚠ Der erste Entwurf suchte '"markt"' im entparsten Ziel und fand nie etwas:
        `ast.unparse` schreibt einfache Anfuehrungszeichen. Ein Test, der auf die
        Schreibweise seiner eigenen Ausgabe hereinfaellt, ist derselbe Fehler eine Ebene
        hoeher."""
        while isinstance(ziel, ast.Subscript):
            k = ziel.slice
            if isinstance(k, ast.Constant) and k.value == "markt":
                return True
            ziel = ziel.value
        return False

    ausgegeben = {
        ast.unparse(z.value)
        for z in ast.walk(baum) if isinstance(z, ast.Assign)
        if any(_geht_nach_markt(t) for t in z.targets)
    }
    assert ausgegeben, 'nichts wird mehr nach raus["markt"] geschrieben'

    assert verglichen & ausgegeben, (
        f"gefiltert wird auf {sorted(verglichen)}, ausgegeben wird {sorted(ausgegeben)} — "
        f"zwei Zahlen fuer dieselbe Aussage. Genau daran ist der Filter am 2026-09-07 "
        f"an der Anzeige vorbeigelaufen.")

    # Und die Grenze darf nicht in ein SQL zurueckwandern: dort rundet DuckDB anders.
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.JoinedStr) and "MARKT_MAX" in ast.unparse(knoten):
            assert "select" not in ast.unparse(knoten).lower(), (
                "MARKT_MAX steht wieder in einem SQL — dann rundet DuckDB die Grenze und "
                "Python die Anzeige, und die beiden sind sich bei x,5 % nicht einig.")
