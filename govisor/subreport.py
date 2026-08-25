"""Quelle DE — subreport ELViS: **Dateilisten**, nicht Dateien.

**Was hier bewusst NICHT passiert: die Vergabeunterlagen herunterladen.** Gemessen
2026-08-14 über drei Vergaben und alle Knopfpositionen: der Download reagiert ohne
Anmeldung nicht. Genau ein Knopf liefert — der erste —, und der trägt die
**Bekanntmachung**, nicht die Unterlagen; im PDF steht wörtlich „Dies ist eine
unverbindliche Darstellung der eForms-formatierten Bekanntmachung". Die haben wir längst
über TED. Ein frischer Versuch mit Knopf 3 bzw. dem ZIP-Knopf als ERSTEM Klick lieferte
gar nichts, es ist also auch kein „ein Download je Sitzung".

⚠ Diese Datei existiert, weil beim Erkunden zweimal zu früh geschlossen wurde:

* Erst galt subreport-elvis.de als **Bot-Sperre**. Falsch — die Seite rendert clientseitig,
  `curl` bekommt nur die Hülle, im Browser lädt sie normal.
* Dann galt sie als **offen**, weil ein Klick ein PDF brachte. Ebenfalls falsch — es war
  die Bekanntmachung. `scripts/probe_portals.py` warnt im eigenen Modulkopf vor exakt
  diesem Fehlschluss („unterscheidet eine Vergabeunterlage nicht von einem beliebigen
  PDF"), und er ist trotzdem noch einmal passiert.

**Was öffentlich IST: die vollständige Dateiliste** mit Namen, und die trägt Substanz.
`govisor.doctypes.classify()` trifft laut Struktur-Studie 69 % der Dokumenttypen allein aus
dem Namen; an einer Stichprobe echter subreport-Namen waren es 7 von 13, darunter drei
Extraktions-Prioritätstypen:

    Brandschutzzentrum Trier - 050 Blitzschutz - LV.pdf   → leistungsbeschreibung ★
    FB 124 Eigenerklärung zur Eignung.pdf                 → eignung ★
    FB 211_EU Aufforderung zur Abgabe eines Angebots.pdf  → aufforderung ★

Damit lässt sich beantworten, ob ein Leistungsverzeichnis existiert und welche Nachweise
verlangt werden — ohne eine einzige Datei zu besitzen. Das ersetzt die Unterlagen nicht und
gibt auch nicht vor, es zu tun; der Status im Manifest heisst deshalb ``nur_liste``.

**Rechtlich unbedenklich:** gelesen wird die öffentlich angezeigte Liste. Es wird nichts
umgangen, keine Anmeldung versucht, keine Datei geholt, die eine Anmeldung verlangt.

Aufruf::

    python3 -m govisor.subreport --limit 50
    python3 -m govisor.subreport --limit 5 --dry-run
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

from . import docfetch_queue as _queue

ROOT = Path(__file__).resolve().parent.parent

# Wie lange ein Lauf OHNE ein einziges neues Ergebnis weiterlaufen darf. Der Fall, der am
# 2026-08-21 zwei Abrufer 54 Stunden hat laufen lassen, war nicht ein haengender Vorgang,
# sondern ein Abrufer, der beschaeftigt aussah und nichts mehr lieferte.
LEERLAUF_S = int(__import__("os").environ.get("GOVISOR_LEERLAUF", "3600"))

# Nur diese Hosts — beide führen auf dieselbe ELViS-Oberfläche.
_HOSTS = ("subreport.de", "subreport-elvis.de")
_WARTE_SEITE_MS = 6000     # clientseitiges Rendern; darunter kam eine leere Hülle
_WARTE_LISTE_MS = 6000     # nach dem Ausklappen der Dateiliste
_HOEFLICH_MS = 1500

# Dateinamen in der ausgeklappten Liste. Die Namen stehen als Textzeilen, nicht als Links —
# ein href-basierter Sucher findet hier nichts (und meldet faelschlich „keine Dateien").
_DATEI = re.compile(r"[^\s/][^\n]*\.(?:pdf|zip|docx?|xlsx?|rtf|dwg|gaeb|x8\d|d8\d|p8\d)\b",
                    re.IGNORECASE)


_ELVIS_ID = re.compile(r"/(E\d{6,})\b")


def ist_subreport(url: str | None) -> bool:
    return bool(url) and any(h in url for h in _HOSTS)


def vergabeseite(url: str) -> str | None:
    """`documents_url` → URL der Vergabeseite, aus der sich die Dateiliste holen lässt.

    Gemessen an 985 offenen subreport-Leads liegen ZWEI Formen vor:

        673  https://www.subreport.de/E74857938                      (Vergabeseite)
        312  https://www.subreport-elvis.de/download/bund/E63477415/…/bekanntmachung.pdf

    Die zweite zeigt direkt auf die Bekanntmachungs-PDF. Ein Aufruf davon startet einen
    Download statt eine Seite (Playwright: „Download is starting") — genau daran scheiterte
    der erste Lauf. Die ELVIS-Kennung steht aber IN der URL, die Vergabeseite ist also
    ableitbar. Es sind exakt die 312 Vorgänge, die in der Portal-Landkarte bis heute als
    „subreport-elvis, Bot-Sperre" standen: keine Sperre, nur eine zweite URL-Form.
    """
    if not url:
        return None
    m = _ELVIS_ID.search(url)
    if not m:
        return None
    return f"https://www.subreport.de/{m.group(1)}"


def _liste_von_seite(pg) -> list[str]:
    """Dateinamen aus dem sichtbaren Text der ausgeklappten Liste."""
    txt = pg.evaluate("() => document.body.innerText")
    namen: list[str] = []
    for zeile in txt.split("\n"):
        z = zeile.strip()
        if not z or len(z) > 160:
            continue
        m = _DATEI.search(z)
        if m:
            namen.append(m.group(0).strip())
    # Reihenfolge erhalten, Dubletten raus.
    gesehen, aus = set(), []
    for n in namen:
        if n.lower() not in gesehen:
            gesehen.add(n.lower())
            aus.append(n)
    return aus


# Die Ueberschrift des Unterlagen-Abschnitts. Alles darueber gehoert zur BEKANNTMACHUNG
# und traegt einen eigenen `download`-Knopf — wer den ganzen Seitentext prueft, verwechselt
# beides. (Dieselbe Falle wie bei NetServer am 2026-08-24, dort war es die Brotkrume.)
_ABSCHNITT = ("Access to the tender documents", "Zugang zu den Vergabeunterlagen")

# ⚠ Gemessen sind die ENGLISCHEN Formen: die Seiten kommen anonym auf Englisch. Die
# deutschen Entsprechungen stehen als beste Annahme daneben und sind UNGEPRUEFT — wer sie
# bestaetigt oder widerlegt, streicht diesen Hinweis.
_ABGELAUFEN = ("Validity expired", "Gültigkeit abgelaufen")
_AUFGEHOBEN = ("canceled", "aufgehoben")
_LOGIN_HINWEIS = ("Already registered", "Bereits registrierte")
_PASSWORT = ("password for the restricted tender", "Passwort für die beschränkte")


# Wie weit der Abschnitt reicht. ⚠ Ohne Grenze waere es „alles ab der Ueberschrift" —
# inklusive Fusszeile und Hinweistexten. Ein „canceled" irgendwo weiter unten wuerde dann
# eine laufende Vergabe abstempeln. Vor dem Ausklappen ist die Tabelle klein (eine Zeile je
# Paket), 900 Zeichen fassen sie mit Reserve.
_ABSCHNITT_MAX = 900


def _abschnitt(txt: str) -> str | None:
    for k in _ABSCHNITT:
        i = txt.find(k)
        if i >= 0:
            return txt[i:i + _ABSCHNITT_MAX]
    return None


def hole_liste(url: str, pg) -> dict:
    """Eine Vergabe → Dateiliste ODER der Grund, warum es keine gibt.

    ⚠ Bis zum 2026-08-24 gab diese Funktion nur eine Zahl zurueck, und der Aufrufer machte
    daraus „nur_liste" oder „leer". 124 Vorgaenge standen damit als „0 Dateien" da — ein
    Satz, der wie „diese Vergabe hat keine Unterlagen" klingt und in Wahrheit vier voellig
    verschiedene Dinge bedeutete. Gemessen an einer Stichprobe von 20:

        ~50 %  `Download` statt `display` + „Already registered …"  → Anmeldung noetig
        ~40 %  Statusspalte „Validity expired" bzw. „canceled"      → Fenster zu
        ~10 %  Passwortabfrage („restricted tender")                → beschraenkte Vergabe
          Rest wirklich unerklaert

    Jeder dieser Faelle braucht eine andere Antwort: warten auf ein Konto, nie wieder
    versuchen, oder nachsehen. Als eine Zahl waren sie ununterscheidbar.
    """
    pg.goto(url, wait_until="domcontentloaded")
    pg.wait_for_timeout(_WARTE_SEITE_MS)
    txt = pg.evaluate("() => document.body.innerText")
    ab = _abschnitt(txt)
    if ab is None:
        return {"dateien": [], "gefunden": 0, "status": "fehler",
                "note": "kein Unterlagen-Abschnitt"}
    # ⚠ REIHENFOLGE: der Ausklapper gewinnt IMMER. Traegt die Tabelle ein „display", ist
    # etwas zu holen — dann wird geholt, egal was sonst auf der Seite steht. Erst wenn es
    # ihn NICHT gibt, wird nach dem Grund gesucht. Andersherum koennte ein Wort aus einer
    # Nachbarzeile eine laufende Vergabe abstempeln, und der Fehler waere unsichtbar: er
    # produziert keinen Fehlschlag, sondern eine falsche Gewissheit.
    if not ("display" in ab or "anzeigen" in ab):
        if any(w in ab for w in _ABGELAUFEN):
            return {"dateien": [], "gefunden": 0, "status": "abgelaufen",
                    "note": "Gültigkeit abgelaufen"}
        if any(w in ab for w in _AUFGEHOBEN):
            return {"dateien": [], "gefunden": 0, "status": "aufgehoben",
                    "note": "Vergabe aufgehoben"}
        # Kein Ausklapper, aber der Hinweis auf angemeldete Nutzer: die Unterlagen sind da,
        # uns fehlt der Zugang. Das ist BLOCKIERT, nicht „leer" — sonst laeuft der Vorgang
        # jede Woche erneut gegen dieselbe Wand und liest sich obendrein wie „nichts da".
        if any(w in txt for w in _LOGIN_HINWEIS):
            return {"dateien": [], "gefunden": 0, "status": "gated",
                    "note": "Download nur für angemeldete Nutzer"}
        return {"dateien": [], "gefunden": 0, "status": "leer", "note": "0 Dateien"}

    try:
        pg.click("xpath=//button[normalize-space()='display' or normalize-space()='anzeigen']")
        pg.wait_for_timeout(_WARTE_LISTE_MS)
    except Exception:                                    # noqa: BLE001
        pass                                             # manche Vergaben zeigen die Liste direkt

    danach = pg.evaluate("() => document.body.innerText")
    if any(w in danach for w in _PASSWORT):
        # Beschraenkte Vergabe: das Passwort geht an eingeladene Bieter. Wir bewerben uns
        # nicht, es wird also nicht versucht. Eigene Klasse statt „leer", damit sichtbar
        # bleibt, dass hier Unterlagen LIEGEN.
        return {"dateien": [], "gefunden": 0, "status": "passwortgeschuetzt",
                "note": "beschränkte Vergabe, Passwort nötig"}
    namen = _liste_von_seite(pg)
    return {"dateien": namen, "gefunden": len(namen),
            "status": "nur_liste" if namen else "leer",
            "note": f"{len(namen)} Dateien"}


def lauf(limit: int | None, dry_run: bool, country: str = "DE",
         alles_neu: bool = False) -> dict:
    import duckdb
    from playwright.sync_api import sync_playwright

    from . import doctypes

    L = ROOT / "data" / "gold" / country / "lead_export.parquet"
    out = ROOT / "data" / "docs" / country / "doc_listing_subreport.parquet"
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT lead_id, documents_url FROM read_parquet('{L.as_posix()}')
        WHERE phase='open' AND documents_url IS NOT NULL
          AND (documents_url LIKE '%subreport.de%' OR documents_url LIKE '%subreport-elvis.de%')
          -- Wie im Unterlagen-Abruf: der Fristtag selbst faellt raus, seine Uhrzeit ist
          -- beim Lauf meist vorbei; und Open House hat keine Unterlagen zum Bieten.
          AND deadline_date > current_date
          AND coalesce(procedure_kind, '') <> 'open_house'
        ORDER BY deadline_date ASC
    """).fetchall()

    # Idempotenz. Eine Vergabe braucht rund 14 s (clientseitiges Rendern, zweimal warten);
    # 985 offene subreport-Vorgaenge waeren vier Stunden — jeden Tag neu, fuer Listen, die
    # sich nicht mehr aendern. Bekannte Vorgaenge fallen deshalb raus. Die Dateiliste einer
    # laufenden Vergabe kann sich zwar noch aendern (Nachtraege), aber das faengt der
    # naechste Durchlauf ueber `--alles-neu` ab; taeglich alles neu zu holen waere das
    # gleiche Muster wie der Bronze-Stau bei NetServer, nur andersherum.
    altbestand: list[dict] = []
    if out.exists() and not alles_neu:
        altbestand = con.execute(
            f"SELECT * FROM '{out.as_posix()}'").arrow().read_all().to_pylist()
        bekannt = {s["lead_id"] for s in altbestand}
        vorher = len(rows)
        rows = [r for r in rows if r[0] not in bekannt]
        if vorher != len(rows):
            print(f"subreport: {vorher - len(rows)} bereits erfasst, werden übersprungen")
    # Zweite Erinnerung, andere Frage. `bekannt` oben ueberspringt, was ERFASST wurde;
    # die Warteschlange ueberspringt, was GESCHEITERT ist. Ohne sie liefen genau die
    # Vorgaenge ewig mit, die unten per `continue` gar keinen Satz hinterlassen.
    _mroot = out.parent
    rows, _weg = _queue.filtere(rows, _queue.frueher(_mroot, "subreport"))
    if _weg:
        print(_queue.bericht(_weg))
    _manifest: list[dict] = []
    if limit:
        rows = rows[:limit]
    print(f"subreport: {len(rows)} offene Vergaben zu prüfen")

    saetze: list[dict] = []
    heute = dt.date.today().isoformat()
    def _sichern():                     # laeuft, wenn die Wache hart abbricht
        if _manifest:
            _queue.schreibe(_mroot, "subreport", _manifest)

    with _queue.Wache("subreport", vorgang_hart_s=0, leerlauf_s=LEERLAUF_S,
                      sichern=_sichern) as wache, sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context()
        pg = ctx.new_page()
        pg.set_default_timeout(45000)
        for i, (lead_id, url) in enumerate(rows, 1):
            seite = vergabeseite(url)
            if not seite:
                print(f"  [{i}/{len(rows)}] {lead_id}: keine ELVIS-Kennung in der URL", flush=True)
                _manifest.append({"lead_id": lead_id, "status": "keine_kennung",
                                  "note": "keine ELVIS-Kennung in der URL"})
                continue
            try:
                r = hole_liste(seite, pg)
            except Exception as e:                       # noqa: BLE001
                print(f"  [{i}/{len(rows)}] {lead_id}: Fehler ({type(e).__name__})", flush=True)
                _manifest.append({"lead_id": lead_id, "status": "fehler",
                                  "note": f"{type(e).__name__}"})
                continue
            typen = [doctypes.classify(n) for n in r["dateien"]]
            prio = sorted({t for t in typen if doctypes.is_priority(t)},
                          key=doctypes.priority_rank)
            saetze.append({
                "lead_id": lead_id, "url": seite, "url_quelle": url, "erfasst_am": heute,
                "n_dateien": r["gefunden"], "dateien": r["dateien"],
                "doktypen": typen, "prioritaetstypen": prio,
                # Ehrlicher Status: die LISTE haben wir, die Dateien nicht. Welcher es
                # ist, weiss nur die Seite selbst — deshalb kommt er aus `hole_liste`.
                "status": r["status"],
            })
            wache.erfolg()
            # Schlank ins Manifest: Status und Zahl, NICHT die Dateiliste. Das Manifest
            # beantwortet „nochmal versuchen?", nicht „was lag drin" — dafuer gibt es
            # `doc_listing_subreport.parquet`. Zwei Dateien mit demselben Inhalt liefen
            # sonst auseinander, und niemand wuesste, welche gilt.
            _manifest.append({"lead_id": lead_id, "url": seite,
                              "status": r["status"], "note": r["note"]})
            print(f"  [{i}/{len(rows)}] {lead_id}: {r['note']}"
                  + (f" · {', '.join(prio)}" if prio else ""), flush=True)
            pg.wait_for_timeout(_HOEFLICH_MS)
        ctx.close()
        b.close()

    mit = sum(1 for s in saetze if s["n_dateien"])
    mit_lv = sum(1 for s in saetze if "leistungsbeschreibung" in s["prioritaetstypen"])
    mit_eig = sum(1 for s in saetze if "eignung" in s["prioritaetstypen"])
    print(f"\n{len(saetze)} Vergaben · {mit} mit Dateiliste · "
          f"{mit_lv} mit Leistungsverzeichnis · {mit_eig} mit Eignungsunterlage")
    if dry_run:
        for s in saetze[:3]:
            print("  ", json.dumps(s, ensure_ascii=False)[:200])
        return {"geprüft": len(saetze), "mit_liste": mit}

    # Das Manifest wird VOR dem frühen Ausstieg unten geschrieben. Ein Lauf, in dem jeder
    # Versuch scheiterte, hat `saetze == []` — und genau seine Fehlschläge sind die, die
    # man beim nächsten Mal überspringen will. Stünde das Schreiben dahinter, wäre der
    # schlechteste Lauf der einzige ohne Gedächtnis.
    if _manifest:
        _mroot.mkdir(parents=True, exist_ok=True)
        _queue.schreibe(_mroot, "subreport", _manifest)

    if not saetze and not altbestand:
        print("nichts zu schreiben.")
        return {"geprüft": 0, "mit_liste": 0, "mit_lv": 0}

    import pyarrow as pa
    import pyarrow.parquet as pq
    out.parent.mkdir(parents=True, exist_ok=True)
    # Neue Saetze gewinnen — bei `--alles-neu` ersetzt der frische Lauf den alten Stand.
    frisch = {s["lead_id"] for s in saetze}
    alle = [s for s in altbestand if s["lead_id"] not in frisch] + saetze
    pq.write_table(pa.Table.from_pylist(alle), out, compression="zstd")
    print(f"→ {out} ({len(alle)} Vergaben gesamt)")
    return {"geprüft": len(saetze), "mit_liste": mit, "mit_lv": mit_lv,
            "gesamt": len(alle)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--alles-neu", action="store_true",
                   help="bekannte Vergaben nicht überspringen (Nachträge einsammeln)")
    a = p.parse_args(argv)
    lauf(a.limit, a.dry_run, alles_neu=a.alles_neu)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
