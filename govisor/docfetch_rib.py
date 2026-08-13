"""Zweiter Plattform-Connector: RIB / „meinauftrag" (www.meinauftrag.rib.de).

**Warum diese Plattform als nächste.** Die Vorprüfung (``scripts/probe_portals.py``) über die
14 größten ungedeckten Portale ergab: **keines** stellt eine Anmelde-Wand vor die Unterlagen.
Das Hindernis ist technisch — die Dateiliste steht nicht als Markup in der Seite. RIB ist mit
**714 offenen Leads** der größte dieser Fälle, und bei ihm liegt die Liste besonders günstig:

    var documentsAttachments        = [{"id":"…","rows":[{"data":[{"value":"…<a href=\\"…\\">"

Ein JavaScript-Literal mit den fertigen Download-Adressen, direkt im HTML. Kein XHR, kein
Nachladen, keine Sitzungslogik. (Beim ersten Zugriff suchte ich wörtlich nach
``"var documentsAttachments = ["`` und fand nichts — dazwischen stehen MEHRERE Leerzeichen.
Deshalb hier ein Ausdruck mit ``\\s*=\\s*``, kein Literal.)

**RIB ist ein Aggregator.** Die Download-Adressen zeigen auf die dahinterliegenden Portale der
Länder und Kommunen (z. B. ``my.vergabeplattform.berlin.de/remote/download.php?k=…``). Ein
Connector deckt damit viele Vergabestellen ab — aber die Zielhosts sind fremd und wechselnd,
weshalb hier bewusst großzügig auf Fehler einzelner Dateien reagiert wird: eine nicht ladbare
Datei darf den Vorgang nicht scheitern lassen.

**Warum am Ende ein ZIP steht.** RIB liefert Einzeldateien, cosinex ein Archiv. Alles dahinter
(``docpipe``, ``extract_positions``) liest ``<notice_id>/*.zip``. Statt diese Kette an zwei
Stellen umzubauen, packt der Connector die geladenen Dateien selbst in ein ZIP — der
Pipeline-Vertrag bleibt damit unverändert.

**Nicht umgesetzt:** die Vergabeunterlagen ändern sich während der Frist. Dieser Connector
lädt einmal und ist danach idempotent (vorhandenes ZIP → ``exists``). Eine Erkennung
geänderter Fassungen fehlt — sie fehlt beim cosinex-Connector genauso und gehört als eigener
Punkt behandelt, nicht hier nebenbei.
"""
from __future__ import annotations

import io

import re
import zipfile
from pathlib import Path

import requests

from .docfetch import FetchResult, _UA

_RIB_RE = re.compile(
    r"^https?://(?:www\.)?meinauftrag\.rib\.de/public/"
    r"DetailsByPlatformIdAndTenderId/platformId/(?P<pid>\d+)/tenderId/(?P<tid>\d+)", re.I)
_VAR = re.compile(r"var\s+documentsAttachments\s*=\s*\[")
_HREF = re.compile(r'href=\\?"([^"\\]{6,})')

# Erste Fassung stand auf 80 — und drei von fuenf Testvorgaengen landeten EXAKT auf 80.
# Eine Grenze, die die Haelfte der Faelle trifft, ist keine Sicherung, sondern stiller
# Datenverlust. Jetzt hoch genug fuer echte Bau-Vergaben, und ein Anschlagen wird gemeldet.
_MAX_DATEIEN = 400
_MAX_BYTES = 300 * 1024 * 1024       # Gesamtgrenze je Vorgang


def is_rib(url: str) -> bool:
    return bool(url and _RIB_RE.match(url))


def _klammer_block(text: str, start: int) -> str | None:
    """Ab ``[`` bis zur passenden ``]`` — zeichenketten- und escape-bewusst.

    Eine Regex mit ``\\[.*?\\]`` würde am ersten ``]`` INNERHALB einer Zeichenkette abbrechen;
    das Literal enthält HTML mit eckigen Klammern. Deshalb von Hand gezählt.
    """
    tiefe, instr, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            instr = not instr
            continue
        if instr:
            continue
        if c == "[":
            tiefe += 1
        elif c == "]":
            tiefe -= 1
            if tiefe == 0:
                return text[start:i + 1]
    return None


def dokumentlinks(html: str) -> list[str]:
    """Download-Adressen aus dem eingebetteten JS-Literal. Leere Liste, wenn es fehlt."""
    m = _VAR.search(html)
    if not m:
        return []
    blk = _klammer_block(html, html.index("[", m.start()))
    if not blk:
        return []
    # ERST entmaskieren, DANN suchen. Im Literal steht `https:\/\/host\/pfad`; ein Ausdruck,
    # der Backslashes ausschliesst, bricht nach `https:` ab — und genau das lieferte beim
    # ersten Lauf fuer JEDEN Vorgang „InvalidURL". Die Meldung sah nach einem Portal-Problem
    # aus und war eine kaputte Regex.
    klar = blk.replace("\\/", "/").replace('\\"', '"').replace("&amp;", "&")
    aus, gesehen = [], set()
    for u in _HREF.findall(klar):
        if u.startswith("http") and u not in gesehen:
            gesehen.add(u)
            aus.append(u)
    return aus


def _dateiname(url: str, antwort: requests.Response, nr: int) -> str:
    """Dateiname aus Content-Disposition, sonst aus der URL, sonst durchnummeriert."""
    cd = antwort.headers.get("content-disposition", "")
    # HTTP-Header sind latin-1; die Portale schreiben aber UTF-8 hinein. Ohne diese
    # Rueckrechnung wird aus „Eigenerklaerung" ein „EigenerklÃ¤rung".
    try:
        cd = cd.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd)
    name = m.group(1).strip() if m else Path(url.split("?")[0]).name
    name = re.sub(r'[^\w.\- ]', "_", name or "").strip() or f"datei_{nr}"
    if "." not in name:
        typ = antwort.headers.get("content-type", "").split(";")[0]
        name += {"application/pdf": ".pdf", "application/zip": ".zip"}.get(typ, ".bin")
    return f"{nr:02d}_{name}"[:120]


def fetch_one(documents_url: str, notice_id: str, out_root: Path,
              session: requests.Session | None = None, timeout: int = 60) -> FetchResult:
    """Ein RIB-Vorgang → ein ZIP mit allen öffentlichen Unterlagen. Idempotent."""
    m = _RIB_RE.match(documents_url or "")
    if not m:
        return FetchResult(notice_id, None, None, "error", 0, 0, None, "keine RIB-URL")
    tid = m.group("tid")
    portal = "meinauftrag.rib.de"
    dest_dir = out_root / notice_id
    dest = dest_dir / f"Vergabeunterlagen_rib_{tid}.zip"
    if dest.exists() and dest.stat().st_size > 0:
        return FetchResult(notice_id, tid, portal, "exists", dest.stat().st_size, 0, str(dest))

    s = session or requests.Session()
    s.headers.update({"User-Agent": _UA, "Accept-Language": "de-DE,de;q=0.9"})
    try:
        r = s.get(documents_url, timeout=timeout, allow_redirects=True)
    except requests.RequestException as e:
        return FetchResult(notice_id, tid, portal, "error", 0, 0, None,
                           f"{type(e).__name__}: {e}"[:150])
    if r.status_code != 200:
        return FetchResult(notice_id, tid, portal, "error", 0, 0, None, f"http {r.status_code}")

    alle_links = dokumentlinks(r.text)
    links = alle_links[:_MAX_DATEIEN]
    gekappt = len(alle_links) - len(links)
    if not links:
        # Kein Literal in der Seite: entweder keine öffentlichen Unterlagen oder ein
        # anderes Seitenlayout. Ehrlich als "gated" melden statt so zu tun, als sei nichts da.
        return FetchResult(notice_id, tid, portal, "gated", 0, 0, None,
                           "keine Dokumentliste in der Seite")

    puffer = io.BytesIO()
    gesamt = n_ok = 0
    fehler: list[str] = []
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for nr, u in enumerate(links, 1):
            if gesamt >= _MAX_BYTES:
                fehler.append("Größengrenze erreicht")
                break
            try:
                d = s.get(u, timeout=timeout, allow_redirects=True)
            except requests.RequestException as e:
                fehler.append(type(e).__name__)
                continue
            # Eine einzelne nicht ladbare Datei darf den Vorgang nicht scheitern lassen —
            # die Ziel-Hosts sind fremde Portale, dort fällt immer mal etwas aus.
            if d.status_code != 200 or not d.content:
                fehler.append(f"http {d.status_code}")
                continue
            if b"<!DOCTYPE" in d.content[:200] or b"<html" in d.content[:200].lower():
                fehler.append("HTML statt Datei")     # Anmeldeseite o. Ä.
                continue
            zf.writestr(_dateiname(u, d, nr), d.content)
            gesamt += len(d.content)
            n_ok += 1

    if not n_ok:
        return FetchResult(notice_id, tid, portal, "gated", 0, 0, None,
                           "; ".join(fehler[:3])[:120] or "keine Datei ladbar")
    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    tmp.write_bytes(puffer.getvalue())
    tmp.replace(dest)
    note = f"{len(links)} Links, {n_ok} geladen"
    if gekappt:
        note += f", {gekappt} ueber der Grenze NICHT geladen"
    if fehler:
        note += f", {len(fehler)} übersprungen ({fehler[0]})"
    return FetchResult(notice_id, tid, portal, "downloaded", dest.stat().st_size, n_ok,
                       str(dest), note)
