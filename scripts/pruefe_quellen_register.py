#!/usr/bin/env python3
"""Sonde: hält `sources.REGISTRY` ehrlich — was gebaut ist, muss auch laufen.

⚠ **WARUM ES DIESE SONDE GIBT.** Am 2026-10-05 fragte Sven, warum wir nicht längst jedes
bekannte Portal anschliessen. Die Antwort war überwiegend gut (von 105 nicht angeschlossenen
Quellen liefern 66 gar keine Bekanntmachungen und 27 nur TED-Dubletten) — bis auf einen Fall:

    cosinex-de  ·  status="prepared"  ·  seit 2026-08-14
    Modul fertig (hole/schreibe_bronze/nach_silber/main), Nutzen GEMESSEN und im Register
    notiert: 23,5 % der Bekanntmachungen neu, bei Rheinland-Pfalz 48 %.
    Im Tageslauf kam "cosinex" nur beim UNTERLAGEN-Abruf vor.
    Gegenprobe: zwei Seiten je Division, nur NRW → 966 neue Bekanntmachungen.

Sieben Wochen, und aufgefallen ist es durch eine Frage, nicht durch eine Prüfung. Das ist
die Fehlerklasse, die CLAUDE.md als unsere häufigste führt — „gebaut, aber nicht verdrahtet"
— diesmal nicht an einer Kennzahl, sondern am Bestand selbst.

⚠ **ZWEITER BEFUND, der beim Bauen auffiel: das Register trägt KEIN DATUM.** Es gibt kein
Feld, das sagt, wann ein Status gesetzt oder zuletzt nachgeprüft wurde. Deshalb kann ein
Urteil beliebig lange stehen, ohne zu altern — und ein Messfehler versteinert. Beispiel vom
selben Tag: `vergabe-westfalen.de` galt als „nicht erreichbar"; die Adresse braucht nur
`www.`. Diese Sonde kann das Alter deshalb NICHT prüfen; sie meldet stattdessen, wie viele
Quellen kein Prüfdatum tragen. Wer das schliessen will, braucht ein Feld `geprueft` in
`Source`.

Aufruf:

    python3 scripts/pruefe_quellen_register.py            # schnell, ohne Netz
    python3 scripts/pruefe_quellen_register.py --netz     # zusätzlich Erreichbarkeit

⚠ `--netz` fragt fremde Portale. Ein Abruf je Host, mit Pause und sprechendem User-Agent.
Er gehört NICHT in den Minutentakt; im Wächterlauf höchstens wöchentlich.

Rückgabe 0 = sauber, 1 = Fund.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from govisor import sources  # noqa: E402

LAUF = ROOT / "scripts" / "daily_leads.sh"

# Bewusst ruhende Quellen — id → Begründung.
#
# ⚠ DIESE LISTE IST DER GEFÄHRLICHE TEIL DER SONDE. Jeder Eintrag schaltet eine Meldung ab,
# und genau so ist cosinex sieben Wochen unsichtbar geblieben. Deshalb: nur mit Begründung,
# und `tests/test_quellen_register.py` lässt keinen Eintrag für eine Quelle zu, die es nicht
# mehr gibt oder die inzwischen `live` ist. Wer hier etwas einträgt, verschiebt eine
# Entscheidung — er erledigt sie nicht.
#
# ⚠ Und der Grund, warum es sie trotzdem geben muss: ein Riegel, der ohne Aussicht auf Grün
# rot leuchtet, wird nach der dritten Nacht überlesen. Dann nützt auch der berechtigte Fall
# nichts mehr.
RUHT_BEWUSST: dict[str, str] = {
    "ted-pl": "Polen liegt mit 326.485 Bekanntmachungen in Silber OHNE Gold — angefangen "
              "und liegengeblieben, in CLAUDE.md als Baustelle `BEWUSST_OHNE_GOLD` geführt. "
              "Einschalten heisst hier nicht „Schritt ergänzen“, sondern die Gold-Kette für "
              "PL bauen.",
}

fehler = 0
hinweise = 0


def klage(s: str) -> None:
    global fehler
    print(f"  ✗ {s}")
    fehler += 1


def hinweis(s: str) -> None:
    global hinweise
    print(f"  · {s}")
    hinweise += 1


def gut(s: str) -> None:
    print(f"  ✓ {s}")


def _lauftext() -> str:
    """Der Tageslauf OHNE Kommentare.

    ⚠ Sonst meldet die Sonde eine Quelle als verdrahtet, weil ihr Name in einem Kommentar
    steht — genau der Fehler, den `waechter-messen-prosa-statt-code` beschreibt. Bei cosinex
    wäre das passiert: der Name stand im Unterlagen-Abschnitt, der Aufruf fehlte.
    """
    roh = LAUF.read_text(encoding="utf-8")
    ohne = []
    for z in roh.splitlines():
        s = z.lstrip()
        if s.startswith("#"):
            continue
        ohne.append(z.split(" #")[0] if " #" in z else z)
    return "\n".join(ohne)


def _stamm(connector: str) -> str:
    """`cosinex-html` → `cosinex`. Der Modulname folgt in diesem Projekt dem Connector-Stamm."""
    return re.split(r"[-_]", connector or "", maxsplit=1)[0].lower()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--netz", action="store_true", help="zusätzlich Erreichbarkeit prüfen")
    p.add_argument("--selbstprobe", action="store_true",
                   help="beweist, dass Zusicherung a) ein gepflanztes Leck findet")
    a = p.parse_args(argv)

    R = list(sources.REGISTRY)
    text = _lauftext()
    bm = [s for s in R if getattr(s, "ebene", "bekanntmachung") == "bekanntmachung"]

    # ── a) VERDRAHTUNG: was live ist, muss aufgerufen werden ─────────────────────────────
    live = [s for s in bm if s.status == "live"]
    tot = [s for s in live if _stamm(s.connector) not in text.lower()]
    if a.selbstprobe:
        # Gepflanztes Leck: eine Quelle, deren Stamm garantiert nirgends steht.
        probe = sources.Source("probe-xy", "Selbstprobe", "garnichtvorhanden-html", "DE",
                               "beides", "live")
        if _stamm(probe.connector) in text.lower():
            klage("SELBSTPROBE GESCHEITERT: der erfundene Connector wurde im Lauf gefunden")
        else:
            gut("Selbstprobe: eine nicht aufgerufene Quelle wird erkannt")
    if tot:
        for s in tot:
            klage(f"{s.id} steht auf 'live', wird im Tageslauf aber NICHT aufgerufen "
                  f"(Connector {s.connector}) — gebaut, nicht verdrahtet")
    else:
        gut(f"alle {len(live)} Bekanntmachungs-Quellen mit Status 'live' werden aufgerufen")

    # ── b) STILLSTAND: gebaut, aber nie eingeschaltet ────────────────────────────────────
    ruht = [s for s in bm if s.status == "prepared"]
    offen_ruhend = [s for s in ruht if s.id not in RUHT_BEWUSST]
    for s in ruht:
        if s.id in RUHT_BEWUSST:
            hinweis(f"{s.id} ruht bewusst: {RUHT_BEWUSST[s.id]}")
    if offen_ruhend:
        for s in offen_ruhend:
            nutzen = (s.overlap or s.coverage or "")[:110]
            klage(f"{s.id} steht auf 'prepared' — gebaut und nicht eingeschaltet."
                  f"{(' Gemessener Nutzen: ' + nutzen) if nutzen else ''}")
    else:
        gut(f"keine Bekanntmachungs-Quelle ruht unbegründet "
            f"({len(ruht)} 'prepared', davon {len(ruht)} begründet)")

    # ── c) ALTER: kann diese Sonde NICHT prüfen, und das muss sichtbar bleiben ───────────
    ohne_datum = [s for s in R if not hasattr(s, "geprueft")]
    if ohne_datum:
        hinweis(f"{len(ohne_datum)} von {len(R)} Quellen tragen kein Prüfdatum — ein Urteil "
                f"im Register altert nicht. Ohne ein Feld `geprueft` in `Source` kann keine "
                f"Sonde melden, dass eine Einschätzung veraltet ist.")

    # ── d) NETZ (freiwillig): erreichbar? Und ist 'nicht erreichbar' wirklich wahr? ──────
    if a.netz:
        import urllib.request
        import urllib.error
        UA = "goVisor-Quellenpruefung/1.0 (+https://govisor.eu)"
        kand = [s for s in bm if s.url and s.status in ("prepared", "candidate", "research")]
        print(f"\n  Netzprüfung über {len(kand)} Quellen (ein Abruf je Host, 1,5 s Pause):")
        for s in kand:
            try:
                req = urllib.request.Request(s.url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=20) as r:
                    code, roh = r.status, r.read(40000)
            except urllib.error.HTTPError as e:
                code, roh = e.code, b""
            except Exception as e:                       # DNS, TLS, Zeitüberschreitung
                hinweis(f"{s.id}: nicht erreichbar ({type(e).__name__}) — {s.url}")
                time.sleep(1.5)
                continue
            # ⚠ WARTUNG IST KEINE SPERRE. Am 2026-10-05 lieferte vergabe-westfalen.de eine
            # 92-KB-Seite "Seite wg. Wartungsarbeiten nicht erreichbar" mit HTTP 200. Wer
            # das als Sperre einträgt, versteinert einen Zufall.
            txt = roh.decode("utf-8", "replace").lower()
            if "wartungsarbeit" in txt or "maintenance" in txt:
                hinweis(f"{s.id}: HTTP {code}, aber WARTUNGSSEITE — kein Urteil ableiten")
            elif code == 200:
                hinweis(f"{s.id}: erreichbar (HTTP 200) — Status ist '{s.status}'")
            else:
                hinweis(f"{s.id}: HTTP {code}")
            time.sleep(1.5)

    print()
    if fehler:
        print(f"⛔ {fehler} Fund(e), {hinweise} Hinweis(e).")
    else:
        print(f"✓ Quellenregister sauber. {hinweise} Hinweis(e).")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
