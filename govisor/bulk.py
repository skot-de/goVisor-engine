"""Access to TED's monthly bulk XML packages.

These packages are the only source that carries both structured fields and the
freetext description across the full archive (verified: 2004-01 through the
current month). The CSV subset on data.europa.eu carries no description at all
and stops at 2023-12-31 — see docs/data-sources.md.
"""

from __future__ import annotations

import io
import re
import tarfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import requests

PACKAGE_URL = "https://ted.europa.eu/packages/monthly/{year:04d}-{month:02d}"
ARCHIVE_START = (2004, 1)

_HEADERS = {"User-Agent": "goVisor/0.1 (data engine; +https://ted.europa.eu)"}


@dataclass(frozen=True)
class Package:
    year: int
    month: int

    @property
    def key(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def url(self) -> str:
        return PACKAGE_URL.format(year=self.year, month=self.month)

    def path(self, cache_dir: Path) -> Path:
        return cache_dir / f"ted_{self.key}.tar.gz"


def months(start: tuple[int, int], end: tuple[int, int]) -> Iterator[Package]:
    year, month = start
    while (year, month) <= end:
        yield Package(year, month)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


class IncompleteDownload(RuntimeError):
    """The archive did not arrive intact."""


def _verify(path: Path) -> int:
    """Read the whole archive and count notices. Raises if it is truncated.

    TED drops connections under sustained load, and a cut-off gzip stream does
    not always raise while writing — it just ends. Without this check a partial
    month gets written as if complete, and nothing downstream can tell: a month
    with 1.555 instead of 13.000 notices looks like a quiet month, not a bug.
    """
    try:
        return sum(1 for _ in iter_notices(path))
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise IncompleteDownload(f"{path.name}: {exc}") from exc


def head(package: Package) -> tuple[int, str | None, str | None]:
    """HEAD-Abfrage für Change-Detection: (status_code, Content-Length, Last-Modified).

    Erlaubt, ein bereits vollständig geladenes (abgeschlossenes) Monatspaket **nicht**
    erneut zu ziehen, wenn es sich seit dem letzten Lauf nicht verändert hat.
    """
    resp = requests.head(package.url, headers=_HEADERS, timeout=60, allow_redirects=True)
    return resp.status_code, resp.headers.get("Content-Length"), resp.headers.get("Last-Modified")


def download(
    package: Package,
    cache_dir: Path,
    force: bool = False,
    attempts: int = 10,
    verify: bool = True,
) -> Path:
    """Fetch a package into the cache and return its path — resume-fähig.

    Alte Monatspakete sind ~2 GB und der Stream bricht regelmäßig ab. Statt bei
    jedem Abbruch von vorn zu laden (was nie fertig wird), setzt der Download per
    ``Range: bytes=N-`` an der abgebrochenen Stelle fort und hängt an die
    ``.part``-Datei an. Erst wenn die Gesamtgröße erreicht UND das Archiv lesbar
    ist, wird umbenannt — ein halb geladenes Archiv gilt nie als vollständig.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = package.path(cache_dir)
    if target.exists() and not force:
        return target

    tmp = target.with_suffix(".part")
    if force:
        tmp.unlink(missing_ok=True)
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            resume = tmp.stat().st_size if tmp.exists() else 0
            headers = dict(_HEADERS)
            if resume:
                headers["Range"] = f"bytes={resume}-"
            with requests.get(package.url, headers=headers, stream=True, timeout=600) as response:
                # Ignoriert der Server den Range-Header (200 statt 206) → von vorn.
                if resume and response.status_code == 200:
                    tmp.unlink(missing_ok=True)
                    resume = 0
                response.raise_for_status()
                if response.status_code == 206:
                    cr = response.headers.get("Content-Range", "")
                    total = int(cr.rsplit("/", 1)[-1]) if "/" in cr else 0
                else:
                    total = int(response.headers.get("Content-Length") or 0)
                with tmp.open("ab" if resume else "wb") as fh:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        fh.write(chunk)
            written = tmp.stat().st_size
            if total and written < total:
                raise IncompleteDownload(f"{package.key}: {written:,} von {total:,} Bytes")
            if verify:
                try:
                    _verify(tmp)
                except Exception as ve:      # korruptes Archiv → verwerfen, neu laden
                    tmp.unlink(missing_ok=True)
                    raise IncompleteDownload(f"{package.key}: Archiv defekt ({ve})")
            tmp.rename(target)
            return target
        except (requests.RequestException, IncompleteDownload) as exc:
            last = exc
            # Definitive Client-Fehler → NICHT wiederholen (Retry würde nur Zeit kosten):
            #   404 = Paket (noch) nicht veröffentlicht, 410 = entfernt, 403 = gesperrt.
            # Sonst 10× Backoff ≈ 7 Min Leerlauf pro Refresh (laufender Monat ist früh
            # erwartbar 404). Transiente Fehler (Timeout, 5xx, Abbruch) laufen weiter.
            resp = getattr(exc, "response", None)
            if resp is not None and resp.status_code in (403, 404, 410):
                raise IncompleteDownload(
                    f"{package.key}: nicht abrufbar (HTTP {resp.status_code})") from exc
            # .part NICHT löschen — der nächste Versuch resumt von dort.
            if attempt < attempts - 1:
                time.sleep(min(5 * 2**attempt, 60))  # TED drosselt; Backoff, gedeckelt
    raise IncompleteDownload(f"{package.key} nach {attempts} Versuchen: {last}")


# TED-Textformat (vor ~2013): eine Datei je Land/Tag enthält VIELE Notices,
# getrennt an einer Versionszeile "d.d/NNNNNN". In einzelne (ND, Record) zerlegen.
_RE_TEXT_RECORD = re.compile(rb"\n(?=\d\.\d/\d)")
_RE_TEXT_ND = re.compile(rb"^ND:\s*(\S+)", re.M)


def _split_text_notices(data: bytes) -> Iterator[tuple[str, bytes]]:
    for record in _RE_TEXT_RECORD.split(data):
        m = _RE_TEXT_ND.search(record)
        if m:
            yield m.group(1).decode("ascii", "replace").strip(), record


def _walk(name: str, data: bytes, country: str | None) -> Iterator[tuple[str, bytes]]:
    """Rekursiv durch beliebig verschachtelte Archive bis zur XML-Notice.

    Die Paketstruktur wechselte über die Jahre mehrfach:
      * aktuell:      ``.xml`` direkt im Monatspaket
      * 2016–2023:    Monat.tar.gz → Tag.tar.gz → ``.xml``
      * bis ~2015:    Monat.tar.gz → Tag.tar.gz → ``DE_…_UTF8_ORG.zip`` → ``.xml``
    Ein Reader, der nur eine Ebene kennt, verliert die alten Jahre still.
    ``country`` überspringt fremde Länder-Zips (``IT_…zip``) — 27× weniger Arbeit.
    """
    low = name.lower()
    if low.endswith(".xml"):
        yield Path(name).stem, data
    elif low.endswith((".tar.gz", ".tgz")):
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            for m in tf:
                if m.isfile():
                    fh = tf.extractfile(m)
                    if fh is not None:
                        yield from _walk(m.name, fh.read(), country)
    elif low.endswith(".zip"):
        base = Path(name).name
        if "_meta" in base.lower():
            return                                   # Metadaten-Zip, keine Notice
        if (country and len(base) > 2 and base[2] == "_"
                and base[:2].isalpha() and base[:2].upper() != country.upper()):
            return                                   # anderes Land → überspringen
        # TED legt in Alt-Paketen (2005–2012) 0-Byte-Platzhalter-Zips ab, z. B. eine
        # leere ``CS_…_ISO_ORG.ZIP`` neben der echten UTF8-Variante. Ein leeres/defektes
        # Zip enthält null Notices — überspringen ist verlustfrei. Ohne diese Toleranz
        # reißt eine einzige leere Datei die Verifikation des GANZEN Monats ab (BadZipFile).
        if not data or not zipfile.is_zipfile(io.BytesIO(data)):
            return
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for zi in zf.namelist():
                if zi.endswith("/"):
                    continue
                if zi.lower().endswith(".xml"):
                    yield from _walk(zi, zf.read(zi), country)
                else:
                    # Vor-XML-Textformat (z. B. DE_…_UTF8_ORG ohne Endung):
                    # eine Datei mit vielen Notices → splitten.
                    body = zf.read(zi)
                    if body.lstrip()[:1] != b"<":
                        yield from _split_text_notices(body)
    else:
        # opoce-input-Format (~2008): eine XML-Notice je Sprache, benannt mit
        # Sprach-Endung (…_2008.de/.en/.fr) statt .xml, ohne Zip. Bei gesetztem Land
        # nur die passende Sprach-Edition lesen — sonst landet jede Notice ~20× im
        # Ingest (einmal je Sprache). Ohne diese Zweig ging der Monat still verloren.
        ext = Path(name).suffix.lstrip(".").lower()
        if len(ext) == 2 and ext.isalpha() and data.lstrip()[:1] == b"<":
            if country and ext != country.lower():
                return
            yield Path(name).stem, data


def iter_notices(archive: Path, country: str | None = None) -> Iterator[tuple[str, bytes]]:
    """Yield ``(notice_id, raw_xml)`` für jede Notice — über alle Paket-Generationen.

    Streamt das Monatsarchiv von der Platte; verschachtelte Tages-/Länder-Archive
    werden einzeln in den Speicher gezogen (je ~100 MB / wenige MB). ``country``
    filtert die Länder-Zips der Alt-Pakete früh weg (siehe ``_walk``).
    """
    with tarfile.open(archive, "r:gz") as tf:
        for member in tf:
            if member.isfile():
                fh = tf.extractfile(member)
                if fh is not None:
                    yield from _walk(member.name, fh.read(), country)
