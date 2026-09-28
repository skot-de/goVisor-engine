"""Malware-Scan (ClamAV) + Quarantaene fuer fremde Dokumente.

⚠ WARUM. Wir laden fremde Dateien von Vergabeportalen und reichen sie ueber
`/api/lead/datei` an Nutzer weiter. Ausgefuehrt wird nichts davon (keine Makros, keine
Konverter), aber eine infizierte Originaldatei, die ein Nutzer in SEINEM Office oeffnet, ist
trotzdem unser Verteilungsweg. Bis zum 2026-09-28 war der einzige Hook (`docupload.scan_malware`)
ein Stub, der immer „sauber" sagte, und er lief nur beim Upload, nie beim Portal-Abruf.

Kein selbstgebauter Scanner (bewusst): ClamAV ueber `clamdscan` (Daemon, schnell) oder
`clamscan` (CLI). Fehlt beides, ist das Urteil `UNGEPRUEFT` — was das bedeutet, entscheidet
der Aufrufer:
  · Auslieferung (`lead_dokumente.hole`): INFIZIERT nie; UNGEPRUEFT nur bei
    `GOVISOR_MALWARE_SCAN=require` gesperrt (sonst wird intern weiter ausgeliefert, damit die
    Funktion ohne installiertes ClamAV nicht bricht — die Sperre ist fuer die Produktion).
  · Upload (`scan_malware`): dieselbe Regel.

Ein Treffer wird QUARANTAENIERT: das ganze Archiv wandert nach `data/quarantaene/<datum>/`
und wird protokolliert — es soll weder erneut ausgeliefert noch geparst werden.
"""
from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import os
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

SAUBER = "sauber"
INFIZIERT = "infiziert"
UNGEPRUEFT = "ungeprueft"

_WURZEL = Path(__file__).resolve().parent.parent
# Modul-Global, damit Tests es auf ein Temp-Verzeichnis umbiegen koennen.
QUARANTAENE = _WURZEL / "data" / "quarantaene"

_ZEIT_MS = 120


def pflicht() -> bool:
    """`GOVISOR_MALWARE_SCAN=require` → ein nicht durchfuehrbarer Scan sperrt fail-closed."""
    return os.environ.get("GOVISOR_MALWARE_SCAN", "auto").strip().lower() == "require"


@lru_cache(maxsize=1)
def _scanner() -> tuple[str, str] | None:
    for name in ("clamdscan", "clamscan"):
        prog = shutil.which(name)
        if prog:
            return name, prog
    return None


def verfuegbar() -> bool:
    return _scanner() is not None


def _lauf(pfad: str) -> tuple[int, str]:
    """Ruft den echten Scanner. Rueckgabe (Exit-Code, Ausgabe). clamscan/clamdscan:
    0 = sauber, 1 = Fund, sonst Fehler."""
    name, prog = _scanner()  # type: ignore[misc]
    if name == "clamdscan":
        args = [prog, "--no-summary", "--fdpass", pfad]
    else:
        args = [prog, "--no-summary", "--stdout", pfad]
    r = subprocess.run(args, capture_output=True, text=True, timeout=_ZEIT_MS)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _deute(rc: int, aus: str) -> tuple[str, str]:
    if rc == 0:
        return SAUBER, ""
    if rc == 1:
        sig = ""
        for z in aus.splitlines():
            if z.strip().endswith("FOUND"):
                # Form: "<pfad>: <Signatur> FOUND"
                sig = z.rsplit(":", 1)[-1].strip()
                if sig.endswith("FOUND"):
                    sig = sig[:-5].strip()
                break
        return INFIZIERT, sig or "unbekannte Signatur"
    return UNGEPRUEFT, f"Scanner-Exit {rc}: {aus.strip()[-100:]}"


def scan_datei(pfad: str | Path, *, lauf=None) -> tuple[str, str]:
    """Scannt eine Datei (Archive entpackt ClamAV selbst). (Urteil, Signatur/Grund)."""
    if lauf is None:
        if not verfuegbar():
            return UNGEPRUEFT, "ClamAV nicht installiert"
        lauf = _lauf
    try:
        rc, aus = lauf(str(pfad))
    except Exception as e:                                # noqa: BLE001
        return UNGEPRUEFT, f"Scanner-Fehler: {str(e)[:80]}"
    return _deute(rc, aus)


def scan_bytes(data: bytes, *, lauf=None) -> tuple[str, str]:
    """Wie `scan_datei`, aber fuer einen Puffer (Upload, einzelne extrahierte Datei)."""
    if lauf is None and not verfuegbar():
        return UNGEPRUEFT, "ClamAV nicht installiert"
    with tempfile.NamedTemporaryFile(prefix="gv-scan-", suffix=".bin", delete=False) as f:
        f.write(data)
        tmp = f.name
    try:
        return scan_datei(tmp, lauf=lauf)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def darf_ausliefern(urteil: str) -> bool:
    """INFIZIERT immer sperren; UNGEPRUEFT nur, wenn der Scan Pflicht ist."""
    if urteil == INFIZIERT:
        return False
    if urteil == UNGEPRUEFT and pflicht():
        return False
    return True


def quarantaene(pfad: str | Path, grund: str) -> Path:
    """Verschiebt eine Datei unwiderruflich aus dem Datenbaum in die Quarantaene und
    protokolliert Quelle, Ziel und Grund. Gibt den Zielpfad zurueck."""
    src = Path(pfad)
    tag = _dt.date.today().isoformat()
    ziel_dir = QUARANTAENE / tag
    ziel_dir.mkdir(parents=True, exist_ok=True)
    kennung = hashlib.sha256(str(src.resolve()).encode("utf-8")).hexdigest()[:12]
    ziel = ziel_dir / f"{kennung}__{src.name}"
    shutil.move(str(src), str(ziel))
    _protokoll(src, ziel, grund)
    return ziel


def _protokoll(src: Path, ziel: Path, grund: str) -> None:
    QUARANTAENE.mkdir(parents=True, exist_ok=True)
    datei = QUARANTAENE / "log.csv"
    neu = not datei.exists()
    with datei.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if neu:
            w.writerow(["zeit", "quelle", "quarantaene", "grund"])
        w.writerow([_dt.datetime.now().isoformat(timespec="seconds"), str(src), str(ziel), grund])
