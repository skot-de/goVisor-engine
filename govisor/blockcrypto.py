"""Umschlag-Verschluesselung der Bausteine — die Python-Seite.

⚠ **DIES IST EINE ZWEITE FASSUNG EINES FORMATS, DAS SCHON EXISTIERT.** Die erste steht in
`web/lib/blockCrypto.ts`. Eine Aussage an zwei Stellen altert an beiden, und bei einem
Verschluesselungsformat heisst „altert" nicht „ist ungenau", sondern **„Daten sind unlesbar"**.
Deshalb gilt hier eine Bedingung: `tests/test_blockcrypto.py` fuehrt einen echten
Sprachuebergreifenden Rundlauf — Python verschluesselt, **Node entschluesselt mit der echten
TypeScript-Datei**, und umgekehrt. Ohne diesen Test darf dieses Modul nicht benutzt werden; eine
Formataenderung auf einer Seite faellt sonst einem Kunden auf und nicht uns.

**Warum es diese Seite ueberhaupt braucht.** Der Antwort-Arbeiter (`scripts/antwort_arbeiter.py`)
laeuft in Python, muss die Bausteine des Kunden lesen und seine Entwuerfe zurueckschreiben. Die
Alternative waere gewesen, die Bausteine im Klartext in die Auftragszeile zu legen — dann waere
die Verschluesselung in `profile_text_blocks` ein Theater, weil derselbe Inhalt eine Tabelle
weiter offen liegt.

**Aufbau des Chiffrats** (identisch zur TypeScript-Seite, Byte fuer Byte):

    Byte  0        Version (1)
    Byte  1..12    IV des Umschlags
    Byte 13..44    Datenschluessel, mit dem Hauptschluessel verschluesselt
    Byte 45..60    Auth-Tag des Umschlags
    Byte 61..72    IV des Inhalts
    Byte 73..88    Auth-Tag des Inhalts
    ab   89        Chiffrat des Inhalts

Benutzung:

    import os
    os.environ["BLOCKS_KEK"] = "<32 Byte, base64>"      # openssl rand -base64 32
    daten = verschluessele("Referenz Stadtwerke, 2024")
    klar  = entschluessele(daten)
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = 1
_KEK_BYTES = 32
_IV = 12
_TAG = 16
_KOPF = 1 + _IV + 32 + _TAG + _IV + _TAG          # 89


class KeinSchluessel(RuntimeError):
    """`BLOCKS_KEK` fehlt.

    ⚠ Kein stiller Rueckfall auf Klartext. Die Spalte heisst `content_encrypted`; waere dort
    Klartext, wuerde niemand nachsehen. Dieselbe Entscheidung wie auf der TypeScript-Seite.
    """

    def __init__(self) -> None:
        super().__init__("BLOCKS_KEK ist nicht gesetzt, Bausteine werden nicht verarbeitet. "
                         "32 zufaellige Bytes, base64: `openssl rand -base64 32`.")


def hauptschluessel() -> bytes:
    roh = os.environ.get("BLOCKS_KEK", "")
    if not roh:
        raise KeinSchluessel()
    k = base64.b64decode(roh)
    if len(k) != _KEK_BYTES:
        raise ValueError(f"BLOCKS_KEK muss 32 Byte sein (base64), ist {len(k)}.")
    return k


def verschluessele(klartext: str) -> bytes:
    """Verschluesselt einen Text so, dass `web/lib/blockCrypto.ts` ihn lesen kann.

    ⚠ **Die eine Falle dieses Ports:** `AESGCM.encrypt` haengt das Auth-Tag **hinten** an das
    Chiffrat, Node fuehrt es **getrennt** und legt es im Format **vor** den Inhalt. Wer die
    Ausgabe von `AESGCM` einfach durchreicht, erzeugt ein Chiffrat, das Python selbst wieder
    lesen kann (dieselbe Verwechslung in beide Richtungen) und Node nicht. Es faellt also
    **nicht** in einem Python-Rundlauf auf, sondern erst im Produkt.
    """
    kek = hauptschluessel()
    dek = os.urandom(32)
    umschlag_iv = os.urandom(_IV)
    umschlag = AESGCM(kek).encrypt(umschlag_iv, dek, None)
    dek_chiffre, umschlag_tag = umschlag[:-_TAG], umschlag[-_TAG:]

    iv = os.urandom(_IV)
    inhalt_mit_tag = AESGCM(dek).encrypt(iv, klartext.encode("utf-8"), None)
    inhalt, tag = inhalt_mit_tag[:-_TAG], inhalt_mit_tag[-_TAG:]

    return bytes([VERSION]) + umschlag_iv + dek_chiffre + umschlag_tag + iv + tag + inhalt


def entschluessele(daten: bytes) -> str:
    """Liest ein Chiffrat, das von einer der beiden Seiten geschrieben wurde."""
    if len(daten) < _KOPF:
        raise ValueError("Chiffrat zu kurz.")
    if daten[0] != VERSION:
        raise ValueError(f"Unbekannte Fassung {daten[0]}.")
    kek = hauptschluessel()
    dek = AESGCM(kek).decrypt(daten[1:13], daten[13:45] + daten[45:61], None)
    return AESGCM(dek).decrypt(daten[61:73], daten[89:] + daten[73:89], None).decode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Transport nach PostgREST
# ─────────────────────────────────────────────────────────────────────────────────────────────

def zu_hex(b: bytes) -> str:
    r"""`bytea` fuer PostgREST.

    ⚠ **`bytea` reist als Hex-Zeichenkette.** PostgREST liefert `\x48616c6c6f` und erwartet
    dieselbe Form beim Schreiben; rohe Bytes landen als JSON-Objekt `{"0":72,…}` und sind beim
    naechsten Lesen Schrott. Das faellt nicht beim Schreiben auf, sondern beim Entschluesseln —
    dieselbe Warnung steht in `web/app/api/blocks/route.ts`, weil sie dort schon zugeschlagen hat.
    """
    return "\\x" + b.hex()


def aus_hex(s: str) -> bytes:
    return bytes.fromhex(s[2:] if s.startswith("\\x") else s)
