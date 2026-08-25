"""Extrahierte Anforderungswerte in eine Form bringen, mit der man rechnen kann.

**Warum es das gibt.** `docextract` liefert je Anforderung ein `value` und eine `unit`,
und beide sind Zeichenketten — so, wie das Modell sie im Dokument gefunden hat. Gemessen
am 2026-08-25 über **346.055 Einträge** aus 7.755 Vergaben:

    berufshaftpflicht     value='3000000'          unit='EUR'
    mindestumsatz         value='600000'           unit='EUR'
    referenz_anzahl       value='2'                unit=''
    zuschlagskriterium    value='Entgelte ohne …'  unit='75 %'
    frist                 value='16.07.2026'       unit=''
    frist                 value='4'                unit='Wochen'

Der Inhalt ist da. Rechnen kann damit niemand: „zeig mir alles, was höchstens zwei
Referenzen verlangt" oder „Haftpflicht bis 3 Mio" ist eine Textsuche über Zahlen, die
als Text dastehen. Genau diese Filter entscheiden aber, ob eine kleine Firma überhaupt
bieten *kann*.

⚠ **Nichts wird überschrieben.** Die Rohwerte bleiben, wie das Modell sie geliefert hat —
sie tragen die Belegpflicht (§6a.2), und ein normalisierter Wert ist eine Auslegung, kein
Zitat. Dazu kommen additive Felder (`wert_num`, `wert_einheit`, `wert_datum`), und wo die
Auslegung scheitert, bleiben sie leer statt zu raten.

⚠ **Deutsche Zahlschreibung ist mehrdeutig.** `3.000` heisst hier dreitausend, nicht drei.
Die Regel: ein Punkt mit genau drei Ziffern dahinter und ohne Komma im Wert ist ein
Tausendertrenner; ein Punkt mit ein bis zwei Ziffern dahinter ist ein Dezimalpunkt. Wer
das verwechselt, macht aus einer Haftpflicht über 3 Mio eine über 3 Euro.

Aufruf::

    from govisor import normwerte
    item.update(normwerte.normalisiere(item))
"""
from __future__ import annotations

import datetime as _dt
import re

# Vielfache, wie sie in Vergabeunterlagen stehen. `t€`/`tsd` sind selten, aber eindeutig.
_FAKTOR: dict[str, float] = {
    "mio": 1e6, "mio.": 1e6, "million": 1e6, "millionen": 1e6, "mill": 1e6,
    "mrd": 1e9, "mrd.": 1e9, "milliarde": 1e9, "milliarden": 1e9,
    "tsd": 1e3, "tsd.": 1e3, "tausend": 1e3, "t€": 1e3, "teur": 1e3, "tdm": 1e3,
}

# Einheiten auf eine Schreibweise. Alles, was hier nicht steht, bleibt roh — eine
# erfundene Vereinheitlichung waere schlimmer als eine ehrliche Rohangabe.
_EINHEIT: dict[str, str] = {
    "eur": "EUR", "euro": "EUR", "€": "EUR", "eur.": "EUR",
    "%": "%", "prozent": "%", "v.h.": "%", "vh": "%",
    "tag": "Tage", "tage": "Tage", "kalendertage": "Tage", "werktage": "Werktage",
    "woche": "Wochen", "wochen": "Wochen",
    "monat": "Monate", "monate": "Monate", "monaten": "Monate",
    "jahr": "Jahre", "jahre": "Jahre", "jahren": "Jahre",
    "stück": "Stück", "stueck": "Stück", "stk": "Stück", "stk.": "Stück",
}

# Umrechnung in Tage — nur dort, wo sie eindeutig ist. Ein Monat ist keine feste Zahl von
# Tagen; 30 ist die Konvention der Vergabefristen (§ 15 VgV rechnet ebenso).
_IN_TAGE: dict[str, int] = {"Tage": 1, "Werktage": 1, "Wochen": 7, "Monate": 30, "Jahre": 365}

_ZAHL = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)(?![\d])")
_DATUM_DE = re.compile(r"\b(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})\b")
_DATUM_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def zahl(text: str | float | int | None) -> float | None:
    """Erste Zahl in deutscher oder neutraler Schreibweise, mit Vielfachem.

    ``"3.000.000"`` → 3000000 · ``"1,5 Mio"`` → 1500000 · ``"75 %"`` → 75 ·
    ``"keine Angabe"`` → None
    """
    if isinstance(text, bool):
        return None
    if isinstance(text, (int, float)):
        return float(text)
    if not text:
        return None
    s = str(text).strip().lower()
    m = _ZAHL.search(s)
    if not m:
        return None
    roh = m.group(1)
    # ⚠ Hier entscheidet sich, ob aus 3.000 dreitausend oder drei wird.
    if "," in roh:                       # Komma ist immer das Dezimalzeichen
        roh = roh.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", roh):
        roh = roh.replace(".", "")       # reiner Tausendertrenner
    try:
        wert = float(roh)
    except ValueError:
        return None
    # Vielfaches unmittelbar hinter der Zahl (max. ein Wort dazwischen).
    rest = s[m.end():m.end() + 24].strip()
    for kuerzel, faktor in _FAKTOR.items():
        if rest.startswith(kuerzel):
            return wert * faktor
    return wert


def einheit(*texte: str | None) -> str | None:
    """Einheit aus `unit` oder aus dem Wert selbst. ``None``, wenn unbekannt."""
    for t in texte:
        if not t:
            continue
        s = str(t).strip().lower()
        if s in _EINHEIT:
            return _EINHEIT[s]
        for wort, norm in _EINHEIT.items():
            if re.search(rf"(?<![a-zä-ü]){re.escape(wort)}(?![a-zä-ü])", s):
                return norm
    return None


def datum(text: str | None) -> str | None:
    """Erstes Datum als ISO-Tag. ``"16.07.2026"`` → ``"2026-07-16"``.

    ⚠ Nur echte Kalenderdaten. ``"4"`` (aus `value='4'`, `unit='Wochen'`) ist eine
    DAUER und hier bewusst kein Datum — sie landet über `zahl()` in `wert_num`.
    """
    if not text:
        return None
    s = str(text)
    m = _DATUM_DE.search(s)
    if m:
        tag, monat, jahr = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = _DATUM_ISO.search(s)
        if not m:
            return None
        jahr, monat, tag = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return _dt.date(jahr, monat, tag).isoformat()
    except ValueError:
        return None                      # 31.02. und Ähnliches: lieber nichts als falsch


def _sieht_wie_datum_aus(text: str | None) -> bool:
    """Trägt das Feld ein Datumsmuster? Auch ein UNGÜLTIGES zählt.

    ⚠ `31.02.2026` ist kein Datum — aber erst recht keine Zahl 31,02. Ein Feld, das wie
    ein Datum aussieht, gibt keinen Betrag her; sonst wurde aus einem Tippfehler im
    Kalender eine Haftpflichtsumme.
    """
    s = str(text or "")
    return bool(_DATUM_DE.search(s) or _DATUM_ISO.search(s))


def normalisiere(item: dict) -> dict:
    """Zusatzfelder zu einem Anforderungs-Eintrag. Verändert `item` NICHT.

    Gibt nur die Felder zurück, die sich belegen liessen — ein leeres Ergebnis heisst
    „nicht auslegbar", nicht „null".
    """
    v, u = item.get("value"), item.get("unit")
    aus: dict = {}

    tag = datum(v) or datum(u)
    if tag:
        aus["wert_datum"] = tag

    # Die Zahl steht mal im Wert (`'3000000'`, `'EUR'`), mal in der Einheit
    # (`'Entgelte ohne Kraftstoff'`, `'75 %'`). Beide Stellen ansehen, Wert zuerst —
    # aber KEINE Stelle, die ein Datum trägt: aus `2026-08-13 11:00` wurde sonst die
    # Zahl 2026, und aus `31.02.2026` die Zahl 31,02.
    n = None
    for feld in (v, u):
        if feld is None or _sieht_wie_datum_aus(feld):
            continue
        n = zahl(feld)
        if n is not None:
            break
    if n is not None:
        aus["wert_num"] = n

    e = einheit(u, v)
    if e is None and re.search(r"(?i)\bt(?:eur|€|dm)\b|\bmio\.?\s*€", f"{v or ''} {u or ''}"):
        e = "EUR"          # `500 TEUR` ist schon in Euro umgerechnet, s. _FAKTOR
    if e:
        aus["wert_einheit"] = e
        if e in _IN_TAGE and aus.get("wert_num") is not None and not tag:
            aus["wert_tage"] = int(round(aus["wert_num"] * _IN_TAGE[e]))
    return aus
