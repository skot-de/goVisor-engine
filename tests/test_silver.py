"""Silber-Bau: Deduplizierung der Alt-Paket-Editionen.

Alt-Pakete (2004–2007) liefern jede Notice doppelt — eine ISO- und eine UTF8-Edition,
beide mit Präfix ``DE_``. Nach dem Parsen sind das identische Zeilen. ``build_month``
muss nach ``notice_id`` deduplizieren und die sauber dekodierende UTF-8-Edition behalten.
"""

import io
import tarfile

import duckdb

from govisor.config import Config
from govisor.silver import build_month

# Minimal parsebare Notice mit Titel (Umlaut im Titel testet die Encoding-Präferenz).
_XML = (
    '<?xml version="1.0" encoding="{enc}"?>'
    "<TED_EXPORT><FORM_SECTION><F03_2014>"
    "<OBJECT_CONTRACT><TITLE><P>Straßenbau München</P></TITLE></OBJECT_CONTRACT>"
    "</F03_2014></FORM_SECTION></TED_EXPORT>"
)


def _bronze(path, members):
    """members: Liste (arcname, raw_bytes) — gleiche arcname erlaubt (Dubletten)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as tf:
        for name, payload in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            tf.addfile(info, io.BytesIO(payload))


def test_build_month_dedupes_iso_and_utf8_editions(tmp_path):
    cfg = Config(countries=("DE",), data_dir=tmp_path)
    src = cfg.raw_path("DE", "2005-01")

    utf8 = _XML.format(enc="utf-8").encode("utf-8")
    iso = _XML.format(enc="iso-8859-1").encode("iso-8859-1")  # scheitert an strict UTF-8
    # Dieselbe Notice viermal (ISO + UTF8, wie im echten Alt-Paket), gleiche arcname.
    _bronze(src, [
        ("770-2005.xml", iso),
        ("770-2005.xml", utf8),
        ("770-2005.xml", iso),
        ("771-2005.xml", utf8),
    ])

    n = build_month(cfg, "DE", "2005-01", force=True)
    assert n == 2                                        # 2 eindeutige Notices, nicht 4

    con = duckdb.connect()
    notices = cfg.silver_table_path("notices", "DE", "2005-01")
    rows = con.execute(f"SELECT notice_id, title FROM '{notices.as_posix()}' ORDER BY notice_id").fetchall()
    assert [r[0] for r in rows] == ["770-2005", "771-2005"]
    # Die behaltene Edition ist die saubere UTF-8-Variante (kein Mojibake im Umlaut).
    assert "München" in rows[0][1]
