"""Hält der Mechanismus, der die Zahlen in der Marktanalyse nachzieht?

Sven am 2026-10-01: „kannst du ein mechanismus bauen, das die zahlen in dem dokument laufend
aktualisiert werden?"

⚠ WAS DIESE PRUEFUNGEN ABSICHERN, und warum jede davon einen Anlass hat:

1. **Der Erzeuger hat einen Aufrufer.** Direkt daneben liegt das Gegenbeispiel: `docs/
   kpi-katalog.md` traegt die Zeile „ERZEUGT, NICHT GETIPPT. python3 scripts/kpi_katalog.py" —
   und NICHTS ruft dieses Skript. Gemessen am 2026-10-01: kein Treffer in daily_leads.sh, in
   keinem Test, nirgends. Das Dokument behauptet also seit seiner Entstehung, frisch zu sein.
2. **Die Prosa ueberlebt.** Ein Erzeuger, der das ganze Dokument schreibt, loescht die
   Strategie. Ersetzt wird nur, was zwischen den Markierungen steht.
3. **Eine fehlende Markierung bricht ab.** Still nichts zu tun waere der schlimmere Fehler:
   das Dokument bliebe veraltet und der Nachtlauf meldete Erfolg.
4. **Eine leere Messung schreibt NICHTS.** Ein leerer Block waere schlimmer als ein veralteter.
5. **Dieselbe Zahl darf nicht zweimal im Dokument stehen.** Beim ersten Lauf fand die Pruefung
   genau das (`1.123.581` stand auch in der Prosa) — eine wird nachgezogen, die andere nicht.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
SKRIPT = WURZEL / "scripts" / "zahlen_nachziehen.py"
DOK = WURZEL / "docs" / "weiterentwicklung" / "sichtbarkeit-in-ki-antworten.md"
NACHTLAUF = WURZEL / "scripts" / "daily_leads.sh"


def _fahre(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SKRIPT), *args],
                          capture_output=True, text=True, cwd=cwd or WURZEL)


def test_der_erzeuger_wird_im_nachtlauf_gerufen():
    """⛔ Ein Erzeuger ohne Aufrufer ist eine Datei, keine Automatik."""
    lauf = NACHTLAUF.read_text(encoding="utf-8")
    ohne_kommentar = "\n".join(z for z in lauf.splitlines() if not z.lstrip().startswith("#"))
    assert "scripts/zahlen_nachziehen.py" in ohne_kommentar, \
        "der Erzeuger steht nur im Ordner, nicht im Nachtlauf"


def test_das_dokument_traegt_die_markierungen():
    text = DOK.read_text(encoding="utf-8")
    for m in ("<!-- ZAHLEN:bestand -->", "<!-- /ZAHLEN:bestand -->"):
        assert text.count(m) == 1, f"{m} steht {text.count(m)}x statt genau einmal"
    assert text.index("<!-- ZAHLEN:bestand -->") < text.index("<!-- /ZAHLEN:bestand -->")


def test_die_pruefung_meldet_aktuell_wenn_nachgezogen():
    r = _fahre("--pruefen")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "aktuell" in r.stdout


def test_eine_fehlende_markierung_bricht_ab(tmp_path):
    """⚠ Still nichts zu tun waere schlimmer: das Dokument bliebe veraltet und der Nachtlauf
    meldete Erfolg."""
    original = DOK.read_text(encoding="utf-8")
    try:
        DOK.write_text(original.replace("<!-- /ZAHLEN:bestand -->", ""), encoding="utf-8")
        r = _fahre()
        assert r.returncode != 0, "der Erzeuger lief durch, obwohl die Markierung fehlte"
        assert "Markierung" in r.stdout + r.stderr
    finally:
        DOK.write_text(original, encoding="utf-8")


def _wegwerfhaus(tmp_path: Path) -> tuple[Path, Path]:
    """Ein Haus mit Erzeuger, Dokument und Datenebene — aber NICHT das Repo. (Wurzel, Dokument)

    ⚠ WARUM. Bis zum 2026-10-05 fuhr `test_die_prosa_ueberlebt_den_lauf` den Erzeuger gegen
    das ECHTE Dokument im Arbeitsbaum und stellte es nicht zurueck. Wer die Suite laufen
    liess, hatte danach eine geaenderte, nachverfolgte Datei — ein Test mit Nebenwirkung auf
    den Bestand. Aufgefallen ist es erst, als die Suite zum ersten Mal im NACHTLAUF-BAUM
    lief: dort soll niemand arbeiten, und der Test tat es.

    Das Muster steht schon in `test_eine_leere_messung_schreibt_nichts` — es war nur nicht
    ueberall benutzt.
    """
    haus = tmp_path / "haus"
    (haus / "docs" / "weiterentwicklung").mkdir(parents=True)
    (haus / "scripts").mkdir()
    shutil.copy(SKRIPT, haus / "scripts" / SKRIPT.name)
    dok = haus / "docs" / "weiterentwicklung" / DOK.name
    shutil.copy(DOK, dok)
    # Die Datenebene wird VERLINKT, nicht kopiert: der Erzeuger misst echt, und kopieren
    # waere ein Vielfaches des Bestands.
    daten = WURZEL / "data"
    if daten.exists():
        (haus / "data").symlink_to(daten.resolve())
    return haus, dok


def test_die_prosa_ueberlebt_den_lauf(tmp_path):
    """Der eigentliche Grund für die Markierungen: Strategie ist Handarbeit."""
    haus, dok = _wegwerfhaus(tmp_path)
    vorher = dok.read_text(encoding="utf-8")
    probe = "Die Suche nach"          # ein Satz aus §5, weit weg vom Block
    assert probe in vorher, "der Probesatz steht nicht mehr im Dokument"
    r = subprocess.run([sys.executable, str(haus / "scripts" / SKRIPT.name)],
                       capture_output=True, text=True, cwd=haus)
    assert r.returncode in (0, 1), r.stdout + r.stderr
    nachher = dok.read_text(encoding="utf-8")
    assert probe in nachher, "der Erzeuger hat die Prosa überschrieben"
    assert "Index-Bauplan" in nachher and "Was ich nicht empfehle" in nachher


def test_die_suite_fasst_das_echte_dokument_nicht_an(tmp_path):
    """⚠ SELBSTPROBE der Regel von oben: nach einem Lauf der schreibenden Pruefungen muss das
    Dokument im Arbeitsbaum Byte fuer Byte dasselbe sein.

    Ohne diese Probe waere die Reparatur eine Behauptung — und genau so ein Nebeneffekt
    verschwindet beim naechsten Umbau lautlos wieder."""
    import hashlib
    vorher = hashlib.sha256(DOK.read_bytes()).hexdigest()
    test_die_prosa_ueberlebt_den_lauf(tmp_path / "probe")
    assert hashlib.sha256(DOK.read_bytes()).hexdigest() == vorher, (
        "die Pruefung hat das echte Dokument veraendert — sie gehoert in ein Wegwerfhaus")


def test_eine_leere_messung_schreibt_nichts(tmp_path):
    """⛔ Ein leerer Block waere schlimmer als ein veralteter. Gefahren wird in einem Verzeichnis
    OHNE Datenebene — dort darf der Erzeuger nur klagen, nicht schreiben."""
    leer = tmp_path / "leeres_haus"
    (leer / "docs" / "weiterentwicklung").mkdir(parents=True)
    (leer / "scripts").mkdir()
    shutil.copy(SKRIPT, leer / "scripts" / SKRIPT.name)
    (leer / "docs" / "weiterentwicklung" / DOK.name).write_text(
        "Prosa.\n<!-- ZAHLEN:bestand -->\nalt\n<!-- /ZAHLEN:bestand -->\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(leer / "scripts" / SKRIPT.name)],
                       capture_output=True, text=True, cwd=leer)
    assert r.returncode != 0, "ohne Daten wurde trotzdem geschrieben"
    inhalt = (leer / "docs" / "weiterentwicklung" / DOK.name).read_text(encoding="utf-8")
    assert "alt" in inhalt, "der Block wurde geleert, obwohl nichts gemessen werden konnte"


def test_keine_zahl_steht_zweimal_im_dokument():
    """Beim ersten Lauf fand genau das einen echten Fehler: `1.123.581` stand auch in der Prosa."""
    r = _fahre("--pruefen")
    assert "ausserhalb des Blocks" not in r.stdout, \
        "eine erzeugte Zahl steht auch in der Prosa:\n" + r.stdout
