"""Paket-Layouts. Beide Formen kommen im Archiv echt vor."""

import io
import tarfile
import zipfile

import pytest

from govisor import bulk

NOTICE = b'<?xml version="1.0"?><TED_EXPORT><FORM_SECTION/></TED_EXPORT>'


def _tar_gz(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, payload in entries.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))
    return buf.getvalue()


def _zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, payload in entries.items():
            zf.writestr(name, payload)
    return buf.getvalue()


def test_flat_package(tmp_path):
    """Neuere Monate: die XML liegen direkt im Monatspaket."""
    path = tmp_path / "flat.tar.gz"
    path.write_bytes(_tar_gz({"330482_2023.xml": NOTICE, "327209_2023.xml": NOTICE}))
    got = dict(bulk.iter_notices(path))
    assert set(got) == {"330482_2023", "327209_2023"}


def test_nested_package(tmp_path):
    """Ältere Monate: das Monatspaket enthält ein Tagespaket je Publikationstag.

    Ein Leser, der nur oberste Ebene nach .xml durchsucht, findet hier nichts —
    und meldet einen leeren Monat statt eines Fehlers. So gingen 42 von 126
    Monaten verloren, ohne dass das Log etwas anderes sagte als '0 behalten'.
    """
    daily = _tar_gz({"123456_2019.xml": NOTICE, "123457_2019.xml": NOTICE})
    path = tmp_path / "nested.tar.gz"
    path.write_bytes(_tar_gz({"10/20191030_2019210.tar.gz": daily}))
    got = dict(bulk.iter_notices(path))
    assert set(got) == {"123456_2019", "123457_2019"}
    assert got["123456_2019"] == NOTICE


def test_mixed_package(tmp_path):
    path = tmp_path / "mixed.tar.gz"
    path.write_bytes(_tar_gz({
        "999_2019.xml": NOTICE,
        "10/day.tar.gz": _tar_gz({"888_2019.xml": NOTICE}),
    }))
    assert set(dict(bulk.iter_notices(path))) == {"999_2019", "888_2019"}


def test_empty_placeholder_zip_does_not_sink_month(tmp_path):
    """TED legt in Alt-Paketen (2005–2012) 0-Byte-Platzhalter-Zips ab — z. B. eine leere
    ``CS_…_ISO_ORG.ZIP`` neben der echten ``DE_…_UTF8_ORG.ZIP``. Ein einziges leeres Zip
    warf früher ``BadZipFile`` und riss die Verifikation des GANZEN Monats ab (13k Notices
    verloren). Das leere Zip enthält null Notices → überspringen, restlichen Monat behalten."""
    daily = _tar_gz({
        "CS_20050201_022_ISO_ORG.ZIP": b"",                                # leerer Platzhalter
        "DE_20050201_022_UTF8_ORG.ZIP": _zip({"777_2005.xml": NOTICE}),     # echte Notice
    })
    path = tmp_path / "month.tar.gz"
    path.write_bytes(_tar_gz({"02/20050201_2005022.tar.gz": daily}))
    got = dict(bulk.iter_notices(path))
    assert set(got) == {"777_2005"}
    assert bulk._verify(path) == 1                                          # verify stürzt nicht mehr ab


def test_language_suffixed_xml_opoce_format(tmp_path):
    """opoce-input-Format (~2008): eine XML-Notice je Sprache, benannt mit Sprach-Endung
    (…_2008.de/.en) statt .xml, ohne Zip. Ein Reader, der nur .xml/.zip kennt, verliert den
    GANZEN Monat still (so ging 2008-05 mit 0 Notices durch). Bei country=DE nur die .de-Edition."""
    daily = _tar_gz({
        "770/opoce-input/770_2008.de": NOTICE,
        "770/opoce-input/770_2008.en": NOTICE,
        "770/opoce-input/770_2008.fr": NOTICE,
        "771/opoce-input/771_2008.de": NOTICE,
    })
    path = tmp_path / "month.tar.gz"
    path.write_bytes(_tar_gz({"05/20080502_2008085.tar.gz": daily}))
    # country=DE: genau eine Edition je Notice (nicht 3×)
    assert set(dict(bulk.iter_notices(path, country="DE"))) == {"770_2008", "771_2008"}
    # ohne country: alle Sprachen lesbar (kein Absturz)
    assert bulk._verify(path) == 4


def test_text_era_zips_are_language_not_country_named(tmp_path):
    """Sprach-Ära (~2004–2012): die Zips heißen nach AMTSSPRACHE (DE_/FR_/…), nicht nach Land.
    `DE_` = alle deutschsprachigen Notices → enthält Österreichs Notices. Der Länder-Perf-Filter
    muss AT deshalb aufs `DE_`-Zip mappen (sonst 0, weil kein `AT_`-Zip existiert — der Bug, der
    die ganze AT-Historie 2004–2010 verschluckte). Das Inhalts-Land filtert danach ingest_month."""
    daily = _tar_gz({
        "DE_20040102_001_ISO_ORG.ZIP": _zip({"770_2004.xml": NOTICE}),   # deutschsprachig (DE+AT)
        "FR_20040102_001_ISO_ORG.ZIP": _zip({"771_2004.xml": NOTICE}),   # französischsprachig
    })
    path = tmp_path / "lang.tar.gz"
    path.write_bytes(_tar_gz({"01/20040102_2004001.tar.gz": daily}))
    # AT liest das deutsche Zip (NICHT leer!) und NICHT das französische.
    assert set(dict(bulk.iter_notices(path, country="AT"))) == {"770_2004"}
    # DE unverändert: liest ebenfalls das deutsche Zip.
    assert set(dict(bulk.iter_notices(path, country="DE"))) == {"770_2004"}
    # FR liest das französische Zip.
    assert set(dict(bulk.iter_notices(path, country="FR"))) == {"771_2004"}


def test_truncated_archive_is_rejected(tmp_path):
    """Ein abgeschnittener Download darf nicht als vollständiger Monat durchgehen."""
    full = _tar_gz({f"{i}_2023.xml": NOTICE for i in range(50)})
    path = tmp_path / "cut.tar.gz"
    path.write_bytes(full[: len(full) // 2])
    with pytest.raises(bulk.IncompleteDownload):
        bulk._verify(path)


def test_months_range():
    got = list(bulk.months((2023, 11), (2024, 2)))
    assert [p.key for p in got] == ["2023-11", "2023-12", "2024-01", "2024-02"]
