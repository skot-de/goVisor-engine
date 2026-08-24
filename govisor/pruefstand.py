"""Prüfstand: neue Modelle bekommen Testaufträge, und nur Bestandene dürfen ran.

Sven, 2026-08-23: *„jedes neue modell bekommt x aufträge als test und wenn es bessere
auswertungen hat, als unser top modell, dann wird gewechselt. für mich steht qualität oben,
aber danach kommt direkt der preis. geschwindigkeit ist nicht wichtig […] sollte mit
gemessen werden."*

Dieses Modul ist diese Regel als Code. Es entscheidet **nicht** nach Bauchgefühl und nicht
nach Katalogpreis, sondern nach gepaarten Messwerten am eigenen Korpus.

---

## Die Rangfolge, in genau dieser Reihenfolge

1. **Verwerfungsriegel (Qualität, hart).** Wirft der Kandidat mehr unbelegte Aussagen als
   der Amtierende, ist er durchgefallen — egal wie billig, egal wie viele Punkte er
   sammelt. Begründung aus unseren eigenen Zahlen vom 2026-08-18: die Modelle, die am
   *wenigsten* fanden, erklärten am *meisten* für grün. Ein Modell, das flüssig behauptet
   und selten belegt, sieht in jeder Punktzahl gut aus und ist trotzdem unbrauchbar.
2. **Signifikant schlechter** (Vorzeichentest) → durchgefallen.
3. **Signifikant besser** → bestanden. *Auch wenn er teurer ist* — Qualität steht oben.
4. **Statistisch gleichwertig** → dann entscheidet der Preis: nur wer spürbar billiger ist,
   löst einen Wechsel aus. Ein Wechsel für 3 % Ersparnis kostet mehr an Risiko und
   Testaufwand, als er bringt.
5. **Geschwindigkeit** wird gemessen und im Urteil ausgewiesen, entscheidet aber nichts.

## Zwei Stufen, damit das Prüfen bezahlbar bleibt

Es gibt 243 taugliche Modelle im Katalog. Jedes mit 15 Vorgängen zu prüfen wäre absurd
teuer. Deshalb:

* **Vorprüfung** (3 Vorgänge) — tötet die offensichtlichen Nieten für rund ein Fünftel des
  Preises. Wer hier katastrophal abfällt, kommt nicht weiter.
* **Hauptprüfung** (15 Vorgänge) — der gepaarte Versuch mit Vorzeichentest.

⚠ **Der Amtierende wird EINMAL gemessen, nicht je Kandidat.** Der Prüfsatz ist fest; die
Grundlinie liegt gespeichert und wird nur erneuert, wenn sie zu alt ist. Das halbiert die
Kosten jedes Vergleichs. Die erste Fassung von `llm_bench.py` fuhr den Amtierenden bei jedem
Lauf mit — richtig gedacht (Pipeline-Änderungen!), aber im Dauerbetrieb doppelt bezahlt.

⚠ **Nicht jeder Kandidat ist eine Prüfung wert.** Ein Modell, das 5 % billiger ist, spart
weniger, als sein Test kostet. Nur wer die Latte `MIN_ERSPARNIS` reißt *oder* neu ist, kommt
in die Warteschlange.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
WARTESCHLANGE = Path(os.environ.get("GOVISOR_PRUEFSTAND",
                                    ROOT / "data" / "pruefstand.json"))

VORPRUEFUNG_N = int(os.environ.get("GOVISOR_VORPRUEFUNG_N", "3"))
HAUPTPRUEFUNG_N = int(os.environ.get("GOVISOR_HAUPTPRUEFUNG_N", "15"))

# Mindestzahl gepaarter Vorgaenge fuer ein Urteil. Darunter ist jeder Unterschied Rauschen:
# bei n=4 braucht es 4:0, um ueberhaupt p<0,13 zu erreichen — ein Ergebnis, das man nicht
# glauben darf. Ab 10 wird p<0,05 mit 9:1 erreichbar.
MIN_N = int(os.environ.get("GOVISOR_MIN_N", "10"))
ALPHA = float(os.environ.get("GOVISOR_ALPHA", "0.05"))

# Verwerfungsriegel: um wie viele PROZENTPUNKTE darf die Verwerfungsquote schlechter sein,
# bevor der Kandidat faellt? 2 Punkte Toleranz fuer Messrauschen, mehr nicht.
VERWERFUNG_TOLERANZ = float(os.environ.get("GOVISOR_VERWERFUNG_TOLERANZ", "0.02"))

# Ab welchem Anteil unlesbarer Antworten ist es ein FORMAT- und kein Qualitaetsproblem?
# 20 %: darunter faengt die eingebaute Wiederholung in `docextract.extract` es ab, darueber
# spricht das Modell schlicht ein anderes Format.
FORMAT_TOLERANZ = float(os.environ.get("GOVISOR_FORMAT_TOLERANZ", "0.20"))

# Ab welcher Ersparnis lohnt ein Wechsel bei gleicher Qualitaet? Und ab welcher lohnt
# ueberhaupt eine Pruefung?
MIN_ERSPARNIS = float(os.environ.get("GOVISOR_MIN_ERSPARNIS", "0.20"))

# Wie lange gilt die Grundlinie des Amtierenden? Danach neu messen — Doktyp-Erkennung,
# Prompts und Dublettenlogik aendern sich, und dann vergleicht man Aepfel mit Aepfeln von
# vorgestern.
GRUNDLINIE_TAGE = int(os.environ.get("GOVISOR_GRUNDLINIE_TAGE", "14"))

# Hoechstens so viele Kandidaten je Tag pruefen — sonst frisst ein Katalogschub mit
# zwanzig neuen Modellen das Tagesbudget auf.
MAX_JE_TAG = int(os.environ.get("GOVISOR_MAX_PRUEFUNGEN", "2"))

STATUS = ("neu", "vorpruefung_bestanden", "bestanden", "durchgefallen", "gleichwertig",
          "formatproblem", "nicht_lieferbar")


# ── Statistik ────────────────────────────────────────────────────────────────────────

def vorzeichentest(gewinne: int, verluste: int) -> float:
    """Zweiseitiger Vorzeichentest; Unentschiedene zaehlen nicht mit."""
    n = gewinne + verluste
    if n == 0:
        return 1.0
    k = min(gewinne, verluste)
    return min(2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n), 1.0)


def kennzahlen(je_vorgang: dict) -> dict:
    """Ein Messreihen-Wörterbuch {vorgang: {...}} → Punkte, Verwerfung, Preis, Dauer."""
    gut = {k: v for k, v in je_vorgang.items() if "punkte" in v}
    if not gut:
        return {"n": 0}
    pkt = sum(v["punkte"] for v in gut.values())
    vw = sum(v.get("verworfen") or 0 for v in gut.values())
    aufrufe = sum(v.get("llm_aufrufe") or 0 for v in gut.values())
    fehler = sum(v.get("formatfehler") or 0 for v in gut.values())
    return {"n": len(gut),
            "formatquote": fehler / aufrufe if aufrufe else 0.0,
            "aufrufe": aufrufe, "formatfehler": fehler,
            "punkte_je": pkt / len(gut),
            "verwerfung": vw / max(pkt + vw, 1),
            "usd_je": sum(v.get("kosten_usd") or 0 for v in gut.values()) / len(gut),
            "sek_je": sum(v.get("sekunden") or 0 for v in gut.values()) / len(gut)}


# ── Das Urteil ───────────────────────────────────────────────────────────────────────

def entscheide(kandidat: dict, amtierend: dict, *, min_n: int | None = None,
               alpha: float | None = None, toleranz: float | None = None,
               min_ersparnis: float | None = None) -> dict:
    """Gepaarte Messreihen → Urteil. Beide Wörterbücher sind {vorgang: {...}}.

    Rückgabe: ``{"status", "grund", "wechseln", plus alle Messwerte}``.

    ⚠ **Die Stellschrauben werden HIER aufgelöst, nicht in der Signatur.** Stünde
    ``min_n: int = MIN_N`` als Vorgabewert, wäre er beim Laden des Moduls eingefroren:
    ein späteres ``pruefstand.MIN_N = 3`` hätte keine Wirkung mehr — auch nicht im Test,
    was genau am 2026-08-24 auffiel. Ein Modul, dessen Regler nach dem Import wirkungslos
    sind, sieht einstellbar aus und ist es nicht.
    """
    min_n = MIN_N if min_n is None else min_n
    alpha = ALPHA if alpha is None else alpha
    toleranz = VERWERFUNG_TOLERANZ if toleranz is None else toleranz
    min_ersparnis = MIN_ERSPARNIS if min_ersparnis is None else min_ersparnis
    paare = [(v["punkte"], amtierend[k]["punkte"]) for k, v in kandidat.items()
             if "punkte" in v and k in amtierend and "punkte" in amtierend[k]]
    kk, ka = kennzahlen(kandidat), kennzahlen(amtierend)
    g = sum(1 for a, b in paare if a > b)
    v = sum(1 for a, b in paare if a < b)
    p = vorzeichentest(g, v)
    ersparnis = (1 - kk.get("usd_je", 0) / ka["usd_je"]) if ka.get("usd_je") else 0.0

    urteil = {"n_paare": len(paare), "gewinne": g, "verluste": v, "p": p,
              "kandidat": kk, "amtierend": ka, "ersparnis": ersparnis,
              # Geschwindigkeit: gemessen, ausgewiesen, NICHT entscheidend.
              "sek_kandidat": kk.get("sek_je"), "sek_amtierend": ka.get("sek_je")}

    if len(paare) < min_n:
        return {**urteil, "status": "neu", "wechseln": False,
                "grund": f"nur {len(paare)} gepaarte Vorgänge, nötig sind {min_n}"}

    # 0. Formatriegel — VOR jedem Qualitätsurteil.
    #
    # ⚠ Ohne ihn wäre die schlimmste Verwechslung dieses Moduls möglich: ein Modell, das
    # unsere Aufgabe beherrscht, aber sein JSON in Prosa wickelt, liefert 0 Punkte UND
    # 0 verworfene Aussagen. Das sieht nach „findet nichts bei perfekter Genauigkeit" aus,
    # fällt über Regel 2 durch und würde als `durchgefallen` NIE WIEDER geprüft. Ein
    # Formatproblem ist aber behebbar (erzwungenes Schema), ein Qualitätsmangel nicht.
    if kk.get("formatquote", 0) > FORMAT_TOLERANZ:
        return {**urteil, "status": "formatproblem", "wechseln": False,
                "grund": (f"{kk['formatfehler']} von {kk['aufrufe']} Antworten waren nicht "
                          f"lesbar ({kk['formatquote']:.0%}) — kein Qualitätsurteil möglich. "
                          f"Das Modell spricht unser JSON-Format nicht; erzwungenes Schema "
                          f"(response_format) wäre der nächste Schritt")}

    # 1. Verwerfungsriegel — steht VOR allem anderen.
    d_vw = kk["verwerfung"] - ka["verwerfung"]
    if d_vw > toleranz:
        return {**urteil, "status": "durchgefallen", "wechseln": False,
                "grund": (f"verwirft {kk['verwerfung']:.0%} statt {ka['verwerfung']:.0%} "
                          f"(+{d_vw * 100:.1f} Punkte) — behauptet mehr, als es belegt")}

    # 2./3. Signifikanz auf den Punkten.
    if p < alpha and v > g:
        return {**urteil, "status": "durchgefallen", "wechseln": False,
                "grund": (f"findet signifikant weniger ({g}:{v} von {len(paare)}, "
                          f"p={p:.3f})")}
    if p < alpha and g > v:
        return {**urteil, "status": "bestanden", "wechseln": True,
                "grund": (f"findet signifikant mehr ({g}:{v} von {len(paare)}, p={p:.3f}) "
                          f"bei gleicher oder besserer Genauigkeit"
                          + (f", dazu {ersparnis:.0%} billiger" if ersparnis > 0 else
                             f" — kostet {-ersparnis:.0%} mehr, Qualität geht vor"))}

    # 4. Gleichwertig → der Preis entscheidet.
    if ersparnis >= min_ersparnis:
        return {**urteil, "status": "bestanden", "wechseln": True,
                "grund": (f"gleichwertig ({g}:{v}, p={p:.3f}) und {ersparnis:.0%} billiger")}
    return {**urteil, "status": "gleichwertig", "wechseln": False,
            "grund": (f"gleichwertig ({g}:{v}, p={p:.3f}), aber nur {ersparnis:.0%} "
                      f"billiger — unter der Latte von {min_ersparnis:.0%}")}


def vorpruefung_bestanden(kandidat: dict, amtierend: dict) -> tuple[bool, str]:
    """Grobfilter nach wenigen Vorgängen: nur offensichtliche Nieten aussortieren.

    ⚠ Bewusst **großzügig**. Bei drei Vorgängen darf man nichts Feines entscheiden; hier
    geht es nur darum, ein Modell auszusortieren, das die Aufgabe erkennbar nicht kann —
    kaum Punkte oder massenhaft unbelegte Behauptungen. Alles Übrige geht weiter.
    """
    kk, ka = kennzahlen(kandidat), kennzahlen(amtierend)
    if not kk.get("n"):
        return False, "keine auswertbaren Vorgänge"
    if kk.get("formatquote", 0) > FORMAT_TOLERANZ:
        return False, (f"{kk['formatfehler']} von {kk['aufrufe']} Antworten unlesbar "
                       f"({kk['formatquote']:.0%}) — Formatproblem, kein Qualitätsurteil")
    if kk["punkte_je"] < 0.5 * ka.get("punkte_je", 0):
        return False, (f"findet nur {kk['punkte_je']:.1f} statt {ka['punkte_je']:.1f} "
                       f"Punkte je Vorgang (unter der Hälfte)")
    if kk["verwerfung"] > ka.get("verwerfung", 0) + 0.15:
        return False, (f"verwirft {kk['verwerfung']:.0%} statt {ka['verwerfung']:.0%} "
                       f"— mehr als 15 Punkte schlechter")
    return True, (f"{kk['punkte_je']:.1f} Punkte, {kk['verwerfung']:.0%} verworfen — "
                  f"geht in die Hauptprüfung")


# ── Warteschlange ────────────────────────────────────────────────────────────────────

def lade() -> dict:
    if WARTESCHLANGE.exists():
        try:
            return json.loads(WARTESCHLANGE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"kandidaten": {}, "grundlinie": {}}


def sichere(stand: dict) -> None:
    WARTESCHLANGE.parent.mkdir(parents=True, exist_ok=True)
    tmp = WARTESCHLANGE.with_suffix(".json.teil")
    tmp.write_text(json.dumps(stand, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(WARTESCHLANGE)


def einreihen(stand: dict, modell: str, *, preis: float, grund: str,
              heute: str | None = None) -> bool:
    """Kandidat aufnehmen. Gibt True, wenn er neu ist oder erneut geprüft werden muss.

    ⚠ Ein einmal durchgefallenes Modell wird **nicht** wieder geprüft, solange sich sein
    Preis nicht materiell geändert hat. Sonst prüft der Prüfstand jede Nacht dieselben
    Nieten und das Testbudget ist weg, bevor ein echter Kandidat drankommt.
    """
    heute = heute or date.today().isoformat()
    vor = stand["kandidaten"].get(modell)
    if vor:
        alt_preis = vor.get("preis") or 0
        billiger = alt_preis > 0 and (alt_preis - preis) / alt_preis >= MIN_ERSPARNIS
        # ⚠ `formatproblem` wird EBENFALLS nicht automatisch wiederholt — es wuerde jede
        # Nacht identisch scheitern und dabei Geld kosten. Es ist aber ausdruecklich KEIN
        # Urteil ueber das Modell, sondern eines ueber unsere Schnittstelle: erst wenn wir
        # das Schema erzwingen (`response_format`), ist eine erneute Pruefung sinnvoll.
        # Wiedervorlage von Hand: den Eintrag aus `data/pruefstand.json` loeschen.
        if vor.get("status") in ("durchgefallen", "gleichwertig", "formatproblem",
                                 "nicht_lieferbar") and not billiger:
            return False
        if vor.get("status") == "bestanden":
            return False
        if billiger:
            vor.update({"preis": preis, "status": "neu", "seit": heute,
                        "grund": f"{grund} (Preis fiel auf {preis:.3f})"})
            return True
        return vor.get("status") in ("neu", "vorpruefung_bestanden")
    stand["kandidaten"][modell] = {"status": "neu", "seit": heute, "preis": preis,
                                   "grund": grund}
    return True


def naechste(stand: dict, hoechstens: int | None = None) -> list[str]:
    """Wer ist als Nächstes dran? Billigste zuerst — dort liegt der größte Gewinn."""
    hoechstens = MAX_JE_TAG if hoechstens is None else hoechstens
    offen = [(v.get("preis") or 9e9, m) for m, v in stand["kandidaten"].items()
             if v.get("status") in ("neu", "vorpruefung_bestanden")]
    offen.sort()
    return [m for _, m in offen[:hoechstens]]


def grundlinie_frisch(stand: dict, heute: str | None = None,
                      tage: int | None = None) -> bool:
    tage = GRUNDLINIE_TAGE if tage is None else tage
    g = stand.get("grundlinie") or {}
    if not g.get("stand") or not g.get("je_vorgang"):
        return False
    try:
        alt = date.fromisoformat(g["stand"])
    except ValueError:
        return False
    return (date.fromisoformat(heute or date.today().isoformat()) - alt).days < tage


# ── Der Messkern ─────────────────────────────────────────────────────────────────────
#
# ⚠ EINE Schleife, die Geld ausgibt — nicht zwei. `scripts/llm_bench.py` (Handbetrieb) und
# `scripts/modellpruefung.py` (Automatik) rufen beide hierher. Zwei Kopien einer bezahlten
# Schleife sind die Stelle, an der Budgetbremse und Zwischenspeicherung auseinanderlaufen,
# ohne dass es jemand merkt — und dann kostet der Unterschied echtes Geld.
#
# Die Abhaengigkeit laeuft per Uebergabe (`analyse`, `llm`), nicht per Import: `analyze_docs`
# ist ein Skript, kein Modul, und ein Paket darf sich nicht auf ein Skript stuetzen.

def _buchstand(kostenbuch) -> int:
    """Byte-Marke im Kostenbuch. ⚠ Nicht die Zeilenzahl — der Analyse-Arbeiter schreibt
    parallel hinein. Nur Anhaengen ist sicher, fremde Zeilen filtert `zweck`."""
    try:
        return kostenbuch.PFAD.stat().st_size
    except OSError:
        return 0


def _kosten_seit(kostenbuch, marke: int, vorgang: str, modell: str,
                 zweck: str) -> tuple[float, int]:
    """⚠ Der `zweck`-Filter ist nicht optional. Der Analyse-Arbeiter schreibt parallel ins
    selbe Buch und koennte dieselbe Vergabe mit demselben Modell buchen; ohne diesen Filter
    wuerde seine Ausgabe dem Test zugerechnet und das Testbudget waere zu frueh leer."""
    grund = kostenbuch.grundmodell(modell)
    summe, fehlt = 0.0, 0
    try:
        with kostenbuch.PFAD.open(encoding="utf-8") as f:
            f.seek(marke)
            for roh in f:
                try:
                    z = json.loads(roh)
                except json.JSONDecodeError:
                    continue
                if (z.get("zweck") != zweck or z.get("vorgang") != vorgang
                        or z.get("modell") != grund):
                    continue
                if z.get("kosten_usd") is None:
                    fehlt += 1
                else:
                    summe += float(z["kosten_usd"])
    except OSError:
        return 0.0, 0
    return summe, fehlt


def messe_reihe(*, analyse, llm, kostenbuch, modell: str, vorgaenge: dict, zweck: str,
                vorhanden: dict | None = None, budget: float | None = None,
                nach_vorgang=None, ausgeben=None) -> tuple[dict, str | None]:
    """Ein Modell durch die Vorgänge. Gibt ``(ergebnisse, abbruchgrund)``.

    ``vorhanden`` sind bereits gemessene Vorgänge (Wiederaufnahme). ``nach_vorgang`` wird
    nach **jedem** Vorgang gerufen — dort gehört das Sichern hin: am 2026-08-23 gingen
    1,27 $ verloren, weil ein Lauf erst am Ende schreiben wollte und vorher starb.
    """
    import time
    ergebnisse = dict(vorhanden or {})
    ausgegeben = sum(v.get("kosten_usd") or 0 for v in ergebnisse.values())
    voll = llm.mit_boden(modell)
    alt_modell = getattr(analyse, "MODEL", None)
    analyse.MODEL = voll
    try:
        for nid, rows in vorgaenge.items():
            if nid in ergebnisse:
                continue
            if budget is not None and ausgegeben >= budget:
                return ergebnisse, f"Testbudget {budget:.2f} $ erreicht"
            marke = _buchstand(kostenbuch)
            t0 = time.time()
            try:
                with llm.kontext(zweck=zweck, vorgang=nid):
                    res = analyse.analyze_notice(
                        rows, structured=analyse.structured_for_notice(nid), notice_id=nid)
            except llm.BudgetErschoepft as e:
                return ergebnisse, f"Geldwache: {e}"
            except Exception as e:                       # noqa: BLE001
                ergebnisse[nid] = {"fehler": type(e).__name__}
                if nach_vorgang:
                    nach_vorgang(ergebnisse)
                if ausgeben:
                    ausgeben(f"      ✖ {nid[:26]}: {type(e).__name__}: {str(e)[:50]}")
                continue
            kosten, ohne_preis = _kosten_seit(kostenbuch, marke, nid, voll, zweck)
            ausgegeben += kosten
            ergebnisse[nid] = {
                "punkte": sum(1 for e in (res.get("checklist") or [])
                              if not e.get("parser") and e.get("marking") == "Zitat"),
                "verworfen": res.get("rejected_items") or 0,
                # Getrennt vom Ergebnis: unlesbare Antworten sind ein Formatproblem,
                # kein Qualitaetsurteil (s. `formatquote`).
                "llm_aufrufe": res.get("llm_aufrufe") or 0,
                "formatfehler": res.get("formatfehler") or 0,
                "kosten_usd": kosten, "ohne_preis": ohne_preis,
                "sekunden": round(time.time() - t0, 1)}
            if nach_vorgang:
                nach_vorgang(ergebnisse)
            if ausgeben:
                e = ergebnisse[nid]
                ausgeben(f"      {nid[:26]:<26} {e['punkte']:>3} Punkte · "
                         f"{kosten:.4f} $ · {e['sekunden']:>5.1f} s")
    finally:
        if alt_modell is not None:
            analyse.MODEL = alt_modell
    return ergebnisse, None
