"""Haelt `scripts/waechterlauf.sh` und den Tageslauf auf derselben Sondenliste.

WARUM. Seit dem 2026-09-20 stehen die Sonden an ZWEI Stellen: im Tageslauf (sofortige
Rueckmeldung im Protokoll) und im eigenstaendigen Waechterlauf (der auch dann laeuft, wenn
der Tageslauf frueh stirbt — genau der Fall, in dem bis dahin keine einzige Sonde feuerte).

Zwei Listen sind eine Kopie, und eine Kopie veraltet. In diesem Haus ist das schon mehrfach
passiert: eine zweite Aufzaehlung in Bash neben der Wahrheit im Modul, und die zweite war
still falsch. Dieser Test ist der Preis dafuer, dass die Kopie ueberhaupt existieren darf.

⚠ KOMMENTARE WERDEN VORHER ENTFERNT. Beide Skripte beschreiben ihre Sonden ausfuehrlich in
Kommentaren und in Hinweistexten („Details: python3 scripts/pruefe_x.py"). Ein naiver
Namensabgleich findet die Prosa und meldet Uebereinstimmung, wo keine ist — dieselbe Falle,
die hier schon mehrfach zugeschlagen hat. Deshalb wird auf die AUFRUFFORM geprueft, nicht
auf den blossen Namen.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
TAGESLAUF = ROOT / "scripts" / "daily_leads.sh"
WAECHTER = ROOT / "scripts" / "waechterlauf.sh"


def _ohne_kommentare(p: pathlib.Path) -> str:
    return "\n".join(z for z in p.read_text(encoding="utf-8").splitlines()
                     if not z.lstrip().startswith("#"))


def _sonden_im_tageslauf() -> set[str]:
    """Wie der Tageslauf sie ruft: `$PY scripts/pruefe_x.py` am Zeilenanfang."""
    return set(re.findall(r"^\$PY scripts/(pruefe_[a-z_]+)\.py",
                          _ohne_kommentare(TAGESLAUF), re.M))


def _sonden_im_waechterlauf() -> set[str]:
    """Wie der Waechterlauf sie ruft: hinter dem `--` der `sonde`-Funktion."""
    return set(re.findall(r"--\s+\$PY scripts/(pruefe_[a-z_]+)\.py",
                          _ohne_kommentare(WAECHTER)))


def test_der_waechterlauf_existiert_und_ist_ausfuehrbar():
    assert WAECHTER.exists(), "scripts/waechterlauf.sh fehlt"
    assert WAECHTER.stat().st_mode & 0o111, "waechterlauf.sh ist nicht ausfuehrbar"


def test_beide_listen_sind_deckungsgleich():
    """Der eigentliche Waechter ueber den Waechtern."""
    tag, wae = _sonden_im_tageslauf(), _sonden_im_waechterlauf()
    assert tag, "im Tageslauf wurde keine einzige Sonde gefunden — Regex kaputt?"
    fehlt_im_waechter = sorted(tag - wae)
    fehlt_im_tageslauf = sorted(wae - tag)
    assert not fehlt_im_waechter, (
        "Diese Sonden ruft der Tageslauf, der Waechterlauf aber nicht — sie fallen aus, "
        f"sobald der Tageslauf frueh stirbt: {fehlt_im_waechter}")
    assert not fehlt_im_tageslauf, (
        "Diese Sonden stehen nur im Waechterlauf. Entweder gehoeren sie auch in den "
        f"Tageslauf, oder sie sind dort geloescht worden: {fehlt_im_tageslauf}")


def test_der_waechterlauf_nimmt_die_tageslauf_sperre_NICHT():
    """Der Sinn der Uebung: er muss laufen koennen, WAEHREND der Tageslauf laeuft.

    Ein Waechter, der auf die Sperre wartet, haengt wieder am Beaufsichtigten — und
    schweigt genau dann, wenn dieser haengt.
    """
    quelle = _ohne_kommentare(WAECHTER)
    assert "mkdir" not in quelle or ".daily_leads.lock" not in quelle.split("mkdir")[1][:80], \
        "waechterlauf.sh scheint die Tageslauf-Sperre zu nehmen — das darf er nicht"
    assert 'rm -rf "$LOCK"' not in quelle, \
        "waechterlauf.sh raeumt eine Sperre weg, die ihm nicht gehoert"


def test_jede_sonde_hat_einen_hinweis_wie_man_sie_von_hand_ruft():
    """Ein Befund ohne Weg zum Detail ist eine Sackgasse um drei Uhr nachts."""
    quelle = _ohne_kommentare(WAECHTER)
    for zeile in quelle.splitlines():
        if zeile.startswith("sonde "):
            assert "Details:" in zeile, f"Sonde ohne Hinweis: {zeile[:60]}"


def test_der_waechterlauf_deckelt_jede_sonde():
    """Zwei Sonden gehen ins Netz. Ohne Frist haelt eine haengende Gegenstelle alles auf —
    dieselbe Klasse Fehler, die den Tageslauf am 2026-09-20 631 Minuten gekostet hat."""
    quelle = _ohne_kommentare(WAECHTER)
    assert "mit_frist" in quelle and "return 124" in quelle
    assert re.search(r'mit_frist "\$FRIST"', quelle), \
        "die Sonden laufen nicht durch mit_frist — dann ist der Deckel Dekoration"
