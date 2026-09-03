#!/usr/bin/env python3
"""Wie lange halten die Portale ihre Vergabeunterlagen vor? — je Land, je Jahrgang.

⚠ WARUM ES DIESES SKRIPT GIBT. Die Frage entscheidet die Sammelstrategie: nur wo NICHT
vorgehalten wird, muss man live abgreifen. Sie wurde zunaechst mit Einzelversuchen
beantwortet und ergab drei Ueberraschungen:

  · Zehn Ein-Plattform-Laender liefern 14 Monate alte Unterlagen anstandslos (39/41).
  · DEUTSCHLAND loescht binnen MONATEN — DTVP und RIB geben schon fuer 2026-01 nichts mehr.
  · Luxemburg entfernt sie nach Fristende.

Daraus folgt: Aufbewahrung ist PLATTFORMSACHE, nicht Laendersache. Wer sie fuer ein neues
Land wissen will, muss messen — und zwar mit dem Abrufweg DIESES Landes, nicht mit einem
allgemeinen „antwortet die URL?". Eine Seite, die 200 zurueckgibt, kann leer sein.

⚠ ZWEI FALLEN, die beim Bauen zugeschlagen haben:
  · Die TED-Monatspakete liegen in ZWEI Bauarten vor (XML direkt / .tar.gz je Tag).
  · Vor eForms heisst das Feld URL_DOCUMENT, nicht CallForTendersDocumentReference.
Beide werden hier behandelt; wer nur eine kennt, misst stumm null.

Aufruf:  python3 scripts/pruefe_aufbewahrung.py [--jahre 2026-06,2025-06,2024-06,2022-06]
"""
from __future__ import annotations

import argparse
import io
import json
import pathlib
import re
import subprocess
import sys
import tarfile
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from govisor import bulk, flatten                                      # noqa: E402

# ⚠ NICHT AENDERN. Mit "…Aufbewahrungspruefung" gab service.eop.bg (BG) HTTP 000 — die
# Verbindung wurde abgewiesen, nicht die Anfrage beantwortet. Mit dieser Zeichenkette
# HTTP 200 und 629 KB. Der Filter dort reagiert auf den Kennungstext selbst.
UA = "goVisor/1.0 (+https://govisor.eu) Sondierung"
AUSSCHREIBUNG = re.compile(rb'<(?:[A-Za-z0-9]+:)?(ContractNotice)[ >]')
LAND_EF = re.compile(rb'listName="(?:eforms-)?country"[^>]*>([A-Z]{3})<')
LAND_ALT = re.compile(rb'<ISO_COUNTRY[^>]*VALUE="([A-Z]{2})"')
URL_ALT = re.compile(rb'<URL_DOCUMENT>([^<]{10,300})</URL_DOCUMENT>')
A3 = {"DEU": "DE", "SVN": "SI", "BGR": "BG", "ROU": "RO", "PRT": "PT", "LTU": "LT",
      "IRL": "IE", "EST": "EE", "LVA": "LV", "HUN": "HU", "CYP": "CY", "MLT": "MT",
      "DNK": "DK", "NLD": "NL", "LUX": "LU", "BEL": "BE", "CZE": "CZ", "FIN": "FI"}

# Je Land: welche Hosts zaehlen, und wie man prueft, ob wirklich Unterlagen da sind.
HOST = {
    "SI": r"enarocanje\.si",
    "PT": r"acingov\.pt|anogov\.com",
    "LT": r"viesiejipirkimai\.lt|eviesiejipirkimai\.lt",
    "IE": r"etenders\.gov\.ie",
    "MT": r"etenders\.gov\.mt",
    "CY": r"eprocurement\.gov\.cy",
    "BG": r"app\.eop\.bg",
    "RO": r"e-licitatie\.ro/pub/notices",
    "EE": r"riigihanked\.riik\.ee",
    "HU": r"ekr\.gov\.hu",
    "DK": r"ethics\.dk",
    "DE": r"dtvp\.de|meinauftrag\.rib\.de|evergabe\.nrw",
    "NL": r"tenderned\.nl",
    "LU": r"pmp\.b2g\.etat\.lu",
}


def hol(url: str, kopf: dict | None = None, max_zeit: int = 45) -> tuple[int, bytes]:
    cmd = ["curl", "-sL", "-m", str(max_zeit), "-A", UA, "-o", "-", "-w", "\n%{http_code}"]
    for k, v in (kopf or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=max_zeit + 15)
    except subprocess.TimeoutExpired:
        return 0, b""
    roh = r.stdout
    i = roh.rfind(b"\n")
    try:
        code = int(roh[i + 1:])
    except ValueError:
        code = 0
    return code, roh[:i if i > 0 else len(roh)]


def post_json(url: str, rumpf: str, ref: str | None = None) -> bytes:
    cmd = ["curl", "-s", "-m", "45", "-A", UA, "-X", "POST",
           "-H", "Content-Type: application/json", "-H", "Accept: application/json"]
    if ref:
        cmd += ["-e", ref]
    cmd += ["-d", rumpf, url]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=60).stdout
    except subprocess.TimeoutExpired:
        return b""


# ── Sonden. Jede gibt (zustand, hinweis) zurueck. ────────────────────────────────────
# zustand: "da" | "weg" | "login" | "unklar"

def sonde_datei(u: str):
    c, b = hol(u, max_zeit=90)
    if c != 200:
        return "weg", f"HTTP {c}"
    if b[:2] == b"PK" or b[:4] == b"%PDF":
        return "da", f"{len(b):,} B"
    if b"downloadDocForAnonymous" in b or b"acessoDocs" in b:
        return "da", "Dokumentenliste"
    if re.search(rb'type="password"|Enter Username', b, re.I):
        return "login", ""
    return "unklar", f"{len(b):,} B, kein Dateikopf"


def sonde_eurodyn(u: str):
    # ⚠ Zwei Adressformen. Die alte (pirkimai.eviesiejipirkimai.lt/app/rfq/rwlentrance_s.asp)
    # zeigt die Dokumente NICHT; dafuer gibt es publicpurchase_docs.asp. Ohne diesen Umweg
    # meldete die Pruefung fuer LT 2024 „0 Dokumente" — und das war MEIN Fehler, nicht
    # Litauens: ueber den richtigen Pfad kamen 2 Download-Aufrufe und 3 Dateinamen.
    if "rwlentrance_s.asp" in u:
        u = u.replace("rwlentrance_s.asp", "publicpurchase_docs.asp").split("&B=")[0]
    c, b = hol(u)
    if b"DownloadPublicDocument" in b:
        n = len(set(re.findall(rb"DownloadPublicDocument\('(\d+)'", b)))
        return ("da", f"{n} Dokumente") if n else ("weg", "0 Dokumente")
    if re.search(rb'Central Authentication|Enter your Username', b, re.I):
        return "login", ""
    n = len(set(re.findall(rb"downloadDocForAnonymous\('(\d+)'", b)))
    return ("da", f"{n} Dokumente") if n else ("weg", f"HTTP {c}, 0 Dokumente")


def sonde_bg(u: str):
    m = re.search(r"/today/(\d+)", u)
    if not m:
        return "unklar", "keine Kennung"
    d = post_json("https://service.eop.bg/NX1Service.svc/GetPublishedTenderDetails",
                  json.dumps({"tenderId": int(m.group(1)), "ianaTimeZone": "Europe/Sofia"}))
    try:
        td = json.loads(d).get("TenderDescriptionDocuments") or []
    except Exception:                                                  # noqa: BLE001
        return "unklar", "keine Antwort"
    mb = sum(int(x.get("Size") or 0) for x in td) / 1048576
    return ("da", f"{len(td)} Dok, {mb:.1f} MB") if td else ("weg", "0 Dokumente")


def sonde_ro(u: str):
    m = re.search(r"/view/(\d+)", u)
    if not m:
        return "unklar", "keine Kennung"
    nid = m.group(1)
    ref = f"https://e-licitatie.ro/pub/notices/c-notice/v2/view/{nid}"
    b = "https://e-licitatie.ro/api-pub/NoticeCommon"
    subprocess.run(["curl", "-s", "-m", "45", "-A", UA, "-e", ref, "-o", "/dev/null",
                    f"{b}/AddArchiveForNotice/?initNoticeId={nid}&sysNoticeTypeId=2"],
                   capture_output=True, timeout=60)
    r = subprocess.run(["curl", "-s", "-m", "45", "-A", UA, "-e", ref,
                        "-H", "Accept: application/json",
                        f"{b}/GetArchiveStatus/?initNoticeId={nid}&sysNoticeTypeId=2"],
                       capture_output=True, timeout=60)
    try:
        a = (json.loads(r.stdout).get("archiveItem") or {})
    except Exception:                                                  # noqa: BLE001
        return "unklar", "keine Antwort"
    st = a.get("sysArchiveStatusId")
    if st == 3:
        return "da", f"{(a.get('fileSize') or 0)/1048576:.1f} MB"
    if st in (2, 4):
        return "unklar", "Archiv wird erzeugt"
    return "weg", f"Status {st}"


def sonde_ee(u: str):
    m = re.search(r"procurement/(\d+)", u)
    if not m:
        return "unklar", "keine Kennung"
    c, b = hol(f"https://riigihanked.riik.ee/rhr/api/public/v1/procurement/{m.group(1)}"
               "/documents-temp-url", {"Accept": "application/json, text/plain, */*"})
    try:
        v = json.loads(b).get("value")
    except Exception:                                                  # noqa: BLE001
        v = None
    if not v:
        return "weg", f"HTTP {c}"
    c2, b2 = hol("https://riigihanked.riik.ee" + v, max_zeit=120)
    return ("da", f"{len(b2)/1048576:.2f} MB") if b2[:2] == b"PK" else ("weg", f"HTTP {c2}")


def sonde_hu(u: str):
    m = re.search(r"(EKR\d+)", u)
    if not m:
        return "unklar", "keine Kennung"
    c, b = hol(f"https://ekr.gov.hu/eljarastar/api/public/eljaras/{m.group(1)}"
               "?relevansReszek=null", {"Accept": "application/json, text/plain, */*"})
    try:
        dl = json.loads(b).get("dokumentumList") or []
    except Exception:                                                  # noqa: BLE001
        return "weg", f"HTTP {c}"
    return ("da", f"{len(dl)} Dokumente") if dl else ("weg", "0 Dokumente")


def sonde_de(u: str):
    c, b = hol(u)
    if re.search(rb'no longer publicly available|nicht mehr .{0,25}verf|unerwarteter Fehler', b, re.I):
        return "weg", "Portal: nicht mehr verfuegbar"
    if c in (400, 404):
        return "weg", f"HTTP {c}"
    if re.search(rb'Vergabeunterlagen|Unterlagen herunterladen|\.zip', b, re.I):
        return "da", f"{len(b):,} B"
    return "unklar", f"HTTP {c}, {len(b):,} B"


def sonde_text(u: str):
    c, b = hol(u)
    if c in (400, 404):
        return "weg", f"HTTP {c}"
    if re.search(rb'type="password"|Enter Username|Central Authentication', b, re.I):
        return "login", ""
    if re.search(rb'\.zip|\.pdf|Vergabeunterlagen|documenten|dokument', b, re.I):
        return "da", f"{len(b):,} B"
    return "unklar", f"HTTP {c}, {len(b):,} B"


def sonde_dk(u: str):
    m = re.search(r"([0-9a-f]{8}-[0-9a-f-]{27})", u)
    if not m:
        return "unklar", "keine Kennung"
    c, b = hol(f"https://www.ethics.dk/ethics/publicTenderDocs/{m.group(1)}",
               {"Accept": "application/json"})
    try:
        td = json.loads(b).get("tenderDocs") or []
    except Exception:                                                  # noqa: BLE001
        return "weg", f"HTTP {c}"
    return ("da", f"{len(td)} Eintraege") if td else ("weg", "0 Eintraege")


def sonde_lu(u: str):
    c, b = hol(u)
    import html as _h
    t = _h.unescape(re.sub(rb"<[^>]+>", b" ", b).decode("utf-8", "replace"))
    if "Aucune pi" in t:
        return "weg", "Aucune piece jointe"
    if "Dossier de soumission" in t:
        return "da", "Dossier vorhanden"
    return "unklar", f"HTTP {c}"


def sonde_nl(u: str):
    c, b = hol(u)
    if c in (400, 404):
        return "weg", f"HTTP {c}"
    if re.search(rb'Documenten|documenten|bijlage|Publicatie', b, re.I):
        return "da", f"{len(b):,} B"
    return "unklar", f"HTTP {c}, {len(b):,} B"


SONDE = {"SI": sonde_datei, "PT": sonde_datei, "LT": sonde_eurodyn, "IE": sonde_eurodyn,
         "MT": sonde_eurodyn, "CY": sonde_eurodyn, "BG": sonde_bg, "RO": sonde_ro,
         "EE": sonde_ee, "HU": sonde_hu, "DE": sonde_de, "DK": sonde_dk,
         "NL": sonde_nl, "LU": sonde_lu}


def sammle(paket: pathlib.Path, je_land: int) -> dict[str, list[str]]:
    """Dokument-Adressen je Land — eForms UND Altformat."""
    tref: dict[str, list[str]] = {l: [] for l in HOST}
    with tarfile.open(paket) as t:
        for m in t:
            if not m.isfile():
                continue
            rohs = []
            if m.name.endswith(".xml"):
                rohs = [t.extractfile(m).read()]
            elif m.name.endswith(".tar.gz"):
                daten = t.extractfile(m).read()
                if AUSSCHREIBUNG.search(daten[:200]) is None:
                    for _x, roh in bulk._walk(m.name, daten, None):
                        rohs.append(roh)
            for roh in rohs:
                urls = []
                if AUSSCHREIBUNG.search(roh[:5000]):
                    c = LAND_EF.search(roh[:200000])
                    land = A3.get(c.group(1).decode()) if c else None
                    if land:
                        try:
                            urls = [w for p, w in flatten.leaves(roh)
                                    if "CallForTendersDocumentReference" in p and w.startswith("http")]
                        except Exception:                              # noqa: BLE001
                            urls = []
                else:
                    c = LAND_ALT.search(roh[:200000])
                    land = c.group(1).decode() if c else None
                    urls = [d.decode("utf-8", "replace").replace("&amp;", "&")
                            for d in URL_ALT.findall(roh)]
                if not land or land not in HOST:
                    continue
                muster = re.compile(HOST[land], re.I)
                for u in urls:
                    if muster.search(u) and u not in tref[land] and len(tref[land]) < je_land:
                        tref[land].append(u)
            if all(len(v) >= je_land for v in tref.values()):
                break
    return tref


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--jahre", default="2026-06,2025-06,2024-06,2022-06")
    p.add_argument("--pro-land", type=int, default=3)
    p.add_argument("--ziel", default="data/sondierung/aufbewahrung.json")
    a = p.parse_args()

    jahre = a.jahre.split(",")
    erg: dict = {}
    for j in jahre:
        pk = ROOT / "data" / "cache" / f"ted_{j}.tar.gz"
        if not pk.exists():
            print(f"  {j}: kein Paket"); continue
        tref = sammle(pk, a.pro_land)
        print(f"\n── {j}", flush=True)
        for land, urls in sorted(tref.items()):
            if not urls:
                erg.setdefault(land, {})[j] = {"n": 0, "zustand": "keine Adresse"}
                print(f"  {land}: keine Adresse im Paket"); continue
            zaehl: dict = {}
            hinweise = []
            for u in urls:
                z, h = SONDE[land](u)
                zaehl[z] = zaehl.get(z, 0) + 1
                if h:
                    hinweise.append(h)
            best = max(zaehl, key=lambda k: (k == "da", zaehl[k]))
            erg.setdefault(land, {})[j] = {"n": len(urls), "zustand": zaehl,
                                           "hinweise": hinweise[:3]}
            print(f"  {land}: {zaehl}  {' · '.join(hinweise[:2])}", flush=True)

    ziel = ROOT / a.ziel
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  → {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
