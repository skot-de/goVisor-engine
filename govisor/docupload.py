"""Upload-Aufnahme & Sicherheitsprüfungen für Vergabeunterlagen (Ticket #23, §4.2/§5).

Reine, testbare Logik — die Reihenfolge der Prüfungen (§5) verantwortet der Aufruf-Kontext
(Upload-Endpunkt). Hier: Grenzwerte, Zip-Slip, ZIP-Bomben-Schutz, Paket-Hash (Dedup),
Eigen-Angebot-Erkennung, Lead-Zuordnung. Der Malware-Scan ist ein Hook (Produktion verdrahtet
einen echten Scanner) — bewusst nicht hier erfunden.
"""
from __future__ import annotations

import hashlib
import re

# ── §4.2 Grenzwerte ──────────────────────────────────────────────────────────────────────────
MAX_PACKAGE_BYTES = 500 * 1024 ** 2       # 500 MB
MAX_FILES = 250
MAX_COMPRESSION_RATIO = 100               # 100:1 ZIP-Bomben-Schutz
MAX_ZIP_DEPTH = 3
MAX_UPLOADS_PER_HOUR = 20


def check_limits(total_bytes: int, file_count: int) -> list[str]:
    """Grenzwert-Verstöße (§4.2). Leere Liste = ok."""
    v = []
    if total_bytes > MAX_PACKAGE_BYTES:
        v.append(f"paket_zu_gross:{total_bytes}")
    if file_count > MAX_FILES:
        v.append(f"zu_viele_dateien:{file_count}")
    return v


def is_zip_slip(name: str) -> bool:
    """Pfad zeigt aus dem Zielverzeichnis (§5-2): absolute Pfade, Laufwerk, ``..``-Segmente."""
    n = (name or "").replace("\\", "/")
    if n.startswith("/") or re.match(r"^[A-Za-z]:", n):
        return True
    return any(seg == ".." for seg in n.split("/"))


def check_zip_bomb(compressed_size: int, uncompressed_size: int) -> bool:
    """True = verdächtiges Kompressionsverhältnis (§4.2, 100:1)."""
    if compressed_size <= 0:
        return uncompressed_size > 0
    return (uncompressed_size / compressed_size) > MAX_COMPRESSION_RATIO


def package_hash(files: list[tuple[str, bytes]]) -> str:
    """Stabiler Paket-Hash über (Dateiname, Inhalts-Hash), sortiert (§5-5 Dedup, §12.2 Herkunft).

    Reihenfolge-unabhängig: identische Dateien in anderer Reihenfolge → gleicher Hash."""
    parts = sorted(f"{name}:{hashlib.sha256(data).hexdigest()}" for name, data in files)
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


# Bietersicht-Signale (§5-3): EIGENES Angebot statt Vergabeunterlagen. Nur COMMITTENDE, präsentische
# Formulierungen — NICHT „unser Angebot"/„Angebotssumme"/„Mit freundlichen Grüßen", denn die stehen
# im Standard-VHB (Formblatt 124: „Falls mein/unser Angebot in die engere Wahl kommt", gemessen an
# 25578112). Reine Phrasen trennen Bieter-Sprache und VHB-Vorlage nicht sauber → konservativ.
_OWN_OFFER = re.compile(
    r"(hiermit bieten wir\b|wir bieten ihnen (?:hiermit |folgende |nachstehend )?an\b|"
    r"anbei (?:unser|unser?es) angebot\b|unser angebot liegt (?:bei|vor)\b|"
    r"unser(?:er)? (?:gesamt)?(?:angebots)?preis (?:beträgt|liegt bei)\b)", re.I)


def detect_own_offer(text: str, threshold: int = 2) -> bool:
    """Heuristik: sieht der Upload nach dem EIGENEN Angebot des Nutzers aus? (§5-3, Abbruch).

    Zählt **distinkte** committende Bieter-Phrasen (ein wiederholtes Vorlagen-Wort zählt einmal);
    ab ``threshold`` gilt es als Eigen-Angebot. Bewusst konservativ: ein verpasstes Eigen-Angebot
    (wird analysiert) ist harmloser als eine fälschlich blockierte Vergabeunterlage."""
    hits = {m.group(0).lower() for m in _OWN_OFFER.finditer(text or "")}
    return len(hits) >= threshold


def _tok(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{4,}", (s or "").lower())}


def match_lead(doc_meta: dict, lead_meta: dict) -> dict:
    """Abgleich Upload↔Lead über Titel/Vergabestelle/Aktenzeichen/CPV (§5-4).

    Gibt ``{"matched": bool, "mismatches": [...], "score": float}``. ``matched`` = kein harter
    Widerspruch (Aktenzeichen ODER hinreichende Titel-/Käufer-Überschneidung). Rückfrage statt
    stillem Durchlauf verantwortet der Aufruf-Kontext."""
    mism = []
    # Aktenzeichen: harter Anker, wenn beidseitig vorhanden
    az_d = re.sub(r"[^a-z0-9]", "", (doc_meta.get("aktenzeichen") or "").lower())
    az_l = re.sub(r"[^a-z0-9]", "", (lead_meta.get("aktenzeichen") or "").lower())
    if az_d and az_l and az_d != az_l:
        mism.append("aktenzeichen")
    # CPV (erste 4 Stellen = Klasse)
    cpv_d = (doc_meta.get("cpv") or "")[:4]
    cpv_l = (lead_meta.get("cpv") or "")[:4]
    if cpv_d and cpv_l and cpv_d != cpv_l:
        mism.append("cpv")
    # Titel-Überschneidung
    ti, tl = _tok(doc_meta.get("title")), _tok(lead_meta.get("title"))
    title_overlap = len(ti & tl) / max(len(ti | tl), 1) if (ti or tl) else 0.0
    # Käufer-Überschneidung
    bi, bl = _tok(doc_meta.get("buyer")), _tok(lead_meta.get("buyer"))
    buyer_overlap = len(bi & bl) / max(len(bi | bl), 1) if (bi or bl) else 0.0
    az_ok = az_d and az_l and az_d == az_l
    matched = (az_ok or (not mism and (title_overlap >= 0.25 or buyer_overlap >= 0.5)))
    return {"matched": bool(matched), "mismatches": mism,
            "score": round(max(title_overlap, buyer_overlap), 2)}


# Wörter, die in fast jedem Behördennamen stehen und deshalb nichts über die Zuordnung
# sagen. Ohne sie zählte „Stadt" als Treffer und jedes kommunale Dokument passte zu jedem
# kommunalen Lead.
_KAEUFER_STOPP = frozenset({"gmbh", "stadt", "der", "die", "und", "des", "fuer", "für",
                            "amt", "eigenbetrieb", "aoer", "anstalt", "landkreis", "kreis"})
# Ab wann der Zweifel greift: weniger als ein Drittel der aussagekräftigen Käufer-Wörter
# steht im Text. Absichtlich niedrig — Käufernamen weichen zwischen Bekanntmachung und
# Unterlagen oft ab, und ein Fehlalarm bei jedem zweiten Upload wäre schlimmer als keiner.
ZUORDNUNG_SCHWELLE = 0.34


def zuordnung_zweifelhaft(lead_buyer: str, fulltext: str) -> dict | None:
    """Kommt der Auftraggeber des Leads in den Unterlagen überhaupt vor? (§5-4)

    ``None`` heisst „kein Widerspruch", ein Dict heisst „nachfragen". Der Aufruf-Kontext
    entscheidet, was daraus folgt — hier wird nur gemessen.

    ⚠ Das Ergebnis gehört ZU DEN DATEN, nicht in eine Meldung an den Hochladenden. Ein
    Upload landet im geteilten Bestand und wird allen Nutzern dieses Vorgangs ausgeliefert;
    ein Vorbehalt, der nur einmal auf einem Bildschirm steht, ist nach dem Seitenwechsel
    weg, während die Daten bleiben.
    """
    if not lead_buyer or not fulltext:
        return None
    toks = {t for t in re.findall(r"[a-zäöüß]{4,}", lead_buyer.lower())
            if t not in _KAEUFER_STOPP}
    if not toks:
        return None                      # nur Allerweltswörter → keine Aussage möglich
    low = fulltext.lower()
    anteil = sum(1 for t in toks if t in low) / len(toks)
    if anteil >= ZUORDNUNG_SCHWELLE:
        return None
    return {"expected_buyer": lead_buyer, "anteil": round(anteil, 2)}


def scan_malware(name: str, data: bytes) -> bool:
    """Hook (§5-1). Gibt True = sauber zurück; die Produktion verdrahtet hier einen echten
    Scanner (z. B. ClamAV). Bewusst kein selbstgebauter Scanner."""
    return True
