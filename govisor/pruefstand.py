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

# Wie viel langsamer als der Amtierende darf ein Kandidat je Vorgang sein, bevor der Test
# abgebrochen wird?
#
# ⚠ Das ist KEIN Qualitaetsurteil und widerspricht auch nicht „Geschwindigkeit entscheidet
# nicht". Es gibt einen Unterschied zwischen *langsamer* und *nicht benutzbar*: gemessen am
# 2026-08-24 brauchte `nex-agi/nex-n2-mini` 760 s fuer einen einzigen Aufruf (Amtierender:
# 2,6 s im Median). Bei 7.241 wartenden Vergaben ist so ein Modell nicht „etwas langsamer",
# es kann die Aufgabe grundsaetzlich nicht erledigen — und blockiert bis dahin den
# naechtlichen Lauf.
#
# ⚠ Und der `timeout` in `requests` hilft hier NICHT: er misst die Pause zwischen Bytes,
# nicht die Gesamtdauer. Der 760-Sekunden-Aufruf lief mit `timeout=120` durch.
ZEIT_FAKTOR = float(os.environ.get("GOVISOR_ZEIT_FAKTOR", "4"))
ZEIT_MINDEST = float(os.environ.get("GOVISOR_ZEIT_MINDEST", "180"))

# Harte Frist je EINZELAUFRUF fuer einen Kandidaten. Der Amtierende braucht ueber 311
# Aufrufe im Maximum 185 s; 240 s laesst also alles Legitime durch und stoppt den Haenger
# nach vier Minuten statt nach dreizehn. Die Vorgangs-Grenze (ZEIT_FAKTOR) bleibt daneben
# bestehen — sie faengt das langsame Modell, diese hier den haengenden Aufruf.
KANDIDAT_FRIST = float(os.environ.get("GOVISOR_KANDIDAT_FRIST", "240"))

# Ab welcher Ersparnis lohnt ein Wechsel bei gleicher Qualitaet? Und ab welcher lohnt
# ueberhaupt eine Pruefung?
MIN_ERSPARNIS = float(os.environ.get("GOVISOR_MIN_ERSPARNIS", "0.20"))

# ── DIE AUSNAHME „EKLATANT BILLIGER" ─────────────────────────────────────────────────
#
# Sven, 2026-08-24: „eig ist qualitaet zuerst, dann die kosten, es sei denn es ist ein
# eklatanter unterschied bei den kosten."
#
# Damit darf ein Kandidat auch dann gewinnen, wenn er etwas WENIGER findet — aber nur,
# wenn der Preisunterschied dramatisch ist UND der Qualitaetsverlust klein bleibt. Beide
# Bedingungen zusammen, sonst waere es die Hintertuer, durch die jedes billige Modell
# hereinkommt.
#
# EKLATANT: hoechstens ein Zehntel unserer Kosten. Nicht „deutlich billiger" (dafuer gibt
# es MIN_ERSPARNIS bei gleicher Qualitaet), sondern eine andere Groessenordnung.
#
# QUALITAETSBODEN: mindestens 90 % der belegten Punkte des Amtierenden. Zum Vergleich der
# reale Fall vom 2026-08-24: `upstage/solar-pro4` kostete 10 % und fand 44 % — das ist kein
# Kompromiss, das ist ein halbes Produkt. Er faellt weiterhin durch.
#
# ⚠ Der Verwerfungsriegel kennt diese Ausnahme NICHT. Ungenauigkeit ist kein Preisthema:
# ein Modell, das mehr behauptet als es belegt, ist zu keinem Preis brauchbar.
EKLATANT = float(os.environ.get("GOVISOR_EKLATANT", "0.10"))
QUALITAETSBODEN = float(os.environ.get("GOVISOR_QUALITAETSBODEN", "0.90"))

# Wie lange gilt die Grundlinie des Amtierenden? Danach neu messen — Doktyp-Erkennung,
# Prompts und Dublettenlogik aendern sich, und dann vergleicht man Aepfel mit Aepfeln von
# vorgestern.
GRUNDLINIE_TAGE = int(os.environ.get("GOVISOR_GRUNDLINIE_TAGE", "14"))

# Hoechstens so viele Kandidaten je Tag pruefen — sonst frisst ein Katalogschub mit
# zwanzig neuen Modellen das Tagesbudget auf.
MAX_JE_TAG = int(os.environ.get("GOVISOR_MAX_PRUEFUNGEN", "2"))

STATUS = ("neu", "vorpruefung_bestanden", "bestanden", "durchgefallen", "gleichwertig",
          "formatproblem", "nicht_lieferbar", "zu_langsam")


# ── Statistik ────────────────────────────────────────────────────────────────────────

def vorzeichentest(gewinne: int, verluste: int) -> float:
    """Zweiseitiger Vorzeichentest; Unentschiedene zaehlen nicht mit."""
    n = gewinne + verluste
    if n == 0:
        return 1.0
    k = min(gewinne, verluste)
    return min(2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n), 1.0)


def fristquote(je_vorgang: dict) -> tuple[float, int, int]:
    """(Anteil, Fristfaelle, Gesamtzahl) der Vorgaenge, die an der ZEITFRIST scheiterten.

    ⚠ Diese Unterscheidung entscheidet, ob ein Urteil ueberhaupt zulaessig ist. Am
    2026-08-24 fielen bei `nex-agi/nex-n2-mini` zwei von drei Vorgaengen in die Frist; der
    dritte ergab null Punkte — dort hatte aber auch der Amtierende null. Es lag also
    **kein einziger** verwertbarer Vergleich vor, und trotzdem lautete das Urteil
    „durchgefallen: findet nur 0,0 statt 25,0 Punkte". Ein Qualitaetsurteil ueber Antworten,
    die nie angekommen sind.
    """
    if not je_vorgang:
        return 0.0, 0, 0
    treffer = sum(1 for v in je_vorgang.values()
                  if "Frist" in (v.get("grund") or ""))
    return treffer / len(je_vorgang), treffer, len(je_vorgang)


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
    # ⚠ ALLES VERGLEICHENDE MUSS AUF DENSELBEN VORGAENGEN RECHNEN.
    #
    # Die erste Fassung verglich die QUALITAET gepaart (nur gemeinsame Vorgaenge), die
    # KOSTEN aber ueber alle gemessenen je Seite. Ein Kandidat, der genau an den grossen,
    # teuren Vergaben scheitert und die kleinen schafft, sieht dadurch dramatisch billiger
    # aus, als er ist. Nachgerechnet am 2026-08-24: gemeldet wurden **84 % Ersparnis**, auf
    # denselben Vorgaengen waren es **10 %** — achtfach ueberhoeht.
    #
    # Das ist kein kosmetischer Fehler: `ersparnis` traegt die Regel „gleichwertig und
    # billiger" UND die Ausnahme „eklatant billiger". Ein Kandidat mit einer Luecke bei den
    # teuren Vergaben haette so uebernommen werden koennen.
    gemeinsam = {k for k, v in kandidat.items()
                 if "punkte" in v and k in amtierend and "punkte" in amtierend[k]}
    paare = [(kandidat[k]["punkte"], amtierend[k]["punkte"]) for k in sorted(gemeinsam)]
    kk = kennzahlen({k: v for k, v in kandidat.items() if k in gemeinsam})
    ka = kennzahlen({k: v for k, v in amtierend.items() if k in gemeinsam})
    # Wie viel wurde ueberhaupt gemessen — fuer den Bericht, nicht fuer das Urteil.
    kk["n_gemessen"] = kennzahlen(kandidat).get("n", 0)
    ka["n_gemessen"] = kennzahlen(amtierend).get("n", 0)
    g = sum(1 for a, b in paare if a > b)
    v = sum(1 for a, b in paare if a < b)
    p = vorzeichentest(g, v)
    ersparnis = (1 - kk.get("usd_je", 0) / ka["usd_je"]) if ka.get("usd_je") else 0.0

    urteil = {"n_paare": len(paare), "gewinne": g, "verluste": v, "p": p,
              "kandidat": kk, "amtierend": ka, "ersparnis": ersparnis,
              # Geschwindigkeit: gemessen, ausgewiesen, NICHT entscheidend.
              "sek_kandidat": kk.get("sek_je"), "sek_amtierend": ka.get("sek_je")}

    # 0a. Fristriegel — GANZ ZUERST, noch vor der Mindestmenge.
    #
    # ⚠ Die Reihenfolge ist hier entscheidend und war zuerst falsch. Ein Kandidat, der in
    # die Frist laeuft, hat zwangslaeufig zu wenige gepaarte Vorgaenge — die
    # Mindestmengenpruefung haette also immer zuerst gegriffen und „nur 1 gepaarter
    # Vorgang" gemeldet. Das ist zwar wahr, aber es verschweigt den Grund und laesst den
    # Kandidaten als `neu` in der Schlange, wo er morgen wieder Zeit verbrennt.
    q, treffer, ges = fristquote(kandidat)
    if q >= 0.5:
        return {**urteil, "status": "zu_langsam", "wechseln": False,
                "grund": (f"{treffer} von {ges} Vorgängen rissen die Zeitfrist "
                          f"({KANDIDAT_FRIST:.0f} s je Aufruf) — kein Qualitätsurteil "
                          f"möglich, die Antworten kamen nie an")}

    if len(paare) < min_n:
        return {**urteil, "status": "neu", "wechseln": False,
                "grund": f"nur {len(paare)} gepaarte Vorgänge, nötig sind {min_n}"}

    # 0b. Formatriegel — VOR jedem Qualitätsurteil.
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
        # Die Ausnahme: eklatant billiger UND nur knapp schwaecher.
        anteil = kk["punkte_je"] / ka["punkte_je"] if ka.get("punkte_je") else 0.0
        kosten_anteil = kk["usd_je"] / ka["usd_je"] if ka.get("usd_je") else 1.0
        if anteil >= QUALITAETSBODEN and kosten_anteil <= EKLATANT:
            return {**urteil, "status": "bestanden", "wechseln": True,
                    "grund": (f"findet zwar etwas weniger ({g}:{v}, p={p:.3f}), aber "
                              f"{anteil:.0%} der Punkte bei {kosten_anteil:.0%} der Kosten "
                              f"— eklatanter Preisunterschied, Qualitätsverlust unter "
                              f"{1 - QUALITAETSBODEN:.0%}")}
        return {**urteil, "status": "durchgefallen", "wechseln": False,
                "grund": (f"findet signifikant weniger ({g}:{v} von {len(paare)}, "
                          f"p={p:.3f}"
                          + (f"; {anteil:.0%} der Punkte bei {kosten_anteil:.0%} der "
                             f"Kosten — für die Ausnahme müssten es ≥ "
                             f"{QUALITAETSBODEN:.0%} bei ≤ {EKLATANT:.0%} sein"
                             if anteil and kosten_anteil <= EKLATANT else "") + ")")}
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
    q, treffer, ges = fristquote(kandidat)
    if q >= 0.5:
        return False, (f"{treffer} von {ges} Vorgängen rissen die Zeitfrist — "
                       f"zu langsam, kein Qualitätsurteil")
    if not kk.get("n"):
        return False, "keine auswertbaren Vorgänge"
    if kk.get("formatquote", 0) > FORMAT_TOLERANZ:
        return False, (f"{kk['formatfehler']} von {kk['aufrufe']} Antworten unlesbar "
                       f"({kk['formatquote']:.0%}) — Formatproblem, kein Qualitätsurteil")
    # ⚠ Der Grobfilter muss GROBER sein als die Ausnahme, sonst wirft er einen eklatant
    # billigen Kandidaten weg, bevor die Hauptpruefung ihn ueberhaupt beurteilen darf.
    # Bei drei Vorgaengen schwanken die Punkte stark; die Huerde liegt deshalb bei der
    # Haelfte und nicht beim Qualitaetsboden von 90 %.
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
              heute: str | None = None, spur: str = "preis") -> bool:
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
                                 "nicht_lieferbar", "zu_langsam") and not billiger:
            return False
        if vor.get("status") == "bestanden":
            return False
        if billiger:
            vor.update({"preis": preis, "status": "neu", "seit": heute,
                        "grund": f"{grund} (Preis fiel auf {preis:.3f})"})
            return True
        return vor.get("status") in ("neu", "vorpruefung_bestanden")
    stand["kandidaten"][modell] = {"status": "neu", "seit": heute, "preis": preis,
                                   "grund": grund, "spur": spur}
    return True


def naechste(stand: dict, hoechstens: int | None = None) -> list[str]:
    """Wer ist als Nächstes dran? **Abwechselnd** aus beiden Spuren.

    ⚠ Die erste Fassung nahm stur die billigsten zuerst. Das klang vernünftig („dort liegt
    der größte Gewinn") und war die schlechteste mögliche Reihenfolge: die billigsten
    Modelle sind die kleinsten und fallen am ehesten durch. Gemessen am 2026-08-24 waren
    die ersten drei Kandidaten ein nicht lieferbares, ein hoffnungslos langsames und eines
    mit 44 % der Punkte — drei Abende für nichts.

    Seit Sven klargestellt hat, dass **Qualität zuerst** kommt, gibt es zwei Spuren:

    * ``preis``     — billiger als wir, sortiert nach Preis (der günstigste zuerst)
    * ``qualitaet`` — teurer, aber neuer als unser Modell; sortiert nach Preis (der
                      günstigste zuerst, denn dort ist der Aufpreis am leichtesten zu
                      rechtfertigen)

    Abwechselnd, damit keine Spur verhungert. Ohne das würde die Preisspur die
    Qualitätsspur monatelang blockieren — 39 gegen 35 Kandidaten.
    """
    hoechstens = MAX_JE_TAG if hoechstens is None else hoechstens
    offen = [(v.get("preis") or 9e9, v.get("spur") or "preis", m)
             for m, v in stand["kandidaten"].items()
             if v.get("status") in ("neu", "vorpruefung_bestanden")]
    spuren = {"preis": sorted(x for x in offen if x[1] == "preis"),
              "qualitaet": sorted(x for x in offen if x[1] == "qualitaet")}
    aus: list[str] = []
    while len(aus) < hoechstens and any(spuren.values()):
        for name in ("qualitaet", "preis"):        # Qualität zuerst, s. Svens Rangfolge
            if spuren[name] and len(aus) < hoechstens:
                aus.append(spuren[name].pop(0)[2])
    return aus


def grundlinie_aktuell(stand: dict, heute: str | None = None,
                       tage: int | None = None) -> bool:
    """Ist die Grundlinie jung genug? Sagt NICHTS ueber ihre Vollstaendigkeit."""
    tage = GRUNDLINIE_TAGE if tage is None else tage
    g = stand.get("grundlinie") or {}
    if not g.get("stand") or not g.get("je_vorgang"):
        return False
    try:
        alt = date.fromisoformat(g["stand"])
    except ValueError:
        return False
    return (date.fromisoformat(heute or date.today().isoformat()) - alt).days < tage


def grundlinie_frisch(stand: dict, heute: str | None = None, tage: int | None = None,
                      vorgaenge: dict | None = None) -> bool:
    """Ist die Grundlinie brauchbar — jung genug UND ueber den ganzen Pruefsatz?

    ⚠ **Die zweite Bedingung fehlte, und das war teuer gedacht.** Die erste Fassung
    prueffte nur das Datum und ob ueberhaupt etwas dasteht. Eine nach drei von fuenfzehn
    Vergaben abgebrochene Grundlinie galt damit als frisch — jeder Kandidat waere gegen
    drei Paare verglichen worden, die Mindestmenge (MIN_N) haette das Urteil verweigert,
    und der Kandidat waere als `neu` in der Schlange geblieben. Jede Nacht wieder, ohne
    dass jemals ein Urteil zustande kaeme.
    """
    if not grundlinie_aktuell(stand, heute, tage):
        return False
    if vorgaenge is None:
        return True
    gemessen = set((stand.get("grundlinie") or {}).get("je_vorgang") or {})
    return set(vorgaenge) <= gemessen


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


def zeitgrenze(vergleich: dict | None, nid: str) -> float | None:
    """Wie lange darf ein Kandidat für diesen Vorgang höchstens brauchen?

    ``None`` **oder 0** heisst: keine Grenze. Ohne Grundlinie als Maßstab wird nicht
    geraten — eine erfundene Zeitgrenze waere schlimmer als keine.
    """
    if not vergleich or nid not in vergleich:
        return None
    s = (vergleich[nid] or {}).get("sekunden")
    return max(ZEIT_MINDEST, float(s) * ZEIT_FAKTOR) if s else None


def messe_reihe(*, analyse, llm, kostenbuch, modell: str, vorgaenge: dict, zweck: str,
                vorhanden: dict | None = None, budget: float | None = None,
                nach_vorgang=None, ausgeben=None,
                vergleich: dict | None = None) -> tuple[dict, str | None]:
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
                # Eine Frist gilt nur fuer KANDIDATEN — erkennbar daran, dass eine
                # Grundlinie zum Vergleich vorliegt. Die Grundlinie selbst wird ohne
                # Sonderfrist gemessen, sonst verzerrte die Bremse den Massstab.
                with llm.kontext(zweck=zweck, vorgang=nid), \
                        llm.frist(KANDIDAT_FRIST if vergleich else None):
                    res = analyse.analyze_notice(
                        rows, structured=analyse.structured_for_notice(nid), notice_id=nid)
            except llm.BudgetErschoepft as e:
                return ergebnisse, f"Geldwache: {e}"
            except Exception as e:                       # noqa: BLE001
                # ⚠ Der Ausnahmetyp allein genuegt nicht. „AllKeysExhausted" entsteht
                # sowohl bei einem echten Anbieterproblem als auch dann, wenn unsere
                # eigene Frist gerissen ist — und das ist ein Unterschied ums Ganze.
                ergebnisse[nid] = {"fehler": type(e).__name__, "grund": str(e)[:200]}
                if nach_vorgang:
                    nach_vorgang(ergebnisse)
                if ausgeben:
                    ausgeben(f"      ✖ {nid[:26]}: {type(e).__name__}: {str(e)[:50]}")
                continue
            dauer = time.time() - t0
            kosten, ohne_preis = _kosten_seit(kostenbuch, marke, nid, voll, zweck)
            ausgegeben += kosten
            # Abbruch NACH dem Vorgang: ein laufender Aufruf laesst sich aus demselben
            # Faden nicht unterbrechen, also wird der Schaden auf EINEN Vorgang begrenzt.
            grenze = zeitgrenze(vergleich, nid)
            if grenze and dauer > grenze:
                ergebnisse[nid] = {"punkte": sum(
                    1 for e in (res.get("checklist") or [])
                    if not e.get("parser") and e.get("marking") == "Zitat"),
                    "verworfen": res.get("rejected_items") or 0,
                    "llm_aufrufe": res.get("llm_aufrufe") or 0,
                    "formatfehler": res.get("formatfehler") or 0,
                    "kosten_usd": kosten, "ohne_preis": ohne_preis,
                    "sekunden": round(dauer, 1)}
                if nach_vorgang:
                    nach_vorgang(ergebnisse)
                return ergebnisse, (
                    f"zu langsam: {dauer:.0f} s für {nid}, erlaubt waren {grenze:.0f} s "
                    f"({ZEIT_FAKTOR:.0f}× der Amtierende). Kein Qualitätsurteil — das "
                    f"Modell kann die Aufgabe zeitlich nicht erledigen")
            ergebnisse[nid] = {
                "punkte": sum(1 for e in (res.get("checklist") or [])
                              if not e.get("parser") and e.get("marking") == "Zitat"),
                "verworfen": res.get("rejected_items") or 0,
                # Getrennt vom Ergebnis: unlesbare Antworten sind ein Formatproblem,
                # kein Qualitaetsurteil (s. `formatquote`).
                "llm_aufrufe": res.get("llm_aufrufe") or 0,
                "formatfehler": res.get("formatfehler") or 0,
                "kosten_usd": kosten, "ohne_preis": ohne_preis,
                "sekunden": round(dauer, 1)}
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
