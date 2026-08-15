"""Ein Archiv → ein Parquet-Bruchstück. Als EIGENER Prozess, nicht als Pool-Arbeiter.

**Warum es diese Datei gibt.** Am 2026-08-14 wurde dreimal versucht, den Speicher eines
Extraktions-Arbeiters zu begrenzen, und dreimal ging es schief:

1. Sperre auf die ARCHIV-Größe — bestraft 507 brauchbare Dateien für den einen Brocken,
   der neben ihnen liegt.
2. Sperre auf die DATEI-Größe — half, reicht aber nicht: aus einer 10-MB-PDF wurden
   gemessen 6,5 GB, weil die Bibliothek den Objektbaum aufspannt. Die Größe sagt nichts
   darüber, was daraus wird.
3. ``RLIMIT_AS`` und ein Wachthread mit ``SIGALRM`` — beide gemessen wirkungslos: macOS
   setzt das Limit nicht durch, und die ``MemoryError`` wird tief in der PDF-Bibliothek
   von einem internen ``except Exception`` geschluckt.

**Die Erkenntnis daraus:** Speicher lässt sich INNERHALB eines Prozesses nicht verlässlich
begrenzen. Die einzige Instanz, die eine Grenze durchsetzen kann, ist das Betriebssystem —
und sein Werkzeug dafür heißt ``SIGKILL``. Also bekommt jedes Archiv einen eigenen Prozess,
den der Elternprozess beobachtet und notfalls hart beendet. Aus einem Rechnerabsturz wird
dann eine Zeile in der Statistik.

**Warum der Arbeiter selbst schreibt.** Er könnte seine Zeilen über die Standardausgabe
zurückgeben — dann hielte der Elternprozess aber wieder den Volltext im Speicher, und genau
das war der Fehler der ersten beiden Anläufe (200 gepufferte Archive à 30 MB = 6 GB). So
wandert nur ein DATEINAME zurück; der Text geht direkt auf die Platte und wird vom
Elternprozess als Arrow-Tabelle durchgereicht, ohne je Python-Objekt zu werden.

Aufruf (nicht von Hand — ``docpipe.build_index`` startet ihn)::

    python3 -m govisor.docworker <notice_id> <archiv.zip> <ziel.parquet>

Rückgabe auf stdout: eine Zeile JSON mit ``{zeilen, chars, status}``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Das Schema MUSS zu dem in `docpipe.build_index` passen — der Elternprozess reicht die
# Bruchstücke unverändert an den Schreiber weiter. Eine Abweichung fiele erst beim
# Zusammenführen auf, also nach der ganzen Arbeit.
SPALTEN = ["notice_id", "archive", "file", "filetype", "n_chars", "status", "text"]


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 3:
        print("Aufruf: python3 -m govisor.docworker <notice_id> <archiv.zip> <ziel.parquet>",
              file=sys.stderr)
        return 2
    notice_id, archiv, ziel = argv

    import pyarrow as pa
    import pyarrow.parquet as pq

    from .docpipe import _schema, process_zip

    zp = Path(archiv)
    try:
        zeilen = [{"notice_id": notice_id, "archive": zp.name, **r} for r in process_zip(zp)]
    except Exception as e:                                # noqa: BLE001
        # Ein Fehlschlag ist eine ZEILE, kein Abbruch — die Projektregel „markieren statt
        # filtern" gilt auch hier. Der Elternprozess erfaehrt es ueber das Bruchstueck.
        zeilen = [{"notice_id": notice_id, "archive": zp.name, "file": "", "filetype": "",
                   "n_chars": 0, "status": "fehler", "text": type(e).__name__}]

    # EIN ARCHIV OHNE DATEIEN MUSS TROTZDEM EINE ZEILE HINTERLASSEN.
    #
    # Gemessen 2026-08-15 nach dem Neuaufbau: 3.311 Archive lagen auf der Platte, 3.222
    # standen im Index. Von den 89 fehlenden waren 60 gueltige, aber LEERE ZIPs (0 Eintraege,
    # 706 Byte aufwaerts). `process_zip` liefert dafuer keine Zeile — und ohne Zeile ist das
    # Archiv aus Sicht des Index nie bearbeitet worden.
    #
    # Zwei Schaeden daraus, beide leise:
    #  · Die Projektregel „markieren statt filtern" ist verletzt: ein Fall verschwindet,
    #    statt gezaehlt zu werden.
    #  · Der Rueckstand im Betriebs-Dashboard erreicht nie null. Eine Kennzahl, die nie
    #    aufgeht, wird irgendwann ignoriert — und dann faellt auch ein echter Rueckstand
    #    nicht mehr auf.
    #
    # (Die restlichen 29 fehlenden waren waehrend des Laufs heruntergeladen worden, als die
    # Arbeitsliste laengst stand. Das ist kein Defekt, sondern Inkrementalitaet.)
    if not zeilen:
        zeilen = [{"notice_id": notice_id, "archive": zp.name, "file": "", "filetype": "",
                   "n_chars": 0, "status": "leeres_archiv", "text": ""}]

    tabelle = pa.Table.from_pylist([{k: r.get(k) for k in SPALTEN} for r in zeilen],
                                   schema=_schema())
    pq.write_table(tabelle, ziel, compression="zstd")

    status: dict[str, int] = {}
    for r in zeilen:
        status[r["status"]] = status.get(r["status"], 0) + 1
    print(json.dumps({"zeilen": len(zeilen),
                      "chars": sum(r["n_chars"] for r in zeilen),
                      "status": status}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
