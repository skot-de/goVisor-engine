"""Vergabeunterlagen eines Leads auflisten und einzelne Dateien herausgeben.

**Warum es das gibt.** Wir laden Vergabeunterlagen herunter, lesen sie aus und zeigen im
Produkt die daraus abgeleiteten Aussagen — aber das Dokument selbst konnte man nie öffnen.
Für Pläne, Zeichnungen und Formulare ist das die falsche Reihenfolge: gemessen 2026-08-15
sind 30 % der bildreinen PDFs **Pläne/Zeichnungen** und nur 2 % Fotodokumentation. Einen
Lageplan will man sehen, nicht als Text lesen — OCR machte daraus bestenfalls versprengte
Beschriftungen.

**Warum ein Python-Helfer und kein JSON-Export.** Die Dateiliste aller Vorgänge wäre 11,3 MB
(75.422 Dateien in 3.193 Vorgängen) — zu groß fürs Ausliefern und unnötig, weil immer nur
EIN Lead gefragt ist. Und das Herausgeben einer Datei braucht ohnehin Zugriff auf die
Archive auf der Platte; Node hat dafür keinen Zip-Leser im Standard.

**⚠ Damit ist das Feature lokal.** Auf einem Deployment ohne `data/docs` liefert es eine
leere Liste — ehrlich leer, nicht kaputt. Wer es dort braucht, muss die Archive in einen
Objektspeicher legen; das ist eine eigene Entscheidung und keine Nebenwirkung dieser Datei.

Aufruf::

    python3 scripts/lead_dokumente.py --lead 444150_2026
    python3 scripts/lead_dokumente.py --lead 444150_2026 --datei "ordner/plan.pdf" --nach /tmp/x
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "data" / "docs"

# Was der Browser gefahrlos selbst anzeigen kann. Alles andere wird zum Herunterladen
# angeboten — ein `.exe` oder `.zip` inline auszuliefern waere fahrlaessig.
ANZEIGBAR = {
    ".pdf": "application/pdf",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
}

# Nie ausliefern: aktive Inhalte und Signaturen. `.svg` steht bewusst NICHT hier — es ist
# oben erlaubt, wird aber unten mit `Content-Disposition: attachment` behandelt, weil SVG
# Skripte tragen kann.
GESPERRT = {".exe", ".bat", ".cmd", ".com", ".scr", ".msi", ".dll", ".js", ".vbs", ".ps1"}


def _lead_ok(lead: str) -> bool:
    """Nur die Kennungen, die das Projekt vergibt. Ohne diese Pruefung waere `../..` in der
    Lead-ID ein Pfad aus dem Datenverzeichnis heraus."""
    return bool(lead) and len(lead) <= 64 and all(
        c.isalnum() or c in "_-" for c in lead)


def liste(lead: str, country: str = "DE") -> dict:
    ordner = DOCS / country / lead
    if not ordner.is_dir():
        return {"lead": lead, "dateien": [], "grund": "keine Unterlagen abgelegt"}
    dateien = []
    for zp in sorted(ordner.glob("*.zip")):
        try:
            with zipfile.ZipFile(zp) as zf:
                for i in zf.infolist():
                    if i.is_dir():
                        continue
                    ext = Path(i.filename).suffix.lower()
                    dateien.append({
                        "archiv": zp.name,
                        "pfad": i.filename,
                        "name": Path(i.filename).name,
                        "endung": ext,
                        "bytes": i.file_size,
                        # Der Browser zeigt es selbst — sonst nur Herunterladen.
                        "anzeigbar": ext in ANZEIGBAR and ext not in GESPERRT,
                        "gesperrt": ext in GESPERRT,
                    })
        except Exception:                                 # noqa: BLE001
            # Ein kaputtes Archiv ist eine Zeile, kein Abbruch — dieselbe Regel wie im
            # Index: markieren statt filtern.
            dateien.append({"archiv": zp.name, "pfad": "", "name": zp.name,
                            "endung": "", "bytes": 0, "anzeigbar": False,
                            "gesperrt": False, "fehler": "Archiv nicht lesbar"})
    return {"lead": lead, "dateien": dateien}


def hole(lead: str, datei: str, nach: str, country: str = "DE") -> dict:
    """EINE Datei aus dem Archiv in eine Zieldatei schreiben.

    Der Pfad kommt aus dem Browser und wird deshalb NICHT zum Öffnen benutzt, sondern nur
    zum Vergleich: wir laufen die Einträge des Archivs durch und nehmen den, der exakt
    passt. Damit kann kein `../` etwas ausserhalb erreichen — es gibt gar keine
    Pfad-Verkettung.
    """
    ordner = DOCS / country / lead
    if not ordner.is_dir():
        return {"fehler": "keine Unterlagen"}
    ext = Path(datei).suffix.lower()
    if ext in GESPERRT:
        return {"fehler": "Dateityp gesperrt"}
    for zp in sorted(ordner.glob("*.zip")):
        try:
            with zipfile.ZipFile(zp) as zf:
                for i in zf.infolist():
                    if i.is_dir() or i.filename != datei:
                        continue
                    if i.file_size > 200 * 1024 ** 2:
                        return {"fehler": "Datei zu gross (>200 MB)"}
                    Path(nach).write_bytes(zf.read(i))
                    return {"pfad": nach, "bytes": i.file_size,
                            "typ": ANZEIGBAR.get(ext, "application/octet-stream"),
                            "name": Path(i.filename).name,
                            # SVG kann Skripte tragen — nie inline anzeigen.
                            "inline": ext in ANZEIGBAR and ext != ".svg"}
        except Exception:                                 # noqa: BLE001
            continue
    return {"fehler": "Datei nicht gefunden"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--lead", required=True)
    p.add_argument("--country", default="DE")
    p.add_argument("--datei")
    p.add_argument("--nach")
    a = p.parse_args(argv)
    if not _lead_ok(a.lead):
        print(json.dumps({"fehler": "ungueltige Lead-Kennung"}))
        return 1
    if a.datei:
        if not a.nach:
            print(json.dumps({"fehler": "--nach fehlt"}))
            return 1
        print(json.dumps(hole(a.lead, a.datei, a.nach, a.country), ensure_ascii=False))
    else:
        print(json.dumps(liste(a.lead, a.country), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
