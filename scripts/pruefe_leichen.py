#!/usr/bin/env python3
"""**Leichensuche** — fuenf Spuren, die `pruefe_verdrahtung.py` nicht abdeckt.

Die Hausfehlerklasse ist „gebaut, aber nicht verdrahtet". Dagegen stehen 15 Sonden. Die
sehen die Datenkette, die Ausliefergueter, die Laenderparitaet und GANZE Dateien in
`web/lib`. Sie sehen nicht:

    Spur 1  Komponenten in `web/components`           — 47 Dateien, 14.101 Zeilen, keine Sonde
    Spur 2  Seiten ohne Verweis, Routen ohne Aufrufer — Next.js importiert sie selbst,
                                                        der Importgraph ist dafuer blind
    Spur 3  EINZELNE Exporte in `web/lib`             — Sonde 7 prueft nur die Datei
    Spur 4  Dauerdienste ohne Eintrag                 — ein Arbeiter, den niemand startet
    Spur 5  Alter der OFFEN-Ausnahmen                 — eine Ausnahme ohne Verfallsdatum

⛔ **DIE FALLE, DIE DIESE SPUREN KIPPEN WUERDE: ein Scan auf EINEM Zweig sieht Verdrahtung
nicht, die auf einem anderen liegt.** Am 2026-10-06 gemessen: vier Zweige liegen nicht in
`main`, und `web/grounding-page` (2 h alt) unterscheidet sich in `web/` allein um 51 Dateien.
Wer auf `main` scannt, haelt fuer tot, was dort gerade eingebunden wurde — und der naechste
Merge bringt es stumm zurueck oder bricht. Deshalb messen alle Spuren gegen die VEREINIGUNG
der Zweige mit Commit < 30 Tage (`_fremde_sicht`). Ein Treffer auf irgendeinem lebenden Zweig
heisst: lebt.

⚠ **RUECKGABE 0, AUCH BEI BEFUNDEN.** Das ist Absicht und der Unterschied zu den anderen
Sonden: dies ist ein BERICHT (Entscheidung Sven, 2026-10-06: „erst nur ein Bericht, Loeschen
spaeter"). Eine Leiche ist kein Betriebsfehler, sondern eine Vorlage zur Entscheidung. Mit
`--streng` gibt es 1 zurueck — so kann die Spur spaeter in den Waechterlauf, wenn die Funde
abgearbeitet sind und jeder neue ein echter Rueckschritt ist.

    python3 scripts/pruefe_leichen.py [--spur alle|komponenten|wege|symbole|dienste|ausnahmen]
                                      [--streng] [--markdown]
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
ENDUNGEN = {".ts", ".tsx", ".js", ".mjs"}

# Ein Zweig, dessen letzter Commit aelter ist, zaehlt als tot — seine Verdrahtung schuetzt
# nichts mehr. 30 Tage, dieselbe Schwelle, die `pruefe_bibel.py` fuer ein stillstehendes
# Kapitel benutzt.
ZWEIG_TAGE = 30
# Eine OFFEN-Ausnahme darf nicht ewig parken. Gemessener Anlass: zwei Eintraege standen am
# 2026-10-06 seit 42 Tagen („offen seit 2026-08-25").
AUSNAHME_TAGE = 30

# ── Bewusst ruhend, mit Grund und Datum. KEINE Leiche. ────────────────────────────────
# ⚠ Diese Liste ist kein Parkplatz. Wer hier etwas eintraegt, nennt Grund UND Datum; Spur 5
# misst ihr Alter mit, sobald „offen seit" darin steht.
RUHEND: dict[str, str] = {
    "components/MessHinweis.tsx":
        "absichtlich ruhend, im Dateikopf begruendet (Datenschutzseite fehlt); "
        "tests/test_telemetrie.py haelt die Bedingung fest",
    "lib/identityGate.ts":
        "Leiche der am 2026-08-21 gestrichenen Erfolgspraemie; wird beim Scharfschalten "
        "von Stripe eingefordert (tests/test_golive_riegel.py)",
}

RUHENDE_DIENSTE: dict[str, str] = {
    "succession_llm.py":
        "kostenpflichtiger Handlauf, als Ausnahme in pruefe_verdrahtung.py hinterlegt",
    "aggregate_outcomes.py":
        "DORMANT bis zur kartellrechtlichen Pruefung (§9.1), schaltet sich selbst ab",
}


# ⛔ **ERZEUGTE VERZEICHNISSE MUESSEN DRAUSSEN BLEIBEN, UND `.next` IST DAS WICHTIGSTE.**
# Gemessener Fehlschlag am 2026-10-06: Spur 2 meldete NULL unverlinkte Seiten, obwohl
# `/authority`, `/marktpuls` und `/intern/claims` nachweislich nirgends verlinkt sind. Der
# Grund: `.next/types/routes.d.ts` und `.next/types/validator.ts` werden beim Bauen erzeugt
# und listen JEDE Route als Zeichenkette auf. Wer sie mitliest, bekommt eine Sonde, die
# grundsaetzlich gruen ist — der teuerste Fehlalarm ist der, der nie anschlaegt.
# ⚠ Dieselbe Luecke hat `pruefe_verdrahtung.sonde_module`: sie schliesst nur `node_modules`
# aus. Bei Modul-Importen fiel das nie auf, weil `.next` Pfade listet, keine Importe.
ERZEUGT = {"node_modules", ".next", ".vercel", "dist", "build", "out", "coverage"}


def _dateien(basis: pathlib.Path, muster: str = "**/*") -> list[pathlib.Path]:
    return [p for p in basis.glob(muster)
            if p.is_file() and p.suffix in ENDUNGEN and not (ERZEUGT & set(p.parts))]


def _git(*args: str) -> str:
    """git lesen, Fehler schlucken. Ein fehlender Zweig darf die Spur nicht abbrechen."""
    try:
        p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                           text=True, timeout=120)
        return p.stdout if p.returncode == 0 else ""
    except Exception:                                                    # noqa: BLE001
        return ""


def lebende_zweige() -> list[str]:
    """Zweige mit Commit juenger als ZWEIG_TAGE, ohne den eigenen HEAD."""
    roh = _git("for-each-ref", "--format=%(refname:short)|%(committerdate:unix)",
               "refs/heads/")
    jetzt = dt.datetime.now().timestamp()
    hier = _git("rev-parse", "--abbrev-ref", "HEAD").strip()
    zweige = []
    for zeile in roh.splitlines():
        if "|" not in zeile:
            continue
        name, _, stamp = zeile.rpartition("|")
        try:
            alter = (jetzt - float(stamp)) / 86400
        except ValueError:
            continue
        if alter <= ZWEIG_TAGE and name != hier:
            zweige.append(name)
    return zweige


def _fremde_sicht(zweige: list[str], pfade: tuple[str, ...]) -> str:
    """Alle Import- und Pfadzeilen der fremden Zweige, in EINEM Textblock.

    ⚠ Nicht je Kandidat ein `git grep` — das waeren bei 47 Komponenten, 25 Seiten, 60 Routen
    und einigen hundert Symbolen tausende Aufrufe. Stattdessen wird je Zweig EINMAL alles
    geholt, was wie ein Import oder ein Pfad aussieht; darin wird dann gesucht. Zu viel Text
    ist hier die sichere Richtung: ein Zeichen zu viel heisst „lebt" und damit kein Fund.
    """
    teile = []
    for z in zweige:
        teile.append(_git("grep", "-h", "-E",
                          r'from +["\x27]|import\(|require\(|["\x27]/[a-zA-Z]', z,
                          "--", *pfade))
    return "\n".join(teile)


# ── Spur 1: Komponenten ohne Importeur ────────────────────────────────────────────────
def spur_komponenten(zeige_offen: bool = False,
                     wurzel: pathlib.Path | None = None) -> list[str]:
    """Welche Komponente unter `web/components` importiert niemand?

    Mechanik wie `pruefe_verdrahtung.sonde_module`, absichtlich uebernommen statt neu
    erfunden: die Endung darf im Import mitstehen (`@/lib/ladegrund.js`), und ein `index`
    wird ueber seinen Verzeichnisnamen importiert. Beide Regeln sind dort je an einem echten
    Fehlalarm gelernt worden.
    """
    web = wurzel or WEB
    if not (web / "components").is_dir():
        return []
    quellen = _dateien(web)
    text = {p: p.read_text(encoding="utf-8", errors="replace") for p in quellen}
    fremd = ("" if wurzel else
             _fremde_sicht(lebende_zweige(), ("web/components", "web/app", "web/lib")))

    befunde: list[str] = []
    for modul in sorted(_dateien(web / "components")):
        rel = modul.relative_to(web).as_posix()
        ohne = modul.relative_to(web).with_suffix("").as_posix()
        wege = {ohne, modul.stem}
        if modul.stem == "index":
            wege.add(modul.parent.relative_to(web).as_posix())
            wege.add(modul.parent.name)
        muster = re.compile("|".join(
            rf'["\x27][^"\x27]*(?:@/)?{re.escape(w)}(?:\.(?:js|mjs|ts|tsx))?["\x27]'
            for w in sorted(wege)))
        if any(muster.search(q) for datei, q in text.items() if datei != modul):
            continue
        if muster.search(fremd):
            if zeige_offen:
                print(f"    (fremder Zweig) {rel}: dort verdrahtet, hier nicht")
            continue
        if rel in RUHEND:
            if zeige_offen:
                print(f"    (ruhend) {rel}: {RUHEND[rel]}")
            continue
        n = len(modul.read_text(encoding="utf-8", errors="replace").splitlines())
        befunde.append(f"Komponente: {rel} ({n} Z) importiert niemand")
    return befunde


# ── Spur 2: Seiten ohne Verweis, Routen ohne Aufrufer ─────────────────────────────────
def spur_wege(zeige_offen: bool = False,
              wurzel: pathlib.Path | None = None) -> list[str]:
    r"""Welche Seite verlinkt niemand, welche API-Route ruft niemand auf?

    ⚠ **DAS OEFFNENDE ANFUEHRUNGSZEICHEN MUSS MITVERLANGT WERDEN.** Ohne es zaehlt
    `"/api/vorgang"` als Verweis auf `/vorgang`, und die Spur gibt drei Seiten frei, die
    niemand verlinkt. Beim ersten Durchlauf der Erkundung ist genau das passiert.

    ⚠ Next.js importiert `page.tsx` und `route.ts` ueber die DATEIKONVENTION. Beide sind
    damit fuer jeden Importgraphen „benutzt" — die Frage ist nicht, ob sie importiert
    werden, sondern ob irgendwo ihr PFAD steht.
    """
    web = wurzel or WEB
    if not (web / "app").is_dir():
        return []
    quellen = _dateien(web) + [p for p in (web / "app").rglob("*.css")
                               if not (ERZEUGT & set(p.parts))]
    for extra in ("vercel.json", "middleware.ts"):
        if (web / extra).is_file():
            quellen.append(web / extra)
    text = {p: p.read_text(encoding="utf-8", errors="replace") for p in quellen}
    fremd = "" if wurzel else _fremde_sicht(lebende_zweige(), ("web",))

    befunde: list[str] = []
    for datei in sorted((web / "app").rglob("*")):
        if datei.name not in ("page.tsx", "route.ts"):
            continue
        teile = datei.relative_to(web / "app").parts[:-1]
        # Dynamische Segmente ([slug]) nie melden: der Pfad steht im Code mit einem Wert
        # darin, nie wortwoertlich.
        if any(t.startswith("[") or t.startswith("(") for t in teile):
            continue
        weg = "/" + "/".join(teile)
        art = "Seite" if datei.name == "page.tsx" else "Route"
        # ⚠ **NICHT „Anfuehrungszeichen davor" VERLANGEN — das war ein gefaehrlicher
        # Fehlalarm.** Der erste Entwurf verlangte `["'`]` unmittelbar vor dem Pfad, um
        # `"/api/vorgang"` nicht als Verweis auf `/vorgang` zu zaehlen. Damit meldete er
        # `/auth/passwort` als Leiche — die Seite wird aber ueber
        # `redirectTo: "…/auth/callback?next=/auth/passwort"` erreicht
        # (`lib/supabase/auth.ts:43`), also MITTEN in einer laengeren URL. Loeschen haette
        # das Passwort-Zuruecksetzen getoetet.
        #
        # Richtig ist die Verneinung: vor dem Pfad darf kein Wortzeichen und kein Schraegstrich
        # stehen. `/api/vorgang` → vor `/vorgang` steht `i`, also kein Verweis. `next=/auth/…`
        # → vor dem Pfad steht `=`, also ein Verweis. Beide Faelle gehen auf.
        muster = re.compile(rf'(?<![\w/]){re.escape(weg)}(?=["\x27`?#/])')
        if any(muster.search(q) for d, q in text.items() if d != datei):
            continue
        if muster.search(fremd):
            if zeige_offen:
                print(f"    (fremder Zweig) {weg}: dort verwiesen, hier nicht")
            continue
        n = len(datei.read_text(encoding="utf-8", errors="replace").splitlines())
        wort = "verlinkt niemand" if art == "Seite" else "ruft niemand auf"
        befunde.append(f"{art}: {weg} ({n} Z) {wort}")
    return befunde


# ── Spur 3: einzelne Exporte in web/lib ───────────────────────────────────────────────
_EXPORT = re.compile(
    r"^export\s+(?:async\s+)?(?:function|const|let|class|type|interface|enum)\s+"
    r"([A-Za-z_$][\w$]*)", re.M)
_EXPORT_BLOCK = re.compile(r"^export\s*\{([^}]*)\}", re.M)
_IMPORT_SPEC = re.compile(r"import\s*(?:type\s*)?\{([^}]*)\}|"
                          r"import\s*\(\s*[^)]*\)\s*\)?\s*\.?\s*then", re.S)


def spur_symbole(zeige_offen: bool = False) -> list[str]:
    """Welches EINZELNE Symbol in `web/lib` importiert niemand?

    ⚠ **WARUM NICHT DIE FUNDSTELLEN IM QUELLTEXT GEZAEHLT WERDEN.** Genau daran ist der
    erste Entwurf von Sonde 7 gescheitert (dort im Docstring belegt): um einen Namen in
    seiner eigenen Fehlermeldung nicht als Benutzung zu zaehlen, muss man Zeichenketten
    entfernen — und ein regulaerer Ausdruck im Code sieht fuer jeden linearen Filter wie
    eine Zeichenkette aus. In `impressum.ts` verschluckte das 9.797 Zeichen und machte aus
    fuenf lebenden Pruefschritten Leichen.

    Dieser Weg braucht keinen Parser: gelesen werden NUR die Import-Spezifikatoren, also der
    Inhalt der `{…}` hinter `import`. Eine solche Klammer ist eindeutig, genau wie eine
    `from`-Zeile.

    ⚠ Und die zweite Haelfte: ein Export, der im EIGENEN Modul benutzt wird, ist keine
    Leiche, sondern hoechstens ein `export` zu viel. Dafuer genuegt die rohe Zahl der
    Vorkommen in der eigenen Datei — mehr als eins heisst „wird intern gerufen". Das ist
    absichtlich grosszuegig: die Richtung unterdrueckt Funde, sie erfindet keine.
    """
    if not (WEB / "lib").is_dir():
        return []
    quellen = _dateien(WEB) + _dateien(ROOT / "web" / "scripts") if (
        ROOT / "web" / "scripts").is_dir() else _dateien(WEB)

    benutzt: set[str] = set()
    for p in quellen:
        q = p.read_text(encoding="utf-8", errors="replace")
        for m in _IMPORT_SPEC.finditer(q):
            if m.group(1):
                for teil in m.group(1).split(","):
                    name = teil.split(" as ")[0].strip()
                    if name:
                        benutzt.add(name)
        # Standard-Import (`import X from "…"`) und `const { a } = await import(…)`
        for m in re.finditer(r"import\s+([A-Za-z_$][\w$]*)\s+from", q):
            benutzt.add(m.group(1))
        for m in re.finditer(r"(?:const|let|var)\s*\{([^}]*)\}\s*=\s*await\s+import", q):
            for teil in m.group(1).split(","):
                name = teil.split(":")[0].strip()
                if name:
                    benutzt.add(name)

    # ⛔ **MODULE, DIE ALS NAMENSRAUM IMPORTIERT WERDEN, SIND AUF SYMBOLEBENE NICHT
    # ENTSCHEIDBAR.** Gemessener Fehlalarm am 2026-10-06: `preise.ts → betragCents` galt als
    # tot, wird aber in `web/scripts/pruefe-preis.mjs:55` als `P.betragCents(...)` gerufen —
    # geholt per `const P = await import(join(verz, "preise.ts"))`. Jeder Export eines so
    # geholten Moduls ist ueber `P.<name>` erreichbar, ohne je in einer `{…}`-Klammer zu
    # stehen. Wer das nicht ausnimmt, meldet reihenweise lebende Funktionen.
    # Entschieden: solche Module ganz ueberspringen. Lieber ein Fund zu wenig als ein
    # Loeschvorschlag fuer eine benutzte Funktion.
    namensraum: set[str] = set()
    for p in quellen:
        q = p.read_text(encoding="utf-8", errors="replace")
        for zeile in q.splitlines():
            if "import * as" in zeile or "await import(" in zeile or "require(" in zeile:
                for s in re.findall(r"[\"\x27]([^\"\x27]+)[\"\x27]", zeile):
                    namensraum.add(pathlib.PurePath(s).stem)

    fremd = _fremde_sicht(lebende_zweige(), ("web",))
    befunde: list[str] = []
    for modul in sorted(_dateien(WEB / "lib")):
        rel = modul.relative_to(WEB).as_posix()
        if modul.stem in namensraum:
            if zeige_offen:
                print(f"    (Namensraum) {rel}: wird als Ganzes geholt, "
                      "Symbolebene nicht entscheidbar")
            continue
        if rel in RUHEND:
            if zeige_offen:
                print(f"    (ruhend) {rel}: {RUHEND[rel]}")
            continue
        q = modul.read_text(encoding="utf-8", errors="replace")
        namen = set(_EXPORT.findall(q))
        for m in _EXPORT_BLOCK.finditer(q):
            for teil in m.group(1).split(","):
                name = teil.split(" as ")[-1].strip()
                if name and name.isidentifier():
                    namen.add(name)
        for name in sorted(namen):
            if name in benutzt:
                continue
            if len(re.findall(rf"\b{re.escape(name)}\b", q)) > 1:
                continue                      # intern gerufen — kein Loeschkandidat
            if re.search(rf"\b{re.escape(name)}\b", fremd):
                if zeige_offen:
                    print(f"    (fremder Zweig) {rel}:{name}")
                continue
            befunde.append(f"Symbol: {rel} → {name} importiert niemand")
    return befunde


# ── Spur 4: Dauerdienste ohne Eintrag ─────────────────────────────────────────────────
# ⚠ **ERSTER ENTWURF: `--takt|while True:` — UND ER MELDETE SICH SELBST.** Das Wort `--takt`
# steht in DIESEM Docstring, also galt die Spur als unverdrahteter Dauerdienst. Dazu
# `miss_eu_groesse.py`, dessen `while True:` eine Blaetterschleife gegen die TED-API ist.
# Es ist die Falle, die in der Auto-Memory steht: ein Waechter, der seine eigene Prosa messt.
#
# ⚠ **UND `Schleife + sleep` WAERE DIE FALSCHE VERSCHAERFUNG GEWESEN.** Gemessen:
# `miss_eu_groesse.py` hat fuenf `sleep`-Aufrufe (Ratenbremse), der echte Dienst
# `antwort_arbeiter.py` genau einen. Das Signal zeigt in die verkehrte Richtung.
#
# Deshalb aus der Quelle abgeleitet, nicht gefuehlt: ein Dienst ERKLAERT seinen Dauerbetrieb.
# In Python durch ein Takt-Argument in argparse (genau ein Skript im Bestand tut das:
# `antwort_arbeiter.py --takt 30`), in der Shell durch `while true` (so laufen
# `dokumente_arbeiter.sh:141` und `analyse_arbeiter.sh`).
_TAKT_PY = re.compile(r"add_argument\(\s*[\"']--(?:takt|interval|intervall)[\"']")
_TAKT_SH = re.compile(r"^\s*while +(?:true|:)\s*;", re.M)


def _ohne_prosa(pfad: pathlib.Path, text: str) -> str:
    """Kommentare und Docstrings entfernen, bevor etwas gemessen wird.

    ⚠ Fuer Python ueber den Syntaxbaum und ueber ALLE Knoten (`ast.walk`), nicht nur
    `body`: ein f-String liefert `JoinedStr`, und ein lineares Verfahren verschluckt
    Zeichenketten, in denen ein Schraegstrich-Paar steht.
    """
    if pfad.suffix == ".py":
        try:
            import ast
            baum = ast.parse(text)
            weg: set[int] = set()
            for k in ast.walk(baum):
                if (isinstance(k, ast.Expr) and isinstance(k.value, ast.Constant)
                        and isinstance(k.value.value, str)):
                    for z in range(k.lineno, (k.end_lineno or k.lineno) + 1):
                        weg.add(z)
            zeilen = [("" if i + 1 in weg else re.sub(r"#.*$", "", z))
                      for i, z in enumerate(text.splitlines())]
            return "\n".join(zeilen)
        except SyntaxError:
            return text
    return "\n".join(re.sub(r"(?<!\$)#.*$", "", z) for z in text.splitlines())


def spur_dienste(zeige_offen: bool = False) -> list[str]:
    """Welcher Dauerdienst ist nirgends eingetragen — und zeigt eine plist falsch?

    ⚠ Der Anlass ist der teuerste Fund dieser Runde: `scripts/antwort_arbeiter.py` laeuft
    nicht, ist in keiner plist, und **kein anderer Abnehmer der Tabelle `user_antwortauftrag`
    existiert**. Die Oberflaeche legt Auftraege ab und fragt nach Ergebnissen, die nie
    entstehen. Kein Test schlaegt an: der Arbeiter ist korrekt, die Route ist korrekt, die
    Komponente ist korrekt.
    """
    skripte = ROOT / "scripts"
    if not skripte.is_dir():
        return []

    # Wo kann ein Start stehen? Shell-Skripte, der Tageslauf, der Waechterlauf, die plists
    # im Repo UND die tatsaechlich installierten.
    heu = []
    for p in list(skripte.glob("*.sh")) + list((ROOT / "deploy").glob("*.plist")):
        heu.append(p.read_text(encoding="utf-8", errors="replace"))
    agenten = pathlib.Path.home() / "Library" / "LaunchAgents"
    installiert = sorted(agenten.glob("*govisor*.plist")) if agenten.is_dir() else []
    for p in installiert:
        heu.append(p.read_text(encoding="utf-8", errors="replace"))
    haystack = "\n".join(heu)

    befunde: list[str] = []
    for p in sorted(list(skripte.glob("*.py")) + list(skripte.glob("*.sh"))):
        q = _ohne_prosa(p, p.read_text(encoding="utf-8", errors="replace"))
        muster = _TAKT_PY if p.suffix == ".py" else _TAKT_SH
        if not muster.search(q):
            continue
        if p.name in haystack.replace(str(ROOT), ""):
            continue
        if p.name in RUHENDE_DIENSTE:
            if zeige_offen:
                print(f"    (ruhend) {p.name}: {RUHENDE_DIENSTE[p.name]}")
            continue
        n = len(q.splitlines())
        befunde.append(f"Dienst: scripts/{p.name} ({n} Z) hat Taktlogik, "
                       "aber keinen Eintrag in plist, Tageslauf oder Waechterlauf")

    # ⚠ Zweiter Fund derselben Spur: eine plist im Repo, die auf einen ANDEREN Baum zeigt
    # als die installierte. Wer sie nachinstalliert, dreht die Lehre vom 2026-10-05 zurueck
    # (der Nachtlauf hat einen eigenen Baum, fest auf `main`).
    for p in sorted((ROOT / "deploy").glob("*.plist")):
        gleich = agenten / p.name
        if not gleich.is_file():
            continue
        hier = re.findall(r"/Users/\S+?\.sh", p.read_text(errors="replace"))
        dort = re.findall(r"/Users/\S+?\.sh",
                          gleich.read_text(errors="replace"))
        if hier and dort and hier[0] != dort[0]:
            befunde.append(f"Dienst: deploy/{p.name} zeigt auf {hier[0]}, "
                           f"installiert laeuft {dort[0]}")
    for p in installiert:
        if p.name.endswith(".vor-logumzug"):
            continue
        if not (ROOT / "deploy" / p.name).is_file():
            befunde.append(f"Dienst: {p.name} laeuft, hat aber keine plist in deploy/ — "
                           "aus einem frischen Checkout nicht herstellbar")
    return befunde


# ── Spur 5: Alter der OFFEN-Ausnahmen ─────────────────────────────────────────────────
def spur_ausnahmen(zeige_offen: bool = False) -> list[str]:
    """Wie alt ist die aelteste geparkte Ausnahme?

    ⚠ Die Sonden trennen `BEWUSST_…` (fuer immer in Ordnung) von `OFFEN_…` (bekannte
    Luecke). Gut gedacht — aber **nichts liess einen OFFEN-Eintrag altern**, und damit ist
    die Liste ein Parkplatz: zwei Eintraege standen am 2026-10-06 seit 42 Tagen. Dieselbe
    Krankheit wie beim Altersbericht und bei der FK-Liste: etwas, das aufhoert zu wachsen
    oder zu schrumpfen, und niemand merkt es.

    `pruefe_bibel.py` hat die Abhilfe schon: ein stillstehendes Kapitel wird nach 30 Tagen
    ein Fehlschlag, nicht nur ein Hinweis. Hier dasselbe Mass.

    ⚠ **DIE PROSA MUSS WEG, UND DAS WAR IN DIESER DATEI DER ZWEITE FALL AN EINEM TAG.** Spur 4
    meldete sich selbst wegen `--takt` im Docstring; diese Spur meldete sich selbst, weil ein
    Beispieldatum („offen seit …") in ihrer eigenen Erklaerung steht. Dieselbe Krankheit,
    zwei Stellen, eine Abhilfe: erst `_ohne_prosa`, dann messen. Deshalb zaehlt die Zeilennummer
    auch gegen den GESTRIPPTEN Text — die geleerten Zeilen bleiben erhalten, damit sie stimmt.
    """
    heute = dt.date.today()
    befunde: list[str] = []
    for p in sorted((ROOT / "scripts").glob("pruefe_*.py")):
        q = _ohne_prosa(p, p.read_text(encoding="utf-8", errors="replace"))
        for m in re.finditer(r"offen seit (\d{4})-(\d{2})-(\d{2})", q):
            tage = (heute - dt.date(int(m.group(1)), int(m.group(2)),
                                    int(m.group(3)))).days
            if tage <= AUSNAHME_TAGE:
                if zeige_offen:
                    print(f"    (frisch) {p.name}: {tage} Tage")
                continue
            zeile = q[:m.start()].count("\n") + 1
            befunde.append(f"Ausnahme: scripts/{p.name}:{zeile} parkt seit {tage} Tagen "
                           f"(Grenze {AUSNAHME_TAGE})")
    return befunde


SPUREN = {
    "komponenten": ("Spur 1: Komponenten (wen importiert niemand?)", spur_komponenten),
    "wege": ("Spur 2: Wege (welche Seite verlinkt, welche Route ruft niemand?)", spur_wege),
    "symbole": ("Spur 3: Symbole (welcher Export in web/lib ist tot?)", spur_symbole),
    "dienste": ("Spur 4: Dienste (welcher Dauerlauf ist nicht eingetragen?)", spur_dienste),
    "ausnahmen": ("Spur 5: Ausnahmen (wie lange parkt eine offene Luecke?)", spur_ausnahmen),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spur", default="alle", choices=["alle", *SPUREN])
    ap.add_argument("--offen", action="store_true",
                    help="auch zeigen, was als ruhend oder fremd-verdrahtet gilt")
    ap.add_argument("--streng", action="store_true",
                    help="Rueckgabe 1 bei Befunden (fuer den Waechterlauf, spaeter)")
    ap.add_argument("--markdown", action="store_true", help="Ausgabe fuer den Bericht")
    a = ap.parse_args()

    zweige = lebende_zweige()
    if not a.markdown:
        print(f"ⓘ Gegengeprueft gegen {len(zweige)} lebende(n) Zweig(e) "
              f"(Commit < {ZWEIG_TAGE} Tage): {', '.join(zweige) or '—'}\n")

    alles: list[str] = []
    for name, (titel, fn) in SPUREN.items():
        if a.spur not in (name, "alle"):
            continue
        if not a.markdown:
            print(f"── {titel} ──")
        f = fn(a.offen)
        alles += f
        if a.markdown:
            print(f"\n### {titel}\n")
            for z in f:
                print(f"- {z}")
            if not f:
                print("- (nichts)")
        else:
            print(f"    {len(f)} Befund(e)")

    if not a.markdown:
        print(f"\n{'⚠' if alles else '✓'} Leichensuche: {len(alles)} Befund(e)")
        for z in alles:
            print(f"  · {z}")
    return 1 if (alles and a.streng) else 0


if __name__ == "__main__":
    sys.exit(main())
