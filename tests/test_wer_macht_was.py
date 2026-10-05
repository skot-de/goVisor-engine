"""Wache: „wer macht was" ist verdrahtet und beruhigt nicht falsch.

WARUM ES DAS GIBT. Am 2026-10-03 habe ich Impressum und Datenschutzerklaerung neu gebaut —
beides lag fertig auf `origin/web/grounding-page`, von einer anderen Sitzung. Mein Fehlschluss
war „neue Dateien, also keine Kollision"; ueber Branches hinweg ist das falsch. Drei Sitzungen
arbeiten an diesem Repo, und ein Worktree verhindert nur gemeinsame SCHREIBZUGRIFFE, nicht
doppelte ARBEIT.

⚠ ZWEI ZUSAGEN SIND HIER FESTGEHALTEN, und beide koennten still verschwinden:
  1. Ein fehlgeschlagener `git fetch` MUSS abbrechen. Antwortet das Skript mit veralteten
     Remote-Refs, meldet es „niemand arbeitet daran" — genau die falsche Beruhigung, gegen die
     es gebaut ist. Dieselbe Fehlerklasse wie `grep -q` auf einer unlesbaren Datei
     (s. memory launchd-Fallen).
  2. Die Ueberlappungs-Anzeige in `laeuft_was.sh` darf `frei` NICHT setzen. Eine Ueberlappung
     ist kein Grund, einen Pipeline-Lauf zu verschieben; wer sie zu einem ⛔ macht, stumpft den
     Riegel ab, und ein oft grundlos roter Waechter wird uebergangen.

⚠ Geprueft wird der Rumpf OHNE Zeilenkommentare — die Begruendungen im Skript nennen dieselben
Woerter wie die Pruefungen (s. memory waechter-messen-prosa-statt-code).
"""
import pathlib
import subprocess

WURZEL = pathlib.Path(__file__).resolve().parent.parent
WER = WURZEL / "scripts" / "wer_macht_was.sh"
LAEUFT = WURZEL / "scripts" / "laeuft_was.sh"


def rumpf(p: pathlib.Path) -> str:
    """Shell-Quelle ohne VOLLZEILEN-Kommentare.

    ⚠ Nur ganze Kommentarzeilen entfernen, keine `#` mitten in einer Zeile: `${pfad/#$WURZEL/.}`
    ist eine Parameter-Ersetzung und kein Kommentar. Ein naives Abschneiden am ersten `#`
    zerlegte genau solche Zeilen.
    """
    assert p.exists(), f"{p.relative_to(WURZEL)} fehlt"
    return "\n".join(z for z in p.read_text(encoding="utf-8").splitlines()
                     if not z.lstrip().startswith("#"))


def test_skript_existiert_und_ist_ausfuehrbar():
    assert WER.exists(), "scripts/wer_macht_was.sh fehlt"
    assert WER.stat().st_mode & 0o111, "nicht ausfuehrbar (chmod +x)"


def test_fehlgeschlagener_abruf_bricht_ab():
    """Zusage 1: keine Antwort auf veralteten Refs."""
    r = rumpf(WER)
    assert "git fetch" in r, "es wird gar nicht abgerufen"
    i = r.index("git fetch")
    block = r[i:i + 600]
    assert "exit 3" in block, (
        "ein fehlgeschlagener Abruf bricht nicht ab — das Skript wuerde mit veralteten "
        "Remote-Refs antworten und „niemand arbeitet daran\" melden")


def test_ohne_abruf_wird_gewarnt():
    """Wer bewusst ohne Abruf faehrt, muss es sehen."""
    r = rumpf(WER)
    assert "--kein-abruf" in r, "kein Schalter, um den Abruf zu uebergehen"
    assert "OHNE ABRUF" in r, "der uebergangene Abruf wird nicht gemeldet"


def test_dateiliste_gegen_den_gemeinsamen_vorfahren():
    """⚠ Nicht gegen origin/main direkt.

    Ist origin/main weitergelaufen, zeigte ein direkter Vergleich fremde Dateien, die der
    Branch nie angefasst hat. Dann sucht man Kollisionen, die es nicht gibt, und uebersieht
    die echten.
    """
    r = rumpf(WER)
    assert "merge-base" in r, "die Dateiliste wird nicht gegen den gemeinsamen Vorfahren gebildet"


def test_in_laeuft_was_verdrahtet():
    assert "wer_macht_was.sh" in rumpf(LAEUFT), (
        "nicht in laeuft_was.sh eingehaengt — dann sieht es niemand vor dem Schreiben")


def test_ueberlappung_macht_den_riegel_nicht_rot():
    """Zusage 2: die Anzeige darf `frei` nicht setzen."""
    r = rumpf(LAEUFT)
    i = r.index("wer_macht_was.sh")
    # Vom Aufruf bis zum Schlussurteil: dort darf `frei=` nicht vorkommen.
    ende = r.index('if [ "$frei" -eq 0 ]', i)
    block = r[i:ende]
    assert "frei=" not in block, (
        "die Ueberlappungs-Anzeige setzt `frei` — damit wuerde eine Branch-Ueberlappung einen "
        "Pipeline-Lauf blockieren, obwohl sie erst beim Zusammenfuehren stoert. Ein oft "
        "grundlos roter Waechter wird uebergangen.")
    assert "--kein-abruf" in block, (
        "laeuft_was.sh ruft MIT Abruf — das laeuft vor jedem schreibenden Schritt und darf "
        "nicht ins Netz")


def test_pfadmodus_findet_fremden_besitz():
    """⚠ SELBSTPROBE am echten Fall, der das Skript ausgeloest hat.

    `web/app/datenschutz/page.tsx` liegt auf `web/grounding-page`. Findet der Pfadmodus das
    nicht, ist er wertlos — und zwar lautlos, denn „niemand" sieht wie eine Antwort aus.
    """
    r = subprocess.run(["bash", str(WER), "--kein-abruf", "web/app/datenschutz/page.tsx"],
                       cwd=WURZEL, capture_output=True, text=True, timeout=120)
    assert "grounding-page" in r.stdout, (
        "SELBSTPROBE: der Pfadmodus findet den fremden Besitz nicht.\n" + r.stdout + r.stderr)
    assert r.returncode == 1, f"fremder Besitz muss Rueckgabewert 1 geben, war {r.returncode}"


def test_pfadmodus_meldet_freie_pfade_als_frei():
    """Die andere Richtung: ein erfundener Pfad darf NICHT als belegt gelten."""
    r = subprocess.run(["bash", str(WER), "--kein-abruf", "scripts/gibt_es_wirklich_nicht.py"],
                       cwd=WURZEL, capture_output=True, text=True, timeout=120)
    assert "niemand" in r.stdout, "ein freier Pfad wird nicht als frei gemeldet"
    assert r.returncode == 0, f"freier Pfad muss 0 geben, war {r.returncode}"


def test_datei_auf_main_die_niemand_aendert_ist_kein_hindernis():
    """⚠ Sonst ist das Werkzeug bei JEDER bestehenden Datei rot und damit wertlos.

    Gemessen am 2026-10-03: die erste Fassung meldete fuer `tests/test_marktwert.py` ACHT
    Branches mit „liegt dort" — die Datei liegt auf main und damit auf jedem Nachkommen. Acht
    Treffer, null Erkenntnis, und das echte Signal („wer hat sie GEAENDERT") ertrank darin.
    Jetzt zaehlt nur noch, wer sie aendert.
    """
    r = subprocess.run(["bash", str(WER), "--kein-abruf", "scripts/laeuft_was.sh"],
                       cwd=WURZEL, capture_output=True, text=True, timeout=120)
    # laeuft_was.sh liegt auf main. Dass ICH sie gerade geaendert habe, darf sie als belegt
    # melden — aber niemals mit „liegt dort" fuer Branches, die sie nur erben.
    assert "liegt dort" not in r.stdout, (
        "eine Datei von origin/main wird als „liegt dort\" gemeldet — das trifft jeden "
        "Nachkommen und erzeugt Rauschen statt Auskunft:\n" + r.stdout)


def test_unterscheidet_neu_angelegt_von_geaendert():
    """Die Unterscheidung ist der Kern: „neu angelegt" heisst Doppelarbeit, „geaendert" heisst
    Konflikt beim Zusammenfuehren. Zwei Befunde mit zwei verschiedenen Konsequenzen."""
    r = rumpf(WER)
    assert "neu angelegt" in r and "geaendert" in r, (
        "das Werkzeug unterscheidet nicht zwischen neu angelegt und geaendert")
    assert "origin/main:$p" in r, (
        "es prueft nicht, ob der Pfad schon auf origin/main liegt — ohne diese Pruefung "
        "kann es die beiden Faelle nicht trennen")
