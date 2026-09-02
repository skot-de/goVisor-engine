"""Verlässlichkeit je Auswertung (Kennzahl 10) — die einzige, die uns misst statt die Vergabe.

Jede Aussage des Modells muss sich mit einem Zitat aus dem Dokument belegen lassen; was das
nicht schafft, wird verworfen. Die Zahl stand längst im Haftungshinweis. Was fehlte, war ihre
Bedeutung — und die ist nicht „unzuverlässig", sondern „lückenhaft".
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
CORE = (WURZEL / "web" / "lib" / "explorerCore.js").read_text(encoding="utf-8")
PARQUET = WURZEL / "data" / "gold" / "DE" / "doc_analysis.parquet"


def _block(name: str) -> str:
    rest = CORE[CORE.index(f"function {name}("):]
    return rest[:rest.index("\n}")]


def _schwelle() -> float:
    return float(re.search(r"const VERWURF_HOCH = ([\d.]+)", CORE).group(1))


# ── die Aussage ─────────────────────────────────────────────────────────────────────────

def test_sagt_lueckenhaft_und_nicht_falsch():
    """⚠ Angezeigt wird nur, was die Belegprüfung BESTANDEN hat — was sie nicht bestand, ist
    gar nicht erst da. „Diese Analyse ist womöglich falsch" wäre deshalb die falsche Warnung
    und würde Vertrauen kosten, das die Daten nicht hergeben."""
    sätze = re.findall(r'tk\(\s*\n?\s*"([^"]+)"', _block("verlaesslichkeit"))
    assert sätze, "der Block gibt gar keinen Satz aus"
    for s in sätze:
        assert "lückenhafter" in s, s
        assert not re.search(r"\bfalsch\b|\bfehlerhaft\b|\bunzuverlässig\b|\bnicht verlässlich\b", s), s


def test_nennt_beide_zahlen():
    """„18 verworfen" allein ist bedeutungslos: 18 von 20 ist etwas anderes als 18 von 200."""
    b = _block("verlaesslichkeit")
    assert "{g: ganz, n: verworfen}" in b


def test_verdoppelt_den_haftungshinweis_nicht():
    """⚠ Die Zahl stand schon im `disc`. Zwei Stellen mit derselben Zahl sind die Sorte
    Doppelung, die eine Oberfläche unlesbar macht — der Halbsatz weicht, wenn die Zeile steht."""
    stelle = CORE[CORE.index('<div class="disc">'):]
    stelle = stelle[:stelle.index("</div>")]
    assert "!verlaesslichkeit(a)" in stelle, "Haftungshinweis und Zeile nennen die Zahl doppelt"


def test_traegt_die_hinweisfarbe_nicht_die_warnfarbe():
    css = (WURZEL / "web" / "app" / "explorer.css").read_text(encoding="utf-8")
    block = css[css.index(".verl {"):css.index(".verl {") + 300]
    assert "--flag" in block and "--risk" not in block, "lückenhaft ist keine Gefahr"


# ── die Schwelle ────────────────────────────────────────────────────────────────────────

def test_die_schwelle_ist_das_oberste_zehntel():
    assert _schwelle() == 0.30


def test_die_schwelle_altert_nicht_still():
    """⚠ DER WÄCHTER, der diese Kennzahl von einer eingefrorenen Zahl unterscheidet. Sie hat
    keinen Export, in dem eine Driftprüfung mitlaufen könnte — also prüft der Test sie gegen
    den echten Bestand. Wandert das oberste Zehntel weit weg (anderes Modell, andere
    Dokumentlage), muss die Schwelle nachgezogen werden, statt still falsch zu bleiben."""
    if not PARQUET.exists():
        return
    import duckdb
    con = duckdb.connect()
    werte = [r[0] for r in con.execute(
        f"select 1.0*rejected_items/nullif(rejected_items+n_checklist,0) "
        f"from read_parquet('{PARQUET.as_posix()}') "
        "where rejected_items is not null and n_checklist is not null "
        "and rejected_items+n_checklist > 0").fetchall() if r[0] is not None]
    if len(werte) < 500:
        return
    werte.sort()
    p90 = werte[int(len(werte) * 0.9) - 1]
    s = _schwelle()
    assert 0.5 * p90 <= s <= 2.0 * p90, (
        f"Schwelle {s:.0%} passt nicht mehr zum Bestand (p90 = {p90:.0%})")
    # ⚠ Und sie muss selten genug greifen, um eine Nachricht zu bleiben.
    anteil = sum(1 for x in werte if x > s) / len(werte)
    assert anteil <= 0.20, f"die Zeile erschiene bei {anteil:.0%} aller Auswertungen"


def test_nicht_nach_modell_gerahmt():
    """⚠ DER PUNKT, an dem die sonst richtige Regel „vergleiche im richtigen Rahmen" kippt. Die
    Quote spreizt 3,2-fach nach Modell (gpt-5.6-luna 4 %, gemini-2.5-flash 8 %, Llama 11 %).
    Bei Kennzahlen über die VERGABE nimmt ein Rahmen fremde Streuung heraus; hier wäre er eine
    Entschuldigung für unsere eigene Werkzeugwahl."""
    b = _block("verlaesslichkeit")
    for feld in ("model", "provider", "modell", "anbieter"):
        assert feld not in b.lower(), f"nach {feld} gerahmt"


def test_nicht_mehr_unter_geplant():
    from govisor import kennzahlen as K
    offen = {x.schluessel for x in K.ALLE if x.flaeche == "geplant"}
    assert "verlaesslichkeitAuswertung" not in offen
    k = [x for x in K.ALLE if x.schluessel == "verlaesslichkeitAuswertung"]
    assert k and k[0].bezug == "keine", "ein angezeigter Vergleichswert müsste benannt werden"
