"""Quelle DE — NetServer (Administration Intelligence) Bekanntmachungs-Downloader.

**Warum diese Quelle.** Fünf Bundesländer fahren dieselbe Software: Bremen,
Mecklenburg-Vorpommern, Sachsen, Baden-Württemberg (LandBW) und Hessen (HAD) — alle fünf
sind angebunden, Hessen über einen eigenen Suchweg (s. unten). Sie führen
ober- UND unterschwellige Vergaben; über TED kommen nur die oberschwelligen, über DÖE nur
ein Teil. Gemessen 2026-08-14 an je 25 Vorgängen der öffentlichen Trefferliste:

    Sachsen   23 von 25 fehlten im Bestand (92 %)      6 unterschwellig
    LandBW    14 von 25 (56 %)                        15 unterschwellig (60 %)
    MV         7 von 25 (28 %)                        23 unterschwellig (92 %)
    Bremen     6 von 25 (24 %)                        18 unterschwellig (72 %)

**Die entscheidende Unterscheidung: Liste öffentlich, Detail nicht.** Die Trefferliste
liefert Titel, Verfahrensart, Rechtsrahmen und Abgabefrist ohne jede Anmeldung. Der Klick
auf einen Vorgang führt dagegen auf ``LoginControllerServlet?function=LoginForm`` — in der
Bremer Liste ist das der einzige vorhandene Klick-Handler, Datei-Links gibt es null.

Daraus folgt der Zuschnitt dieses Moduls: **es holt Bekanntmachungen, keine Unterlagen.**
Ein früherer Anlauf im Projekt hat aus der Zugänglichkeit einer Schicht auf eine andere
geschlossen und lag falsch (s. `scripts/probe_portals.py`); hier steht die Grenze deshalb
im Modulkopf und nicht in einer Fussnote. Wer später Unterlagen will, braucht eine
Registrierung — das ist eine Vertrags-, keine Technikfrage.

**Kein Browser nötig — ausser für Hessen.** Bei Bremen, Sachsen, MV und Baden-Württemberg
ist die Trefferliste serverseitig gerendert; ``curl`` genügt. **HAD (Hessen) sucht anders**:
unter ``/NetServer/`` liegen dort nur die Detailseiten, die Suche ist eine eigene Oberfläche
mit einem POST-Formular, dessen Ergebnis sich per ``curl`` nicht reproduzieren liess (sechs
Parameter-Varianten mit und ohne Sitzung, durchweg ohne eine Trefferzeile). Dafür gibt es
`hole_had()` mit Playwright — dieselbe Begründung wie bei DTVP.

⚠ **Die Instanzen sind unterschiedlich geskinnt.** Bremen liefert fünf schlichte ``<td>``
(Datum · Titel · Verfahrensart · Rechtsrahmen · Frist), Sachsen eine Definitionsliste mit
Titel, Beschreibung, Auftraggeber und Fundstelle. Der Parser ist deshalb **feldsuchend statt
spaltenzählend**: er liest alle Zellen einer Zeile und ordnet sie über Muster zu. Ein
spaltenbasierter Parser hätte an der zweiten Instanz gebrochen.

⚠ **Es gibt keine portalseitige Vorgangs-ID.** Weder Bremen noch Sachsen tragen in der
Trefferzeile einen Link mit Kennung — nur Sortier- und Blätter-Links. Der Schlüssel wird
deshalb aus dem Inhalt gebildet (`sha1` über Portal + Veröffentlichung + Titel). Folge, die
man kennen muss: **korrigiert eine Vergabestelle den Titel, entsteht ein zweiter Satz.**
Die Dubletten-Firewall fängt das ab, aber es ist eine echte Grenze und kein Detail. Wo eine
Vergabenummer im Titel steht (`(V0471/2026)`, `(7A032308)`), wird sie zusätzlich als
Attribut mitgeführt — sie ist der stabilere Schlüssel, wenn er denn da ist.

Aufruf::

    python3 -m govisor.netserver --portale hb,sn,mv,bw,he --kategorien tender
    python3 -m govisor.netserver --nur-silber
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")

# Kürzel → (Land, Basis-URL). Bewusst eine Tabelle: eine weitere NetServer-Instanz mit dem
# üblichen Servlet ist eine Zeile, kein Codepfad.
PORTALE: dict[str, tuple[str, str | None]] = {
    "hb": ("Bremen", "https://vergabe.bremen.de/NetServer/"),
    "sn": ("Sachsen", "https://www.sachsen-vergabe.de/NetServer/"),
    "mv": ("Mecklenburg-Vorpommern", "https://vergabe.mv-regierung.de/NetServer/"),
    "bw": ("Baden-Württemberg", "https://vergabe.landbw.de/NetServer/"),
    # Hessen sucht anders als die vier anderen — eigener Pfad in `hole_had`. Die Basis-URL
    # bleibt None, damit der generische Servlet-Weg gar nicht erst versucht wird.
    "he": ("Hessen (HAD)", None),
    # Berlin und Saarland: 2026-08-14 ergaenzt. Beide fahren dieselbe NetServer-Software wie
    # die vier oben — sie standen nur nicht in dieser Tabelle. Das ist der ganze Aufwand
    # gewesen: die Landesportale waren nicht „nicht angebunden", sondern nicht eingetragen.
    # Gemessen an offenen Leads mit Unterlagen-Link: BE 85, SL 48.
    "be": ("Berlin", "https://vergabekooperation.berlin/NetServer/"),
    "sl": ("Saarland", "https://saarvpsl.vmstart.de/NetServer/"),
}

# NetServer-Kategorien → unser `notice_kind`.
KATEGORIEN = {
    "tender": ("InvitationToTender", "cn"),
    "vorinfo": ("PriorInformation", "pin"),
    "zuschlag": ("ContractAward", "can"),
}

_SERVLET = "PublicationSearchControllerServlet?function=SearchPublications"
# Das Suchformular bietet 10/25/50/100 Treffer je Seite an — 100 ist die vom Portal
# selbst angebotene Obergrenze, kein Umgehen einer Begrenzung. Spart Abrufe.
_MAX_PRO_SEITE = 100
# Obergrenze der Blätter je Kategorie — eine Notbremse gegen eine kaputte Endebedingung,
# kein fachliches Limit. Wird sie erreicht, sagt der Lauf es (sonst wäre es stiller Verlust).
_MAX_SEITEN = 20
_HOEFLICH_S = 2.0          # Pause zwischen Abrufen — fremdes System
_HAD_SUCHE = "https://www.had.de/onlinesuche_einfach.html"

_RECHTSRAHMEN = re.compile(r'\b(VOB|UVgO|VgV|VOL(?:/VgV)?|SektVO|KonzVgV|VSVgV)\b', re.I)
_VERFAHRENSART = re.compile(
    r'(Offenes Verfahren|Nicht ?offenes Verfahren|Beschränkte Ausschreibung|'
    r'Öffentliche Ausschreibung|Freihändige Vergabe|Verhandlungsverfahren[^,;]{0,40}|'
    r'Verhandlungsvergabe|Teilnahmewettbewerb)', re.I)
_DATUM = re.compile(r'\b(\d{2}\.\d{2}\.\d{4})\b')
_FRIST = re.compile(r'\b(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})')
# Reiner Datums-/Zeitstempel — nie ein Titel (s. Verdopplungs-Falle in `zeilen_lesen`).
_NUR_DATUM = re.compile(r'\s*\d{2}\.\d{2}\.\d{4}(?:\s+\d{2}:\d{2})?\s*')
_VERGABENR = re.compile(r'\(([A-Za-z0-9][A-Za-z0-9._/\-]{4,30})\)\s*$')
# Verfahren, die per Vorschrift unterschwellig sind bzw. es typischerweise anzeigen.
_UNTERSCHWELLIG = re.compile(r'UVgO|Freihändige|Beschränkte Ausschreibung|Verhandlungsvergabe', re.I)


def _txt(x: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()


def _datum(s: str | None):
    try:
        return dt.datetime.strptime((s or "").strip(), "%d.%m.%Y").date()
    except (ValueError, AttributeError):
        return None


def _frist(s: str | None):
    m = _FRIST.search(s or "")
    if not m:
        return None
    try:
        return dt.datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d.%m.%Y %H:%M")
    except ValueError:
        return None


def hol(url: str, timeout: int = 40) -> str:
    """Über ``curl``, NICHT ``urllib``.

    In dieser Umgebung scheitert `urllib` an einem TLS-Proxy und meldet für **jedes** Portal
    denselben Fehler. Genau daraus wurde im Projekt schon einmal ein Portalbefund abgeleitet
    („14 von 14 Plattformen …"), der keiner war. curl kommt durch.
    """
    r = subprocess.run(["curl", "-sL", "--max-time", str(timeout), "-A", UA, url],
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl exit {r.returncode} für {url}")
    return r.stdout.decode("utf-8", "replace")


def _spalten(seite: str) -> dict[str, int]:
    """Kopfzeile → {Spaltenname: Index}, sofern die Instanz eine führt.

    Nötig, weil die Vergabestelle je Skin anders auftaucht: MV und Baden-Württemberg
    führen eine **Spalte „Vergabestelle"**, Sachsen ein Feld „Auftraggeber:" in einer
    Definitionsliste, Bremen gar nichts. Ein rein musterbasierter Parser fand deshalb nur
    Sachsen und liess 68 Auftraggeber liegen — die dann am `JOIN buyer` des Lead-Baus
    lautlos ausgefallen wären.
    """
    kopf = re.search(r"<tr[^>]*>((?:(?!</tr>).)*?<th.*?)</tr>", seite, re.S | re.I)
    if not kopf:
        return {}
    namen = [_txt(t) for t in re.findall(r"<th[^>]*>(.*?)</th>", kopf.group(1), re.S | re.I)]
    return {n.lower(): i for i, n in enumerate(namen) if n}


def zeilen_lesen(seite: str) -> list[dict]:
    """Trefferzeilen feldsuchend auslesen — unabhängig von Spaltenzahl und Skin.

    Gibt je Zeile die erkannten Felder zurück. Nicht erkannte Felder bleiben leer; sie
    werden NICHT geraten. Eine Zeile ohne Titel gilt nicht als Vorgang.
    """
    aus: list[dict] = []
    spalten = _spalten(seite)
    # Spaltenindex der Vergabestelle, wo die Instanz eine Kopfzeile führt.
    i_stelle = next((i for n, i in spalten.items()
                     if "vergabestelle" in n or "auftraggeber" in n), None)
    for roh in re.findall(r"<tr[^>]*>(.*?)</tr>", seite, re.S | re.I):
        if "<td" not in roh.lower():
            continue
        zellen = [_txt(z) for z in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", roh, re.S | re.I)]
        zellen = [z for z in zellen if z]
        if not zellen:
            continue
        ganz = " · ".join(zellen)
        # Titel = längste Zelle, die nicht nur Datum/Verfahrensart ist. Bei Sachsen steht
        # der Titel im <strong>, deshalb der Vorzug für dessen Inhalt, wenn vorhanden.
        stark = [_txt(m) for m in re.findall(r"<strong[^>]*>(.*?)</strong>", roh, re.S | re.I)]
        stark = [s for s in stark if len(s) > 12]
        # Wo die Kopfzeile eine Titelspalte benennt, gilt SIE — nicht die längste Zelle.
        # Sonst gewinnt bei einem kurzen Titel die Vergabestelle: „Neubau Feuerwache Los 3"
        # (23 Zeichen) verlor gegen „Landesforst Mecklenburg Vorpommern" (34). In den echten
        # MV-Daten ging das nur zufällig gut, weil die Titel dort länger sind.
        i_titel = next((i for n, i in spalten.items()
                        if "ausschreibung" in n or "bezeichnung" in n or "titel" in n), None)
        aus_spalte = (zellen[i_titel] if i_titel is not None and i_titel < len(zellen) else None)
        if aus_spalte and len(aus_spalte) > 12 and not _NUR_DATUM.fullmatch(aus_spalte):
            titel = aus_spalte
        else:
            kandidaten = stark or [z for z in zellen if len(z) > 12 and not _DATUM.fullmatch(z)]
            if not kandidaten:
                continue
            titel = max(kandidaten, key=len)
        # Ein Datum/Zeitstempel ist kein Titel. Die Tabellen rendern jeden Vorgang ZWEIMAL —
        # einmal vollständig, einmal als reine Fristzeile („11.09.2026 10:00"). Die
        # Längenschwelle allein liess den Zeitstempel als Titel durch und verdoppelte damit
        # den Bestand: Bremen meldete 82 statt 41 Vorgänge.
        if (_VERFAHRENSART.fullmatch(titel) or len(titel) < 12
                or _NUR_DATUM.fullmatch(titel)):
            continue

        # Vergabestelle auf drei Wegen, in dieser Reihenfolge:
        #   1. Spalte laut Kopfzeile (MV, Baden-Württemberg)
        #   2. Feld „Auftraggeber:" in der Definitionsliste (Sachsen)
        #   3. gar nicht (Bremen führt sie nicht) — dann NULL, nicht geraten
        auftraggeber = None
        if i_stelle is not None and i_stelle < len(zellen):
            kand = zellen[i_stelle]
            # Nicht die Titelzelle und kein Datum/Verfahrensart erwischen.
            if (kand and kand != titel and not _NUR_DATUM.fullmatch(kand)
                    and not _VERFAHRENSART.fullmatch(kand) and len(kand) > 2):
                auftraggeber = kand
        if not auftraggeber:
            m_ag = re.search(r"Auftraggeber:?\s*(?:</dt>\s*<dd[^>]*>)?\s*([^<·]{3,80})", roh, re.I)
            auftraggeber = _txt(m_ag.group(1)) if m_ag else None

        daten = _DATUM.findall(ganz)
        frist = _frist(ganz)
        # Veröffentlichung = das früheste Datum, das NICHT die Frist ist.
        #
        # KEIN Rückfall auf „irgendein Datum": Sachsen führt in der Trefferliste gar kein
        # Veröffentlichungsdatum, nur die Abgabefrist. Ein Rückfall setzte dann die Frist
        # als Veröffentlichung — gemessen an allen 202 Zeilen, und das verschöbe Jahr/Monat
        # der Notice und damit den Marktpuls. Lieber NULL als ein falsches Datum.
        pub = None
        for d in daten:
            k = _datum(d)
            if k and (not frist or k != frist.date()):
                pub = k if pub is None or k < pub else pub

        m_rr = _RECHTSRAHMEN.search(ganz)
        m_va = _VERFAHRENSART.search(ganz)
        m_nr = _VERGABENR.search(titel)
        # Eine echte Trefferzeile trägt mindestens EIN hartes Vergabemerkmal. Ohne diese
        # Hürde zählen verschachtelte Layout-Tabellen als Vorgänge mit: bei Sachsen ergaben
        # sich so 202 „Zeilen", von denen nur 50 einen Rechtsrahmen hatten.
        if not (frist or m_rr):
            continue
        aus.append({
            "titel": titel,
            "auftraggeber": auftraggeber,
            "pub": pub.isoformat() if pub else None,
            "frist": frist.isoformat() if frist else None,
            "rechtsrahmen": m_rr.group(1).upper() if m_rr else None,
            "verfahrensart": m_va.group(1) if m_va else None,
            "vergabenummer": m_nr.group(1) if m_nr else None,
            "unterschwellig": bool(_UNTERSCHWELLIG.search(ganz)),
        })
    return aus


def schluessel(portal: str, satz: dict) -> str:
    """Inhaltsschlüssel — es gibt keine portalseitige ID (s. Modulkopf).

    Bewusst über Portal + Veröffentlichung + Titel und NICHT über die Frist: eine
    Fristverlängerung ist derselbe Vorgang und darf keinen zweiten Satz erzeugen.
    """
    roh = f"{portal}|{satz.get('pub') or ''}|{(satz.get('titel') or '').lower()}"
    return hashlib.sha1(roh.encode("utf-8")).hexdigest()[:16]


def hole_had(bekannt: set[str]) -> list[dict]:
    """Hessen (HAD) — eigener Pfad, weil HAD *nicht* wie die anderen vier sucht.

    Gemessen: unter ``/NetServer/`` liegen bei HAD nur die DETAILseiten; die Suche ist eine
    eigene Oberfläche (``onlinesuche_einfach.html``) mit einem POST-Formular, dessen
    Ergebnis sich per ``curl`` nicht reproduzieren liess (sechs Parameter-Varianten mit und
    ohne Sitzung: durchweg 6,4 KB ohne eine einzige Trefferzeile). Deshalb hier ein Browser
    — dieselbe Begründung wie bei DTVP, und ebenso wenig aus Bequemlichkeit.

    Zwei Fallen, beide beim Bauen zugeschlagen:
      * Die Seite trägt DREI Formulare. ``forms[0]`` ist der Sprachumschalter (submitten
        stellt die Seite auf Englisch), ``forms[1]`` das kleine Suchfeld, und erst
        ``forms[2]`` ist die Suche mit ``L_CAT``/``CNT``/``CMD``.
      * ``CMD`` ist ein RADIO, kein Absende-Knopf. Ein Klick darauf schickt nichts ab —
        nötig ist ``form.submit()``. Mit dem Klick kamen 0 Zeilen zurück, und das sah aus
        wie „HAD liefert nichts".

    Die Trefferliste ist dafür die reichste aller fünf Instanzen: HAD-Referenz, Verfahren,
    Leistung, Veröffentlichung UND Ablauftermin, Vergabestelle mit Ort, Leistungsort.
    """
    from playwright.sync_api import sync_playwright

    aus: list[dict] = []
    heute = dt.date.today().isoformat()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        pg = browser.new_page()
        pg.set_default_timeout(45000)
        pg.goto(_HAD_SUCHE, wait_until="domcontentloaded")
        pg.wait_for_timeout(1500)
        pg.evaluate("""() => {
          const f = document.forms[2];                 // NICHT forms[0] (Sprache)
          f.querySelector("[name='L_CAT']").value = 'SQLM';
          const c = [...f.querySelectorAll("[name='CNT']")].find(r => r.value === '500');
          if (c) c.checked = true;                     // 500 = die vom Portal angebotene Obergrenze
          const se = [...f.querySelectorAll("[name='CMD']")].find(r => r.value === 'SE');
          if (se) se.checked = true;
          f.submit();                                  // CMD ist ein Radio, kein Submit-Knopf
        }""")
        pg.wait_for_timeout(9000)
        # Zeilenumbrüche BEHALTEN — sie sind hier die Struktur, nicht Formatierung.
        # Zelle 1 trennt per Umbruch: Verfahrensart → Leistungsart → eigentlicher Titel.
        # Mit `\s+ → ' '` verschmilzt alles zu „Auftragsbekanntmachung – allgemeine
        # Richtlinie, Standardregelung Offenes Verfahren (Dienstleistungen) Stadtteil…",
        # und jeder HAD-Titel begänne mit demselben Formularsatz. Fuer den Abgleich gegen
        # den Bestand waere das toedlich: gemeinsame Wortstaemme ueberall, Trennschaerfe null.
        zeilen = pg.evaluate("""() => {
          const t = [...document.querySelectorAll('table')]
                      .sort((a, b) => b.rows.length - a.rows.length)[0];
          if (!t) return [];
          return [...t.rows].map(r => [...r.cells].map(c => c.innerText.trim()));
        }""")
        browser.close()

    for z in zeilen:
        if len(z) < 5:
            continue
        _ref, verfahren, daten, stelle, _ort = z[0], z[1], z[2], z[3], z[4]
        # Letzter nicht-leerer Block der Zelle = der Auftragsgegenstand.
        bloecke = [b.strip() for b in (verfahren or "").split("\n") if b.strip()]
        if not bloecke:
            continue
        titel = bloecke[-1]
        # Faellt der letzte Block als Verfahrensart aus (kurze Zeilen wie „Bauleistung"),
        # den laengsten Block nehmen — nie den ersten, der ist immer der Formularsatz.
        if len(titel) < 12 and len(bloecke) > 1:
            titel = max(bloecke[1:], key=len)
        if len(titel) < 12 or titel.lower().startswith("verfahren"):
            continue
        # „14.08.2026 / 11.09.2026" = Veröffentlichung, dann Ablauftermin.
        dd = _DATUM.findall(daten or "")
        pub = _datum(dd[0]) if dd else None
        frist = _datum(dd[1]) if len(dd) > 1 else None
        m_rr = _RECHTSRAHMEN.search(verfahren)
        m_va = _VERFAHRENSART.search(verfahren)
        satz = {
            "titel": titel[:400],
            "auftraggeber": (stelle or "").split("\n")[0][:120] or None,
            "pub": pub.isoformat() if pub else None,
            "frist": dt.datetime.combine(frist, dt.time()).isoformat() if frist else None,
            "rechtsrahmen": m_rr.group(1).upper() if m_rr else None,
            "verfahrensart": m_va.group(1) if m_va else None,
            "vergabenummer": None,
            "unterschwellig": bool(_UNTERSCHWELLIG.search(verfahren)),
            "portal": "he", "land": PORTALE["he"][0], "kategorie": "tender",
            "erfasst_am": heute,
        }
        satz["key"] = schluessel("he", satz)
        if satz["key"] in bekannt:
            continue
        bekannt.add(satz["key"])
        aus.append(satz)
    unter = sum(1 for z in aus if z["unterschwellig"])
    print(f"  he/tender: {len(zeilen)} Zeilen, {len(aus)} neu, {unter} unterschwellig", flush=True)
    return aus


def hole(portale: list[str], kategorien: list[str], bekannt: set[str]) -> list[dict]:
    saetze: list[dict] = []
    for kuerzel in portale:
        if kuerzel == "he":                      # eigener Suchweg, s. `hole_had`
            try:
                saetze += hole_had(bekannt)
            except Exception as e:               # noqa: BLE001
                print(f"  he: Abruf fehlgeschlagen ({type(e).__name__}) — "
                      f"Playwright installiert?", flush=True)
            continue
        land, basis = PORTALE.get(kuerzel, (kuerzel, None))
        if not basis:
            print(f"  {kuerzel}: kein Suchendpunkt hinterlegt — übersprungen", flush=True)
            continue
        for kat in kategorien:
            cat, _kind = KATEGORIEN[kat]
            # Blättern über `Start`. Ohne das endet jede Kategorie stumm bei 100 Treffern:
            # gemessen lieferte Baden-Württemberg genau 100 und trug einen Blätter-Link
            # `Start=100` — der Rest wäre nie geholt worden, ohne dass irgendwo ein Fehler
            # auftaucht. Die anderen drei Portale lagen darunter und hätten den Fehler
            # verdeckt.
            zeilen: list[dict] = []
            for start in range(0, _MAX_SEITEN * _MAX_PRO_SEITE, _MAX_PRO_SEITE):
                url = (f"{basis}{_SERVLET}&Gesetzesgrundlage=All&Category={cat}"
                       f"&Max={_MAX_PRO_SEITE}&Start={start}")
                try:
                    seite = hol(url)
                except Exception as e:                   # noqa: BLE001
                    print(f"  {kuerzel}/{kat}: nicht erreichbar ({type(e).__name__})", flush=True)
                    break
                teil = zeilen_lesen(seite)
                if not teil:
                    break
                zeilen += teil
                # Volle Seite → es kann eine weitere geben. Kürzere Seite = Ende.
                if len(teil) < _MAX_PRO_SEITE:
                    break
                time.sleep(_HOEFLICH_S)
            if not zeilen:
                continue
            neu = 0
            heute = dt.date.today().isoformat()
            for z in zeilen:
                z["portal"], z["land"], z["kategorie"] = kuerzel, land, kat
                # Wann WIR die Zeile gesehen haben. Nötig, weil Sachsen in der Trefferliste
                # gar kein Veröffentlichungsdatum führt (gemessen: 0 von 50). Das ist eine
                # Tatsache über uns, kein erfundenes Quellendatum — und es hält die Sätze
                # aus der `year=0`-Partition, ohne ein Datum zu behaupten.
                z["erfasst_am"] = heute
                z["key"] = schluessel(kuerzel, z)
                if z["key"] in bekannt:
                    continue
                bekannt.add(z["key"])
                saetze.append(z)
                neu += 1
            # `--neu-einlesen` ist kein Komfort, sondern nötig: Bronze speichert die
            # GEPARSTE Zeile, nicht das rohe HTML. Verbessert sich der Parser, sind die
            # alten Sätze trotzdem „bekannt" und werden übersprungen — hier passiert:
            # nach dem Vergabestellen-Fix meldete MV weiter 0 % Stellen, weil die 18 Sätze
            # aus dem Lauf davor unverändert liegen blieben. Anders als bei TED/DÖE heilt
            # ein Parser-Fix hier also NICHT durch erneutes Lesen lokaler Dateien.
            unter = sum(1 for z in zeilen if z["unterschwellig"])
            print(f"  {kuerzel}/{kat}: {len(zeilen)} Zeilen, {neu} neu, "
                  f"{unter} unterschwellig", flush=True)
            time.sleep(_HOEFLICH_S)
    return saetze


def schreibe_bronze(saetze: list[dict], country: str = "DE") -> dict:
    """Nach Monat gebündelt als JSONL, dedupliziert über `key`. Idempotent.

    Verlustfreiheit liegt wie bei TED/DÖE/simap/DTVP in Bronze: ein Parser-Fix kostet einen
    Re-Run über lokale Dateien, keinen erneuten Abruf beim Portal.
    """
    root = ROOT / "data" / "raw_netserver" / country
    root.mkdir(parents=True, exist_ok=True)
    nach_monat: dict[str, list[dict]] = {}
    for s in saetze:
        # Ohne Veröffentlichungsdatum nach Erfassungsmonat ablegen — die Datei bleibt so
        # auffindbar und der Re-Run idempotent.
        monat = (s.get("pub") or s.get("erfasst_am") or "")[:7] or "unbekannt"
        nach_monat.setdefault(monat, []).append(s)
    stat: dict[str, tuple[int, int]] = {}
    for monat, neue in nach_monat.items():
        pfad = root / f"{monat}.jsonl"
        vorhanden: dict[str, dict] = {}
        if pfad.exists():
            for zeile in pfad.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(zeile)
                    vorhanden[r["key"]] = r
                except (json.JSONDecodeError, KeyError):
                    continue
        vor = len(vorhanden)
        for r in neue:
            vorhanden[r["key"]] = r
        pfad.write_text("\n".join(json.dumps(r, ensure_ascii=False)
                                  for r in vorhanden.values()) + "\n", encoding="utf-8")
        stat[monat] = (len(vorhanden) - vor, len(vorhanden))
    return stat


def bekannte_keys(country: str = "DE") -> set[str]:
    root = ROOT / "data" / "raw_netserver" / country
    aus: set[str] = set()
    if not root.exists():
        return aus
    for f in root.glob("*.jsonl"):
        for zeile in f.read_text(encoding="utf-8").splitlines():
            m = re.search(r'"key":\s*"([0-9a-f]+)"', zeile)
            if m:
                aus.add(m.group(1))
    return aus


# ── Bronze → Silber ───────────────────────────────────────────────────────────────────────
#
# Dieselbe CPV-Frage wie bei DTVP, dieselbe Antwort: **VOB/A ist per Definition die Vergabe-
# und Vertragsordnung für BAULEISTUNGEN**, also CPV-Division 45 — das ist keine Vermutung,
# sondern der Geltungsbereich der Vorschrift. Für VOL/UVgO/VgV gibt es keine solche
# Ableitung (kann IT, Reinigung, Beratung, Medizintechnik sein), dort bleibt `cpv_main`
# NULL. Eine erfundene Branche wäre schlimmer als eine fehlende.
_CPV_AUS_REGELWERK = {"VOB": "45000000-7"}
_NATUR = {"VOB": "works"}


def nach_silber(country: str = "DE") -> dict:
    """Bronze-JSONL → Silber-Parquet (notices, notice_parties, attributes).

    `notice_id` ist ``ns:<portal>:<key>`` — der Präfix hält den Namensraum von TED-IDs
    getrennt (dieselbe Konvention wie DÖE und DTVP).
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    roh_dir = ROOT / "data" / "raw_netserver" / country
    if not roh_dir.exists():
        print(f"kein Bronze-Bestand unter {roh_dir}")
        return {}
    saetze: list[dict] = []
    for f in sorted(roh_dir.glob("*.jsonl")):
        for zeile in f.read_text(encoding="utf-8").splitlines():
            try:
                saetze.append(json.loads(zeile))
            except json.JSONDecodeError:
                continue
    if not saetze:
        return {}

    notices, parties, attrs = [], [], []
    for r in saetze:
        nid = f"ns:{r['portal']}:{r['key']}"
        pub = dt.date.fromisoformat(r["pub"]) if r.get("pub") else None
        # `publication_date` bleibt NULL, wenn die Quelle keins führt — kein erfundenes
        # Datum. Für year/month tritt ersatzweise das Erfassungsdatum ein: sonst landen
        # alle sächsischen Sätze in `year=0` und fallen aus jeder Zeitreihe. Die Herkunft
        # steht als Attribut daneben, damit die gröbere Angabe sichtbar bleibt.
        platz = pub or (dt.date.fromisoformat(r["erfasst_am"]) if r.get("erfasst_am") else None)
        frist = dt.datetime.fromisoformat(r["frist"]) if r.get("frist") else None
        rr = (r.get("rechtsrahmen") or "").upper()
        # „VOL/VGV" trägt beide; für die CPV-Ableitung zählt nur reines VOB.
        cpv = _CPV_AUS_REGELWERK.get(rr)
        _, kind = KATEGORIEN.get(r.get("kategorie", "tender"), ("", "cn"))
        notices.append({
            "notice_id": nid, "publication_number": r["key"], "oj_ref": None,
            "publication_date": pub, "ted_url": None, "country": country,
            "buyer_countries": [country],
            "year": platz.year if platz else None, "month": platz.month if platz else None,
            "schema_gen": "netserver", "form_type": r.get("verfahrensart"),
            "notice_kind": kind,
            "language": "de",                       # kleingeschrieben — Guard-Konvention
            "title": r.get("titel"), "description": None, "description_field": None,
            "cpv_main": cpv, "performance_nuts": None,
            "contract_nature": _NATUR.get(rr),
            "procedure_type": r.get("verfahrensart"),
            "submission_deadline": frist,
            "portal_url": PORTALE.get(r["portal"], ("", None))[1],
            "estimated_value": None, "final_value": None, "value_currency": None,
            "award_date": None, "start_date": None, "end_date": None,
            "lot_count": None, "text_chars": len(r.get("titel") or ""),
            "ref_publication_number": None, "ref_ted_url": None,
            "flags": [], "unknown_country_codes": [],
        })
        # Vergabestelle: echt, wo die Quelle sie führt — sonst eine ausdrücklich als
        # unbekannt benannte Sammelstelle je Portal.
        #
        # Warum überhaupt eine Ersatz-Partei: `gold.build_prospective_leads` verbindet mit
        # `JOIN buyer`. Ohne Partei fällt der Vorgang lautlos aus der Lead-Schicht — bei
        # Bremen wären das ALLE 41 Ausschreibungen, weil das Portal die Stelle in der
        # Trefferliste nicht ausweist (gemessen: 0 von 41; die Spalte existiert dort nicht).
        #
        # Warum dieser Name: er ist als Nicht-Stelle lesbar und kann in keiner Auswertung
        # mit einer echten Vergabestelle verwechselt werden. Ein plausibel klingender Name
        # wie „Freie Hansestadt Bremen" wäre die schlechtere Wahl — er sähe wie ein Fakt
        # aus und würde `buyer_stats` still verfälschen, indem 41 verschiedene Dienststellen
        # zu einem Grosskäufer verschmölzen.
        stelle = r.get("auftraggeber")
        stelle_hergeleitet = not stelle
        if stelle_hergeleitet:
            stelle = f"Vergabestelle nicht ausgewiesen ({PORTALE.get(r['portal'], (r['portal'], None))[0]})"
        if stelle_hergeleitet:
            attrs.append({"notice_id": nid, "path": "netserver/stelle_unbekannt",
                          "value": "Portal führt die Vergabestelle nicht in der Trefferliste"})
        if stelle:
            parties.append({
                "notice_id": nid, "role": "buyer", "seq": 0, "name": stelle,
                "national_id": None, "town": None, "postal_code": None, "country": country,
                "nuts": None, "email": None, "phone": None, "contact_person": None,
                "url": None, "is_sme": None, "in_consortium": None,
                "year": platz.year if platz else None,
            })
        attrs.append({"notice_id": nid, "path": "netserver/portal", "value": r["portal"]})
        if r.get("erfasst_am"):
            attrs.append({"notice_id": nid, "path": "netserver/erfasst_am",
                          "value": r["erfasst_am"]})
        if not pub:
            attrs.append({"notice_id": nid, "path": "netserver/zeitpunkt_aus_erfassung",
                          "value": "Quelle führt kein Veröffentlichungsdatum"})
        attrs.append({"notice_id": nid, "path": "netserver/land", "value": r.get("land")})
        if rr:
            attrs.append({"notice_id": nid, "path": "netserver/rechtsrahmen", "value": rr})
        if r.get("vergabenummer"):
            # Der stabilere Schlüssel, wo er existiert — für spätere Dubletten-Prüfung.
            attrs.append({"notice_id": nid, "path": "netserver/vergabenummer",
                          "value": r["vergabenummer"]})
        if r.get("unterschwellig"):
            attrs.append({"notice_id": nid, "path": "netserver/unterschwellig", "value": "ja"})
        if cpv:
            attrs.append({"notice_id": nid, "path": "netserver/cpv_hergeleitet",
                          "value": f"aus Regelwerk {rr}"})

    stat = {}
    for name, zeilen in (("notices", notices), ("notice_parties", parties),
                         ("attributes", attrs)):
        nach_jahr: dict[int, list] = {}
        for z in zeilen:
            nach_jahr.setdefault(z.get("year") or 0, []).append(z)
        n = 0
        for jahr, gruppe in nach_jahr.items():
            d = ROOT / "data" / "silver" / country / name / f"year={jahr}"
            d.mkdir(parents=True, exist_ok=True)
            pq.write_table(pa.Table.from_pylist(gruppe), d / f"{jahr}-netserver.parquet",
                           compression="zstd")
            n += len(gruppe)
        stat[name] = n
    ohne_cpv = sum(1 for x in notices if not x["cpv_main"])
    unter = sum(1 for r in saetze if r.get("unterschwellig"))
    print(f"NetServer Silber {country}: " + " · ".join(f"{k} {v:,}" for k, v in stat.items()))
    print(f"  cpv_main aus Regelwerk hergeleitet: {len(notices)-ohne_cpv:,} (VOB/A = Bauleistung)")
    print(f"  ohne CPV (VOL/UVgO/VgV, bewusst NULL): {ohne_cpv:,}")
    print(f"  als unterschwellig erkannt:          {unter:,}")
    return stat


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--portale", default="hb,sn,mv,bw,he",
                   help="Kürzel, Komma-getrennt: " + ", ".join(PORTALE))
    p.add_argument("--kategorien", default="tender",
                   help="tender (Ausschreibung) · vorinfo · zuschlag")
    # Gleiche Bedeutung wie bei `govisor.dtvp`: `--silber` schreibt NACH dem Abruf auch
    # nach Silber. Eine abweichende Bedeutung waere im Tageslauf eine stille Falle.
    p.add_argument("--silber", action="store_true",
                   help="nach dem Abruf auch Bronze -> Silber schreiben")
    p.add_argument("--nur-silber", action="store_true",
                   help="kein Abruf, nur Bronze -> Silber")
    p.add_argument("--neu-einlesen", action="store_true",
                   help="bekannte Vorgaenge erneut holen und ueberschreiben - noetig nach "
                        "jeder Parser-Aenderung, weil Bronze die geparste Zeile speichert")
    p.add_argument("--dry-run", action="store_true", help="abrufen, nichts schreiben")
    a = p.parse_args(argv)

    if a.nur_silber:
        nach_silber()
        return 0

    portale = [x.strip() for x in a.portale.split(",") if x.strip()]
    kats = [x.strip() for x in a.kategorien.split(",") if x.strip()]
    unbekannt = [k for k in kats if k not in KATEGORIEN]
    if unbekannt:
        print(f"unbekannte Kategorie: {unbekannt} — erlaubt: {list(KATEGORIEN)}", file=sys.stderr)
        return 2

    bekannt = set() if (a.dry_run or a.neu_einlesen) else bekannte_keys()
    print(f"NetServer-Abruf: {len(portale)} Portale, {len(bekannt):,} Vorgänge bereits bekannt")
    saetze = hole(portale, kats, bekannt)
    print(f"\n{len(saetze):,} neue Bekanntmachungen")
    if a.dry_run:
        for s in saetze[:5]:
            print("  ", json.dumps(s, ensure_ascii=False)[:150])
        return 0
    for monat, (neu, gesamt) in sorted(schreibe_bronze(saetze).items()):
        print(f"  {monat}: +{neu} → {gesamt}")
    if a.silber:
        nach_silber()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
