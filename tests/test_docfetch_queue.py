"""Die Warteschlange muss vorankommen — sonst holt ein Fetcher jeden Tag dieselbe Niete.

Der Fehler, den diese Tests festnageln, hat drei Fetcher gleichzeitig lahmgelegt und sah
dabei aus wie drei verschiedene Fehler: `aumass` 0 von 2, `staatsanzeiger` 0 von 3,
`docfetch_healyhudson` 0 von 40. Die Ursache war eine einzige — ein Vorgang ohne Unterlagen
hinterlässt keine ZIP-Datei, und die Kandidatenwahl prüfte nur, ob eine Datei da ist. Der
Fehlschlag wurde sauber gemeldet, aber nirgends behalten.

Nach dem Fix: `aumass --limit 2` ging von 0 geladen auf 2 geladen (27 Dateien, 21,3 MB).
Es war nie ein Fetcher-Problem.
"""
from __future__ import annotations

import datetime as dt

from govisor import docfetch_queue as q

HEUTE = dt.date(2026, 8, 14)


def test_dauerhaftes_wird_nie_wieder_versucht():
    """Eine Ex-Ante-Bekanntmachung kündigt eine beabsichtigte Direktvergabe an. Es GIBT
    keine Unterlagen — nicht heute und nicht in drei Wochen."""
    for status in ("ohne_unterlagen", "kein_downloadbereich", "frameset"):
        vorher = {"status": status, "wann": dt.date(2020, 1, 1)}
        assert q.ueberspringen(vorher, HEUTE) == status, status


def test_voruebergehendes_bekommt_eine_sperrfrist_keinen_ausschluss():
    """Eine Vorgangsseite ohne Dateien kann morgen welche haben — Unterlagen werden oft
    nach der Bekanntmachung nachgereicht. „Nie wieder" wäre hier echter Datenverlust."""
    frisch = {"status": "leer", "wann": HEUTE - dt.timedelta(days=2)}
    assert q.ueberspringen(frisch, HEUTE), "innerhalb der Sperre: überspringen"

    alt = {"status": "leer", "wann": HEUTE - dt.timedelta(days=q.SPERRE_TAGE + 1)}
    assert q.ueberspringen(alt, HEUTE) is None, "nach der Sperre: wieder versuchen"

    netz = {"status": "fehler", "wann": HEUTE - dt.timedelta(days=q.SPERRE_TAGE)}
    assert q.ueberspringen(netz, HEUTE) is None, "ein Netzfehler ist kein Urteil"


def test_erfolg_und_trockenlauf_sind_kein_fehlschlag():
    """`probe` ist der Trockenlauf-Vermerk. Ihn als Fehlschlag zu werten hiesse, dass ein
    einziger `--dry-run` den Kandidaten für eine Woche sperrt."""
    for status in ("downloaded", "probe"):
        assert q.ueberspringen({"status": status, "wann": HEUTE}, HEUTE) is None


def test_unbekannter_kandidat_wird_versucht():
    """Kein Gedächtnis heisst „noch nie probiert", nicht „gescheitert"."""
    assert q.ueberspringen({}, HEUTE) is None
    assert q.ueberspringen({"status": None, "wann": None}, HEUTE) is None


def test_filtere_zaehlt_die_gruende_statt_still_zu_kappen():
    """Ein Lauf, der 200 Kandidaten still auslässt und „3 versucht" meldet, führt in die
    Irre. Was übersprungen wird, muss gezählt und benannt werden."""
    offen = [("a", "u"), ("b", "u"), ("c", "u"), ("d", "u")]
    vorher = {
        "a": {"status": "ohne_unterlagen", "wann": HEUTE},
        "b": {"status": "frameset", "wann": HEUTE},
        "c": {"status": "downloaded", "wann": HEUTE},
    }
    bleibt, gruende = q.filtere(offen, vorher)
    assert [x[0] for x in bleibt] == ["c", "d"]
    assert gruende == {"ohne_unterlagen": 1, "frameset": 1}
    assert "ohne_unterlagen=1" in q.bericht(gruende)
    assert q.bericht({}) == "", "nichts übersprungen → keine Zeile"


def test_manifest_wird_fortgeschrieben_nicht_ueberschrieben(tmp_path):
    """Das alte Verhalten warf mit jedem Lauf die gesamte Vorgeschichte weg. Damit war
    nicht nur die Warteschlange blind, sondern auch jede Frage nach dem Verlauf
    unbeantwortbar."""
    q.schreibe(tmp_path, "test", [
        {"lead_id": "a", "status": "ohne_unterlagen", "bytes": 0},
        {"lead_id": "b", "status": "downloaded", "bytes": 100},
    ])
    q.schreibe(tmp_path, "test", [{"lead_id": "c", "status": "leer", "bytes": 0}])

    bekannt = q.frueher(tmp_path, "test")
    assert set(bekannt) == {"a", "b", "c"}, "der erste Lauf darf nicht verschwinden"
    assert bekannt["a"]["status"] == "ohne_unterlagen"


def test_juengster_satz_gewinnt_je_lead():
    """Sonst wüchse die Datei mit jedem Lauf, und ein alter Fehlschlag könnte einen
    späteren Erfolg überstimmen."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        q.schreibe(p, "t", [{"lead_id": "a", "status": "leer",
                             "versucht_am": dt.date(2026, 8, 1)}])
        q.schreibe(p, "t", [{"lead_id": "a", "status": "downloaded",
                             "versucht_am": dt.date(2026, 8, 10)}])
        bekannt = q.frueher(p, "t")
        assert len(bekannt) == 1
        assert bekannt["a"]["status"] == "downloaded"


def test_kaputtes_manifest_kostet_historie_nicht_den_lauf(tmp_path):
    """Der schlimmste Fall darf sein, dass wieder von vorn probiert wird — das ist der
    Zustand von gestern, kein Ausfall."""
    (tmp_path / "_manifest_kaputt.parquet").write_bytes(b"kein parquet")
    assert q.frueher(tmp_path, "kaputt") == {}


def test_alle_vier_fetcher_nutzen_das_gedaechtnis():
    """Der Fehler war viermal derselbe. Die Lösung darf nicht bei dreien hängenbleiben."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for name in ("netserver", "aumass", "healyhudson", "staatsanzeiger"):
        text = (root / "govisor" / f"docfetch_{name}.py").read_text(encoding="utf-8")
        assert "docfetch_queue" in text, f"{name} liest das Gedächtnis nicht"
        assert "_queue.filtere" in text, f"{name} filtert nicht"
        assert "_queue.schreibe" in text, f"{name} schreibt das Manifest noch selbst"
        # Der Filter MUSS vor dem Limit stehen, sonst kappt das Limit auf Kandidaten,
        # die gleich wieder aussortiert werden — und der Lauf holt wieder nichts.
        assert text.index("_queue.filtere") < text.index("offen = offen[:limit]"), (
            f"{name}: gefiltert wird nach dem Kappen — dann bleibt nichts übrig")


# ══ Einheitliches Vokabular + dritte Klasse (2026-08-15) ═══════════════════════════════
#
# Ausgangslage: sieben von zwölf Abrufern schrieben ein Manifest, fünf nicht — und gelesen
# wurde nur ein Teil davon. Status wie `leer`, `gesperrt` oder `interesse_noetig` lebten
# damit ausschliesslich in der Konsolenausgabe. Diese Tests halten den vereinheitlichten
# Zustand fest, weil er nur so lange trägt, wie ihn jemand prüft.

def test_jeder_abrufer_liest_und_schreibt_das_manifest():
    """Ein Manifest, das niemand liest, ist kein Fortschritt — und eines, das niemand
    schreibt, ist eine Lücke im Gedächtnis. Beides muss zusammen vorkommen.

    Gemessen am 2026-08-15: `gated` stand mit **389 Leads** im Manifest von `docfetch.py`
    und wurde nie gelesen. Diese 389 Vorgänge wurden bei jedem Lauf erneut bei einem
    fremden Portal angefragt.
    """
    import pathlib
    import re

    wurzel = pathlib.Path(__file__).resolve().parent.parent / "govisor"
    # `docfetch_rib` ist ein Connector, den `docfetch.py` aufruft — er führt keine eigene
    # Warteschlange und schreibt in das Manifest seines Aufrufers.
    ausnahmen = {"docfetch_queue.py", "docfetch_rib.py"}
    abrufer = [p for p in sorted(wurzel.glob("docfetch*.py")) if p.name not in ausnahmen]
    abrufer += [wurzel / n for n in ("simap_docs.py", "subreport.py", "vergabeportal_at.py")]

    luecken = []
    for p in abrufer:
        text = p.read_text(encoding="utf-8")
        liest = re.search(r"_queue\.(frueher|filtere)", text)
        schreibt = "_queue.schreibe" in text
        if not (liest and schreibt):
            luecken.append(f"{p.name} (liest={bool(liest)}, schreibt={schreibt})")
    assert not luecken, "Abrufer ohne vollständige Warteschlangen-Anbindung: " + ", ".join(luecken)


def test_filtern_geschieht_vor_dem_limit():
    """Sonst kappt `--limit` auf Kandidaten, die gleich wieder aussortiert werden.

    Der Lauf meldete dann „20 geprüft", hätte aber 20 bereits bekannte Fehlschläge
    weggeworfen und nichts Neues angefasst — ein Fortschritt, den es nicht gab.
    """
    import pathlib
    import re

    wurzel = pathlib.Path(__file__).resolve().parent.parent / "govisor"
    falsch = []
    for p in sorted(wurzel.glob("*.py")):
        text = p.read_text(encoding="utf-8")
        if "_queue.filtere" not in text:
            continue
        f = text.index("_queue.filtere")
        m = re.search(r"\n    if limit:", text)
        if m and m.start() < f:
            falsch.append(p.name)
    assert not falsch, f"Limit wird VOR dem Filtern angewandt in: {falsch}"


def test_schreibweisen_werden_vereinheitlicht():
    """`error` und `fehler` sind dieselbe Aussage — die Regeln vergleichen Zeichenketten."""
    assert q.normalisiere("error") == "fehler"
    assert q.normalisiere("empty") == "leer"
    assert q.normalisiere("downloaded") == "downloaded"
    assert q.normalisiere(None) is None


def test_blockiertes_laeuft_nicht_per_frist_wieder_auf(tmp_path):
    """Der Kern der dritten Klasse: keine Wartefrist heilt ein fehlendes Konto."""
    import datetime as dt

    vorher = {"status": "gated", "wann": dt.date(2020, 1, 1)}   # uralt
    assert q.ueberspringen(vorher) is not None, "blockiert muss übersprungen bleiben"
    assert "blockiert: konto" in q.ueberspringen(vorher)

    # …bis der Abrufer den Blocker als gelöst meldet.
    assert q.ueberspringen(vorher, frei={"konto"}) is None


def test_vorübergehendes_laeuft_nach_der_frist_wieder_auf():
    """Gegenprobe: was sich ändern kann, darf nicht dauerhaft hängenbleiben."""
    import datetime as dt

    frisch = {"status": "fehler", "wann": dt.date.today()}
    assert q.ueberspringen(frisch) is not None
    alt = {"status": "fehler", "wann": dt.date.today() - dt.timedelta(days=q.SPERRE_TAGE)}
    assert q.ueberspringen(alt) is None


def test_nur_liste_gilt_als_erfolg():
    """subreport und vergabeportal.at LADEN nichts — die Liste ist ihr Ergebnis.

    Als Fehlschlag gewertet liefe jeder erfolgreich erfasste Vorgang für immer in der
    Warteschlange mit und verdrängte echte Kandidaten.
    """
    import datetime as dt
    assert q.ueberspringen({"status": "nur_liste", "wann": dt.date.today()}) is None


def test_entsperre_gibt_genau_einen_blocker_frei(tmp_path):
    q.schreibe(tmp_path, "x", [
        {"lead_id": "a", "status": "gated"},        # konto
        {"lead_id": "b", "status": "zu_gross"},     # groesse
        {"lead_id": "c", "status": "downloaded"},
    ])
    assert q.entsperre(tmp_path, "x", "groesse") == 1
    rest = q.frueher(tmp_path, "x")
    assert set(rest) == {"a", "c"}, "nur der Grössen-Blocker durfte fallen"
    assert q.entsperre(tmp_path, "x", "groesse") == 0, "zweiter Aufruf ändert nichts"


def test_alte_schreibweise_im_bestand_heilt_beim_lesen(tmp_path):
    """Ein Altmanifest mit `error` muss ohne Migration wie `fehler` behandelt werden."""
    import datetime as dt
    import pyarrow as pa
    import pyarrow.parquet as pq

    pq.write_table(pa.table({
        "lead_id": ["a"], "status": ["error"],
        "versucht_am": pa.array([dt.date.today()], pa.date32()),
    }), tmp_path / "_manifest_y.parquet", compression="zstd")
    assert q.frueher(tmp_path, "y")["a"]["status"] == "fehler"


def test_vorgang_frist_bricht_einzelnen_vorgang_ab():
    """Ein haengender Vorgang darf den Schritt nicht mitreissen.

    Am 2026-08-16 stand Healy-Hudson bei Vorgang 33 von 60, gab 30 min keine Zeile aus,
    und die Stillstandswache des Tageslaufs erschlug den GANZEN Schritt. Die 27 Vorgaenge
    dahinter waren nicht kaputt, sie kamen nur nicht mehr dran.

    Playwrights `set_default_timeout` half nicht: die deckelt eine OPERATION. Zehn Dateien
    à 33 MB bleiben jede darunter und brauchen zusammen eine halbe Stunde.
    """
    import time
    import signal
    from govisor import docfetch_queue as Q

    t = time.time()
    try:
        with Q.vorgang_frist(1):
            time.sleep(30)
        raise AssertionError("Frist hat nicht ausgeloest")
    except Q.VorgangZuLang:
        pass
    assert time.time() - t < 5, "Abbruch kam zu spaet"

    # Der Wecker muss danach ABGERAEUMT sein, sonst schlaegt er mitten im naechsten
    # Vorgang zu und der Abrufer stirbt an einer Frist, die laengst vorbei ist.
    with Q.vorgang_frist(30):
        time.sleep(0.05)
    assert signal.getsignal(signal.SIGALRM) in (0, signal.SIG_DFL, signal.SIG_IGN), \
        "SIGALRM-Handler blieb stehen"

    # Ohne Frist (0) laeuft der Block ungeschuetzt — kein Absturz, keine Wache.
    with Q.vorgang_frist(0):
        pass


def test_alle_abrufer_haben_vorgangsfrist_und_byte_deckel():
    """Jeder Abrufer braucht beide Grenzen — Zeit je Vorgang UND Bytes je Lauf.

    `--limit 60` zaehlt VORGAENGE, und ein Vorgang ist gemessen alles zwischen 0 und
    636 MB (Median 8, 90 % unter 72). 60 Stueck sind damit je nach Zusammensetzung 0,6
    bis 3,3 GB. Die beobachtete Streuung von 55,6 bis 719,1 min ist deshalb zum grossen
    Teil kein Server-Zufall, sondern eine falsche Zaehleinheit.

    healyhudson war der einzige ohne Byte-Deckel — und der Abrufer mit den 719 Minuten.
    """
    from pathlib import Path
    wurzel = Path(__file__).resolve().parent.parent / "govisor"
    fehlt_frist, fehlt_bytes = [], []
    for p in sorted(wurzel.glob("docfetch_*.py")):
        s = p.read_text(encoding="utf-8")
        if "hole_vergabe(" not in s or "sync_playwright" not in s:
            continue                       # kein Vorgangs-Abrufer
        if "vorgang_frist(" not in s:
            fehlt_frist.append(p.name)
        if not any(k in s for k in ("_LAUF_BUDGET_MB", "MAX_BYTES", "BUDGET_MB")):
            fehlt_bytes.append(p.name)
    assert not fehlt_frist, f"ohne Zeitgrenze je Vorgang: {fehlt_frist}"
    assert not fehlt_bytes, f"ohne Byte-Deckel je Lauf: {fehlt_bytes}"
