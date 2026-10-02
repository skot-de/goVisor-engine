"""Die Grounding Page: jede Zahl nachgerechnet, jedes Tor nachgeprüft.

⚠ **WARUM DIESE DATEI STRENGER IST ALS ANDERE PRÜFUNGEN.** `web/app/fakten` ist die
einzige Seite, die ausdrücklich als Faktenquelle für Sprachmodelle gedacht ist. Ein
Modell übernimmt die Zahlen von dort wörtlich und gibt sie weiter, ohne dass jemand die
Quelle nachschlägt. Eine falsche Zahl ist deshalb nicht ein Schönheitsfehler, sondern
etwas, das sich verbreitet.

**Die Regel, die daraus folgt: untertreiben ist erlaubt, übertreiben nie.** Der Bestand
wächst täglich, eine Seite darf also hinterherhinken. Sie darf aber nie mehr behaupten,
als da ist. Beides prüfen die Mengen-Tests unten, dazu eine Frist gegen das Veralten.

Der zweite Block prüft die Verdrahtung. Bei goVisor ist „gebaut, nicht verdrahtet" die
häufigste Fehlerklasse, und bei dieser Seite ist sie die teuerste: hinter der
Coming-Soon-Sperre bekäme ein Abrufer eine schwarze Seite mit `noindex` und lernte
daraus, dass unter dieser Adresse nichts steht.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAKTEN = ROOT / "web" / "lib" / "fakten.ts"
SEITE = ROOT / "web" / "app" / "fakten" / "page.tsx"
MIDDLEWARE = ROOT / "web" / "middleware.ts"
SITEMAP = ROOT / "web" / "app" / "sitemap.ts"
LLMS = ROOT / "web" / "public" / "llms.txt"

#: Wie weit die Seite hinter dem Bestand zurückbleiben darf, bevor sie nachgezogen wird.
#: 10 % ist kein Gefühlswert: der Bestand wuchs im September 2026 um rund 0,5 % im Monat
#: (DE 2.285.225 am 16.09. auf 2.301.205 am 02.10.), 10 % sind also gut anderthalb Jahre.
#: Wer die Frist enger zieht, erzeugt Rauschen; wer sie weiter zieht, lässt die Seite alt
#: werden, ohne dass es auffällt.
TOLERANZ = 0.10

#: Spätestens so alt darf der Prüfstempel sein. Dieselbe Frist wie beim Bibel-Nachlauf:
#: eine Warnung ohne Frist ist folgenlos.
MAX_TAGE = 90


def _text(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")


def _zahl(roh: str) -> int:
    """„2.890.294" → 2890294."""
    return int(roh.replace(".", "").replace(" ", "").strip())


def _genannt(muster: str) -> int:
    """Die erste Zahl, die hinter `muster` in `fakten.ts` steht."""
    t = _text(FAKTEN)
    m = re.search(muster, t)
    assert m, f"Muster nicht gefunden in fakten.ts: {muster}"
    return _zahl(m.group(1))


def _duck():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("SET memory_limit='2GB'")
    con.execute("SET threads=2")
    return con


def _silber_da() -> bool:
    return (ROOT / "data" / "silver" / "DE" / "notices").is_dir()


def _pruefe_menge(name: str, genannt: int, gemessen: int) -> None:
    """Untertreiben erlaubt, übertreiben nie."""
    assert genannt <= gemessen, (
        f"{name}: die Seite nennt {genannt:,}, gemessen sind {gemessen:,}. "
        f"Sie behauptet mehr, als da ist — das ist die eine Richtung, die auf einer "
        f"Faktenseite nicht passieren darf.")
    assert genannt >= gemessen * (1 - TOLERANZ), (
        f"{name}: die Seite nennt {genannt:,}, gemessen sind {gemessen:,} "
        f"({100 * (1 - genannt / gemessen):.1f} % veraltet). Zahlen in "
        f"web/lib/fakten.ts nachziehen und `geprueft` aktualisieren.")


# ── Teil 1: die Zahlen ────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _silber_da(), reason="kein Silber auf dieser Maschine")
def test_bekanntmachungen_und_zuschlaege_stimmen():
    con = _duck()
    try:
        n = z = 0
        for land in ("DE", "AT", "CH", "LU"):
            muster = (ROOT / "data" / "silver" / land / "notices" / "**" / "*.parquet").as_posix()
            a, b = con.execute(
                f"""SELECT count(*), count(*) FILTER (WHERE notice_kind='can')
                    FROM read_parquet('{muster}')""").fetchone()
            n += a
            z += b
    finally:
        con.close()
    _pruefe_menge("Bekanntmachungen", _genannt(r'wert: "([\d.]+), davon'), n)
    _pruefe_menge("Zuschläge", _genannt(r'davon ([\d.]+) Zuschläge'), z)


@pytest.mark.skipif(not (ROOT / "data" / "gold" / "DE").is_dir(), reason="kein Gold")
def test_vorgangsakten_und_vertragsketten_stimmen():
    con = _duck()
    akten = ketten = dubletten = 0
    try:
        for land in ("DE", "AT", "CH", "LU"):
            g = ROOT / "data" / "gold" / land
            for datei, ziel in (("vorgaenge.parquet", "akten"),
                                ("contract_successions.parquet", "ketten"),
                                ("notice_duplicates.parquet", "dubletten")):
                p = g / datei
                if not p.exists():
                    continue
                n = con.execute(
                    f"SELECT count(*) FROM read_parquet('{p.as_posix()}')").fetchone()[0]
                if ziel == "akten":
                    akten += n
                elif ziel == "ketten":
                    ketten += n
                else:
                    dubletten += n
    finally:
        con.close()
    _pruefe_menge("Vorgangsakten", _genannt(r'wert: "([\d.]+) Vergabevorgänge'), akten)
    _pruefe_menge("Vertragsketten", _genannt(r'wert: "([\d.]+) belegte Vorgänger'), ketten)
    # ⚠ Die Dubletten-Zahl steht in einem umgebrochenen String, der Regex muss das wissen.
    roh = re.search(r'Derzeit sind ([\d.]+) "', _text(FAKTEN))
    assert roh, "Dubletten-Zahl nicht in fakten.ts gefunden"
    _pruefe_menge("Dubletten-Paare", _zahl(roh.group(1)), dubletten)


@pytest.mark.skipif(not _silber_da(), reason="kein Silber auf dieser Maschine")
def test_laendertabelle_stimmt_je_land():
    """⚠ Die Summe kann stimmen, während die Zeilen falsch sind.

    Eine Gesamtzahl verdeckt, wenn zwei Länder in entgegengesetzte Richtungen abweichen.
    Deshalb wird jede Zeile einzeln nachgerechnet.
    """
    t = _text(FAKTEN)
    con = _duck()
    try:
        for land in ("DE", "AT", "CH", "LU"):
            m = re.search(
                rf'code: "{land}".*?bekanntmachungen: "([\d.]+)", zuschlaege: "([\d.]+)"', t)
            assert m, f"Zeile für {land} nicht in fakten.ts gefunden"
            muster = (ROOT / "data" / "silver" / land / "notices" / "**" / "*.parquet").as_posix()
            a, b = con.execute(
                f"""SELECT count(*), count(*) FILTER (WHERE notice_kind='can')
                    FROM read_parquet('{muster}')""").fetchone()
            _pruefe_menge(f"{land} Bekanntmachungen", _zahl(m.group(1)), a)
            _pruefe_menge(f"{land} Zuschläge", _zahl(m.group(2)), b)
    finally:
        con.close()


def test_quellenzahlen_stimmen():
    """20 angebunden von 125 erfassten — beide Zahlen aus der Registry, nicht geschätzt."""
    import sys
    sys.path.insert(0, str(ROOT))
    from govisor import sources  # noqa: PLC0415

    eintraege = sources.REGISTRY if isinstance(sources.REGISTRY, list) else list(sources.REGISTRY)
    live = sum(1 for e in eintraege if str(getattr(e, "status", "")) == "live")
    t = _text(FAKTEN)
    m = re.search(r'wert: "(\d+) produktiv angebunden, (\d+) Quellen', t)
    assert m, "Quellen-Zeile nicht in fakten.ts gefunden"
    assert int(m.group(1)) == live, (
        f"Die Seite nennt {m.group(1)} angebundene Quellen, die Registry führt {live}.")
    assert int(m.group(2)) == len(eintraege), (
        f"Die Seite nennt {m.group(2)} erfasste Quellen, die Registry führt {len(eintraege)}.")


def test_laenderliste_stimmt_mit_aktiv():
    """⚠ Die Seite darf kein Land nennen, das die Pipeline nicht baut, und keines auslassen."""
    import sys
    sys.path.insert(0, str(ROOT))
    from govisor.laender import AKTIV  # noqa: PLC0415

    t = _text(FAKTEN)
    genannt = set(re.findall(r'code: "([A-Z]{2})"', t))
    assert genannt == set(AKTIV), (
        f"Die Seite führt {sorted(genannt)}, gebaut werden {sorted(AKTIV)}. "
        f"Ein Land auf der Faktenseite, das es im Produkt nicht gibt, ist eine Falschangabe; "
        f"ein fehlendes verschenkt es.")


def test_pruefstempel_ist_nicht_veraltet():
    m = re.search(r'const GEMESSEN = "(\d{4}-\d{2}-\d{2})"', _text(FAKTEN))
    assert m, "Kein Prüfstempel `GEMESSEN` in fakten.ts"
    alter = (dt.date.today() - dt.date.fromisoformat(m.group(1))).days
    assert alter <= MAX_TAGE, (
        f"Der Prüfstempel der Grounding Page ist {alter} Tage alt (max {MAX_TAGE}). "
        f"Zahlen nachmessen und `GEMESSEN` setzen.")


def test_keine_zahl_ohne_stichtag():
    """⚠ Eine Mengenangabe ohne Datum liest sich als Gegenwart und ist morgen falsch.

    Dieselbe Regel wie in der Länder-Bibel. Auf einer Seite, die zitiert werden soll,
    wiegt sie schwerer: das Zitat trägt das Datum mit, wenn es danebensteht.
    """
    t = _text(FAKTEN)
    assert "gemessenAm" in t and "GEMESSEN" in t
    seite = _text(SEITE)
    assert "f.gemessenAm" in seite, (
        "Der Stichtag steht nicht auf der Seite — dann liest sich jede Zahl als heute.")


# ── Teil 2: die Verdrahtung ───────────────────────────────────────────────────────────

def test_seite_kommt_durch_die_coming_soon_sperre():
    """⚠ Ohne diese Ausnahme ist die ganze Seite wertlos, nicht halb wertlos."""
    t = _text(MIDDLEWARE)
    assert "const GROUNDING" in t, "Keine GROUNDING-Liste in der Middleware"
    assert "/fakten" in t.split("const GROUNDING")[1].split("]")[0], (
        "/fakten steht nicht in GROUNDING")
    assert "istGrounding(pfad)" in t, (
        "Die Blackout-Kette fragt `istGrounding` nicht ab — ein Crawler bekäme die "
        "schwarze Seite mit noindex.")
    # Die Abfrage muss in der Kette stehen, die `blackPage` verhindert, nicht irgendwo.
    kette = t.split("return blackPage(pfad);")[0].rsplit("if (!unlocked", 1)[-1]
    assert "istGrounding" in kette, (
        "`istGrounding` steht nicht in der Blackout-Ausnahmekette.")


def test_seite_verlangt_keine_anmeldung():
    t = _text(MIDDLEWARE)
    assert "const OFFEN = [...GROUNDING" in t, (
        "Die Grounding-Pfade stehen nicht in OFFEN — ein Abrufer landete auf /login.")


def test_llms_txt_kommt_auch_durch():
    """⚠ Der Matcher nimmt nur Bilder aus. `.txt` läuft durch die Middleware.

    Genau diese Falle hat bei `robots.txt` schon einmal zugeschlagen: der Crawler bekam
    eine schwarze HTML-Seite statt der Datei und fiel auf „alles erlaubt" zurück.
    """
    assert LLMS.exists(), "web/public/llms.txt fehlt"
    t = _text(MIDDLEWARE)
    assert "/llms.txt" in t.split("const GROUNDING")[1].split("]")[0], (
        "/llms.txt steht nicht in GROUNDING und bekäme die schwarze Seite.")


def test_steht_in_der_sitemap():
    assert "/fakten" in _text(SITEMAP), (
        "Die Grounding Page fehlt in der Sitemap — eine Faktenseite, die niemand findet, "
        "ist keine.")


def test_kanonischer_verweis_zeigt_auf_sich_selbst():
    """⚠ Das Wurzel-Layout setzt `canonical: "/"`.

    Ohne Überschreiben erklärte die Faktenseite sich selbst zur Startseite und verlöre
    genau die Eigenschaft, um derentwillen es sie gibt.
    """
    t = _text(SEITE)
    assert 'alternates: { canonical: PFAD }' in t, (
        "Kein eigener kanonischer Verweis — die Seite zeigt auf die Startseite.")
    assert 'robots: { index: true, follow: true }' in t


def test_seite_braucht_kein_javascript():
    """Abrufer von Modellen rendern kein Javascript. Was nur im Browser entsteht, zählt nicht."""
    t = _text(SEITE)
    assert not t.lstrip().startswith('"use client"'), (
        "Die Grounding Page ist eine Client-Komponente — ihr Inhalt entstünde erst im "
        "Browser und wäre für einen Abrufer unsichtbar.")
    for haken in ("useState(", "useEffect(", "fetch("):
        assert haken not in t, f"{haken} auf der Grounding Page: das braucht Javascript."


def test_json_ld_traegt_die_drei_typen():
    t = _text(SEITE)
    for typ in ("SoftwareApplication", "Organization", "FAQPage", "WebPage"):
        assert f'"{typ}"' in t, f"JSON-LD ohne {typ}"
    assert "application/ld+json" in t


def test_methodikbegriffe_kommen_im_produkt_vor():
    """⚠ Ein Begriff auf der Faktenseite, den das Produkt nicht einlöst, ist eine Behauptung.

    Geprüft wird gegen Code UND Oberfläche, nicht gegen die Dokumentation: in `docs/`
    steht auch, was wir erst vorhaben. Genau deshalb fehlt die Fonds-Ebene hier, obwohl
    sie 16 Fundstellen in der Doku hat und keine im Produkt.
    """
    begriffe = re.findall(r'begriff: "([^"]+)"', _text(FAKTEN))
    assert begriffe, "Keine Methodikbegriffe in fakten.ts"
    quellen = [p for p in (ROOT / "govisor").rglob("*.py")]
    quellen += [p for p in (ROOT / "scripts").rglob("*.py")]
    quellen += [p for p in (ROOT / "web" / "lib").rglob("*.js")]
    quellen += [p for p in (ROOT / "web" / "components").rglob("*.tsx")]
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in quellen)
    for b in begriffe:
        kern = b.split("-")[0].rstrip("e")           # Nachfolge-Adjudikation → Nachfolg
        assert kern.lower() in text.lower(), (
            # ⚠ KEIN deutsches Schlusszeichen in einem f-String: das ist ein ASCII-"
            # und beendet die Zeichenkette mitten im Satz (Auto-Memory, schon zugeschlagen).
            f"Der Methodikbegriff {b} kommt im Produktcode nicht vor. Entweder ist er "
            f"anders benannt, oder er gehoert nicht auf die Faktenseite.")


def test_fonds_ebene_steht_bewusst_nicht_drauf():
    """Die Auslassung ist eine Entscheidung und wird als solche festgehalten.

    Ohne diesen Test wäre sie beim nächsten Durchsehen ein Versehen, das jemand
    „behebt" — und dann stünde ein Verfahren auf der Seite, das es nicht gibt.
    """
    t = _text(FAKTEN)
    begriffe = re.findall(r'begriff: "([^"]+)"', t)
    assert not any("onds" in b for b in begriffe), (
        "Die Fonds-Ebene ist als Methodikbegriff aufgenommen worden. Sie ist in keinem "
        "der vier Länder angebunden; der Begriff gehört erst auf die Seite, wenn das "
        "Produkt ihn einlöst.")
    assert "Fonds-Ebene" in t, (
        "Die Begründung für die Auslassung ist verschwunden — dann wird sie beim nächsten "
        "Durchsehen für ein Versehen gehalten.")
