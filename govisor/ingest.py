"""Stage 1: download a month, keep the notices we care about, index them.

Output is split in two:

``raw/<country>/<YYYY-MM>.tar.gz``
    The untouched original XML of every kept notice. Nothing downstream writes
    here, so a parser bug is always recoverable without re-downloading 55 GB.

``index/<country>/<YYYY-MM>.jsonl.gz``
    Parsed summaries. Regenerate freely from raw.
"""

from __future__ import annotations

import gzip
import io
import json
import tarfile
from dataclasses import asdict, dataclass
from pathlib import Path

from . import bulk, locales, review, schema
from .config import Config


@dataclass
class IngestStats:
    key: str
    scanned: int = 0
    kept: int = 0
    with_description: int = 0
    lots: int = 0
    text_chars: int = 0
    queued: int = 0          # Zweifelsfaelle zur Nachbearbeitung

    @property
    def description_rate(self) -> float:
        return self.kept and self.with_description / self.kept * 100


def ingest_month(
    cfg: Config,
    package: bulk.Package,
    force: bool = False,
    evict: bool = False,
) -> dict[str, IngestStats]:
    """Ingest one monthly package for every configured country.

    With ``evict``, the downloaded package is deleted once its notices are
    written. A full run is ~25 GB of packages but only ~5 GB of DE bronze, so
    keeping them all would need more free disk than the machine has. They stay
    re-downloadable from TED.
    """
    archive = bulk.download(package, cfg.cache_dir, force=force)
    wanted = set(cfg.countries)

    stats = {c: IngestStats(key=package.key) for c in wanted}
    buffers: dict[str, list[tuple[str, bytes]]] = {c: [] for c in wanted}
    records: dict[str, list[dict]] = {c: [] for c in wanted}
    queue = review.ReviewQueue()

    # Bei genau einem Zielland die fremden Länder-Zips der Alt-Pakete früh weglassen.
    hint = next(iter(wanted)) if len(wanted) == 1 else None
    # Sprach-/institutionsspezifisches Parsen (Freitext-Gewinner der Text-Ära)
    # folgt dem Länder-Profil. Bei genau einem Zielland aktivieren; sonst DE-Default.
    if hint is not None and hint in locales.LOCALES:
        locales.use(hint)
    for notice_id, raw in bulk.iter_notices(archive, country=hint):
        for country in wanted:
            stats[country].scanned += 1

        # Byte-level probe first: it is over-inclusive but ~100x cheaper than
        # parsing, and it rejects the ~80% of notices from other countries.
        candidates = schema.probe_countries(raw) & wanted
        if not candidates:
            continue

        try:
            notice = schema.parse(raw, notice_id)
        except Exception as exc:
            queue.add(review.ReviewItem(
                notice_id=notice_id,
                reason=review.Reason.PARSE_FAILED,
                kept=False,
                probe_countries=sorted(candidates),
                note=f"{type(exc).__name__}: {exc}"[:200],
            ), raw)
            continue

        # The probe matches place-of-performance too; only buyers decide.
        # A notice counts for every buyer's country, not just the lead's —
        # that is how TED counts it, and a joint EU procurement led from
        # Brussels that buys for Frankfurt is a German lead.
        notice_countries = set(notice.buyer_countries or ([notice.country] if notice.country else []))
        hits = notice_countries & wanted

        def _item(kept: bool) -> review.ReviewItem:
            return review.ReviewItem(
                notice_id=notice_id,
                reason="; ".join(notice.flags),
                kept=kept,
                publication_number=notice.publication_number,
                ted_url=notice.ted_url,
                schema_gen=notice.schema,
                form_type=notice.form_type,
                title=notice.title,
                probe_countries=sorted(candidates),
                raw_country_codes=schema.raw_country_codes(raw),
                unknown_country_codes=notice.unknown_country_codes,
            )

        if not notice_countries:
            # The probe saw one of our countries but no buyer resolved. Do not
            # guess and do not drop it — a human decides. The XML rides along:
            # a dropped notice is in no bronze archive, so this is the only
            # copy a reviewer would have.
            queue.add(_item(kept=False), raw)
            continue

        if not hits:
            continue

        # Filed under the lead buyer when that is one of ours, else under the
        # first match — so a notice never lands in two countries' archives.
        country = notice.country if notice.country in hits else sorted(hits)[0]
        buffers[country].append((notice_id, raw))
        records[country].append(asdict(notice))
        stats[country].kept += 1
        stats[country].lots += len(notice.lots)
        stats[country].text_chars += notice.text_length
        if notice.has_description:
            stats[country].with_description += 1

        # Kept, but something did not fit the pattern. No XML needed — bronze
        # already holds it.
        if notice.flags:
            queue.add(_item(kept=True), None)

    for country in wanted:
        if buffers[country]:
            _write_raw(cfg.raw_path(country, package.key), buffers[country])
            _write_index(cfg.index_path(country, package.key), records[country])
        stats[country].queued = len(queue)

    queue.write(cfg.review_path(package.key), cfg.review_raw_path(package.key))

    if evict:
        archive.unlink(missing_ok=True)

    return stats


def is_done(cfg: Config, package: bulk.Package) -> bool:
    """True if every configured country already has bronze for this month.

    Lets an interrupted run resume without re-downloading what it already has.
    """
    return all(cfg.raw_path(c, package.key).exists() for c in cfg.countries)


def _write_raw(path: Path, notices: list[tuple[str, bytes]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    with tarfile.open(tmp, "w:gz") as tf:
        for notice_id, raw in notices:
            info = tarfile.TarInfo(name=f"{notice_id}.xml")
            info.size = len(raw)
            tf.addfile(info, io.BytesIO(raw))
    tmp.rename(path)


def _write_index(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    tmp.rename(path)
