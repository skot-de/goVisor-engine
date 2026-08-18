#!/usr/bin/env python3
"""``web/data`` in einen S3-kompatiblen Speicher schieben. Ohne neue Abhaengigkeit.

**Warum es das braucht.** Seit dem 2026-08-18 liegt `web/data` nicht mehr in Git (s.
`.gitignore` dort, mit Begruendung). Damit fehlen dem Deployment die Daten, solange sie
nicht woanders liegen: `web/lib/dataSource.ts` liest `DATA_BASE_URL` und faellt nur LOKAL
auf die Platte zurueck. Dieses Skript ist das fehlende Stueck.

**Warum SigV4 von Hand und nicht boto3.** boto3 zieht botocore mit (rund 100 MB entpackt)
fuer eine einzige Aufgabe: ein signiertes PUT. Die Signatur ist 40 Zeilen Standardbibliothek,
und sie ist an einer Stelle nachlesbar statt in einer Abhaengigkeit versteckt. Das Skript
spricht damit R2, S3, B2 und MinIO gleich gut.

**Warum nur Geaendertes.** Der Tageslauf schreibt jede Nacht alles neu, aber inhaltlich
aendert sich wenig. Vor jedem PUT fragt das Skript per HEAD die Groesse ab und ueberspringt,
was gleich gross ist. Das ist bewusst KEIN Hash-Vergleich: S3 liefert bei mehrteiligen
Uploads kein verlaessliches MD5, und eine Groessengleichheit bei identischem Export ist in
der Praxis eindeutig. Wer es erzwingen will, nimmt `--alles`.

Konfiguration (Umgebungsvariablen, z. B. in `web/.env.local` oder im Runner):

    DATA_S3_ENDPOINT   https://<konto>.r2.cloudflarestorage.com
    DATA_S3_BUCKET     govisor-data
    DATA_S3_KEY_ID     …
    DATA_S3_SECRET     …
    DATA_S3_REGION     auto           (Vorgabe: auto — R2 will genau das)
    DATA_S3_PREFIX     web-data       (optional, Unterordner im Bucket)

Aufruf::

    scripts/upload_web_data.py --probe          # nur zeigen, was hochginge
    scripts/upload_web_data.py                  # nur Geaendertes
    scripts/upload_web_data.py --alles
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import hmac
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
QUELLE = ROOT / "web" / "data"
LEER_HASH = hashlib.sha256(b"").hexdigest()

TYPEN = {".json": "application/json", ".csv": "text/csv"}


def env() -> dict[str, str]:
    """Konfiguration aus der Umgebung, sonst aus `web/.env.local`.

    Der Tageslauf laeuft ohne Shell-Profil; auf `export` in irgendeiner Sitzung ist kein
    Verlass. Die Datei ist die Quelle, die auch das Frontend benutzt.
    """
    e = dict(os.environ)
    datei = ROOT / "web" / ".env.local"
    if datei.exists():
        for k, v in re.findall(r"^([A-Z_0-9]+)\s*=\s*(.*)$", datei.read_text(encoding="utf-8"), re.M):
            e.setdefault(k, v.strip())
    return e


def _signieren(schluessel: bytes, msg: str) -> bytes:
    return hmac.new(schluessel, msg.encode(), hashlib.sha256).digest()


def kopf_bauen(methode: str, endpunkt: str, bucket: str, pfad: str, region: str,
               key_id: str, secret: str, nutzlast: bytes | None) -> tuple[str, dict]:
    """AWS-Signature-Version-4 fuer einen einzelnen Aufruf. Rueckgabe: URL + Kopfzeilen."""
    host = endpunkt.split("://", 1)[1].rstrip("/")
    kanon_uri = "/" + bucket + "/" + pfad.lstrip("/")
    url = f"{endpunkt.rstrip('/')}{kanon_uri}"
    jetzt = _dt.datetime.now(_dt.timezone.utc)
    stempel = jetzt.strftime("%Y%m%dT%H%M%SZ")
    tag = jetzt.strftime("%Y%m%d")
    inhalt = hashlib.sha256(nutzlast).hexdigest() if nutzlast is not None else LEER_HASH

    kopf = {"host": host, "x-amz-content-sha256": inhalt, "x-amz-date": stempel}
    signierte = ";".join(sorted(kopf))
    kanon_kopf = "".join(f"{k}:{kopf[k]}\n" for k in sorted(kopf))
    kanon = f"{methode}\n{kanon_uri}\n\n{kanon_kopf}\n{signierte}\n{inhalt}"

    bereich = f"{tag}/{region}/s3/aws4_request"
    zu_signieren = f"AWS4-HMAC-SHA256\n{stempel}\n{bereich}\n{hashlib.sha256(kanon.encode()).hexdigest()}"
    k = _signieren(f"AWS4{secret}".encode(), tag)
    k = _signieren(k, region)
    k = _signieren(k, "s3")
    k = _signieren(k, "aws4_request")
    signatur = hmac.new(k, zu_signieren.encode(), hashlib.sha256).hexdigest()

    kopf["Authorization"] = (f"AWS4-HMAC-SHA256 Credential={key_id}/{bereich}, "
                             f"SignedHeaders={signierte}, Signature={signatur}")
    return url, kopf


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="nichts hochladen, nur auflisten")
    ap.add_argument("--alles", action="store_true", help="auch unveraenderte Dateien")
    a = ap.parse_args()

    e = env()
    endpunkt = e.get("DATA_S3_ENDPOINT", "").strip()
    bucket = e.get("DATA_S3_BUCKET", "").strip()
    key_id = e.get("DATA_S3_KEY_ID", "").strip()
    secret = e.get("DATA_S3_SECRET", "").strip()
    region = e.get("DATA_S3_REGION", "auto").strip() or "auto"
    prefix = e.get("DATA_S3_PREFIX", "").strip().strip("/")

    dateien = sorted(p for p in QUELLE.rglob("*") if p.is_file() and p.suffix in TYPEN)
    gesamt = sum(p.stat().st_size for p in dateien)
    print(f"  {len(dateien):,} Dateien, {gesamt/1048576:.0f} MB in {QUELLE.relative_to(ROOT)}")

    if not all((endpunkt, bucket, key_id, secret)):
        print("  ✖ Nicht konfiguriert. Erwartet: DATA_S3_ENDPOINT, DATA_S3_BUCKET, "
              "DATA_S3_KEY_ID, DATA_S3_SECRET.\n"
              "    Ohne Speicher bleibt web/data lokal — das Frontend laeuft hier weiter,\n"
              "    ein Deployment ohne DATA_BASE_URL findet aber keine Daten.", file=sys.stderr)
        return 2 if not a.probe else 0

    hoch, gleich, fehler, bytes_hoch = 0, 0, 0, 0
    for p in dateien:
        ziel = f"{prefix}/{p.relative_to(QUELLE).as_posix()}" if prefix else p.relative_to(QUELLE).as_posix()
        groesse = p.stat().st_size

        if not a.alles:
            url, kopf = kopf_bauen("HEAD", endpunkt, bucket, ziel, region, key_id, secret, None)
            try:
                r = requests.head(url, headers=kopf, timeout=30)
                if r.status_code == 200 and int(r.headers.get("content-length", -1)) == groesse:
                    gleich += 1
                    continue
            except requests.RequestException:
                pass                       # im Zweifel hochladen, nicht ueberspringen

        if a.probe:
            print(f"    → {ziel} ({groesse/1048576:.1f} MB)")
            hoch += 1
            continue

        daten = p.read_bytes()
        url, kopf = kopf_bauen("PUT", endpunkt, bucket, ziel, region, key_id, secret, daten)
        kopf["Content-Type"] = TYPEN[p.suffix]
        try:
            r = requests.put(url, data=daten, headers=kopf, timeout=900)
        except requests.RequestException as ex:
            print(f"    ✖ {ziel}: {ex}", file=sys.stderr); fehler += 1; continue
        if r.status_code not in (200, 201):
            print(f"    ✖ {ziel}: HTTP {r.status_code} {r.text[:120]}", file=sys.stderr)
            fehler += 1; continue
        hoch += 1; bytes_hoch += groesse
        print(f"    ✓ {ziel} ({groesse/1048576:.1f} MB)")

    print(f"  {hoch:,} hochgeladen ({bytes_hoch/1048576:.0f} MB) · {gleich:,} unveraendert "
          f"· {fehler:,} Fehler")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
