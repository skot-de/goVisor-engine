"""Quelle CH — Vergabeunterlagen von simap.ch über die **offizielle API**.

Die Schweiz hängt vollständig an einer Plattform: **alle 889 offenen CH-Leads mit
Unterlagen-Link zeigen auf `simap.ch`**. Ein Connector deckt damit 100 % des Landes ab.

**Warum API und nicht Browser.** Die erste Fassung dieser Datei steuerte die Weboberfläche.
Das war der falsche Weg: simap.ch betreibt eine **dokumentierte, kostenlose, ausdrücklich
für Dritte gedachte API** (`https://www.simap.ch/api-doc/`, OpenAPI 3.0, 224 Pfade). Die
eigenen AGB sagen dazu:

* API-AGB Ziff. 6: „Authentifizierung als Anbieter: **Bezug von Ausschreibungsunterlagen**"
* API-AGB Ziff. 4: „API-Benutzer können Publikationsdaten **für kommerzielle Zwecke**
  beziehen und an Dritte weitergeben."
* API-AGB Ziff. 7: gegenwärtig nicht gebührenpflichtig.

Eine Oberfläche nachzuklicken, für die es eine gewollte Schnittstelle gibt, wäre nicht nur
zerbrechlicher, sondern auch die schlechtere Bürgerschaft.

**Der Weg, aus der Spezifikation** (Basis ``/api``, Sicherheit ``SimapOIDC``)::

    GET /api/vendors/v1/my/projects/{projectId}/documents            → Liste (ProjectDocuments)
    GET /api/vendors/v1/my/projects/{projectId}/documents/zip-token  → {"token": "…"}
    GET /api/project-documents/v1/docs/zip-download?token=…          → ZIP (chunked)

**Die Projekt-ID steht in unserer eigenen `documents_url`** — kein Umweg über die Seite:
``https://www.simap.ch/de/redirect?context=<base64>`` dekodiert zu
``{"page":"project","projectId":"d8235438-…","lotId":null,…}``.

**Warum die Aufrufe AUS DER SEITE laufen.** `curl` und eigene HTTP-Clients bekommen von
simap.ch 302 auf die SPA, der Browser 200 — dasselbe Fingerprint-Muster wie an drei
deutschen Portalen an diesem Tag. Der Connector meldet sich deshalb per Playwright an
(Keycloak, ``#username``/``#password``/``#kc-login``) und ruft die API mit ``fetch(…,
{credentials:'include'})`` im Seitenkontext auf. Das ZIP kommt über einen synthetischen
Anker, damit Chromes eigener Netzwerk-Stack lädt.

⚠ **DER DOWNLOAD IST EINE INTERESSENSBEKUNDUNG.** AGB Ziff. 4.6: „Indem Anbietende ihr
Interesse an einer Ausschreibung bekunden, erteilen sie ihre Zustimmung, dass ihre Angaben
den Auftraggebenden mitgeteilt werden dürfen." Jeder Abruf macht goVisor bei der jeweiligen
Vergabestelle als interessierten Anbieter sichtbar — bei 889 Vergaben ist das eine
Geschäftsentscheidung, keine technische. Deshalb ist dieser Connector **nicht** im
Tageslauf verdrahtet, bis das bewusst entschieden ist.

⚠ **Pflichten bei Weitergabe** (API-AGB Ziff. 5), die das FRONTEND erfüllen muss, nicht
dieser Connector:

* Daten inhaltlich unverändert, optisch von Kommentaren unterscheidbar
* Pflichthinweis: „Dies ist keine amtliche Veröffentlichung. Massgebend sind die auf der
  Plattform www.simap.ch veröffentlichten Daten."
* **Sperrfrist:** Weitergabe an Dritte erst ab 08:00 Uhr des Erscheinungstages
* Berichtigungen nachpublizieren

Dazu AGB Ziff. 9.1 Abs. 2: Einschränkungen, die IN den Unterlagen stehen, sind einzuhalten.
Der Verein empfiehlt den Vergabestellen dafür den Satz „Diese Unterlagen dürfen ausser zur
Einreichung eines Angebots nur eingeschränkt weiterverwendet werden" — nach genau dem sucht
``EINSCHRAENKUNG`` unten, und betroffene Vergaben werden im Manifest markiert.

**Zugangsdaten** kommen aus ``.secrets/simap.txt`` (zwei Zeilen), gitignored, nur gelesen,
nie ausgegeben. Fehlt die Datei, bricht der Lauf vor Browser und Abfrage ab.

Aufruf::

    python3 -m govisor.simap_docs --limit 3 --dry-run   # anmelden, Liste zeigen, nichts laden
    python3 -m govisor.simap_docs --limit 20
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import secrets
from pathlib import Path

from . import docfetch_queue as _queue
from urllib.parse import parse_qs, urlencode, urlparse

ROOT = Path(__file__).resolve().parent.parent
ZUGANG = ROOT / ".secrets" / "simap.txt"

_LOGIN = "https://www.simap.ch/de/provider/login"
_HOST = "www.simap.ch"
_API = "/api"
_CLIENT = "simap-fe"
_REDIRECT = "https://www.simap.ch/"

_WARTE_MS = 8000
_HOEFLICH_MS = 2000
_DOWNLOAD_MS = 300000
_MAX_ZIP = 500 * 1024**2
_LAUF_BUDGET_MB = 1500

_CONTEXT = re.compile(r"context=([A-Za-z0-9+/=_-]+)")

# Der vom Verein empfohlene Hinweis auf Weiterverwendungs-Einschränkungen (AGB 9.1 Abs. 2).
# Wer ihn findet, darf die Unterlagen nur eingeschraenkt weiterverwenden — das muss sichtbar
# bleiben, statt in einem ZIP unterzugehen.
EINSCHRAENKUNG = re.compile(
    r"nur eingeschr[äa]nkt weiterverwendet|ausser zur Einreichung eines Angebots",
    re.IGNORECASE)

_KLICK = """u => { const a = document.createElement('a'); a.href = u; a.download = '';
                   document.body.appendChild(a); a.click(); a.remove(); }"""


def ist_simap(url: str | None) -> bool:
    return bool(url) and f"//{_HOST}/" in url


def projekt_id(url: str | None) -> str | None:
    """`documents_url` → projectId, ohne Netzaufruf.

    Der `context`-Parameter ist base64-kodiertes JSON und traegt die ID bereits. Das spart
    je Vergabe einen Seitenaufruf — bei 889 Leads keine Kleinigkeit, und es macht den
    Connector unabhaengig davon, ob die Weiterleitung sich aendert.
    """
    if not ist_simap(url):
        return None
    m = _CONTEXT.search(url)
    if not m:
        # Direktform `/de/project-detail/<uuid>` kommt auch vor.
        d = re.search(r"/project-detail/([0-9a-f-]{36})", url)
        return d.group(1) if d else None
    s = m.group(1).replace("-", "+").replace("_", "/")
    s += "=" * (-len(s) % 4)
    try:
        return json.loads(base64.b64decode(s)).get("projectId")
    except Exception:                                    # noqa: BLE001
        return None


def zugang() -> tuple[str, str]:
    """`.secrets/simap.txt` → (Benutzer, Passwort). Kein anonymer Rueckfallpfad."""
    if not ZUGANG.exists():
        raise SystemExit(
            f"Zugangsdaten fehlen: {ZUGANG}\n"
            "  Zwei Zeilen anlegen — Benutzername, dann Passwort:\n"
            "    printf 'BENUTZER\\nPASSWORT\\n' > .secrets/simap.txt && chmod 600 .secrets/simap.txt\n"
            "  Die Datei ist gitignored und wird nur gelesen.")
    zeilen = [z.strip() for z in ZUGANG.read_text(encoding="utf-8").splitlines() if z.strip()]
    if len(zeilen) < 2:
        raise SystemExit(f"{ZUGANG}: erwartet zwei Zeilen (Benutzer, Passwort).")
    # Vorlage noch nicht ausgefuellt. Ohne diese Pruefung liefe ein Anmeldeversuch mit
    # „PASSWORT_HIER_EINTRAGEN" gegen Keycloak und die Meldung hiesse „Anmeldung
    # fehlgeschlagen" — das schickt einen auf die Suche nach einem Konto-Problem, das es
    # nicht gibt.
    if any("HIER_EINTRAGEN" in z for z in zeilen[:2]):
        raise SystemExit(
            f"{ZUGANG} enthält noch die Vorlage.\n"
            "  Zeile 1 = Benutzername, Zeile 2 = Passwort eintragen und speichern.")
    return zeilen[0], zeilen[1]


def anmelden(pg) -> str | None:
    """Authorization Code Flow mit PKCE → Zugriffstoken, oder None.

    ⚠ **Warum nicht einfach das Anmeldeformular und dann Cookies.** Genau das war die erste
    Fassung, und sie war doppelt falsch:

    1. Die Erfolgspruefung („wir sind weg vom Keycloak-Pfad") war ein FEHLALARM. Sie meldete
       „angemeldet", waehrend die Oberflaeche weiter einen Login-Knopf zeigte. Gemessen:
       kein einziger Aufruf des Token-Endpunkts, kein `Authorization`-Kopf.
    2. Die dokumentierte `/api/`-Schnittstelle nimmt **kein Sitzungs-Cookie**. Mit gueltiger
       Sitzung und `credentials:'include'` antwortet sie 401. Die Oberflaeche selbst spricht
       naemlich `/rest/`, nicht `/api/` — das sind zwei verschiedene Wege.

    `simap-fe` erlaubt keinen Direct Grant („Client not allowed for direct access grants"),
    also der dokumentierte Weg: PKCE-Paar erzeugen, Anmeldemaske ausfuellen, den Code aus der
    Weiterleitung abfangen, gegen ein Token tauschen.

    ⚠ **Den Code MUSS man im Moment der Weiterleitung abfangen.** Die Oberflaeche verarbeitet
    ihn und leitet sofort auf `/de` bzw. `/en` weiter — danach ist die Abfrage aus `pg.url`
    leer. Deshalb zwei Horcher (`framenavigated` UND `response`): mit nur einem ging der Code
    in einem von zwei Laeufen verloren.
    """
    benutzer, passwort = zugang()
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    auth = f"https://{_HOST}/auth/realms/simap/protocol/openid-connect/auth?" + urlencode({
        "client_id": _CLIENT, "response_type": "code", "scope": "openid",
        "redirect_uri": _REDIRECT, "code_challenge": challenge,
        "code_challenge_method": "S256", "state": "govisor"})

    gefangen: list[str] = []
    def fang_nav(f):
        if f == pg.main_frame and "code=" in f.url:
            gefangen.append(f.url)
    def fang_resp(r):
        if "code=" in r.url and f"{_HOST}/?" in r.url:
            gefangen.append(r.url)
    pg.on("framenavigated", fang_nav)
    pg.on("response", fang_resp)
    try:
        pg.goto(auth, wait_until="domcontentloaded")
        pg.wait_for_timeout(_WARTE_MS)
        if pg.query_selector("#username") is None:
            print("  ⚠ Keine Anmeldemaske — hat simap.ch den Ablauf geändert?")
            return None
        pg.fill("#username", benutzer)
        pg.fill("#password", passwort)
        pg.click("#kc-login")
        pg.wait_for_timeout(_WARTE_MS + 2000)
    finally:
        pg.remove_listener("framenavigated", fang_nav)
        pg.remove_listener("response", fang_resp)

    code = None
    for u in gefangen:
        c = parse_qs(urlparse(u).query).get("code")
        if c:
            code = c[0]
            break
    if not code:
        # Kein Code heisst: Keycloak hat die Anmeldung NICHT abgeschlossen — meist falsche
        # Zugangsdaten. Das Passwort wird dabei nirgends ausgegeben.
        print("  ⚠ Kein Autorisierungscode erhalten — Zugangsdaten prüfen.")
        return None

    antwort = pg.evaluate(
        """async ([code, verifier, redirect, client]) => {
             const body = new URLSearchParams({grant_type: 'authorization_code',
               client_id: client, code, code_verifier: verifier, redirect_uri: redirect});
             const r = await fetch('/auth/realms/simap/protocol/openid-connect/token',
               {method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body});
             const t = await r.text(); let j = null; try { j = JSON.parse(t); } catch (e) {}
             return {status: r.status, token: j ? j.access_token : null,
                     fehler: j ? (j.error_description || j.error || '') : t.slice(0, 120)};
           }""", [code, verifier, _REDIRECT, _CLIENT])
    if not antwort.get("token"):
        print(f"  ⚠ Token-Tausch fehlgeschlagen (http {antwort['status']}): "
              f"{antwort.get('fehler', '')[:90]}")
        return None
    return antwort["token"]


def api(pg, pfad: str, token: str) -> dict:
    """GET auf die API mit Bearer-Token, aus der Seite heraus.

    ⚠ Das Token ist Pflicht: mit blossem Sitzungs-Cookie antwortet `/api/` 401 — gemessen,
    auch bei einer Oberflaeche, die den Nutzer als angemeldet fuehrt. Der Aufruf laeuft
    trotzdem im Seitenkontext, weil eigene HTTP-Clients von simap.ch 302 auf die SPA
    bekommen.
    """
    return pg.evaluate(
        """async ([p, tk]) => {
             const r = await fetch(p, {headers: {'Authorization': 'Bearer ' + tk,
                                                 'Accept': 'application/json'}});
             const t = await r.text();
             let j = null; try { j = JSON.parse(t); } catch (e) {}
             return {status: r.status, json: j, text: t.slice(0, 200)};
           }""", [pfad, token])


def interesse_bekunden(pg, pid: str, token: str) -> dict:
    """PUT …/interest — macht uns beim Auftraggeber als Interessent SICHTBAR.

    ⚠ **Das ist keine technische Formalie, sondern eine Aussenwirkung.** Die Spezifikation
    ist eindeutig: der Auftraggeber ruft `/procoffices/v2/my/projects/{id}/involved-vendors`
    ab und sieht uns mit Firmenname, Adresse, handelndem Nutzer und Zeitstempel
    (`status='interest_shown'`), und ueber `…/history/document-downloads` zusaetzlich, welche
    Unterlagen wir gezogen haben. Auf 889 Schweizer Vergaben angewandt hiesse das: goVisor
    taucht bei praktisch jeder Schweizer Vergabestelle als Bieter-Interessent auf, ohne je
    bieten zu wollen.

    Deshalb ist der Schritt **standardmaessig aus** und kein Nebeneffekt des Holens. Er
    laeuft nur mit ausdruecklichem `--interesse-bekunden`.
    """
    return pg.evaluate(
        """async ([p, tk]) => {
             const r = await fetch(p, {method: 'PUT',
               headers: {'Authorization': 'Bearer ' + tk,
                         'Content-Type': 'application/json'},
               body: JSON.stringify({interest: 'interest_shown'})});
             return {status: r.status, text: (await r.text()).slice(0, 200)};
           }""", [f"{_API}/publications/v1/project/{pid}/interest", token])


def hole_vergabe(pid: str, pg, token: str, ziel: Path, dry_run: bool = False,
                 interesse: bool = False) -> dict:
    """Ein Projekt → Unterlagen-ZIP über die API."""
    liste = api(pg, f"{_API}/vendors/v1/my/projects/{pid}/documents", token)
    if liste["status"] == 401:
        return {"status": "nicht_angemeldet", "bytes": 0, "n_files": 0, "note": "401"}
    if liste["status"] == 403:
        # 403 heisst hier NICHT „gesperrt", sondern „nicht in *meinen* Projekten". Die
        # Unterlagen haengen an der Interessensbekundung (s. interesse_bekunden). Ohne die
        # ausdrueckliche Freigabe bleibt es beim ehrlichen Befund.
        if not interesse:
            return {"status": "interesse_noetig", "bytes": 0, "n_files": 0,
                    "note": "403 — Interessensbekundung erforderlich"}
        antwort = interesse_bekunden(pg, pid, token)
        if antwort["status"] not in (200, 204):
            return {"status": "interesse_abgelehnt", "bytes": 0, "n_files": 0,
                    "note": f"http {antwort['status']} {antwort['text'][:50]}"}
        liste = api(pg, f"{_API}/vendors/v1/my/projects/{pid}/documents", token)
        if liste["status"] != 200:
            return {"status": "kein_zugriff", "bytes": 0, "n_files": 0,
                    "note": f"nach Bekundung http {liste['status']}"}
    if liste["status"] != 200 or not liste["json"]:
        return {"status": "fehler", "bytes": 0, "n_files": 0,
                "note": f"http {liste['status']} {liste['text'][:60]}"}

    dokumente = (liste["json"] or {}).get("documents") or []
    namen = [d.get("name") or d.get("fileName") or "" for d in dokumente]
    if not dokumente:
        return {"status": "leer", "bytes": 0, "n_files": 0, "note": "keine Dokumente"}
    if dry_run:
        return {"status": "probe", "bytes": 0, "n_files": len(dokumente),
                "note": ", ".join(n for n in namen[:3] if n)}

    tok = api(pg, f"{_API}/vendors/v1/my/projects/{pid}/documents/zip-token", token)
    if tok["status"] != 200 or not (tok["json"] or {}).get("token"):
        return {"status": "kein_token", "bytes": 0, "n_files": len(dokumente),
                "note": f"http {tok['status']}"}

    url = f"https://{_HOST}{_API}/project-documents/v1/docs/zip-download?token={tok['json']['token']}"
    try:
        with pg.expect_download(timeout=_DOWNLOAD_MS) as dl:
            pg.evaluate(_KLICK, url)
        d = dl.value
        ziel.parent.mkdir(parents=True, exist_ok=True)
        tmp = ziel.with_suffix(".part")
        d.save_as(str(tmp))
    except Exception as e:                               # noqa: BLE001
        return {"status": "fehler", "bytes": 0, "n_files": len(dokumente),
                "note": type(e).__name__}

    groesse = tmp.stat().st_size
    if groesse > _MAX_ZIP:
        tmp.unlink(missing_ok=True)
        return {"status": "zu_gross", "bytes": groesse, "n_files": 0,
                "note": f"{groesse/1024**2:.0f} MB"}
    import zipfile
    try:
        with zipfile.ZipFile(tmp) as z:
            eintraege = [i for i in z.infolist() if not i.is_dir()]
            n = len(eintraege)
            # AGB 9.1 Abs. 2: Einschraenkungen, die IN den Unterlagen stehen, gelten. Sie
            # muessen sichtbar bleiben, statt im ZIP unterzugehen.
            eingeschraenkt = any(
                EINSCHRAENKUNG.search(i.filename) for i in eintraege)
    except zipfile.BadZipFile:
        tmp.unlink(missing_ok=True)
        return {"status": "fehler", "bytes": groesse, "n_files": 0, "note": "kein ZIP"}
    tmp.replace(ziel)
    return {"status": "downloaded", "bytes": groesse, "n_files": n,
            "note": "weiterverwendung_eingeschraenkt" if eingeschraenkt else ""}


def lauf(limit: int | None = None, dry_run: bool = False, country: str = "CH",
         interesse: bool = False) -> dict:
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    from playwright.sync_api import sync_playwright

    # ZUERST die Zugangsdaten — vor Browser, vor Abfrage, vor jeder Ausgabe.
    zugang()

    L = ROOT / "data" / "gold" / country / "lead_export.parquet"
    out_root = ROOT / "data" / "docs" / country
    con = duckdb.connect()
    rows = con.execute(f"""
        SELECT lead_id, documents_url FROM read_parquet('{L.as_posix()}')
        WHERE phase='open' AND documents_url LIKE '%//{_HOST}/%'
          AND deadline_date > current_date
          AND coalesce(procedure_kind, '') <> 'open_house'
        ORDER BY deadline_date ASC""").fetchall()

    offen, ohne_id = [], 0
    for lead_id, url in rows:
        pid = projekt_id(url)
        if not pid:
            ohne_id += 1
            continue
        ziel = out_root / lead_id / f"Vergabeunterlagen_simap_{pid[:8]}.zip"
        if ziel.exists() and ziel.stat().st_size > 0:
            continue
        offen.append((lead_id, pid, ziel))
    # Frueher Gescheitertes ueberspringen. VOR dem Limit, sonst kappt das Limit auf
    # Kandidaten, die gleich wieder aussortiert werden.
    #
    # `frei` ist hier keine Formalie: `interesse_noetig` heisst „die Unterlagen gibt es,
    # wir haben nur kein Interesse bekundet". Ohne `--interesse-bekunden` bleibt das bei
    # JEDEM Lauf so — der Vorgang gehoert also uebersprungen. Mit dem Schalter faellt der
    # Blocker, und zwar sofort und ohne Wartefrist, weil sich nichts an der Gegenseite
    # geaendert hat, sondern an uns.
    _frei = {"interesse"} if interesse else set()
    offen, _weg = _queue.filtere(offen, _queue.frueher(out_root, "simap"), frei=_frei)
    if _weg:
        print(_queue.bericht(_weg))
    if limit:
        offen = offen[:limit]
    print(f"simap.ch (API): {len(offen)} Vergaben zu holen (von {len(rows)} offenen CH-Leads)"
          + (f", {ohne_id} ohne ableitbare Projekt-ID" if ohne_id else ""))

    saetze, geladen_mb = [], 0.0
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(accept_downloads=True)
        pg = ctx.new_page()
        pg.set_default_timeout(90000)
        token = anmelden(pg)
        if not token:
            b.close()
            return {"versucht": 0, "geladen": 0, "note": "Anmeldung fehlgeschlagen"}
        print("  angemeldet (Zugriffstoken erhalten).")
        for i, (lead_id, pid, ziel) in enumerate(offen, 1):
            if geladen_mb >= _LAUF_BUDGET_MB:
                print(f"\n  Lauf-Budget erreicht — {len(offen) - i + 1} bleiben für morgen.")
                break
            try:
                r = hole_vergabe(pid, pg, token, ziel, dry_run, interesse)
            except Exception as e:                       # noqa: BLE001
                # Der Klassenname allein ist wertlos — Playwright wirft fuer alles `Error`.
                # Die erste Zeile der Meldung sagt, was wirklich schiefging.
                erste = str(e).strip().splitlines()[0] if str(e).strip() else ""
                r = {"status": "fehler", "bytes": 0, "n_files": 0,
                     "note": f"{type(e).__name__}: {erste}"[:200]}
            saetze.append({"lead_id": lead_id, "project_id": pid, **r})
            info = (f"{r['n_files']} Dateien  {r['bytes']/1024**2:.1f} MB"
                    if r["status"] == "downloaded" else f"{r['status']} ({r['note'][:44]})")
            marke = "  ⚠ eingeschränkt" if r["note"] == "weiterverwendung_eingeschraenkt" else ""
            print(f"  [{i}/{len(offen)}] {lead_id[:16]:<16} {info}{marke}", flush=True)
            geladen_mb += r["bytes"] / 1e6
            pg.wait_for_timeout(_HOEFLICH_MS)
        ctx.close()
        b.close()

    ok = sum(1 for s in saetze if s["status"] == "downloaded")
    mb = sum(s["bytes"] for s in saetze) / 1e6
    eing = sum(1 for s in saetze if s["note"] == "weiterverwendung_eingeschraenkt")
    print(f"\nsimap.ch: {len(saetze)} versucht · {ok} geladen · {mb:.1f} MB")
    if eing:
        print(f"  ⚠ {eing} Vergaben mit Weiterverwendungs-Einschränkung in den Unterlagen")
    schlecht: dict[str, int] = {}
    for s in saetze:
        if s["status"] != "downloaded":
            schlecht[s["status"]] = schlecht.get(s["status"], 0) + 1
    if schlecht:
        print("  ⚠ " + ", ".join(f"{k}={v}" for k, v in sorted(schlecht.items())))
    if saetze and not dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        _queue.schreibe(out_root, "simap", saetze)
    return {"versucht": len(saetze), "geladen": ok, "mb": round(mb, 1)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="anmelden und die Dokumentliste zeigen, nichts herunterladen")
    p.add_argument("--interesse-bekunden", action="store_true",
                   help="AUSSENWIRKUNG: meldet goVisor bei jeder betroffenen Vergabestelle "
                        "namentlich als Interessent an. Ohne diese Angabe endet der Lauf bei "
                        "403 mit Status 'interesse_noetig'.")
    a = p.parse_args(argv)
    if a.interesse_bekunden and a.dry_run:
        # Sonst waere „Probelauf" ein irrefuehrendes Wort: die Bekundung ist echt und bleibt.
        p.error("--dry-run und --interesse-bekunden schliessen sich aus — eine "
                "Interessensbekundung ist keine Probe, sie ist beim Auftraggeber sichtbar.")
    lauf(a.limit, a.dry_run, interesse=a.interesse_bekunden)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
