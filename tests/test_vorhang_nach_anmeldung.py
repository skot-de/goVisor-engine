"""Wer sich anmeldet, muss danach etwas sehen — auch auf einem fremden Geraet.

⚠ GEMESSEN AM 2026-09-17 ueber einen Tunnel, Stunden vor einer Vorfuehrung: Anmeldelink auf
einem Geraet OHNE vorherigen `?preview=`-Aufruf. Der Einmal-Token wird eingeloest, die
Sitzung steht, die Umleitung nach `/leads` greift — und dort steht eine LEERE SCHWARZE
SEITE. Der Nutzer hat sich gerade erfolgreich angemeldet und sieht nichts.

Der Callback kannte den Fall und oeffnet den Vorhang — aber nur ueber `ZUGANG_PFAD`, und
der ist in keinem Setup gesetzt. Der zweite Riegel `PREVIEW_KEY` blieb dabei zu. Beide
bewachen DENSELBEN Vorhang (`middleware.ts`: `unlocked` haengt an PREVIEW_KEY, `vorhangAuf`
an ZUGANG_PFAD); die Begruendung im Kommentar galt fuer beide, der Code nur fuer einen.

⚠ WARUM DAS AUF DEM EIGENEN RECHNER NIE AUFFAELLT: dort liegt der Vorschau-Cookie vom
Entwickeln noch. Der Fehler trifft ausgerechnet den Fall, fuer den es Anmeldelinks
ueberhaupt gibt — ein anderes Geraet.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALLBACK = ROOT / "web" / "app" / "auth" / "callback" / "route.ts"
MIDDLEWARE = ROOT / "web" / "middleware.ts"


def _ohne_kommentar(s: str) -> str:
    raus, i, n = [], 0, len(s)
    while i < n:
        if s[i] == "/" and i + 1 < n and s[i + 1] == "/":
            while i < n and s[i] != "\n":
                raus.append(" ")
                i += 1
            continue
        if s[i] == "/" and i + 1 < n and s[i + 1] == "*":
            while i < n and not (s[i] == "*" and i + 1 < n and s[i + 1] == "/"):
                raus.append("\n" if s[i] == "\n" else " ")
                i += 1
            raus.append("  ")
            i += 2
            continue
        raus.append(s[i])
        i += 1
    return "".join(raus)


def test_der_callback_oeffnet_JEDEN_riegel_des_vorhangs():
    """Die Middleware kennt zwei Wege durch den Vorhang. Der Callback muss beide bedienen.

    Geprueft wird der ZUSAMMENHANG im entkommentierten Code: fuer jeden Cookie, den die
    Middleware als Schluessel akzeptiert, muss der Callback ihn auch setzen. Ein Test, der
    nur nach dem Wort `gv_preview` sucht, faende die Erklaerung daneben (F13).
    """
    mw = _ohne_kommentar(MIDDLEWARE.read_text(encoding="utf-8"))
    cb = _ohne_kommentar(CALLBACK.read_text(encoding="utf-8"))

    # Welche Cookies oeffnen laut Middleware den Vorhang?
    riegel = set(re.findall(r'"(gv_[a-z]+)"', mw))
    assert riegel, "middleware.ts nennt keine Vorhang-Cookies mehr — Test veraltet?"

    gesetzt = set(re.findall(r'antwort\.cookies\.set\(\s*"(gv_[a-z]+)"', cb))
    fehlt = riegel - gesetzt
    assert not fehlt, (
        f"Der Callback setzt {sorted(fehlt)} nicht. Die Middleware akzeptiert diesen Cookie "
        f"als Schluessel durch den Vorhang — wer sich per Anmeldelink auf einem FREMDEN "
        f"Geraet anmeldet, landet sonst auf einer schwarzen Seite. Auf dem eigenen Rechner "
        f"faellt das nie auf, weil der Cookie vom Entwickeln dort liegt.")


def test_beide_wege_bleiben_fail_closed():
    """Ohne gesetzte Variable darf kein Cookie fliegen — sonst oeffnet der Callback den
    Vorhang mit einem leeren Wert, und der passt dann auf jede leere Anfrage."""
    cb = _ohne_kommentar(CALLBACK.read_text(encoding="utf-8"))
    for quelle in ("ZUGANG_PFAD", "PREVIEW_KEY"):
        i = cb.find(quelle)
        assert i > 0, f"{quelle} kommt im Callback nicht mehr vor"
        # Zwischen Variable und dem cookies.set muss eine Wahrheitspruefung stehen.
        block = cb[i:i + 260]
        assert re.search(r"if\s*\(\s*\w+\s*\)", block), (
            f"{quelle} wird ohne Pruefung auf einen Wert gesetzt — ein leerer Schluessel "
            f"waere dann ein Generalschluessel.")
