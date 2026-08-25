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

ZWEI ZIELE, EINE MECHANIK. S3-kompatibel (R2, S3, B2, MinIO) und **Azure Blob Storage**.
Azure ist das perspektivische Ziel (Sven am 2026-08-18: „ich wuerde es perspektivisch zu
azure hochladen"), und dort ist der einfachste Weg zugleich der sicherste: ein **SAS-Token**.
Er ist auf Container und Rechte begrenzt, laeuft ab, und es muss nichts signiert werden — der
Runner kennt damit keinen Kontoschluessel, der alles darf.

Konfiguration (Umgebungsvariablen, z. B. in `web/.env.local` oder im Runner):

    DATA_S3_ENDPOINT   https://<konto>.r2.cloudflarestorage.com
    DATA_S3_BUCKET     govisor-data
    DATA_S3_KEY_ID     …
    DATA_S3_SECRET     …
    DATA_S3_REGION     auto           (Vorgabe: auto — R2 will genau das)
    DATA_S3_PREFIX     web-data       (optional, Unterordner im Bucket)

Oder Azure:

    DATA_AZURE_URL     https://<konto>.blob.core.windows.net/<container>?<sas-token>
    DATA_AZURE_PREFIX  web-data       (optional)

Ist `DATA_AZURE_URL` gesetzt, gilt Azure; sonst S3. Beides gleichzeitig waere eine Frage
danach, welche Fassung die echte ist, und die soll niemand raten muessen.

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
LEER_HASH = hashlib.sha256(b"").hexdigest()

# ZWEI QUELLEN, EINE MECHANIK.
#
# `web` ist der Betriebszweck: die Dateien, die das Frontend liest. Sie gehen in die
# heisse Stufe, werden taeglich neu geschrieben und sind klein (984 MB).
#
# `docs` ist die SICHERUNG des Korpus: 175 GB Vergabeunterlagen in 6.830 ZIPs. Sven am
# 2026-08-22: „ich will die ausschreibungsdokumente behalten, um daraus muster abzuleiten".
# Sie liegen bisher genau EINMAL, auf einer externen SSD. Der Rest der Plattform ist aus
# ihnen regenerierbar, sie selbst aus nichts: Portale geben nicht alles zweimal heraus, und
# `SPERRE_TAGE` bremst jeden zweiten Versuch. Deshalb kalte Stufe, selten geschrieben,
# nie geloescht.
# ⚠ ARBEITSSTAENDE UND SICHERUNGEN GEHOEREN NICHT IN DEN OBJEKTSPEICHER.
# `doc-analysis.json` ist die Datei, aus der `analyse_arbeiter.sh` liest, was noch fehlt —
# 332 MB, die das Frontend seit dem 2026-08-22 nicht mehr anfasst (es liest
# `doc-analysis/<id>.json`). Sie jede Nacht hochzuladen, damit sie niemand liest, waere
# teuer und sinnlos.
#
# ⚠ EIN EXAKTER NAME REICHT NICHT. Genau das stand hier bis zum 2026-08-25, und die
# Sicherung vor einer Neuberechnung heisst `doc-analysis.vor_neurechnung-<zeit>.json` —
# also anders. Sie rutschte durch und war mit **112 MB die groesste Einzeldatei des
# Uploads**, groesser als jede echte Produktdatei. Der Fehler war nicht die vergessene
# Zeile, sondern die Form der Regel: eine Liste exakter Namen faellt beim naechsten
# Namen wieder um, und zwar lautlos. Deshalb jetzt zusaetzlich ein Muster.
NICHT_HOCH = {"doc-analysis.json"}
NICHT_HOCH_MUSTER = (".vor_", ".bak", ".backup", ".tmp", ".alt-")


def auswahl(quelle, typen) -> list:
    """Was hochgeht: Nutzdaten, keine Arbeitsstaende.

    Ausgelagert, damit `tests/` die Regel an einem Beispielbaum pruefen kann — im
    Rumpf von `main()` waere sie nur durch einen echten Upload zu erreichen.
    """
    return sorted(p for p in quelle.rglob("*")
                  if p.is_file() and p.suffix in typen
                  and p.name not in NICHT_HOCH
                  and not any(m in p.name for m in NICHT_HOCH_MUSTER))


QUELLEN = {
    "web": (ROOT / "web" / "data", {".json": "application/json", ".csv": "text/csv"}),
    "docs": (ROOT / "data" / "docs", {".zip": "application/zip",
                                      ".parquet": "application/octet-stream",
                                      ".json": "application/json", ".csv": "text/csv"}),
}

# Speicherstufe. Kalt kostet rund ein Fuenftel von heiss, verlangt aber laengere
# Mindestliegezeit und Abrufgebuehren — fuer eine Sicherung, die man hoffentlich nie liest,
# genau richtig. Archiv waere noch billiger, muss aber vor jedem Zugriff stundenlang
# aufgetaut werden; das will man nicht, wenn man Muster ableiten moechte.
STUFEN = {"hot": "Hot", "cool": "Cool", "cold": "Cold", "archive": "Archive"}


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
               key_id: str, secret: str, nutzlast: bytes | None,
               speicherklasse: str | None = None) -> tuple[str, dict]:
    """AWS-Signature-Version-4 fuer einen einzelnen Aufruf. Rueckgabe: URL + Kopfzeilen."""
    host = endpunkt.split("://", 1)[1].rstrip("/")
    kanon_uri = "/" + bucket + "/" + pfad.lstrip("/")
    url = f"{endpunkt.rstrip('/')}{kanon_uri}"
    jetzt = _dt.datetime.now(_dt.timezone.utc)
    stempel = jetzt.strftime("%Y%m%dT%H%M%SZ")
    tag = jetzt.strftime("%Y%m%d")
    inhalt = hashlib.sha256(nutzlast).hexdigest() if nutzlast is not None else LEER_HASH

    kopf = {"host": host, "x-amz-content-sha256": inhalt, "x-amz-date": stempel}
    # ⚠ MUSS MITSIGNIERT WERDEN. Eine `x-amz-`-Kopfzeile, die nachtraeglich angehaengt wird,
    # macht die Signatur ungueltig — und der Fehler kommt als 403 zurueck, also als „falsche
    # Zugangsdaten". Deshalb steht sie hier, VOR der Berechnung, und nicht beim Aufrufer.
    if speicherklasse:
        kopf["x-amz-storage-class"] = speicherklasse
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


def azure_ziel(basis: str, pfad: str) -> str:
    """Container-URL mit SAS + Blob-Pfad zusammensetzen, ohne den Token zu verlieren.

    Die SAS-URL traegt ihre Rechte in der Query. Wer den Pfad naiv anhaengt, schiebt ihn
    HINTER das Fragezeichen und bekommt 403 — ein Fehler, der nach falschen Rechten aussieht
    und keiner ist.
    """
    kopf, _, query = basis.partition("?")
    url = f"{kopf.rstrip('/')}/{pfad.lstrip('/')}"
    return f"{url}?{query}" if query else url


def azure_hochladen(basis: str, pfad: str, daten: bytes, typ: str, timeout: int = 900,
                    stufe: str = "Hot"):
    """Ein Blob schreiben. `stufe` setzt die Speicherklasse gleich beim Schreiben.

    ⚠ Die Stufe NACHTRAeglich zu aendern kostet eine zweite Operation je Blob und bei
    6.830 Dateien einen eigenen Lauf. Beim Schreiben ist sie ein Kopfzeilen-Feld.
    """
    kopf = {"x-ms-blob-type": "BlockBlob", "Content-Type": typ}
    if stufe and stufe != "Hot":
        kopf["x-ms-access-tier"] = stufe
    return requests.put(azure_ziel(basis, pfad), data=daten, timeout=timeout, headers=kopf)


def azure_groesse(basis: str, pfad: str) -> int | None:
    try:
        r = requests.head(azure_ziel(basis, pfad), timeout=30)
    except requests.RequestException:
        return None
    return int(r.headers.get("content-length", -1)) if r.status_code == 200 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="nichts hochladen, nur auflisten")
    ap.add_argument("--alles", action="store_true", help="auch unveraenderte Dateien")
    ap.add_argument("--quelle", choices=sorted(QUELLEN), default="web",
                    help="web = Frontend-Daten (Vorgabe), docs = Sicherung des Dokumentkorpus")
    ap.add_argument("--stufe", choices=sorted(STUFEN), default=None,
                    help="Speicherstufe; Vorgabe: hot fuer web, cool fuer docs")
    a = ap.parse_args()

    QUELLE, TYPEN = QUELLEN[a.quelle]
    if not QUELLE.exists():
        print(f"  ✖ {QUELLE} gibt es nicht.", file=sys.stderr)
        return 2
    # Die Sicherung landet unter einem eigenen Praefix. Sonst mischen sich 175 GB Archiv und
    # 984 MB Betriebsdaten in einem Verzeichnis, und die Lebenszyklus-Regel des Speichers
    # (kalt nach X Tagen) trifft die falschen Dateien.
    stufe = STUFEN[a.stufe] if a.stufe else ("Cool" if a.quelle == "docs" else "Hot")
    eigen_prefix = "docs" if a.quelle == "docs" else ""

    e = env()
    azure = e.get("DATA_AZURE_URL", "").strip()
    endpunkt = e.get("DATA_S3_ENDPOINT", "").strip()
    bucket = e.get("DATA_S3_BUCKET", "").strip()
    key_id = e.get("DATA_S3_KEY_ID", "").strip()
    secret = e.get("DATA_S3_SECRET", "").strip()
    region = e.get("DATA_S3_REGION", "auto").strip() or "auto"
    prefix = e.get("DATA_S3_PREFIX", "").strip().strip("/")
    if eigen_prefix:
        prefix = f"{prefix}/{eigen_prefix}".strip("/")

    dateien = auswahl(QUELLE, TYPEN)
    gesamt = sum(p.stat().st_size for p in dateien)
    print(f"  {len(dateien):,} Dateien, {gesamt/1048576:.0f} MB in {QUELLE.relative_to(ROOT)} "
          f"→ Stufe {stufe}")

    if azure:
        prefix = e.get("DATA_AZURE_PREFIX", "").strip().strip("/")
        if eigen_prefix:
            prefix = f"{prefix}/{eigen_prefix}".strip("/")
        hoch, gleich, fehler, bytes_hoch = 0, 0, 0, 0
        for p in dateien:
            ziel = f"{prefix}/{p.relative_to(QUELLE).as_posix()}" if prefix else p.relative_to(QUELLE).as_posix()
            groesse = p.stat().st_size
            if not a.alles and azure_groesse(azure, ziel) == groesse:
                gleich += 1
                continue
            if a.probe:
                print(f"    → {ziel} ({groesse/1048576:.1f} MB)")
                hoch += 1
                continue
            r = azure_hochladen(azure, ziel, p.read_bytes(), TYPEN[p.suffix], stufe=stufe)
            if r.status_code not in (200, 201):
                print(f"    ✖ {ziel}: HTTP {r.status_code} {r.text[:120]}", file=sys.stderr)
                fehler += 1
                continue
            hoch += 1
            bytes_hoch += groesse
        print(f"  Azure · {hoch:,} hochgeladen ({bytes_hoch/1048576:.0f} MB) · {gleich:,} "
              f"unveraendert · {fehler:,} Fehler")
        return 1 if fehler else 0

    if not all((endpunkt, bucket, key_id, secret)):
        folge = ("Ohne Speicher bleibt web/data lokal — das Frontend laeuft hier weiter,\n"
                 "    ein Deployment ohne DATA_BASE_URL findet aber keine Daten."
                 if a.quelle == "web" else
                 "Ohne Speicher gibt es den Dokumentkorpus weiterhin GENAU EINMAL, auf der\n"
                 "    externen SSD. Der Rest der Plattform ist aus ihm regenerierbar, er selbst\n"
                 "    aus nichts.")
        print("  ✖ Nicht konfiguriert. Erwartet entweder DATA_AZURE_URL (SAS) oder "
              "DATA_S3_ENDPOINT + DATA_S3_BUCKET + DATA_S3_KEY_ID + DATA_S3_SECRET.\n"
              f"    {folge}", file=sys.stderr)
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
        # S3-Speicherklassen heissen anders als bei Azure; nur die kalten Stufen abbilden.
        klasse = {"Cool": "STANDARD_IA", "Cold": "GLACIER_IR", "Archive": "GLACIER"}.get(stufe)
        url, kopf = kopf_bauen("PUT", endpunkt, bucket, ziel, region, key_id, secret, daten,
                               speicherklasse=klasse)
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
