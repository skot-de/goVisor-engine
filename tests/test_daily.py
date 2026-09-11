"""Der Tageslauf — Zahlen im Skript gegen das, was die Protokolle wirklich sagen.

Ein Sicherheitsabstand, der aus einer Messung stammt, altert mit der Messung. `daily_leads.sh`
reserviert Zeit für die Auswertung („Ernte") und begründet das mit einer ausgezählten Tabelle.
Am 2026-08-30 war die Tabelle über einen Monat alt, zählte 7 der inzwischen 10 Schritte, und
die Reserve lag mit dem **0,91-fachen** der gemessenen Erntezeit unter dem, was sie decken
sollte — sie war gar keine Reserve mehr.

⚠ Aufgefallen ist das nicht im Betrieb. Die Läufe blieben mit 87 bis 184 Minuten weit unter
der 8-Stunden-Grenze, die Reserve wurde also nie geprüft. Sie hätte beim ersten langen Abruf
gegriffen — und genau dann versagt. Diese Sorte Fehler meldet sich erst im Ernstfall.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LAUF = ROOT / "scripts" / "daily_leads.sh"
LOGS = ROOT / "data" / "logs"

# Wie viel Luft die Reserve über dem gemessenen schlimmsten Fall haben muss. Das Skript
# begründet sie mit „dem Doppelten"; der Test verlangt 1,5× — er soll melden, wenn der
# Abstand schmilzt, nicht schon beim ersten Ausreisser rot werden.
MINDEST_FAKTOR = 1.5
# Wie viele Läufe angesehen werden. Zu wenige, und ein einzelner kurzer Lauf redet die
# Ernte klein; zu viele, und längst behobene Ausreisser halten die Zahl künstlich hoch.
LAEUFE = 8


def _erntesc_hritte() -> list[str]:
    """Die Schritte hinter der Marke „AB HIER: AUSWERTUNG" — das, was die Reserve deckt.

    Aus dem Skript gelesen, nicht abgeschrieben: genau daran ist die alte Tabelle
    gescheitert (sie kannte `Dokument-Dubletten` nicht, 18 min).
    """
    zeilen = LAUF.read_text(encoding="utf-8").splitlines()
    # ⚠ AUF DIE TRENNZEILE ANKERN, nicht auf den Wortlaut. Die Begruendung der Reserve
    # ZITIERT die Marke im Kommentar — ein `"AB HIER: AUSWERTUNG" in z` findet deshalb
    # zuerst den Kommentar, und der steht 600 Zeilen VOR der Stelle. Der Test maass damit
    # den halben Nachtlauf als Ernte und meldete 179 statt 99 min. Ein Waechter, der die
    # falsche Menge misst, ist schlimmer als keiner: seine Zahl sieht benutzbar aus.
    marke = [i for i, z in enumerate(zeilen) if z.startswith("# ══ AB HIER: AUSWERTUNG")]
    assert len(marke) == 1, f"Marke nicht eindeutig: {len(marke)} Treffer"
    # Nur Schritte auf oberster Ebene (`step "…"` ohne Einrueckung) — eingerueckte stehen
    # in Bedingungen und Schleifen und laufen nicht zwingend.
    return [m.group(1) for z in zeilen[marke[0]:]
            if (m := re.match(r'step "(.+)"$', z))]


def _ernte_minuten() -> list[float]:
    """Erntezeit je Lauf, aus den Protokollen ausgezählt."""
    schritte = _erntesc_hritte()
    aus = []
    for log in sorted(LOGS.glob("daily-*.log"), reverse=True)[:LAEUFE]:
        text = log.read_text(encoding="utf-8", errors="replace")
        s = sum(int(m.group(1))
                for name in schritte
                if (m := re.search(rf"⏱ {re.escape(name)} — (\d+)s", text)))
        if s:
            aus.append(s / 60)
    return aus


def test_die_erntesc_hritte_werden_ueberhaupt_gefunden():
    """Ohne diesen Test wäre der Wächter darunter geräuschlos wirkungslos.

    Findet die Marke oder das `step "…"`-Muster nicht mehr, käme eine leere Liste heraus —
    und eine leere Liste besteht jede Schwellenprüfung. Genau so verschwindet ein Test,
    ohne dass jemand ihn löscht.
    """
    schritte = _erntesc_hritte()
    assert len(schritte) >= 8, f"nur {len(schritte)} Erntesc hritte erkannt: {schritte}"
    assert "Frontend-Daten exportieren (web/data)" in schritte, \
        "der Frontend-Export liegt nicht mehr in der Ernte — stimmt die Marke noch?"


@pytest.mark.skipif(not LOGS.exists() or not list(LOGS.glob("daily-*.log")),
                    reason="keine Tageslauf-Protokolle (frische Arbeitskopie)")
def test_ernte_reserve_deckt_die_gemessene_ernte():
    """Die reservierte Zeit muss über der wirklich gebrauchten liegen — mit Abstand.

    Der Sinn der Reserve: bevor ein Abrufschritt startet, prüft der Lauf, ob danach noch
    genug Zeit bis zur Gesamtgrenze bleibt, um aus den Daten das Produkt zu machen. Ist sie
    zu klein, wird der Lauf mitten in der Auswertung abgeschnitten — also genau dann, wenn
    er sich gerade gelohnt hätte, weil der Abruf viel gebracht hat.
    """
    quelle = LAUF.read_text(encoding="utf-8")
    m = re.search(r"ERNTE_RESERVE=\$\{GOVISOR_ERNTE_RESERVE:-(\d+)\}", quelle)
    assert m, "ERNTE_RESERVE steht nicht mehr in der erwarteten Form im Skript"
    reserve = int(m.group(1)) / 60

    gemessen = _ernte_minuten()
    assert gemessen, "keine Erntezeiten in den Protokollen gefunden — Format geaendert?"
    schlimmster = max(gemessen)

    assert reserve >= schlimmster * MINDEST_FAKTOR, (
        f"Die Ernte-Reserve deckt die Wirklichkeit nicht mehr:\n"
        f"  reserviert          {reserve:.0f} min\n"
        f"  gemessen (schlimmster von {len(gemessen)} Laeufen)  {schlimmster:.0f} min\n"
        f"  Faktor              {reserve / schlimmster:.2f}×  (verlangt: {MINDEST_FAKTOR}×)\n"
        f"  Werte: {', '.join(f'{x:.0f}' for x in sorted(gemessen))}\n"
        f"Entweder die Reserve erhoehen oder einen Erntesc hritt guenstiger machen.")


# ── Zwischenzeiten im Frontend-Export ───────────────────────────────────────────────

def _frontend_block() -> str:
    quelle = LAUF.read_text(encoding="utf-8")
    return quelle.split('step "Frontend-Daten exportieren')[1].split('step "')[0]


def test_jedes_skript_im_frontend_export_wird_gemessen():
    """⚠ Zehn Skripte lagen unter EINER Zeitmessung. Am 2026-09-03 stand dafür eine einzige
    Zahl im Protokoll (Median 575 s), und „welches davon" war nur durch Subtraktion zu
    beantworten — sechs von Hand messen, den Rest ausrechnen. Das Ergebnis war eine
    Schätzung mit Fehlerbalken, wo eine Messung hätte stehen können."""
    import re
    # ⚠ ZEILENWEISE, NICHT MIT RUECKSCHAU. `(?<!teil )` prueft die vier Zeichen direkt vor
    # `$PY` — dort steht aber der Skriptname, nicht `teil`. Das Muster meldete deshalb ALLE
    # zehn als ungemessen, auch die umschlossenen; ein Test, der immer anschlaegt, sagt
    # nichts.
    ungemessen = []
    for zeile in _frontend_block().splitlines():
        m = re.search(r"\$PY scripts/([a-z_]+)\.py", zeile)
        if m and f"teil {m.group(1)} $PY" not in zeile:
            ungemessen.append(m.group(1))
    assert not ungemessen, f"ohne Zwischenzeit: {ungemessen}"


def test_teil_reicht_den_rueckgabewert_durch():
    """⚠ Die Aufrufer hängen `|| echo "⚠ …"` an oder stehen in einem `if`. Verschluckt der
    Helfer den Code, meldet kein einziger Schritt mehr einen Fehlschlag — und ein stiller
    Ausfall ist genau das, was dieser Lauf sonst überall bekämpft."""
    quelle = LAUF.read_text(encoding="utf-8")
    kern = quelle.split("teil() {")[1].split("\n}")[0]
    assert "local code=$?" in kern
    assert "return $code" in kern


def test_zwischenzeit_geht_auf_stderr():
    """⚠ Zwei Aufrufe schicken ihre Ausgabe nach `/dev/null`. Stünde die Zeile auf stdout,
    verschwände sie mit. `exec > >(tee …) 2>&1` führt stderr ohnehin ins selbe Protokoll."""
    quelle = LAUF.read_text(encoding="utf-8")
    kern = quelle.split("teil() {")[1].split("\n}")[0]
    assert "1>&2" in kern


def test_zwischenzeiten_kollidieren_nicht_mit_den_schrittzeiten():
    """`_ernte_minuten` sucht `⏱ <Schrittname> — Ns`. Hiesse ein Skript wie ein Schritt,
    zählte der Wächter die Zwischenzeit als Schrittdauer mit."""
    import re
    quelle = LAUF.read_text(encoding="utf-8")
    skripte = {m.group(1) for m in re.finditer(r"teil ([a-z_]+) \$PY", quelle)}
    schritte = {m.group(1) for m in re.finditer(r'step "(.+)"', quelle)}
    assert not (skripte & schritte)


def test_kein_schrittname_traegt_eine_variable():
    """Der Schrittname ist der Schluessel der Zeitmessung.

    Im Protokoll steht `⏱ <Name> — <n>s`. Der Name ist damit die einzige Handhabe, die Dauer
    eines Schritts ueber mehrere Naechte zu verfolgen. Steht eine Variable darin, heisst der
    Schritt jede Nacht anders — und die Reihe zerfaellt.

    ⚠ GEMESSEN AM 2026-09-06: `step "Gold-Rebuild (Leads mit Stichtag $TODAY)"` liess
    ausgerechnet den GROESSTEN Schritt in Einzelnamen zerfallen. Von 61 verschiedenen
    Schrittnamen aus 14 Naechten waren **13 derselbe** Gold-Rebuild. Seine Entwicklung war
    damit unsichtbar — und genau die will Schritt 4 des Effizienzplans messen.

    Wandernde Angaben (Stichtag, Land, Zahl) gehoeren in die AUSGABE des Schritts, nicht in
    seinen Namen.
    """
    import re
    from pathlib import Path
    quelle = (Path(__file__).resolve().parent.parent / "scripts" / "daily_leads.sh"
              ).read_text(encoding="utf-8")
    treffer = [z.strip() for z in quelle.splitlines()
               if re.match(r'\s*step\s+"', z) and "$" in z]
    assert not treffer, (
        "Diese Schrittnamen tragen eine Variable und zerfallen damit ueber die Naechte:\n  "
        + "\n  ".join(treffer))


# ── Zeitstempel je Zeile ────────────────────────────────────────────────────────────

def _praefixer() -> str:
    """Der `exec`-Block, der jede Ausgabezeile mit der Uhrzeit versieht."""
    q = LAUF.read_text(encoding="utf-8")
    return q.split("exec > >(")[1].split('| tee -a "$LOG") 2>&1')[0]


def test_jede_zeile_bekommt_die_uhrzeit():
    """⚠ Die Schrittzeiten (`⏱`) sagen, WELCHER Schritt lange brauchte, nicht WO darin die
    Zeit blieb. Am 2026-09-09 stand „DÖE-Ingest 5148s" bei exakt derselben Arbeit, die zwei
    Tage vorher 1498s kostete — und ohne Zeitstempel liess sich nicht unterscheiden, ob es
    am Warten auf die Gegenstelle lag, an Wiederholungen oder an der eigenen Rechnung."""
    assert '%H:%M:%S' in _praefixer()


def test_praefixer_nutzt_PY_nicht_bares_python():
    """Unter launchd ist die Umgebung eine andere; `$PY` ist die Fassung, die der ganze
    Lauf benutzt. Ein bares `python3` waere eine zweite Annahme an derselben Stelle."""
    assert "$PY -c" in _praefixer()


def test_praefixer_ist_ungepuffert():
    """Sonst haengt die Ausgabe im Puffer und die Zeitstempel messen Puffer-Leerungen statt
    Arbeit — genau der Fehler, der am 2026-09-05 in den Python-Schritten gefunden wurde."""
    quelle = LAUF.read_text(encoding="utf-8")
    assert 'PY="python3 -u"' in quelle


def test_praefixer_ueberlebt_muell_im_strom():
    """⚠ Stirbt er, geht das Protokoll eines Siebenstundenlaufs verloren und der Lauf
    schreibt in eine tote Pipe. Ein einziges ungültiges UTF-8-Byte würde genügen.

    Geprüft wird das VERHALTEN, nicht die Absicht: der echte Block wird ausgeführt."""
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        skript = (f'set -uo pipefail\nPY="python3 -u"\nLOG={d}/x.log\n'
                  f'exec > >({_praefixer()}| tee -a "$LOG") 2>&1\n'
                  r'printf "eins\nkaputt: \xff\xfe\nzwei\n"' + "\n")
        subprocess.run(["bash", "-c", skript], capture_output=True, timeout=60)
        # ⚠ NICHT SCHLAFEN, SONDERN WARTEN. Die Prozess-Substitution wird nach dem
        # Skriptende abgebaut; ein festes `sleep(1)` reicht auf einer belasteten Maschine
        # nicht und macht den Test zum Flackern. Genau das ist am 2026-09-09 passiert:
        # allein gruen, im Gesamtlauf rot. Ein Test, der unter Last rot wird, erzieht
        # dazu, Rot zu ignorieren.
        import time
        ziel, frist = Path(f"{d}/x.log"), time.time() + 20
        text = ""
        while time.time() < frist:
            text = ziel.read_text(encoding="utf-8", errors="replace") if ziel.exists() else ""
            if "zwei" in text:
                break
            time.sleep(0.05)
    assert "eins" in text and "zwei" in text, "nach dem Muell wurde nichts mehr geschrieben"
    assert re.search(r"\[\d\d:\d\d:\d\d\] zwei", text), "die Zeile hat keinen Zeitstempel"


def test_bestehende_leser_vertragen_das_praefix():
    """`test_daily` selbst sucht mit `re.search` nach `⏱ … — Ns`; ein Präfix davor darf das
    nicht brechen. Sonst misst die Ernte-Reserve ab morgen nichts mehr."""
    zeile = "[04:07:12]   ⏱ Gold-Rebuild (Leads mit Stichtag 2026-09-09) — 243s"
    m = re.search(r"⏱ Gold-Rebuild \(Leads mit Stichtag 2026-09-09\) — (\d+)s", zeile)
    assert m and m.group(1) == "243"


def test_der_warnungszaehler_vertraegt_das_praefix():
    """⚠ DER LESER, DEN DIE PRÄFIX-EINFÜHRUNG ÜBERSAH — und er steht in derselben Datei.

    `abschluss()` zählt die Warnungen eines Laufs mit einem Muster, das an `^` hängt. Mit
    dem Zeitstempel davor traf es nichts mehr: der Lauf vom 2026-09-10 meldete **0
    Warnungen**, während sechs im Protokoll standen, darunter die Ausfälle von TED-Live
    und DTVP. Eine Kennzahl, die immer null ist, liest niemand — genau die Falle, gegen die
    der Zähler 2026-08-25 überhaupt erst verschärft worden war.

    Der Test liest das Muster AUS DEM SKRIPT, nicht aus einer Kopie. Eine Kopie altert mit
    und beweist am Ende nur, dass zwei Stellen denselben Fehler haben.
    """
    m = re.search(r"warn=\$\(grep -cE '([^']+)'", LAUF.read_text(encoding="utf-8"))
    assert m, "Die Zeile, die Warnungen zählt, ist nicht mehr auffindbar."
    muster = m.group(1).replace("[[:space:]]", r"\s")

    treffen_muss = [
        "[01:43:23]   ⚠ TED-Live fehlgeschlagen — Bestand bleibt auf altem Stand.",
        "  ⚠ ohne Praefix, wie die Protokolle bis zum 2026-09-08",
        "⚠ ganz ohne Einzug",
    ]
    # ⚠ Und die Gegenprobe, die den Zähler 2026-08-25 erst brauchbar gemacht hat: das
    # Zeichen dient MITTEN in der Zeile als Marker. Wer die einrechnet, zählt jede Nacht
    # dieselbe Zahl — und ein Lauf, in dem wirklich etwas kaputtging, sähe genauso aus.
    treffen_nicht = [
        "[05:10:21]   SH  Schleswig-Holstein   19 von 21 (90%)  ⚠ unvollständig",
        "   gesamt simap → Serie 'simap' (beginnt_spaeter), ab 2024: 859 … 1,933 ⚠2024=6Mon",
    ]
    for z in treffen_muss:
        assert re.match(muster, z), f"Warnung nicht gezählt: {z!r}"
    for z in treffen_nicht:
        assert not re.match(muster, z), f"Inline-Marker fälschlich gezählt: {z!r}"


def test_der_zaehler_findet_die_warnungen_im_letzten_protokoll():
    """Gegenprobe am echten Bestand: ein Lauf mit Warnungen darf nicht auf null stehen."""
    protokolle = sorted(LOGS.glob("daily-*.log"))[-3:]
    if not protokolle:
        pytest.skip("keine Protokolle — frische Arbeitskopie")
    m = re.search(r"warn=\$\(grep -cE '([^']+)'", LAUF.read_text(encoding="utf-8"))
    muster = re.compile(m.group(1).replace("[[:space:]]", r"\s"))
    for log in protokolle:
        zeilen = log.read_text(errors="replace").splitlines()
        gezaehlt = sum(1 for z in zeilen if muster.match(z))
        # Jede Zeile, die (nach optionalem Zeitstempel) mit dem Zeichen beginnt, ist eine
        # Warnung — egal wie das Skript sie sucht.
        echte = sum(1 for z in zeilen if re.match(r"^(\[[0-9:]+\]\s*)?\s*⚠", z))
        assert gezaehlt == echte, (
            f"{log.name}: der Zaehler des Skripts findet {gezaehlt}, im Protokoll stehen "
            f"{echte} Warnzeilen.")


# ─────────────────────────────────────────── Aufschub statt Abbruch (seit 2026-09-10)

# Die Schritte, die einen Tag warten koennen, ohne dass etwas verloren geht: sie lesen
# Dokumente, die morgen noch da sind, und der Dauerarbeiter macht einen davon ohnehin
# jede Runde. ⚠ Alles andere hinter dem Gold-Rebuild ist das PRODUKT — Export, Waechter,
# Ertragsbericht — und darf nie aufgeschoben werden.
AUFSCHIEBBAR = (
    "_index_alle",                     # Volltext-Index (Stufe 1 des Dauerarbeiters)
    "govisor.dokdubletten",            # Dokument-Dubletten
    "_signale_alle",                   # Anforderungs-Signale
    "export_doc_text.py",              # doc-text.json
    "extract_positions.py",            # Leistungsverzeichnisse
    "build_marktpuls.py",              # Marktpuls
    "gap_effects.py",                  # Vorberechnung
)


def test_die_teuren_ernteschritte_stehen_unter_der_aufschub_regel():
    """⚠ DER FALL VOM 2026-09-10. Der Lauf riss die 8 h und verlor 20 von 49 Schritten —
    darunter JEDEN Frontend-Export, obwohl Gold längst fertig war. `web/data` stand einen
    Tag still.

    Der Grund war die Reihenfolge: die teuersten Ernteschritte sind aufschiebbar, stehen
    aber VOR dem Export, der es nicht ist. `ERNTE_RESERVE` half nicht — die schützt die
    Ernte vor den ABRUFERN, nicht vor sich selbst.
    """
    text = LAUF.read_text(encoding="utf-8")
    assert "nur_mit_zeit()" in text, "Die Aufschub-Regel fehlt."
    fehlt = [n for n in AUFSCHIEBBAR
             if not re.search(r"nur_mit_zeit [^\n]*" + re.escape(n), text)]
    assert fehlt == [], (
        f"Diese Schritte laufen ohne Aufschub-Regel: {fehlt}. Wer hier einen teuren "
        f"Schritt einhängt, ohne ihn zu schützen, verliert beim nächsten langen Lauf "
        f"wieder den Export.")


def test_der_export_steht_nicht_unter_der_aufschub_regel():
    """Die Gegenprobe — sonst schiebt der Lauf irgendwann genau das auf, was er liefern
    soll, und meldet dabei brav „fertig"."""
    text = LAUF.read_text(encoding="utf-8")
    for pflicht in ("export_web_leads", "export_landing", "build_city_index"):
        assert not re.search(r"nur_mit_zeit [^\n]*" + re.escape(pflicht), text), (
            f"{pflicht} ist aufschiebbar gemacht worden — das ist das Produkt.")


def test_ernte_kern_deckt_den_gemessenen_pflichtteil():
    """Wie die Ernte-Reserve: eine Zahl, die aus einer Messung stammt, altert mit ihr."""
    text = LAUF.read_text(encoding="utf-8")
    m = re.search(r"ERNTE_KERN=\$\{GOVISOR_ERNTE_KERN:-(\d+)\}", text)
    assert m, "ERNTE_KERN ist nicht mehr auffindbar."
    reserve = int(m.group(1))
    KERN = ("Bundeslaender ableiten", "Frontend-Daten exportieren", "Ertragsbericht",
            "Namenswoerter-Tabelle")
    gemessen = []
    for log in sorted(LOGS.glob("daily-*.log"))[-LAEUFE:]:
        paare = re.findall(r"⏱ (.+?) — (\d+)s", log.read_text(errors="replace"))
        s = sum(int(x) for n, x in paare if any(n.startswith(k) for k in KERN))
        if s:
            gemessen.append(s)
    if not gemessen:
        pytest.skip("keine Protokolle mit Pflichtteil")
    schlimmster = max(gemessen)
    assert reserve >= schlimmster * MINDEST_FAKTOR, (
        f"ERNTE_KERN = {reserve // 60} min, der schlimmste gemessene Pflichtteil lag bei "
        f"{schlimmster // 60} min. Der Abstand ist unter {MINDEST_FAKTOR}× gefallen.")


def test_der_maschinen_mitschreiber_wird_gestartet_und_beendet():
    """Ein Mitschreiber, der den Lauf überlebt, läuft bis zum Neustart weiter."""
    text = LAUF.read_text(encoding="utf-8")
    assert "maschine_mitschreiben.sh" in text, "Der Mitschreiber wird nicht gestartet."
    assert 'kill "$MASCHINE_PID"' in text, "Der Mitschreiber wird nicht beendet."
    # ⚠ Und zwar im `trap`, nicht am Ende des Skripts: ein Lauf, der an der Zeitgrenze
    # stirbt, kommt am Ende nie an.
    i_trap = text.index("abschluss()")
    i_kill = text.index('kill "$MASCHINE_PID"')
    i_ende = text.index("# ══ ERNTE VOR ABRUF")
    assert i_trap < i_kill < i_ende, "Das Beenden steht nicht in abschluss()."
    assert (ROOT / "scripts" / "maschine_mitschreiben.sh").exists()


# ───────────────────────────── Der Rechner muss wach bleiben (seit 2026-09-11)

def test_der_lauf_haelt_den_rechner_wach():
    """⚠ DER GRÖSSTE EINZELBEFUND DIESER WOCHE, und er lag nicht im Code.

    Der Mitschreiber sollte alle 30 s eine Zeile schreiben und schaffte in 405 Minuten
    **151 statt 810**. Die Lücken waren 16 bis 18 Minuten lang, dreissigmal, zusammen
    **344 von 405 Minuten**. `pmset -g log` nennt den Grund auf die Sekunde genau:

        01:44:08  Sleep     'Maintenance Sleep' … 1007 secs
        02:00:55  DarkWake

    Der Rechner schläft während des Laufs. Die tatsächliche Arbeit waren 61 Minuten — der
    Rest war Schlaf, und jeder Zeitablauf dieser Woche (curl nach 960 s, Chromium nach
    180 s) fiel in ein Schlaffenster.
    """
    text = LAUF.read_text(encoding="utf-8")
    assert "caffeinate" in text, "Nichts hält den Rechner wach — der Lauf verschläft sich."
    # ⚠ `-i`, nicht `-d`/`-s`: der Bildschirm darf schlafen, die Maschine nicht.
    # `-w $$` bindet es an DIESEN Lauf, danach schläft sie wieder wie vorher.
    assert re.search(r"caffeinate -i -w \$\$", text), (
        "caffeinate ohne `-i -w $$` — entweder hält es den Bildschirm wach (unnötig) "
        "oder es überlebt den Lauf (dann schläft die Maschine nie wieder).")


def test_der_mitschreiber_meldet_sich_nicht_beim_beenden():
    """Ohne `disown` schreibt die Shell „Terminated: 15" mitten in die Abschlusszeile —
    so geschehen am 2026-09-11, direkt hinter der Zusammenfassung des Laufs."""
    text = LAUF.read_text(encoding="utf-8")
    i = text.index("maschine_mitschreiben.sh")
    assert "disown" in text[i:i + 400], "Der Mitschreiber bleibt in der Auftragsverwaltung."


def test_der_zweitversuch_laeuft_fuer_alle_aktiven_laender():
    """⚠ Er lief drei Wochen nur für DE, obwohl das Modul `--country` kennt und AT, CH und
    LU beide Vorstufen tragen. Gemeldet hat es die Verdrahtungsprüfung am 2026-09-11 —
    aber erst, als ein Lauf überhaupt wieder bis zu den Wächtern kam."""
    text = LAUF.read_text(encoding="utf-8")
    i = text.index("govisor.retender_link")
    zeile = text[text.rindex("\n", 0, i) + 1:text.index("\n", i)]
    assert "--country DE" not in zeile, "Der Zweitversuch hängt wieder an einem Land."
    assert '"$L"' in zeile, zeile
    # Die Liste kommt aus `govisor/laender.py` — eine getippte Liste im Nachtlauf ist die
    # Stelle, die beim fünften Land vergessen wird.
    assert "from govisor.laender import AKTIV" in text
