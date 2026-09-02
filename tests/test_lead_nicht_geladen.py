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
# ⚠ Nachsichtig lesen, damit eine FEHLENDE Route den betroffenen Test rot macht statt die
# ganze Datei beim Einsammeln zu sprengen. Sonst nimmt ein geloeschter Endpunkt auch die
# zwoelf Pruefungen mit, die mit ihm nichts zu tun haben — und die Meldung sagt „Import-
# fehler" statt „der Endpunkt fehlt".
_R = WEB / "app" / "api" / "lead-branche" / "route.ts"
ROUTE = _R.read_text(encoding="utf-8") if _R.exists() else ""
INDEX = (WEB / "lib" / "leadIndex.ts").read_text(encoding="utf-8")
MIDDLEWARE = (WEB / "middleware.ts").read_text(encoding="utf-8")
EXPORT = (WURZEL / "scripts" / "export_web_leads.py").read_text(encoding="utf-8")


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
    assert "holeFremdenLead(id)" in kopf
    hole = _ohne_kommentar(_funktion(SHELL, "async function holeFremdenLead"))
    assert "setActiveId(null)" in hole


# ── 2. Das Nachladen: der Klick landet dort, wo der Lead liegt ───────────────────────

def test_der_fremde_grundraum_wird_nachgeschlagen_und_gewechselt():
    """⚠ DER KERN DIESER STUFE. Im Käufer-Verlauf ist der Sprung in einen anderen Grundraum
    der Normalfall, nicht die Ausnahme (`buyer_recent_awards` läuft über alle Branchen).
    Dem Nutzer aufzutragen, was wir selbst tun können, ist eine halbe Antwort."""
    hole = _ohne_kommentar(_funktion(SHELL, "async function holeFremdenLead"))
    assert "/api/lead-branche?id=" in hole, "Es wird gar nicht nachgeschlagen"
    assert "encodeURIComponent(id)" in hole, "Kennung ungeschützt in die URL"
    assert "setAktiveBranche(branche)" in hole, "Es wird nachgeschlagen, aber nicht gewechselt"
    # Der Vermerk, der das Öffnen nach dem Laden auslöst — sonst wechselt die Ansicht den
    # Grundraum und der Lead bleibt trotzdem zu.
    assert "deepRef.current = { lead: id" in hole


def test_das_nachladen_dreht_sich_nicht_im_kreis():
    """⚠ Verortet der Server die Kennung im BEREITS geladenen Grundraum, wäre ein Wechsel
    dorthin eine Schleife, die nie ankommt: laden, nicht finden, nachschlagen, laden …"""
    hole = _ohne_kommentar(_funktion(SHELL, "async function holeFremdenLead"))
    m = re.search(r"if \(!branche \|\| branche === aktiveBranche\)[^\n]*return", hole)
    assert m, "Kein Abbruch, wenn der Server auf den geladenen Grundraum zeigt"
    assert m.start() < hole.index("setAktiveBranche(branche)"), (
        "Der Abbruch steht hinter dem Wechsel — die Schleife läuft trotzdem an")


def test_eine_spaete_antwort_reisst_den_nutzer_nicht_heraus():
    """⚠ Zwischen Klick und Antwort kann der Nutzer längst etwas anderes offen haben. Eine
    verspätete Antwort würde ihn dann in einen Grundraumwechsel reissen, den er nicht mehr
    wollte — und er hat nichts angefasst."""
    hole = _ohne_kommentar(_funktion(SHELL, "async function holeFremdenLead"))
    assert "++fremdMarke.current" in hole, "Kein Merkmal, an dem eine alte Antwort erkennbar wäre"
    m = re.search(r"if \(marke !== fremdMarke\.current\) return", hole)
    assert m, "Die Marke wird gesetzt, aber nie geprüft"
    assert m.start() < hole.index("setAktiveBranche(branche)"), (
        "Die Prüfung steht hinter dem Wechsel und kommt zu spät")
    # Ein Wechsel VON HAND muss die fliegende Antwort ebenfalls entwerten.
    assert "fremdMarke.current++" in _funktion(SHELL, "function fremdAbbrechen()")
    for weg in ("function setBranche(k: string)", "function resetBranche()"):
        assert "fremdAbbrechen()" in _funktion(SHELL, weg), f"{weg} bricht das Nachladen nicht ab"


def test_der_deeplink_geht_denselben_weg():
    """Ein `?lead=` ohne `?branche=` war vorher nur so gut wie die Kenntnis des Absenders:
    wer den Grundraum nicht mitschickte, verschickte einen toten Link."""
    code = _ohne_kommentar(SHELL)
    assert "dl.branche" in code, "Der Deep-Link merkt sich den angefragten Grundraum nicht"
    stelle = code[code.index("deepRef.current = { lead, tab"):]
    stelle = stelle[:stelle.index("aktiveBranche, bump]")]
    assert "holeFremdenLead(dl.lead, dl.tab)" in stelle, (
        "Der Deep-Link hat einen eigenen Weg statt des gemeinsamen")


def test_der_endpunkt_gibt_nur_den_grundraum_heraus():
    """⚠ Eine Route, die den LEAD selbst lieferte, wäre ein zweiter Weg an dieselben Daten —
    vorbei an der Redaktion je Tarif in `/api/lead-detail`, und jede Gate-Regel müsste dort
    noch einmal nachgebaut werden."""
    assert ROUTE, "Es gibt keinen Endpunkt `/api/lead-branche` — ohne ihn kann die Anwendung "\
                  "nicht wissen, welchen Grundraum sie laden soll"
    code = _ohne_kommentar(ROUTE)
    assert "leadBranchen()" in code
    assert "{ branche }" in code
    for verboten in ("titel", "beschreibung", "loadDataFile", "lead-detail"):
        assert verboten not in code, f"Die Route reicht mehr heraus als den Grundraum: {verboten}"
    # Nicht in OFFEN → hinter dem Anmelde-Tor, wie /api/leads auch.
    assert '"/api/lead-branche"' not in MIDDLEWARE, "Der Endpunkt steht offen"


def test_der_index_nimmt_den_billigen_weg_zuerst():
    """⚠ Der Rückfall liest sieben Dateien à 110 MB — in einem ANFRAGEPFAD, nicht in einem
    Nachtlauf. Er muss existieren (sonst ist das Nachladen bis zum nächsten Export tot),
    aber er muss sich auch melden."""
    code = _ohne_kommentar(INDEX)
    assert code.index("brancheAusSchlankerDatei()") < code.index("brancheAusAllenBranchen()")
    rueck = _funktion(INDEX, "async function brancheAusAllenBranchen")
    assert "console.error" in rueck, "Der teure Rückfall läuft still"

    schlank = _funktion(INDEX, "async function brancheAusSchlankerDatei")
    # ⚠ Ein Export von VOR dieser Änderung hat das Feld nicht. Ohne diese Prüfung entstünde
    # ein Index, der zu JEDER Kennung „kein Grundraum" sagt — das sähe aus wie eine Antwort.
    assert 'typeof arr[0]?.branche !== "string"' in schlank, (
        "Ein Export ohne `branche` würde als leerer Index durchgehen")

    # Und der Index darf nicht bei jeder Anfrage neu gebaut werden.
    assert "ausSpeicher" in code and "inSpeicher" in code


def test_der_export_traegt_den_grundraum():
    """Gebaut, aber nicht verdrahtet — die häufigste Fehlerklasse hier. Der schnelle Weg im
    Index existiert nur, wenn der Export das Feld auch schreibt."""
    block = EXPORT[EXPORT.index("def _frist_zeile"):EXPORT.index("def export_branche")]
    assert '"branche": branche' in block
    assert "_frist_zeile(l, key)" in EXPORT, "Der Grundraum wird nicht mitgegeben"


# ── 3. Die Fundstelle: keine behauptete Auflösung mehr ───────────────────────────────

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
    assert re.search(r"if \(!l\) return <FremderGrundraum", kopf), (
        "Kein Zweig für den nicht gefundenen Lead vor dem ersten Feldzugriff")


def test_kein_optional_chaining_als_pflaster():
    """Der Absturz war mit `l?.sprachen` in einer Zeile zu verstecken. Dann rendert das Panel
    eine leere Hülle zu einer Ausschreibung, die es nicht hat — schlimmer als der Fehler,
    weil niemand es merkt."""
    code = _ohne_kommentar(PANEL)
    assert "l?.sprachen" not in code
    assert "l?.titel" not in code


# ── 4. Verdrahtung: gebaut UND aufgerufen ────────────────────────────────────────────

def test_der_leerzustand_ist_verdrahtet():
    """Die häufigste Fehlerklasse in diesem Projekt: der Baustein stimmt, nur ruft ihn
    niemand auf. `FremderGrundraum` nützt nichts, wenn die Shell den Zustand nicht durchreicht."""
    assert "function FremderGrundraum(" in PANEL
    assert 'stand: "sucht" | "wechselt" | "unbekannt"' in PANEL, "Das Panel nimmt den Zustand nicht an"
    assert "fremderLead={fremderLead}" in SHELL, "Die Shell reicht den Zustand nicht durch"

    # Der Zustand muss auch wieder verschwinden — sonst bleibt die Meldung stehen, während
    # daneben längst ein Lead offen ist.
    assert "setFremderLead(null)" in _funktion(SHELL, "function closeLead()")
    assert "setFremderLead(null)" in _funktion(SHELL, "function fremdAbbrechen()")


def test_warten_sieht_nicht_aus_wie_scheitern():
    """⚠ Der Grundraumwechsel lädt bis zu 42 MB, das dauert sichtbar. Wäre das Warten
    derselbe Zustand wie „gibt es nicht", stünde sekundenlang eine Absage auf dem Schirm,
    die sich danach als falsch herausstellt — und wer vorher wegklickt, hat eine Fehlmeldung
    gelesen."""
    rumpf = _funktion(PANEL, "function FremderGrundraum(")
    assert 'lead.stand !== "unbekannt"' in rumpf, "Warten und Scheitern sind derselbe Zweig"
    # Das Warten sagt, WOHIN es geht — sonst ist es nur ein Spinner.
    assert "{raum}" in rumpf
    assert "BRANCHEN" in rumpf, "Der Grundraum wird als roher Schlüssel gezeigt, nicht als Name"
    # Nur der Endzustand bekommt den Ausweg; ein „Zurück" mitten im Laden bricht etwas ab,
    # was gleich von selbst fertig ist. Geprüft wird der ZWEIG, nicht die Funktion: `onClose`
    # steht auch in der Parameterliste, und daran wäre die Prüfung sonst hängengeblieben.
    warte = rumpf[rumpf.index('lead.stand !== "unbekannt"'):]
    warte = warte[:warte.index("return (", warte.index("}\n\n  return ("))]
    assert "onClick={onClose}" not in warte, "Der Wartezustand bietet schon einen Ausweg an"
    assert "onClick={onClose}" in rumpf, "Der Endzustand hat keinen Ausweg"
    assert "{id}" in rumpf, "Die Meldung nennt die Kennung nicht, über die sie spricht"
