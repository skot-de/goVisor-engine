"""Eine Kennung, die der geladene Grundraum nicht enthält, darf das Detail nicht öffnen.

⚠ DER FEHLER, gegen den diese Datei steht (bis 2026-09-02 in der Konsole):

    Uncaught TypeError: Cannot read properties of undefined (reading 'sprachen')

Aufgefallen ist er in `DetailPanel.tsx` beim ersten Feldzugriff. Dort saß er aber nicht.
`LEADS` trägt immer nur EINEN Grundraum (`/api/leads?branche=…`), während Kennungen auch
von ausserhalb kommen: der Vergabe-Verlauf einer Vergabestelle (`data-openlead`, gespeist
aus `buyer_recent_awards` über ALLE Branchen) und der `?lead=`-Deep-Link. `openLead` setzte
`activeId` unbedingt — auch auf eine Kennung, die es nicht auflösen konnte. Das Detail löste
sie gegen `LEADS` auf, bekam `undefined` und stürzte ab. Die Ursache ist die Zeile, die den
unmöglichen Zustand ERZEUGT, nicht die, an der er auffällt.

Deshalb prüft diese Datei drei Dinge, und zwar in dieser Reihenfolge:
  1. das Tor in `openLead` (die Ursache),
  2. dass `DetailPanel` die Auflösung nicht mehr per `!` behauptet (die Fundstelle),
  3. dass der Leerzustand auch VERDRAHTET ist — die häufigste Fehlerklasse hier ist ein
     korrekter Baustein, den niemand aufruft (s. CLAUDE.md).
"""
from __future__ import annotations

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
WEB = WURZEL / "web"
SHELL = (WEB / "components" / "explorer" / "ExplorerShell.tsx").read_text(encoding="utf-8")
PANEL = (WEB / "components" / "explorer" / "DetailPanel.tsx").read_text(encoding="utf-8")


def _funktion(quelle: str, kopf: str) -> str:
    """Rumpf einer Funktion ab ihrem Kopf bis zur schliessenden Klammer auf gleicher Ebene.

    ⚠ Nicht bis zum nächsten `}` — der Rumpf enthält Blöcke. Und nicht die ganze Datei
    durchsuchen: sonst schlägt der Test auf einer ANDEREN Funktion an, die zufällig das
    Gesuchte enthält, und meldet grün, wo nichts geprüft wurde.
    """
    start = quelle.index(kopf)
    # ⚠ Erst die Parameterliste überspringen. Sonst zählt bei `({ id, onClose })` die
    # Destrukturierung als Rumpf — der Test prüft dann drei Wörter statt der Funktion.
    p = quelle.index("(", start)
    tiefe = 0
    for j in range(p, len(quelle)):
        if quelle[j] == "(":
            tiefe += 1
        elif quelle[j] == ")":
            tiefe -= 1
            if tiefe == 0:
                p = j
                break
    i = quelle.index("{", p)
    tiefe = 0
    for j in range(i, len(quelle)):
        if quelle[j] == "{":
            tiefe += 1
        elif quelle[j] == "}":
            tiefe -= 1
            if tiefe == 0:
                return quelle[start:j + 1]
    raise AssertionError(f"Funktionsrumpf zu {kopf!r} nicht abgeschlossen")


def _ohne_kommentar(text: str) -> str:
    """⚠ Kommentare raus, sonst schlägt der Test an der BEGRÜNDUNG an — die zitiert den
    kaputten Code, um zu erklären, warum er weg ist. Dieselbe Falle wie in
    `test_aktivierung_d.py`."""
    raus, im_block = [], False
    for z in text.splitlines():
        t = z.strip()
        if t.startswith("/*"):
            im_block = True
        if im_block:
            if "*/" in t:
                im_block = False
            continue
        if t.startswith("//") or t.startswith("*"):
            continue
        raus.append(z)
    return "\n".join(raus)


# ── 1. Die Ursache: das Tor in openLead ──────────────────────────────────────────────

def test_openlead_oeffnet_nur_was_es_aufloesen_kann():
    """⚠ DER KERN. Ohne diese Prüfung geht `setActiveId(id)` auch für eine Kennung durch,
    die `LEADS` nicht kennt — und genau daraus entsteht der TypeError im Detail."""
    code = _ohne_kommentar(_funktion(SHELL, "function openLead(id: string)"))

    # Der Lead wird nachgeschlagen …
    assert "CORE.find((x) => x.id === id)" in code

    # … und der Fehlschlag BRICHT AB, statt weiterzulaufen.
    tor = re.search(r"if \(!l\)[^\n]*\breturn\b", code)
    assert tor, ("`openLead` hat kein Tor für den nicht auflösbaren Lead — "
                 "erwartet wird ein `if (!l) { … return; }`")

    # Reihenfolge ist der ganze Punkt: das Tor muss VOR dem Setzen des Zustands stehen.
    setzt = code.index("setActiveId(id)")
    assert tor.start() < setzt, ("Das Tor steht hinter `setActiveId(id)` — dann ist der "
                                 "unmögliche Zustand bereits gesetzt.")


def test_die_unbekannte_kennung_landet_nicht_in_activeid():
    """`activeId` ist der Schlüssel, mit dem das Detail in `LEADS` sucht. Eine Kennung, die
    dort nicht liegt, gehört deshalb in einen EIGENEN Zustand — nicht in `activeId` mit
    einem Sonderfall drumherum."""
    code = _ohne_kommentar(_funktion(SHELL, "function openLead(id: string)"))
    kopf = code[:code.index("setActiveId(id)")]
    assert "setFehlenderLead(id)" in kopf
    assert "setActiveId(null)" in kopf


def test_der_deeplink_verschluckt_die_kennung_nicht_mehr():
    """Ein `?lead=<fremde-id>` war vorher wirkungslos: die Liste stand da wie ohne Parameter,
    ohne jeden Hinweis. Sobald der angefragte Grundraum geladen ist, muss es gesagt werden."""
    code = _ohne_kommentar(SHELL)
    assert "dl.branche" in code, "Der Deep-Link merkt sich den angefragten Grundraum nicht"
    stelle = code[code.index("deepRef.current = { lead"):]
    stelle = stelle[:stelle.index("aktiveBranche, bump]")]
    assert "setFehlenderLead(dl.lead)" in stelle


# ── 2. Die Fundstelle: keine behauptete Auflösung mehr ───────────────────────────────

def test_detailpanel_behauptet_den_lead_nicht_mehr():
    """⚠ `find(…)!` war eine Behauptung, keine Prüfung: das Ausrufezeichen versprach dem
    Compiler etwas, was die Datenlage nicht hergibt. Genau dadurch war der Absturz für
    `tsc` unsichtbar."""
    code = _ohne_kommentar(PANEL)
    assert "x.id === activeId)!" not in code, (
        "Die Auflösung von `activeId` gegen LEADS behauptet wieder ein Ergebnis (`!`)")
    assert "const l = (LEADS as Lead[]).find((x) => x.id === activeId);" in code

    # Und der Fehlschlag hat einen eigenen Zweig, statt in den Feldzugriff zu laufen.
    kopf = code[:code.index(".sprachen")]
    assert re.search(r"if \(!l\) return <NichtGeladen", kopf), (
        "Kein Zweig für den nicht gefundenen Lead vor dem ersten Feldzugriff")


def test_kein_optional_chaining_als_pflaster():
    """Der Absturz war mit `l?.sprachen` in einer Zeile zu verstecken. Dann rendert das Panel
    eine leere Hülle zu einer Ausschreibung, die es nicht hat — schlimmer als der Fehler,
    weil niemand es merkt."""
    code = _ohne_kommentar(PANEL)
    assert "l?.sprachen" not in code
    assert "l?.titel" not in code


# ── 3. Verdrahtung: gebaut UND aufgerufen ────────────────────────────────────────────

def test_der_leerzustand_ist_verdrahtet():
    """Die häufigste Fehlerklasse in diesem Projekt: der Baustein stimmt, nur ruft ihn
    niemand auf. `NichtGeladen` nützt nichts, wenn die Shell den Zustand nicht durchreicht."""
    assert "function NichtGeladen(" in PANEL
    assert "fehlenderLead?: string | null;" in PANEL, "Das Panel nimmt den Zustand nicht an"
    assert "fehlenderLead={fehlenderLead}" in SHELL, "Die Shell reicht den Zustand nicht durch"

    # Der Zustand muss auch wieder verschwinden — sonst bleibt die Meldung stehen, während
    # daneben längst ein Lead offen ist.
    for weg in ("function closeLead()", "function setBranche(k: string)"):
        assert "setFehlenderLead(null)" in _funktion(SHELL, weg), (
            f"{weg} räumt die Meldung nicht weg")


def test_die_meldung_sagt_was_los_ist():
    """Ein verschluckter Klick lässt die Zeile im Käufer-Verlauf kaputt aussehen. Die Meldung
    muss den Grund nennen UND den Weg — der Lead existiert ja, nur in einem anderen
    Grundraum."""
    rumpf = _funktion(PANEL, "function NichtGeladen(")
    assert "Grundraum" in rumpf
    assert "{id}" in rumpf, "Die Meldung nennt die Kennung nicht, über die sie spricht"
