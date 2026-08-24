"""Kostenbuch: was jeder LLM-Aufruf wirklich gekostet hat — Zeile für Zeile.

**Warum es das gibt.** Bis hierher kannten wir nur den Kontostand: eine Zahl, die fällt.
Woran sie fiel, stand nirgends. Am 2026-08-23 kostete ein Deckel-Test 20,65 $ statt der
gemeldeten 7,59 $, und die Differenz liess sich nur aus dem Kontostand rekonstruieren —
nachträglich, grob, ohne zu wissen, welcher Aufruf der teure war.

OpenRouter liefert die Kosten **je Antwort** mit (``usage.cost``), ohne Zusatzaufruf und
ohne Aufpreis; seit der Umstellung der Nutzungsabrechnung ist das Feld immer dabei. Diese
Zahl festzuhalten kostet also nichts und beantwortet drei Fragen, die sonst offen bleiben:

* **Bringt der Anbieterboden etwas?** ``:floor`` soll den Flex-Endpunkt treffen — halber
  Listenpreis. Ob er ihn wirklich trifft, zeigt nur der abgerechnete Betrag.
* **Was kostet ein belegter Punkt?** Erst Kosten je Modell machen „effizient" messbar.
  Punkte allein sagen nichts über den Preis, Preise nichts über die Güte.
* **Wer hat das Geld ausgegeben?** Getrennt nach Zweck: Produktion, Versuch, Stapel.

**Was hier NICHT steht: die Bremse.** Die sitzt in :func:`govisor.llm._geldwache` und
arbeitet am Kontostand. Dieses Buch schreibt nur mit, es hält nichts an. Beides zu
vermischen wäre ein Fehler: die Bremse muss auch dann greifen, wenn das Mitschreiben
scheitert — und das Mitschreiben darf nie einen Aufruf scheitern lassen.

⚠ **Ein stilles Buch ist schlimmer als keines.** Das Tagesbuch der Geldwache scheiterte
wochenlang lautlos an einem ``except: pass``; der Tagesdeckel war damit wirkungslos, und
niemand konnte es sehen. Hier meldet sich ein Schreibfehler deshalb **einmal laut** auf
stderr und danach nie wieder — laut genug, um aufzufallen, leise genug, um kein Protokoll
zu fluten.

Aufruf::

    from govisor import kostenbuch
    kostenbuch.notiere(anbieter="openrouter", modell="google/gemini-2.5-flash",
                       endpunkt="Google AI Studio", kosten_usd=0.0031)
    for zeile in kostenbuch.lies():
        ...
    kostenbuch.zusammenfassung(("modell", "endpunkt"))
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time as _time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

ROOT = Path(__file__).resolve().parent.parent
PFAD = Path(os.environ.get("GOVISOR_KOSTENBUCH", ROOT / "data" / "llm_kosten.jsonl"))

# Ab hier wird umgehaengt: das Buch waechst mit rund 200 Byte je Aufruf, 32 MB sind gut
# 160.000 Aufrufe.
#
# ⚠ DIE ERSTE FASSUNG HAT DABEI DATEN VERNICHTET, und zwar still. Sie benannte die Datei in
# `.1` um und ueberschrieb damit die vorige `.1`; `lies()` las per Vorgabe nur die aktuelle.
# Gemessen am 2026-08-24 an einem winzigen Deckel: 40 geschriebene Zeilen, 2 lesbar. Von
# 4,00 $ ausgegebenem Geld meldete das Buch danach 0,20 $.
#
# Das war nicht nur Datenverlust. Daran haengen vier Bremsen, und alle vier haetten zu
# WENIG gemeldet und damit zu VIEL erlaubt:
#   · `modellpruefung.heute_ausgegeben()` — der Testtopf-Deckel
#   · `llm._tagesbuch` (Uebernahme) — der Tagesdeckel
#   · `kostenbericht --abgleich` — die Marke haelt eine Summe von vor dem Umhaengen fest,
#     die Differenz wird negativ und meldet einen Fehlalarm
#   · `qualitaetsschranke` — der Etappenvergleich verliert seine Grundlage
#
# Jetzt bekommt jede umgehaengte Generation einen EIGENEN Namen, und `lies()` liest per
# Vorgabe ALLE. Aufgeraeumt wird nach Alter, nicht durch Ueberschreiben.
MAX_MB = float(os.environ.get("GOVISOR_KOSTENBUCH_MB", "32"))
AUFBEWAHREN_TAGE = int(os.environ.get("GOVISOR_KOSTENBUCH_TAGE", "90"))

# Routing-Endungen, die KEIN anderes Modell bezeichnen, sondern nur einen anderen Weg dorthin.
# `:floor` (guenstigster Endpunkt, Flex erlaubt) und `:nitro` (schnellster) liefern dasselbe
# Modell. Sie muessen weg, bevor nach Modell gruppiert wird, sonst zerfaellt die Historie
# eines Modells in zwei Reihen und jeder Vorher-Nachher-Vergleich ist zerschnitten.
#
# ⚠ NICHT `:free` mitstreichen: das IST ein anderes Angebot (eigene Grenzen, eigene Guete).
_WEGE = ("floor", "nitro")

_LOCK = threading.Lock()
_GEMECKERT = False          # Schreibfehler: einmal laut, danach still


def grundmodell(name: str | None) -> str:
    """``"google/gemini-2.5-flash:floor"`` → ``"google/gemini-2.5-flash"``."""
    if not name:
        return ""
    kopf, _, schwanz = name.rpartition(":")
    return kopf if kopf and schwanz in _WEGE else name


def weg(name: str | None) -> str:
    """Die Routing-Endung allein — ``"floor"``, ``"nitro"`` oder ``""``."""
    if not name:
        return ""
    _, _, schwanz = name.rpartition(":")
    return schwanz if schwanz in _WEGE else ""


def _zahl(v: Any) -> float | None:
    """Robuste Zahl. ⚠ Diese Umwandlung MUSS scheitern duerfen, ohne zu werfen.

    Der erste Entwurf rechnete ``float(kosten_usd)`` beim Bauen der Zeile — also ausserhalb
    des Schutzes, der den Schreibvorgang umgibt. Ein unerwarteter Wert aus der Gegenstelle
    (``"0.0031"``, ``None`` an anderer Stelle, ein Feld, das eines Tages ein Objekt wird)
    haette damit einen **erfolgreichen, bezahlten** LLM-Aufruf in eine Ausnahme verwandelt.
    Buchhaltung darf niemals die Ware vernichten, die sie verbucht.
    """
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ganz(v: Any) -> int:
    z = _zahl(v)
    return int(z) if z is not None else 0


def _generationen(p: Path | None = None) -> list[Path]:
    """Alle Generationen des Buchs, aelteste zuerst.

    Die umgehaengten heissen `<stamm>-<zeitstempel>.jsonl` und sortieren dadurch VOR der
    laufenden Datei `<stamm>.jsonl` — `-` (0x2D) kommt vor `.` (0x2E).
    """
    p = p or PFAD
    stamm = p.name[: -len(p.suffix)] if p.suffix else p.name
    if not p.parent.exists():
        return []
    return sorted(q for q in p.parent.glob(f"{stamm}*{p.suffix}") if q.is_file())


def _aufraeumen(p: Path) -> None:
    """Generationen aelter als `AUFBEWAHREN_TAGE` entfernen. Die laufende bleibt immer."""
    if not AUFBEWAHREN_TAGE:
        return
    grenze = _time.time() - AUFBEWAHREN_TAGE * 86400
    for q in _generationen(p):
        if q == p:
            continue
        try:
            if q.stat().st_mtime < grenze:
                q.unlink()
        except OSError:
            pass


def _umhaengen() -> None:
    try:
        if not (PFAD.exists() and PFAD.stat().st_size > MAX_MB * 1024 * 1024):
            return
        stamm = PFAD.name[: -len(PFAD.suffix)] if PFAD.suffix else PFAD.name
        # ⚠ ALLE umgehaengten Namen brauchen DIESELBE Form, sonst stimmt die Reihenfolge
        # nicht. Der erste Entwurf nahm bei einer Kollision `…-<marke>-1`, sonst
        # `…-<marke>` — und `-` (0x2D) sortiert VOR `.` (0x2E), womit die spaetere Datei
        # vor der frueheren stand. Gefunden, weil ein Test die Reihenfolge prueft; ohne
        # ihn haette jede Auswertung „seit Zeitpunkt X" still die falschen Zeilen genommen.
        marke = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        n = 0
        ziel = PFAD.with_name(f"{stamm}-{marke}-{n:03d}{PFAD.suffix}")
        while ziel.exists():                      # mehrfach in derselben Sekunde
            n += 1
            ziel = PFAD.with_name(f"{stamm}-{marke}-{n:03d}{PFAD.suffix}")
        PFAD.replace(ziel)
        _aufraeumen(PFAD)
    except OSError:
        pass


def notiere(*, anbieter: str, modell: str, endpunkt: str | None = None,
            vorgang: str | None = None, zweck: str | None = None,
            eingabe_token: int = 0, ausgabe_token: int = 0, cache_token: int = 0,
            kosten_usd: float | None = None, upstream_usd: float | None = None,
            sekunden: float | None = None, leer: bool = False,
            abgebrochen: bool = False) -> None:
    """Eine Zeile ins Buch. Wirft nie — ein Buchungsfehler darf keinen Aufruf kosten.

    ``modell`` darf die Routing-Endung tragen; sie wird getrennt abgelegt (``weg``), damit
    nach dem Modell gruppiert werden kann, ohne den Weg zu verlieren.
    """
    global _GEMECKERT
    zeile = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "anbieter": anbieter,
        "modell": grundmodell(modell),
        "weg": weg(modell),
        "endpunkt": endpunkt or "",
        "vorgang": vorgang or "",
        "zweck": zweck or "",
        "eingabe_token": _ganz(eingabe_token),
        "ausgabe_token": _ganz(ausgabe_token),
        "cache_token": _ganz(cache_token),
        "kosten_usd": None if _zahl(kosten_usd) is None else round(_zahl(kosten_usd), 8),
        "upstream_usd": None if _zahl(upstream_usd) is None else round(_zahl(upstream_usd), 8),
        "sekunden": None if _zahl(sekunden) is None else round(_zahl(sekunden), 3),
        # 200er ohne verwertbaren Inhalt — bezahlt, aber ohne Ertrag. Getrennt gefuehrt,
        # damit „was hat es gekostet" und „was hat es gebracht" nicht vermischt werden.
        "leer": bool(leer),
        # Frist gerissen: oben abgerechnet, Antwort nie gesehen. Preis unbekannt — die
        # Zeile erklaert die Luecke im Abgleich, statt sie unerklaert zu lassen.
        "abgebrochen": bool(abgebrochen),
    }
    try:
        with _LOCK:
            _umhaengen()
            PFAD.parent.mkdir(parents=True, exist_ok=True)
            with PFAD.open("a", encoding="utf-8") as f:
                f.write(json.dumps(zeile, ensure_ascii=False) + "\n")
    except Exception as e:                                   # noqa: BLE001
        if not _GEMECKERT:
            _GEMECKERT = True
            print(f"⚠ Kostenbuch nicht schreibbar ({PFAD}): {type(e).__name__}: {e}. "
                  f"Die Aufrufe laufen weiter, aber es wird nichts mitgeschrieben.",
                  file=sys.stderr, flush=True)


def lies(pfad: Path | None = None, mit_alt: bool = True) -> Iterator[dict]:
    """Zeilen des Buchs ueber ALLE Generationen, aelteste zuerst.

    ⚠ `mit_alt` steht auf True und bleibt nur aus Ruecksicht auf bestehende Aufrufe
    erhalten. Die erste Fassung las per Vorgabe nur die laufende Datei — elf von dreizehn
    Aufrufstellen benutzten den Schalter nicht, und nach dem ersten Umhaengen meldeten alle
    zu wenig. Eine Vorgabe, die Daten verschweigt, ist die falsche Vorgabe.
    """
    p = pfad or PFAD
    quellen = _generationen(p) if mit_alt else [p]
    for q in quellen:
        if not q.exists():
            continue
        with q.open(encoding="utf-8") as f:
            for roh in f:
                roh = roh.strip()
                if not roh:
                    continue
                try:
                    yield json.loads(roh)
                except json.JSONDecodeError:
                    continue           # abgeschnittene letzte Zeile nach einem Abbruch


def zusammenfassung(schluessel: Iterable[str] = ("modell", "weg", "endpunkt"),
                    zeilen: Iterable[dict] | None = None) -> dict[tuple, dict[str, Any]]:
    """Gruppiert das Buch und rechnet je Gruppe zusammen.

    Rueckgabe je Gruppe: ``n``, ``kosten_usd``, ``eingabe_token``, ``ausgabe_token``,
    ``cache_token``, ``sekunden``, ``je_aufruf`` und ``usd_je_mio_token``.
    """
    schluessel = tuple(schluessel)
    aus: dict[tuple, dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "kosten_usd": 0.0, "eingabe_token": 0, "ausgabe_token": 0,
                 "cache_token": 0, "sekunden": 0.0, "ohne_kosten": 0})
    for z in (zeilen if zeilen is not None else lies()):
        g = aus[tuple(z.get(k) or "" for k in schluessel)]
        g["n"] += 1
        if z.get("kosten_usd") is None:
            g["ohne_kosten"] += 1
        else:
            g["kosten_usd"] += _zahl(z["kosten_usd"]) or 0.0
        for feld in ("eingabe_token", "ausgabe_token", "cache_token"):
            g[feld] += _ganz(z.get(feld))
        g["sekunden"] += _zahl(z.get("sekunden")) or 0.0
    for g in aus.values():
        g["je_aufruf"] = g["kosten_usd"] / g["n"] if g["n"] else 0.0
        mio = (g["eingabe_token"] + g["ausgabe_token"]) / 1e6
        g["usd_je_mio_token"] = g["kosten_usd"] / mio if mio else 0.0
    return dict(aus)
