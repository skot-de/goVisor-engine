"""Wer das Profil im Browser schreibt, muss es auch sagen.

⚠ GEMELDET AM 2026-09-18. Nach einem Onboarding auf „H. Klostermann Baugesellschaft mbH"
stand in der Kopfzeile weiter „CANCOM" — die Firma aus einem frueheren Durchlauf. Auf
demselben Bildschirm zwei verschiedene Firmen, und der Nutzer kann nicht wissen, welche
gilt.

Die Mechanik: `useProfil` haelt den Wert im React-Zustand und liest ihn nur neu, wenn das
Ereignis `govisor:profil` feuert. Das `storage`-Ereignis des Browsers hilft NICHT — es
feuert nur in anderen Tabs, nie im eigenen. Deshalb gibt es `profilGeaendert()`, und im
Docstring steht ausdruecklich „Ausloesen, wann immer PROFILE_KEY geschrieben oder entfernt
wurde".

⚠ DIE URSACHE WAR EINE KOPIERTE KONSTANTE. `onboarding/page.tsx` fuehrte
`const PROFILE_KEY = "govisor.profile.v1"` selbst, statt sie aus `lib/useProfil` zu holen.
Wer die Konstante kopiert, sieht die Pflicht nicht, die daneben steht — der Aufruf fehlte
an genau der Stelle, die das Profil ERSTMALS setzt. `ExplorerShell` und `Trefferguete`
machen es richtig, auch bei der Abmeldung.
"""
import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
WEB = WURZEL / "web"
SCHLUESSEL = "govisor.profile.v1"
EIGENTUEMER = "lib/useProfil.ts"

# ⚠ BELEGTE AUSNAHME, KEIN FREIBRIEF. `ExplorerShell.tsx` fuehrt die Konstante ebenfalls
# selbst — anders als das Onboarding LOEST es das Signal aber an beiden Stellen aus, auch
# bei der Abmeldung. Es ist also Hygiene, kein Fehler. Nicht mitrepariert am 2026-09-18,
# weil eine zweite Sitzung die Datei zu dem Zeitpunkt offen hatte und unfertige Aenderungen
# darin lagen; wer in fremdem Gebiet schreibt, sagt es an.
#
# Der zweite Test (`test_jeder_schreiber_loest_das_signal_aus`) deckt die Datei WEITER ab —
# die Ausnahme gilt nur fuer die Konstante, nicht fuer die Meldepflicht.
AUSNAHMEN = {"components/explorer/ExplorerShell.tsx"}


def _ohne_kommentar(s: str) -> str:
    """`//` und `/* */` raus — sonst prueft der Test die Begruendung (F13)."""
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


def _dateien():
    for p in sorted(WEB.rglob("*")):
        if p.suffix in (".ts", ".tsx") and "node_modules" not in p.parts and ".next" not in p.parts:
            yield p


def test_nur_ein_modul_kennt_den_schluessel_woertlich():
    """Eine kopierte Konstante trennt den Schreiber von der Pflicht, die daneben steht."""
    kopien = []
    for p in _dateien():
        rel = str(p.relative_to(WEB))
        if rel == EIGENTUEMER or rel in AUSNAHMEN:
            continue
        code = _ohne_kommentar(p.read_text(encoding="utf-8"))
        for m in re.finditer(rf'(const|let|var)\s+\w+\s*=\s*["\']{re.escape(SCHLUESSEL)}["\']', code):
            kopien.append(f"{rel}: {m.group(0)}")
    assert not kopien, (
        f"{len(kopien)} eigene Kopien des Profil-Schluessels. Sie gehoert aus "
        f"`{EIGENTUEMER}` importiert, damit `profilGeaendert` danebensteht.\n  "
        + "\n  ".join(kopien))


def test_jeder_schreiber_loest_das_signal_aus():
    """⚠ Geprueft wird ein FENSTER von acht Zeilen nach dem Zugriff, nicht die ganze Datei.

    Sonst genuegt ein `profilGeaendert()` irgendwo weit entfernt, um den Test gruen zu
    halten — und genau der Fall ist der gefaehrliche: eine Datei mit zwei Schreibstellen,
    von denen nur eine meldet.
    """
    stumm = []
    for p in _dateien():
        rel = str(p.relative_to(WEB))
        if rel == EIGENTUEMER:
            continue                      # der Eigentuemer setzt den Zustand selbst
        zeilen = _ohne_kommentar(p.read_text(encoding="utf-8")).splitlines()
        for i, z in enumerate(zeilen):
            if not re.search(r"localStorage\.(setItem|removeItem)\s*\(\s*PROFILE_KEY", z):
                continue
            # ⚠ ACHT NICHT-LEERE ZEILEN, nicht acht Zeilen. `_ohne_kommentar` laesst
            #   Kommentare als Leerzeilen stehen (damit Zeilennummern stimmen); ein
            #   siebenzeiliger Kommentar zwischen Zugriff und Meldung schob den Aufruf
            #   sonst aus dem Fenster — beim Schreiben dieses Tests genau so passiert.
            rest = [z2 for z2 in zeilen[i:i + 30] if z2.strip()]
            fenster = "\n".join(rest[:8])
            if "profilGeaendert()" not in fenster:
                stumm.append(f"{rel}:{i + 1}  {z.strip()[:70]}")
    assert not stumm, (
        f"{len(stumm)} Schreibzugriffe auf das Profil melden sich nicht. Der Kopf behaelt "
        f"dann den alten Firmennamen, bis jemand die Seite neu laedt.\n  "
        + "\n  ".join(stumm))
