"""Nachbearbeitungs-Queue für Notices, die der Parser nicht sicher zuordnen kann.

Wenn der billige Vorfilter ein Land sieht, der Parser aber keinen Käufer
auflösen kann, gibt es zwei Möglichkeiten, damit umzugehen:

* wegwerfen — dann ist die Zahl sauber und die Wahrheit verloren
* raten — dann ist die Zahl sauber und falsch

Beides sind Entscheidungen, die wir gar nicht treffen müssen. Der Fall kommt
in die Queue, mitsamt dem Original-XML, und wird geprüft.

Die Welthungerhilfe zeigt, warum das zählt: Sie beschafft aus Kiew, Gaziantep
und Bangui. Der Käufer sitzt in einem Land, das diese Registry nicht kennt,
also löst er nicht auf. Raten hätte drei Ausschreibungen aus Zentralafrika als
deutsche Leads ausgeliefert. Wegwerfen hätte verschwiegen, dass hier eine
deutsche Organisation beschafft — vielleicht ja doch ein Treffer.

Wer Wahrscheinlichkeiten verkauft, muss die Zweifelsfälle zeigen können.
"""

from __future__ import annotations

import gzip
import io
import json
import tarfile
from dataclasses import asdict, dataclass, field
from pathlib import Path


class Reason:
    """Gründe, die nicht aus den Parser-Marken kommen."""

    PARSE_FAILED = "XML nicht parsebar"


@dataclass
class ReviewItem:
    notice_id: str
    reason: str
    # Behalten oder verworfen? Beides kann prüfenswert sein: eine behaltene
    # Notice ohne Freitext ist kein Fehler, aber der Freitext ist der Rohstoff
    # der Extraktion — jemand sollte wissen, dass er fehlt.
    kept: bool = True
    publication_number: str | None = None
    ted_url: str | None = None
    schema_gen: str | None = None
    form_type: str | None = None
    title: str | None = None
    # Was der Vorfilter sah — meist der Grund, warum wir überhaupt hinsehen.
    probe_countries: list[str] = field(default_factory=list)
    # Welche Ländercodes im Dokument vorkamen, auch die unbekannten.
    raw_country_codes: list[str] = field(default_factory=list)
    unknown_country_codes: list[str] = field(default_factory=list)
    note: str | None = None


class ReviewQueue:
    """Sammelt Zweifelsfälle eines Monats und legt sie mit XML ab."""

    def __init__(self) -> None:
        self.items: list[ReviewItem] = []
        self._raw: list[tuple[str, bytes]] = []

    def add(self, item: ReviewItem, raw: bytes | None) -> None:
        """XML nur für verworfene Fälle — behaltene stehen ohnehin in Bronze."""
        self.items.append(item)
        if raw is not None:
            self._raw.append((item.notice_id, raw))

    def __len__(self) -> int:
        return len(self.items)

    def write(self, jsonl_path: Path, tar_path: Path) -> None:
        """Metadaten und Beweismaterial ablegen.

        Das XML kommt mit: Wer den Fall später prüft, soll ihn ansehen können,
        ohne 200 MB neu zu laden.
        """
        if not self.items:
            return
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = jsonl_path.with_suffix(".part")
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            for item in self.items:
                fh.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")
        tmp.rename(jsonl_path)

        if not self._raw:
            return
        tar_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = tar_path.with_suffix(".part")
        with tarfile.open(tmp, "w:gz") as tf:
            for notice_id, raw in self._raw:
                info = tarfile.TarInfo(name=f"{notice_id}.xml")
                info.size = len(raw)
                tf.addfile(info, io.BytesIO(raw))
        tmp.rename(tar_path)


def load(jsonl_path: Path) -> list[ReviewItem]:
    if not jsonl_path.exists():
        return []
    with gzip.open(jsonl_path, "rt", encoding="utf-8") as fh:
        return [ReviewItem(**json.loads(line)) for line in fh]
