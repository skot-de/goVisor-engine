#!/usr/bin/env python3
"""Jahresdurchschnittskurse der EZB → `data/reference/waehrungskurse.json`.

**Wozu.** Die Schweiz veroeffentlicht in Franken, und die Pipeline hat Fremdwaehrungen bis
zum 2026-09-15 nicht umgerechnet, sondern verworfen: `final_value_clean` fuellte nur bei
`value_currency = 'EUR'`. Gemessen an dem Tag traegt Silber fuer CH bei **52.537 von
123.956** Bekanntmachungen einen Wert — in Gold kamen **76 von 8.400** Leads damit an, also
1 %. Der Parser war nie das Problem.

Was daran haengt, steht in Kapitel 13 der Laender-Bibel: Gebuehren-Band, `value_anchor`,
die Wert-Achse von `market_opportunity`, `region_kpi`, die Strategie-Ansicht. Die Schweiz
sah dadurch aus wie ein kleiner Markt — „2.479 Vertraege, davon 2.477 ohne Wert".

**Quelle: die EZB-Referenzkurse** (`data-api.ecb.europa.eu`, Datensatz `EXR`, Frequenz `A`
= Jahresdurchschnitt). Oeffentlich, ohne Schluessel, ohne Registrierung. Die Reihe nennt
**wie viele Einheiten der Fremdwaehrung ein Euro kostet** — 2015 also 1,0679 CHF je EUR.
Umgerechnet wird deshalb mit `betrag / kurs`, nicht mal.

⚠ **Jahresdurchschnitt, nicht Tageskurs.** Kapitel 13 nennt beide Wege; der Tageskurs waere
fuer eine einzelne Vergabe genauer, der Jahresschnitt fuer Zeitreihen richtig — und die
Zahlen hier gehen in Zeitreihen (Marktgroesse je Jahr, Preisbaender, Regionsvergleich). Ein
Tageskurs wuerde dort Wechselkursrauschen als Marktbewegung ausweisen.

⚠ **Das laufende Jahr hat noch keinen Jahresdurchschnitt.** Der Vorjahreskurs waere dafuer
eine schlechte Naeherung — 2022 bis 2025 hat sich der Franken um 13 % bewegt, und eine
Vergabe von heute mit dem Kurs von vorletztem Jahr umzurechnen ist genau die Sorte stiller
Fehler, die dieses Projekt jagt. Deshalb holt dieses Skript fuer das laufende Jahr die
**Monatsreihe** (`M`) und mittelt die bisher veroeffentlichten Monate: ein *laufender*
Jahresdurchschnitt, der mit jedem Monat genauer wird und am Jahresende gegen den echten
ausgetauscht wird. Welche Jahre so entstanden sind, steht im Block `laufend` der Zieldatei.

⚠ **Und deshalb gehoert der Aufruf in den Tageslauf**, nicht in die Hand. Eine Kursdatei,
die jemand einmal geholt hat, ist genau so lange richtig, wie sich die Welt nicht bewegt.
`daily_leads.sh` ruft das Skript vor dem Gold-Bau; faellt der Abruf aus, bleibt die alte
Datei stehen und der Lauf geht weiter — alte Kurse sind besser als keine.

Aufruf:  python3 scripts/fetch_ezb_kurse.py [--ab 2004] [--waehrungen CHF]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import pathlib
import ssl
import urllib.request
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent
ZIEL = ROOT / "data" / "reference" / "waehrungskurse.json"
BASIS = "https://data-api.ecb.europa.eu/service/data/EXR"
_UA = "goVisor/0.1 (procurement analytics; ECB reference rates)"


def _hole(waehrung: str, ab: int, bis: int) -> dict[int, float]:
    url = (f"{BASIS}/A.{waehrung}.EUR.SP00.A"
           f"?format=csvdata&startPeriod={ab}&endPeriod={bis}")
    # ⚠ Zertifikatsfallback wie in `simap._get` und `atverg._get`: auf dieser Maschine
    # fehlt der Zwischenzertifikat-Speicher, und ein Abrufer, der daran scheitert, sieht
    # aus wie eine geschlossene Quelle.
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:                                                # noqa: BLE001
        ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
        text = r.read().decode("utf-8", "replace")
    aus: dict[int, float] = {}
    for zeile in csv.DictReader(io.StringIO(text)):
        try:
            aus[int(zeile["TIME_PERIOD"])] = float(zeile["OBS_VALUE"])
        except (KeyError, TypeError, ValueError):
            continue
    return aus


def _hole_laufend(waehrung: str, jahr: int) -> tuple[float | None, int]:
    """Laufender Jahresdurchschnitt aus der Monatsreihe. (Mittel, Anzahl Monate).

    ⚠ Ungewichtetes Mittel der bisher veroeffentlichten Monate — nicht das Mittel der
    Tageskurse. Der Unterschied liegt im Promillebereich und die Alternative waere, 250
    Tageswerte je Waehrung zu holen; die EZB veroeffentlicht den echten Jahresdurchschnitt
    ohnehin im Januar, und dann ersetzt er diesen Wert.
    """
    url = (f"{BASIS}/M.{waehrung}.EUR.SP00.A"
           f"?format=csvdata&startPeriod={jahr}-01&endPeriod={jahr}-12")
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:                                                # noqa: BLE001
        ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
        text = r.read().decode("utf-8", "replace")
    werte = []
    for zeile in csv.DictReader(io.StringIO(text)):
        try:
            werte.append(float(zeile["OBS_VALUE"]))
        except (KeyError, TypeError, ValueError):
            continue
    if not werte:
        return None, 0
    return sum(werte) / len(werte), len(werte)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--ab", type=int, default=2004, help="erstes Jahr (Vorgabe 2004)")
    # Gemessen am 15.09.2026 im Silber aller vier Laender: neben EUR kommen CHF (50.350),
    # USD (216), GBP (31), BGN (8), PLN/DKK/ISK (je 1) vor — und AED (11), das die EZB
    # nicht fuehrt und das darum weiter ausfaellt. Die nordischen und mitteleuropaeischen
    # Reihen stehen fuer die naechsten Laender schon bereit.
    p.add_argument("--waehrungen",
                   default="CHF,USD,GBP,DKK,SEK,NOK,PLN,CZK,HUF,RON,BGN,ISK,TRY",
                   help="Komma-Liste; die Reihe heisst <WAEHRUNG> je EUR")
    p.add_argument("--trocken", action="store_true", help="nur zeigen, nichts schreiben")
    a = p.parse_args(argv)

    bis = date.today().year
    kurse: dict[str, dict[str, float]] = {}
    laufend: dict[str, dict[str, int]] = {}
    for w in [x.strip().upper() for x in a.waehrungen.split(",") if x.strip()]:
        # ⚠ EINE FEHLENDE REIHE DARF DEN LAUF NICHT KIPPEN. Die EZB fuehrt nicht jede
        # Waehrung ueber den ganzen Zeitraum (ISK etwa ruht seit 2008), und ein 404 fuer
        # eine Randwaehrung soll nicht die Kurse kosten, die wir wirklich brauchen.
        try:
            reihe = _hole(w, a.ab, bis)
        except Exception as e:                                       # noqa: BLE001
            print(f"  ⚠ {w}: {type(e).__name__} — uebersprungen")
            continue
        if not reihe:
            print(f"  ⚠ {w}: keine Werte — Reihe oder Zeitraum pruefen")
            continue
        kurse[w] = {str(j): round(k, 6) for j, k in sorted(reihe.items())}
        jahre = sorted(reihe)
        print(f"  {w}: {len(reihe)} Jahre, {jahre[0]}–{jahre[-1]} · "
              f"{jahre[0]} {reihe[jahre[0]]:.4f} → {jahre[-1]} {reihe[jahre[-1]]:.4f}")

        # Laufendes Jahr aus der Monatsreihe. ⚠ Nur, wenn der Jahresdurchschnitt wirklich
        # noch fehlt: sobald die EZB ihn im Januar veroeffentlicht, hat er Vorrang vor
        # jedem selbst gemittelten Wert.
        if bis in reihe:
            continue
        try:
            mittel, monate = _hole_laufend(w, bis)
        except Exception as e:                                       # noqa: BLE001
            print(f"     ⚠ {bis}: {type(e).__name__} — laufendes Jahr ohne Kurs")
            continue
        if mittel is None:
            print(f"     ⚠ {bis}: noch kein Monat veroeffentlicht")
            continue
        kurse[w][str(bis)] = round(mittel, 6)
        laufend[w] = {"jahr": bis, "monate": monate}
        vorjahr = reihe.get(bis - 1)
        drift = f" · {100 * (mittel / vorjahr - 1):+.1f} % gegen {bis - 1}" if vorjahr else ""
        print(f"     {bis} laufend: {mittel:.4f} aus {monate} Monat(en){drift}")
    if not kurse:
        return 1
    if a.trocken:
        return 0
    inhalt = {"quelle": "EZB-Referenzkurse (data-api.ecb.europa.eu, EXR, "
                        "Frequenz A; laufendes Jahr gemittelt aus Frequenz M)",
              "bedeutung": "Einheiten der Fremdwaehrung je 1 EUR — umrechnen mit betrag/kurs",
              "geholt_am": date.today().isoformat(),
              # ⚠ Welche Jahreswerte NICHT der amtliche Jahresdurchschnitt sind, sondern
              # ein laufendes Mittel der bisherigen Monate. Wer mit diesen Zahlen rechnet,
              # muss es wissen koennen, ohne den Code zu lesen.
              "laufend": laufend,
              "kurse": kurse}
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    teil = ZIEL.with_suffix(".teil")
    teil.write_text(json.dumps(inhalt, ensure_ascii=False, indent=1), encoding="utf-8")
    teil.replace(ZIEL)
    print(f"→ {ZIEL.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
