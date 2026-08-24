"""Modellkatalog: was der Markt heute anbietet — täglich festgehalten, täglich verglichen.

**Warum täglich und nicht monatlich.** Preise sind veränderlich. Ein Modell, das gestern
0,30 $ kostete, kann heute 0,15 kosten oder abgekündigt sein; ein neues erscheint ohne
Ankündigung. Wer im Monatstakt schaut, zahlt im Schnitt zwei Wochen lang zu viel — und
erfährt von einer Abkündigung erst, wenn die Aufrufe scheitern.

**Warum es nichts kostet.** Der ganze Katalog kommt in **einem** HTTP-Aufruf
(``/api/v1/models``, 422 Modelle am 2026-08-23). Keine Token, kein Guthaben, keine
Geldwache. Genau deshalb ist die Trennung wichtig, die dieses Modul durchhält:

    billiger Wächter  →  meldet, dass sich etwas Materielles geändert hat
    teurer Test       →  `scripts/llm_bench.py`, nur wenn der Wächter etwas meldet

Ein Benchmark im Tagestakt verbrennt Geld für die Bestätigung, dass alles beim Alten ist.

**Was dieses Modul NICHT tut: urteilen.** Es sagt „dieses Modell ist neu, erfüllt unseren
Bedarf und ist billiger". Ob es *besser* ist, weiß nur der gepaarte Versuch am eigenen
Korpus — Preis ist keine Güte, und ein Katalogeintrag erst recht nicht. Das ist derselbe
Fehler, an dem mazhs „Value Score" scheiterte: TPS je Euro misst Geschwindigkeit, nicht ob
die Antwort stimmt.

⚠ **Der Katalogpreis ist NICHT unser Preis.** ``/api/v1/models`` nennt den Listenpreis
(0,300 für Gemini 2.5 Flash). Was wir zahlen, ist der billigste Endpunkt (0,150 über
`:floor`, s. `docs/modellwahl-und-anbieterboden.md`). Für die beobachteten Modelle holt
:func:`bodenpreis` deshalb die Endpunktliste dazu — ein Vergleich von Listenpreisen gegen
unseren Bodenpreis würde jedes zweite Modell fälschlich als „billiger" melden.

Aufruf::

    from govisor import modellkatalog as mk
    stand = mk.verdichte(mk.hole())
    mk.schreibe(stand)
    befunde = mk.vergleiche(mk.lies_vorherigen(), stand)
"""
from __future__ import annotations

import gzip
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

ROOT = Path(__file__).resolve().parent.parent
ORDNER = Path(os.environ.get("GOVISOR_MODELLKATALOG", ROOT / "data" / "modellkatalog"))

KATALOG_URL = "https://openrouter.ai/api/v1/models"
ENDPUNKT_URL = "https://openrouter.ai/api/v1/models/{slug}/endpoints"

# Unser Bedarf, aus der Aufgabe abgeleitet und nicht geraten:
#
#   Kontext — `scripts/analyze_docs.py` schickt je Doktyp einen Aufruf bis zu einem
#   200k-Token-Deckel. Ein Modell mit weniger Kontext kann die Aufgabe nicht annehmen,
#   egal wie billig es ist. Genau diese Auswahl konnte mazh nicht treffen: dort war
#   `context_window` bei allen 740 Modellen leer.
#
#   Strukturierte Ausgabe — die typisierte Extraktion (Ticket #23) erzwingt ein Schema.
#   Ohne `structured_outputs` faellt das Modell aus, ohne dass man es probieren muesste.
MIN_KONTEXT = int(os.environ.get("GOVISOR_MIN_KONTEXT", "200000"))
BRAUCHT = ("structured_outputs",)

# Ab wann ist eine Preisaenderung eine Meldung wert? 20 % — darunter ist es Rauschen im
# Katalog (Anbieter runden, Endpunkte kommen und gehen), darueber lohnt das Hinsehen.
SCHWELLE = float(os.environ.get("GOVISOR_PREIS_SCHWELLE", "0.20"))


# ── Holen ────────────────────────────────────────────────────────────────────────────

def hole(url: str = KATALOG_URL, timeout: int = 30) -> list[dict]:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json().get("data") or []


def _preis(p: dict, feld: str) -> float:
    """Katalogpreise stehen als Zeichenkette je EINZELNEM Token. Mal 1e6 = je Mio."""
    try:
        return float(p.get(feld) or 0) * 1e6
    except (TypeError, ValueError):
        return 0.0


def verdichte(roh: Iterable[dict]) -> dict[str, dict]:
    """Katalog → schlanker Stand je Modell-ID. Nur was fuer den Vergleich zaehlt."""
    aus: dict[str, dict] = {}
    for m in roh:
        mid = m.get("id")
        if not mid:
            continue
        pr = m.get("pricing") or {}
        aus[mid] = {
            "name": m.get("name") or mid,
            "kontext": int(m.get("context_length") or 0),
            "ein": _preis(pr, "prompt"),
            "aus": _preis(pr, "completion"),
            "params": sorted(m.get("supported_parameters") or []),
            "auslauf": m.get("expiration_date") or None,
            # Erscheinungsdatum: das einzige mechanische Indiz fuer „neuere Generation".
            # Es sagt nichts ueber Guete — aber ein Modell, das aelter ist als unseres,
            # ist als Qualitaetsverbesserung unplausibel genug, um es nicht zu bezahlen.
            "erschienen": int(m.get("created") or 0),
        }
    return aus


def bodenpreis(slug: str, timeout: int = 25) -> dict | None:
    """Der **billigste** Endpunkt eines Modells — das, was wir mit `:floor` zahlen.

    Gibt ``{"ein", "aus", "endpunkt", "haeuser", "endpunkte"}`` oder ``None``.
    """
    try:
        r = requests.get(ENDPUNKT_URL.format(slug=slug), timeout=timeout)
        r.raise_for_status()
        eps = (r.json().get("data") or {}).get("endpoints") or []
    except Exception:                                    # noqa: BLE001
        return None
    tauglich = [e for e in eps if _preis(e.get("pricing") or {}, "prompt") > 0]
    if not tauglich:
        return None
    billig = min(tauglich, key=lambda e: _preis(e["pricing"], "prompt"))
    return {"ein": _preis(billig["pricing"], "prompt"),
            "aus": _preis(billig["pricing"], "completion"),
            "endpunkt": billig.get("tag") or billig.get("provider_name") or "",
            # „Haeuser" = eigenstaendige Anbieter, nicht Regionen/Dienstguete desselben
            # Hauses. Die Zahl sagt, ob es fuer dieses Modell ueberhaupt Wettbewerb gibt:
            # proprietaere Modelle haben 2–4 (Hersteller + seine Wiederverkaeufer),
            # offene Gewichte 8–18.
            "haeuser": len({e.get("provider_name") for e in eps}),
            "endpunkte": len(eps)}


# ── Ablegen ──────────────────────────────────────────────────────────────────────────

def pfad(tag: str | None = None) -> Path:
    return ORDNER / f"{tag or date.today().isoformat()}.json.gz"


def schreibe(stand: dict, tag: str | None = None) -> Path:
    p = pfad(tag)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".gz.teil")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump({"geholt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "modelle": stand}, f, ensure_ascii=False)
    os.replace(tmp, p)
    return p


def lies(tag: str) -> dict | None:
    p = pfad(tag)
    if not p.exists():
        return None
    try:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f).get("modelle") or {}
    except (OSError, json.JSONDecodeError):
        return None


def staende() -> list[str]:
    """Alle vorhandenen Tage, aelteste zuerst."""
    return sorted(p.name[: -len(".json.gz")] for p in ORDNER.glob("*.json.gz"))


def lies_vorherigen(vor: str | None = None) -> tuple[str, dict] | tuple[None, None]:
    """Der juengste Stand VOR ``vor`` (Vorgabe: heute). Fuer den Tagesvergleich."""
    grenze = vor or date.today().isoformat()
    for tag in reversed(staende()):
        if tag < grenze:
            d = lies(tag)
            if d is not None:
                return tag, d
    return None, None


# ── Vergleichen ──────────────────────────────────────────────────────────────────────

def taugt(m: dict) -> bool:
    """Kann dieses Modell unsere Aufgabe ueberhaupt annehmen?"""
    return (m.get("kontext", 0) >= MIN_KONTEXT
            and all(p in (m.get("params") or []) for p in BRAUCHT))


def vergleiche(alt: dict | None, neu: dict, *, nur_taugliche: bool = True,
               schwelle: float = SCHWELLE, beobachtet: Iterable[str] = ()) -> list[dict]:
    """Was hat sich materiell geaendert? Liste von Befunden, wichtigste Art zuerst.

    ``beobachtet`` sind Modelle, die uns immer interessieren (unser eigenes, die
    Bench-Kandidaten) — bei ihnen zaehlt **jede** Aenderung, auch wenn sie unterhalb der
    Schwelle liegt oder das Modell die Tauglichkeitspruefung nicht besteht.
    """
    beobachtet = set(beobachtet)
    befunde: list[dict] = []

    def relevant(mid: str, m: dict) -> bool:
        return mid in beobachtet or not nur_taugliche or taugt(m)

    if alt is None:                                      # erster Lauf: kein Vergleich
        return []

    for mid, m in neu.items():
        if not relevant(mid, m):
            continue
        vor = alt.get(mid)
        if vor is None:
            befunde.append({"art": "neu", "modell": mid, "name": m["name"],
                            "ein": m["ein"], "aus": m["aus"], "kontext": m["kontext"]})
            continue
        for feld, wie in (("ein", "Eingabe"), ("aus", "Ausgabe")):
            a, b = vor.get(feld) or 0, m.get(feld) or 0
            if a <= 0 or b <= 0:
                continue
            d = (b - a) / a
            if abs(d) >= schwelle or (mid in beobachtet and abs(d) > 1e-9):
                befunde.append({"art": "preis_runter" if d < 0 else "preis_rauf",
                                "modell": mid, "name": m["name"], "feld": wie,
                                "von": a, "auf": b, "delta": d})
        if m.get("auslauf") and not vor.get("auslauf"):
            befunde.append({"art": "auslauf", "modell": mid, "name": m["name"],
                            "auslauf": m["auslauf"]})
        if m.get("kontext") != vor.get("kontext"):
            befunde.append({"art": "kontext", "modell": mid, "name": m["name"],
                            "von": vor.get("kontext"), "auf": m.get("kontext")})

    for mid, m in alt.items():
        if mid in neu:
            continue
        # ⚠ Ein verschwundenes Modell ist nur dann eine Meldung, wenn es uns betrifft oder
        # taugte. Der Katalog verliert staendig Randmodelle; jede davon zu melden waere
        # Laerm, und Laerm ist der sichere Weg, dass niemand mehr hinsieht.
        if mid in beobachtet or (nur_taugliche and taugt(m)):
            befunde.append({"art": "weg", "modell": mid, "name": m.get("name") or mid})

    rang = {"weg": 0, "auslauf": 1, "preis_rauf": 2, "preis_runter": 3, "neu": 4,
            "kontext": 5}
    befunde.sort(key=lambda b: (rang.get(b["art"], 9), b["modell"]))
    return befunde


def guenstiger_als(stand: dict, ein: float, aus: float,
                   ausser: Iterable[str] = ()) -> list[tuple[str, dict]]:
    """Taugliche Modelle, die bei BEIDEN Preisen unter der Messlatte liegen.

    Die Messlatte ist unser **Bodenpreis**, nicht unser Listenpreis — sonst meldet die
    Auswertung Modelle als billiger, die es gegen 0,150/1,250 gar nicht sind.
    """
    ausser = set(ausser)
    treffer = [(mid, m) for mid, m in stand.items()
               if mid not in ausser and taugt(m)
               and 0 < m["ein"] <= ein and 0 < m["aus"] <= aus]
    treffer.sort(key=lambda x: x[1]["ein"] + x[1]["aus"])
    return treffer
