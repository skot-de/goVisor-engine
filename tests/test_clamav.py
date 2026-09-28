"""ClamAV-Malware-Scan + Quarantaene — ohne installiertes ClamAV geprueft.

⚠ WARUM. Fremde Dokumente von Portalen werden ueber `/api/lead/datei` an Nutzer
weitergereicht. Der Scan (`govisor.clamav`) sperrt Infiziertes und quarantaeniert das ganze
Archiv. Diese Tests speisen einen Attrappen-Scanner ein (`lauf=`), damit die Deutung der
Exit-Codes, die Auslieferungs-Regel und die Quarantaene pruefbar sind, auch wo ClamAV fehlt.
Der echte End-to-End-Fall (EICAR) laeuft nur, wenn ein Scanner da ist, sonst Skip.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(WURZEL / "scripts"))
from govisor import clamav  # noqa: E402


# ── Deutung der Scanner-Ausgabe ───────────────────────────────────────────────────────────

def test_sauber():
    assert clamav.scan_bytes(b"harmlos", lauf=lambda p: (0, ""))[0] == clamav.SAUBER


def test_fund_mit_signatur():
    aus = "/tmp/x.bin: Win.Test.EICAR_HDB-1 FOUND"
    urteil, sig = clamav.scan_bytes(b"x", lauf=lambda p: (1, aus))
    assert urteil == clamav.INFIZIERT
    assert sig == "Win.Test.EICAR_HDB-1"


def test_scanner_fehler_ist_ungeprueft():
    assert clamav.scan_bytes(b"x", lauf=lambda p: (2, "error"))[0] == clamav.UNGEPRUEFT


def test_ausnahme_ist_ungeprueft():
    def kaputt(p):
        raise RuntimeError("clamd weg")
    assert clamav.scan_bytes(b"x", lauf=kaputt)[0] == clamav.UNGEPRUEFT


# ── Auslieferungs-Regel: fail-closed nur bei Pflicht ──────────────────────────────────────

def test_darf_ausliefern(monkeypatch):
    assert clamav.darf_ausliefern(clamav.SAUBER) is True
    assert clamav.darf_ausliefern(clamav.INFIZIERT) is False          # nie
    monkeypatch.setenv("GOVISOR_MALWARE_SCAN", "auto")
    assert clamav.darf_ausliefern(clamav.UNGEPRUEFT) is True           # auto: durch
    monkeypatch.setenv("GOVISOR_MALWARE_SCAN", "require")
    assert clamav.darf_ausliefern(clamav.UNGEPRUEFT) is False          # require: fail-closed


# ── Quarantaene: verschiebt aus dem Baum und protokolliert ────────────────────────────────

def test_quarantaene_verschiebt_und_protokolliert(tmp_path, monkeypatch):
    monkeypatch.setattr(clamav, "QUARANTAENE", tmp_path / "q")
    opfer = tmp_path / "boese.zip"
    opfer.write_bytes(b"PK\x03\x04 tu so als ob")
    ziel = clamav.quarantaene(opfer, "Eicar-Test-Signature")
    assert not opfer.exists(), "Quelle blieb liegen"
    assert ziel.exists() and ziel.read_bytes().startswith(b"PK")
    log = (tmp_path / "q" / "log.csv").read_text(encoding="utf-8")
    assert "Eicar-Test-Signature" in log and "boese.zip" in log


# ── Upload-Hook nutzt jetzt wirklich den Scanner ──────────────────────────────────────────

def test_scan_malware_sperrt_fund(monkeypatch):
    from govisor import docupload
    monkeypatch.setattr(clamav, "scan_bytes", lambda data: (clamav.INFIZIERT, "X"))
    assert docupload.scan_malware("a.pdf", b"x") is False
    monkeypatch.setattr(clamav, "scan_bytes", lambda data: (clamav.SAUBER, ""))
    assert docupload.scan_malware("a.pdf", b"x") is True


# ── Auslieferungs-Tor: Fund → Fehler + Archiv quarantaeniert ──────────────────────────────

def _mach_archiv(dir_: Path, lead: str, dateiname: str = "plan.pdf") -> Path:
    ordner = dir_ / "DE" / lead
    ordner.mkdir(parents=True, exist_ok=True)
    zp = ordner / "unterlagen.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr(dateiname, b"%PDF-1.4 harmloser Inhalt")
    return zp


def test_serve_tor_quarantaeniert_bei_fund(tmp_path, monkeypatch):
    import lead_dokumente
    monkeypatch.setattr(lead_dokumente, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(clamav, "QUARANTAENE", tmp_path / "q")
    zp = _mach_archiv(tmp_path / "docs", "444150_2026")
    monkeypatch.setattr(clamav, "scan_bytes", lambda data: (clamav.INFIZIERT, "Eicar-Test"))

    r = lead_dokumente.hole("444150_2026", "plan.pdf", str(tmp_path / "out.pdf"))
    assert "fehler" in r and r.get("signatur") == "Eicar-Test"
    assert not zp.exists(), "infiziertes Archiv blieb im Datenbaum"
    assert not (tmp_path / "out.pdf").exists(), "infizierte Datei wurde trotzdem geschrieben"
    assert list((tmp_path / "q").rglob("*.zip")), "nichts in Quarantaene"


def test_serve_tor_liefert_sauberes_aus(tmp_path, monkeypatch):
    import lead_dokumente
    monkeypatch.setattr(lead_dokumente, "DOCS", tmp_path / "docs")
    _mach_archiv(tmp_path / "docs", "444150_2026")
    monkeypatch.setattr(clamav, "scan_bytes", lambda data: (clamav.SAUBER, ""))
    r = lead_dokumente.hole("444150_2026", "plan.pdf", str(tmp_path / "out.pdf"))
    assert r.get("pfad") and (tmp_path / "out.pdf").exists()
    assert (tmp_path / "out.pdf").read_bytes().startswith(b"%PDF")


def test_serve_tor_sperrt_ungeprueft_bei_pflicht(tmp_path, monkeypatch):
    import lead_dokumente
    monkeypatch.setattr(lead_dokumente, "DOCS", tmp_path / "docs")
    _mach_archiv(tmp_path / "docs", "444150_2026")
    monkeypatch.setattr(clamav, "scan_bytes", lambda data: (clamav.UNGEPRUEFT, "kein ClamAV"))
    monkeypatch.setenv("GOVISOR_MALWARE_SCAN", "require")
    r = lead_dokumente.hole("444150_2026", "plan.pdf", str(tmp_path / "out.pdf"))
    assert "fehler" in r and not (tmp_path / "out.pdf").exists()


# ── Echter End-to-End-Lauf gegen ClamAV, sonst Skip ───────────────────────────────────────

def test_eicar_wird_erkannt_wenn_clamav_da():
    if not clamav.verfuegbar():
        pytest.skip("ClamAV nicht installiert")
    # EICAR-Teststring aus Fragmenten, damit der Literal nicht im Repo steht.
    eicar = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}" + "$EICAR-STANDARD-"
             + "ANTIVIRUS-TEST-FILE!" + "$H+H*").encode()
    urteil, sig = clamav.scan_bytes(eicar)
    assert urteil == clamav.INFIZIERT, (urteil, sig)
