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
import time
import urllib.error
import urllib.request
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent
ZIEL = ROOT / "data" / "reference" / "waehrungskurse.json"
BASIS = "https://data-api.ecb.europa.eu/service/data/EXR"
_UA = "goVisor/0.1 (procurement analytics; ECB reference rates)"


# ⚠ **DER ENDPUNKT FLACKERT.** Gemessen am 2026-10-05: der Nachtlauf um 01:13 bekam fuer
# `M.CHF` einen 504 und fuer `A.RON` einen Fehler, waehrend zehn andere Reihen durchkamen;
# dieselben zwei Reihen antworteten am Vormittag sechsmal von sechs mit 200. Der Ausfall war
# ein Zeitfenster, der Schaden dauerhaft: ohne Wiederholung wurde aus einem voruebergehenden
# 504 eine **fehlende Zahl in der Datei**, und zwar lautlos — das Skript lief mit Exit 0
# durch, der Tageslauf meldete nichts, und `value_eur` rechnete fuer die Schweiz ab sofort
# mit dem Vorjahreskurs.
WIEDERHOLBAR = {500, 502, 503, 504, 408, 429}
VERSUCHE = 3
PAUSE_S = (2, 5)
# ⚠ **ZWEI DECKEL, UND BEIDE SIND NOETIG.** Ein hoeherer Zeitdeckel je Anfrage und vier
# Versuche ergeben zusammen 26 Reihen x 4 x 90 s — ueber zwei Stunden fuer einen Schritt, der
# sonst Sekunden braucht. Beim ersten Probelauf nach dem Umbau hing genau das: fuenf Minuten
# ohne eine Zeile Ausgabe. Deshalb ein **Gesamtdeckel** ueber den ganzen Lauf: ist er
# aufgebraucht, wird nicht mehr wiederholt, die restlichen Reihen fallen ins Lueckenbuch, und
# die Uebernahme aus der alten Datei faengt sie auf. Lieber eine geflickte Datei in vier
# Minuten als eine vollstaendige nach zwei Stunden — der Tageslauf hat beides nicht uebrig.
# ⚠ 20 s sind grosszuegig, nicht knapp: eine gesunde Reihe antwortet in **0,1 bis 0,5 s**
# (gemessen 2026-10-05 ueber acht Abrufe). Der Deckel bremst keinen gesunden Abruf, er
# begrenzt nur, was eine kranke Reihe kosten darf — und kranke Reihen gibt es: `A.ISK` und
# `A.BGN` lieferten an diesem Tag beide reproduzierbar nach genau 30 s einen 504, waehrend
# ihre Monatsreihen in 0,2 s antworteten.
ZEIT_JE_ANFRAGE_S = 20
GESAMTDECKEL_S = 240
_begonnen = time.monotonic()


def _rest() -> float:
    """Wie viel vom Gesamtdeckel noch uebrig ist."""
    return GESAMTDECKEL_S - (time.monotonic() - _begonnen)


def _ctx() -> "ssl.SSLContext":
    """⚠ Zertifikatsfallback wie in `simap._get` und `atverg._get`: auf dieser Maschine fehlt
    der Zwischenzertifikat-Speicher, und ein Abrufer, der daran scheitert, sieht aus wie eine
    geschlossene Quelle."""
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:                                                # noqa: BLE001
        ctx = ssl._create_unverified_context()
    return ctx


def _lies(url: str) -> str:
    """Holt eine Reihe und wiederholt bei voruebergehenden Fehlern.

    ⚠ Ein **404 wird NICHT wiederholt**: die Reihe gibt es dann wirklich nicht (BGN fuehrt
    seit dem Euro-Beitritt keinen Kurs mehr), und viermal nachzufragen kostet nur Zeit.
    """
    letzter: Exception | None = None
    for versuch in range(VERSUCHE):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=ZEIT_JE_ANFRAGE_S, context=_ctx()) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            letzter = e
            if e.code not in WIEDERHOLBAR:
                raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            letzter = e
        # ⚠ JEDE Wiederholung wird gesagt. Ohne das dauert der Schritt im Protokoll ohne
        # sichtbaren Grund vier Minuten statt acht Sekunden, und am Ende steht trotzdem
        # „ok" — ein Lauf, der sich muehsam durchbeisst, sieht dann aus wie ein glatter.
        print(f"     ⟳ {url.rsplit('/', 1)[-1].split('?')[0]}: "
              f"{type(letzter).__name__}{getattr(letzter, 'code', '')}, "
              f"Versuch {versuch + 1}/{VERSUCHE}")
        pause = PAUSE_S[min(versuch, len(PAUSE_S) - 1)]
        # Nicht mehr wiederholen, wenn der naechste Versuch den Gesamtdeckel reissen wuerde.
        if versuch >= VERSUCHE - 1 or _rest() < pause + ZEIT_JE_ANFRAGE_S:
            break
        time.sleep(pause)
    raise letzter if letzter else RuntimeError("Abruf ohne Ergebnis")


def _werte(text: str) -> list[tuple[str, float]]:
    aus = []
    for zeile in csv.DictReader(io.StringIO(text)):
        try:
            aus.append((zeile["TIME_PERIOD"], float(zeile["OBS_VALUE"])))
        except (KeyError, TypeError, ValueError):
            continue
    return aus


def _hole(waehrung: str, ab: int, bis: int) -> dict[int, float]:
    text = _lies(f"{BASIS}/A.{waehrung}.EUR.SP00.A"
                 f"?format=csvdata&startPeriod={ab}&endPeriod={bis}")
    aus: dict[int, float] = {}
    for zeit, wert in _werte(text):
        try:
            aus[int(zeit)] = wert
        except ValueError:
            continue
    return aus


def _hole_laufend(waehrung: str, jahr: int) -> tuple[float | None, int]:
    """Laufender Jahresdurchschnitt aus der Monatsreihe. (Mittel, Anzahl Monate).

    ⚠ Ungewichtetes Mittel der bisher veroeffentlichten Monate — nicht das Mittel der
    Tageskurse. Der Unterschied liegt im Promillebereich und die Alternative waere, 250
    Tageswerte je Waehrung zu holen; die EZB veroeffentlicht den echten Jahresdurchschnitt
    ohnehin im Januar, und dann ersetzt er diesen Wert.
    """
    text = _lies(f"{BASIS}/M.{waehrung}.EUR.SP00.A"
                 f"?format=csvdata&startPeriod={jahr}-01&endPeriod={jahr}-12")
    werte = [w for _, w in _werte(text)]
    if not werte:
        return None, 0
    return sum(werte) / len(werte), len(werte)


def _bestand() -> dict[str, dict[str, float]]:
    """Die Kurse aus der Datei, die schon da liegt. Leer, wenn es keine gibt."""
    try:
        return json.loads(ZIEL.read_text(encoding="utf-8")).get("kurse", {}) or {}
    except Exception:                                                # noqa: BLE001
        return {}


def _uebernimm(neu: dict[str, dict[str, float]], alt: dict[str, dict[str, float]],
               gefragt: set[str]) -> dict[str, list[str]]:
    """Traegt jeden Wert nach, den die alte Datei hatte und die neue nicht.

    ⚠ **DAS IST DER EIGENTLICHE SCHUTZ, nicht die Wiederholung.** Dieses Skript schreibt die
    Zieldatei GANZ neu. Faellt eine Reihe aus, war die neue Datei bisher schlechter als die
    alte, und zwar ohne Fehlermeldung: am 2026-10-05 fehlte CHF der laufende Jahreskurs und
    RON die ganze Reihe, in einer Datei mit `geholt_am` von DEMSELBEN TAG. Wer sie ansieht,
    haelt sie fuer frisch.

    Ein alter Kurs ist dabei keine Notloesung, sondern das Richtige: Jahresdurchschnitte
    aelterer Jahre aendern sich nicht mehr, und der laufende Wert von gestern ist naeher an
    der Wahrheit als der Jahresschnitt von vorletztem Jahr.
    """
    uebernommen: dict[str, list[str]] = {}
    for w, jahre in alt.items():
        for jahr, kurs in jahre.items():
            if jahr not in neu.setdefault(w, {}):
                neu[w][jahr] = kurs
                # ⚠ Als Luecke GEMELDET wird nur, was dieser Lauf holen WOLLTE. Ein Lauf mit
                # `--waehrungen CHF` traegt die uebrigen zwoelf weiter mit, damit die Datei
                # nicht schrumpft — sie als „nicht frisch geholt" zu melden waere aber
                # Laerm: niemand hat sie angefragt. Beim Messen am 2026-10-05 meldete ein
                # Dreiwaehrungs-Lauf zehn Warnungen, von denen keine jemanden anging.
                if w in gefragt:
                    uebernommen.setdefault(w, []).append(jahr)
    for w in uebernommen:
        uebernommen[w].sort()
    return uebernommen


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--ab", type=int, default=2004, help="erstes Jahr (Vorgabe 2004)")
    # Gemessen am 15.09.2026 im Silber aller vier Laender: neben EUR kommen CHF (50.350),
    # USD (216), GBP (31), BGN (8), PLN/DKK/ISK (je 1) vor — und AED (11), das die EZB
    # nicht fuehrt und das darum weiter ausfaellt. Die nordischen und mitteleuropaeischen
    # Reihen stehen fuer die naechsten Laender schon bereit.
    # ⚠ **DIE REIHENFOLGE IST TEIL DES SCHUTZES, nicht Geschmack.** Der Zeitdeckel wird von
    # vorn nach hinten verbraucht; was hinten steht, faellt bei einer kranken Quelle zuerst
    # aus. CHF steht deshalb vorn — es ist die einzige Fremdwaehrung mit nennenswertem
    # Bestand (50.350 Bekanntmachungen gegen 216 fuer USD und 31 fuer GBP). Wer hier
    # umsortiert, verschiebt, welche Waehrung bei einer Stoerung als Erste verloren geht.
    p.add_argument("--waehrungen",
                   default="CHF,USD,GBP,DKK,SEK,NOK,PLN,CZK,HUF,RON,BGN,ISK,TRY",
                   help="Komma-Liste; die Reihe heisst <WAEHRUNG> je EUR")
    p.add_argument("--trocken", action="store_true", help="nur zeigen, nichts schreiben")
    a = p.parse_args(argv)

    bis = date.today().year
    kurse: dict[str, dict[str, float]] = {}
    laufend: dict[str, dict[str, int]] = {}
    luecken: dict[str, str] = {}
    alt = _bestand()
    gefragt = [x.strip().upper() for x in a.waehrungen.split(",") if x.strip()]
    for w in gefragt:
        # ⚠ EINE FEHLENDE REIHE DARF DEN LAUF NICHT KIPPEN. Die EZB fuehrt nicht jede
        # Waehrung ueber den ganzen Zeitraum (ISK etwa ruht seit 2008), und ein 404 fuer
        # eine Randwaehrung soll nicht die Kurse kosten, die wir wirklich brauchen.
        # ⚠ Deckel aufgebraucht: GAR NICHT erst anfragen. Nur die Wiederholungen zu stoppen
        # reicht nicht — der erste Versuch jeder restlichen Reihe kostet weiterhin seinen
        # vollen Anfragedeckel, und bei 13 Waehrungen mal zwei Reihen summiert sich das auf
        # ein Vielfaches des Gesamtdeckels. Beim Probelauf am 2026-10-05 waren es 4:42
        # gegen 4:00 Deckel, weil genau dieser Riegel noch fehlte.
        if _rest() <= 0:
            print(f"  ⚠ {w}: Zeitdeckel aufgebraucht — nicht mehr angefragt")
            luecken[w] = "Zeitdeckel aufgebraucht"
            continue
        try:
            reihe = _hole(w, a.ab, bis)
        except Exception as e:                                       # noqa: BLE001
            print(f"  ⚠ {w}: {type(e).__name__} — uebersprungen")
            luecken[w] = f"Jahresreihe: {type(e).__name__}"
            continue
        if not reihe:
            print(f"  ⚠ {w}: keine Werte — Reihe oder Zeitraum pruefen")
            luecken[w] = "Jahresreihe: keine Werte"
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
            luecken[w] = f"Monatsreihe {bis}: {type(e).__name__}"
            continue
        if mittel is None:
            print(f"     ⚠ {bis}: noch kein Monat veroeffentlicht")
            # ⚠ KEINE Luecke. Die EZB fuehrt die Reihe dann wirklich nicht mehr — BGN hat
            # seit dem Euro-Beitritt keinen Kurs, und das ist richtig so, nicht kaputt.
            continue
        kurse[w][str(bis)] = round(mittel, 6)
        laufend[w] = {"jahr": bis, "monate": monate}
        vorjahr = reihe.get(bis - 1)
        drift = f" · {100 * (mittel / vorjahr - 1):+.1f} % gegen {bis - 1}" if vorjahr else ""
        print(f"     {bis} laufend: {mittel:.4f} aus {monate} Monat(en){drift}")
    if not kurse:
        return 1
    uebernommen = _uebernimm(kurse, alt, set(gefragt))
    for w, jahre in sorted(uebernommen.items()):
        print(f"  ⚠ {w}: {len(jahre)} Jahr(e) aus der alten Datei uebernommen "
              f"({jahre[0]}..{jahre[-1]}) — frisch geholt wurden sie NICHT.")
    if a.trocken:
        # ⚠ Auch der Probelauf meldet den Teilausfall. Haette er hier stur 0 gesagt, waere
        # das exakt der Fehler, den dieses Skript abstellt: ein Lauf mit Luecken, der sich
        # als Erfolg meldet.
        return 2 if (luecken or uebernommen) else 0
    inhalt = {"quelle": "EZB-Referenzkurse (data-api.ecb.europa.eu, EXR, "
                        "Frequenz A; laufendes Jahr gemittelt aus Frequenz M)",
              "bedeutung": "Einheiten der Fremdwaehrung je 1 EUR — umrechnen mit betrag/kurs",
              "geholt_am": date.today().isoformat(),
              # ⚠ Welche Jahreswerte NICHT der amtliche Jahresdurchschnitt sind, sondern
              # ein laufendes Mittel der bisherigen Monate. Wer mit diesen Zahlen rechnet,
              # muss es wissen koennen, ohne den Code zu lesen.
              "laufend": laufend,
              # ⚠ Was NICHT frisch geholt werden konnte, und was deshalb aus der vorigen
              # Datei steht. Ohne diese zwei Felder sieht eine geflickte Datei genauso aus
              # wie eine vollstaendige — und `geholt_am` behauptet dann etwas, das fuer
              # einen Teil der Zahlen nicht stimmt.
              "luecken": luecken,
              "uebernommen": uebernommen,
              "kurse": kurse}
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    teil = ZIEL.with_suffix(".teil")
    teil.write_text(json.dumps(inhalt, ensure_ascii=False, indent=1), encoding="utf-8")
    teil.replace(ZIEL)
    print(f"→ {ZIEL.relative_to(ROOT)}")
    # ⚠ EIGENER AUSGANG FUER DEN TEILAUSFALL. 0 hiesse „alles geholt", 1 hiesse „nichts
    # geschrieben, die alte Datei gilt" — beides waere hier falsch. 2 heisst: die Datei ist
    # da und benutzbar, aber ein Teil davon ist nicht von heute. `daily_leads.sh` sagt das
    # entsprechend an; ohne den eigenen Code waere der Teilausfall genau das gewesen, was
    # dieses Projekt jagt: ein Fehler, der wie ein Erfolg aussieht.
    return 2 if (luecken or uebernommen) else 0


if __name__ == "__main__":
    raise SystemExit(main())
