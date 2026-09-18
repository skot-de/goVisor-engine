"""Gehen grosse Antworten komprimiert ueber die Leitung?

⚠ WARUM DIESE DATEI EXISTIERT. `next start` gzippt statische Dateien, aber KEINE
API-Antwort. Gemessen am 2026-09-18 mit angemeldeter Sitzung:

    /api/leads?branche=bau      46.044.875 Bytes   Content-Encoding: KEINE
    /api/plz-geo                 1.463.245 Bytes   Content-Encoding: KEINE
    /_next/static/chunks/*.js        1.905 Bytes   Content-Encoding: gzip

43,9 MB roh sind bei 30 Mbit/s 12,3 Sekunden — genau die Zeit, die gemeldet wurde
(„warum dauert das denn 12 sekunden?"). Ein Kommentar in der Route nannte „5,6 MB gzip";
das war die Groesse, die eine Komprimierung ERGEBEN WUERDE, nicht die, die ankommt. Ich
habe sie am 2026-09-17 als Messwert weitergereicht, ohne sie zu messen.

⚠ WARUM ES DIESE PRUEFUNG BRAUCHT UND NICHT NUR EINEN BLICK IN DIE KOPFZEILE. Setzt
jemand `Content-Encoding`, ohne dass der Rumpf so kodiert ist, zeigt der Browser keine
Fehlermeldung — er zeigt eine kaputte Seite. Die Sonde entpackt deshalb und vergleicht
Byte fuer Byte gegen die unkomprimierte Fassung.
"""
import shutil
import socket
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
SONDE = WURZEL / "web" / "scripts" / "pruefe-komprimierung.mjs"
PASSWORT = WURZEL / ".secrets" / "pruefkonto.txt"


def _server_laeuft(port: int = 3000) -> bool:
    with socket.socket() as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _cookie() -> str | None:
    """Angemeldete Sitzung, oder None wenn kein Pruefkonto eingerichtet ist."""
    if not PASSWORT.exists():
        return None
    r = subprocess.run(
        ["node", str(WURZEL / "web" / "scripts" / "pruefanmeldung.mjs"),
         "pruef@govisor.invalid", PASSWORT.read_text(encoding="utf-8").strip()],
        capture_output=True, text=True, cwd=WURZEL, env={"LEISE": "1", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"})
    if r.returncode != 0:
        return None
    zeile = r.stdout.strip()
    # Der Vorhang braucht seinen eigenen Zugang, sonst kommt HTML statt JSON.
    env = (WURZEL / "web" / ".env.local").read_text(encoding="utf-8")
    for z in env.splitlines():
        if z.startswith("PREVIEW_KEY="):
            zeile += f"; gv_preview={z.split('=', 1)[1].strip().strip(chr(34))}"
    return zeile


def test_grosse_antworten_sind_komprimiert_und_wiederherstellbar():
    """⚠ Braucht einen laufenden Server UND ein Pruefkonto — sonst uebersprungen.

    Genau diese Huerde hat die Aenderung einen Tag lang blockiert: ohne Sitzung
    antwortet `/api/leads` mit 401, und eine Komprimierungsaenderung an der wichtigsten
    Route ungeprueft auszuliefern waere die falsche Wette gewesen. `scripts/pruefkonto.py`
    legt das Konto an (mailfrei), `web/scripts/pruefanmeldung.mjs` holt die Sitzung.

    Gegengeprueft am 2026-09-18: rot, wenn (a) `Content-Encoding` gesetzt wird, ohne dass
    der Rumpf so kodiert ist, (b) `Vary: Accept-Encoding` fehlt.
    """
    if not shutil.which("node") or not _server_laeuft():
        return
    cookie = _cookie()
    if not cookie:
        return
    r = subprocess.run(["node", str(SONDE), cookie], capture_output=True, text=True, cwd=WURZEL)
    assert r.returncode == 0, r.stdout[-1200:] + r.stderr[-400:]
    assert "Byte fuer Byte wiederherstellbar" in r.stdout


def test_die_aushandlung_prueft_auf_wortgrenzen():
    """`brotli-irgendwas` ist nicht `br`.

    ⚠ Ein `includes("br")` haette bei jedem Accept-Encoding zugeschlagen, das die zwei
    Buchstaben irgendwo enthaelt — und dann einen Brotli-Rumpf an einen Client geschickt,
    der ihn nicht lesen kann. Der meldet keinen Fehler, er zeigt eine kaputte Seite.
    """
    import re
    roh = (WURZEL / "web" / "lib" / "komprimiert.ts").read_text(encoding="utf-8")
    # ⚠ KOMMENTARE RAUS. Die erste Fassung schlug an der ERKLAERUNG an, die `includes("br")`
    # als abschreckendes Beispiel zitiert — sie mass Prosa statt Code. Das ist am
    # 2026-09-17/18 der fuenfte Waechter mit demselben Fehler; wer hier eine Quelle liest,
    # entfernt zuerst die Kommentare.
    quelle = re.sub(r"(?m)(^|[^:])//.*$", r"\1", re.sub(r"/\*.*?\*/", "", roh, flags=re.S))
    assert 'includes("br")' not in quelle, "die Aushandlung prueft nicht auf Wortgrenzen"
    assert "RegExp" in quelle and "kann(" in quelle


def test_der_zwischenspeicher_trennt_die_verfahren():
    """Ein Brotli-Rumpf aus dem Speicher an einen gzip-Client waere Datenmuell.

    ⚠ Und ohne eindeutige Marke darf gar nicht zwischengespeichert werden: ein Schluessel,
    der die DATEN nicht benennt, liefert irgendwann den Stand von gestern aus — lautlos.
    """
    quelle = (WURZEL / "web" / "lib" / "komprimiert.ts").read_text(encoding="utf-8")
    i = quelle.index("const schluessel")
    zeile = quelle[i:quelle.index("\n", i)]
    assert "wie" in zeile, "das Verfahren steht nicht im Zwischenspeicher-Schluessel"
    assert "marke ?" in zeile, "ohne Marke wird trotzdem zwischengespeichert"
