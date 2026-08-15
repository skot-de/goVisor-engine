"""Dokument-Signale — Vergabeunterlagen-Volltext → strukturierte Lead-Signale („verwertbar machen").

Die docpipe-Pipeline liefert Volltext je Dokument (``doc_text.parquet``). Diese Schicht zieht daraus
die **entscheidungsrelevanten Strukturdaten**, die in den strukturierten eForms-Feldern oft fehlen
(gemessen: Eignung nur 2 %, Bürgschaft 32 %, Zuschlagsgewichte 24 %). Genau diese Felder speisen den
**Angebots-Aufwand** (#18) — d. h. Dokumente füllen die Lücke für die Leads, für die wir Unterlagen
haben.

Rein **regelbasiert/deterministisch** (kein LLM, keine Kosten, reproduzierbar). Die deutsche
Vergabe-Sprache ist stark standardisiert (VOB/VgV/UVgO-Formblätter), deshalb tragen Schlüssel-
begriffe weit. Jedes Signal trägt die **Fundstelle** (Snippet) als Beleg — nichts wird behauptet,
was nicht im Text steht. Unsicheres bleibt ``None`` (nicht „nein").

Ausgabe je Vorgang (``notice_id``): ``guarantee_required`` (Bürgschaft), ``binding_days``
(Bindefrist), ``eligibility_count`` + ``certificates`` (Eignung), ``award_weights`` (Zuschlags-
kriterien), ``variants_allowed`` (Nebenangebote), ``framework`` (Rahmenvertrag) — plus Belege.
Schreibt ``doc_signals.parquet``; der Web-Export/Aufwand kann es je Lead joinen.
"""
from __future__ import annotations

import re
from datetime import date as _date

_FLAGS = re.IGNORECASE | re.DOTALL


def _find(text: str, pattern: str) -> str | None:
    """Erstes Match mit ~60 Zeichen Kontext als Beleg-Snippet (oder None)."""
    m = re.search(rf".{{0,40}}(?:{pattern}).{{0,40}}", text, _FLAGS)
    return re.sub(r"\s+", " ", m.group(0)).strip() if m else None


# ── Bürgschaft / Sicherheitsleistung ──────────────────────────────────────────────────────────
_GUAR_YES = (r"vertragserfüllungsbürgschaft|gewährleistungsbürgschaft|bietungsbürgschaft|"
             r"sicherheitsleistung|sicherheitseinbehalt|bürgschaft (?:in|von|über|i\.?H\.?v)")
_GUAR_NO = r"(?:keine|ohne)\s+sicherheitsleistung|auf (?:eine )?sicherheit(?:sleistung)? wird verzichtet"

# ── Bindefrist ────────────────────────────────────────────────────────────────────────────────
# GEMESSEN am Korpus (241 Vorgänge, 592 Fundstellen): die Tageszahl ist die AUSNAHME.
#   „endet am <Datum>" / „bis zum …"  424×   ·  „N Tage"  5×  ·  Monate/Wochen  3×
# Die alte Regel kannte nur „N Tage" — deshalb fand sie 1 von 234 Vorgängen. Das Datum ist
# die VOB/A-Standardform (Formblatt 211 „Aufforderung zur Abgabe eines Angebots").
_BIND = r"(?:zuschlags?-?\s*und\s*)?binde\s*frist|zuschlagsfrist|(?:angebote?|bindung).{0,15}gebunden"
_BIND_DAYS = re.compile(
    r"(?:binde\s*frist|zuschlagsfrist|gebunden)[^.\n]{0,40}?(\d{1,3})\s*(?:kalender-?)?tage"
    r"|(\d{1,3})\s*(?:kalender-?)?tage[^.\n]{0,25}?(?:gebunden|binde\s*frist)", _FLAGS)
# „Bindefrist endet am 03.11.2026" / „Ende der Bindefrist: 30.10.2026" / „…bis zum 12.10.26"
_BIND_DATE = re.compile(
    r"(?:binde\s*frist|zuschlagsfrist)[^.\n]{0,40}?"
    r"(?:endet|läuft|gilt|ist)?\s*(?:am|bis(?:\s+zum)?)?\s*:?\s*"
    r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", _FLAGS)
# TABELLENFORM — von `scripts/parser_gaps.py` gefunden (14×): erst die Beschriftungen, dann
# die Werte: „Ende der Angebotsfrist | Ende der Bindefrist | 31.08.2026 | 30.10.2026". Das
# 40-Zeichen-Fenster oben greift da nicht. Aus den Datumswerten im Fenster wird das SPÄTESTE
# genommen: die Bindefrist endet zwangsläufig nach der Angebotsfrist — eine Ordnungsaussage,
# keine Positionsannahme (die Spaltenreihenfolge wechselt je Formular).
_BIND_TABELLE = re.compile(r"binde\s*frist.{0,120}?((?:\d{1,2}\.\d{1,2}\.\d{2,4}[^\n]{0,25}){1,3})", _FLAGS)
_DATUM = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})")

# ── Pflichttermine: Ortsbesichtigung / Präsentation ────────────────────────────────────────────
# Beides sind harte Terminzwänge: wer den Termin verpasst, darf nicht bieten bzw. verliert
# Punkte. Gemessen 36 % bzw. 31 % der Vorgänge — und im Gegensatz zu „Nachunternehmer" (92 %)
# unterscheiden sie tatsächlich zwischen Ausschreibungen.
_SITE_VISIT = r"ortsbesichtigung|ortstermin|objektbesichtigung|begehung(?:stermin)?"
_SITE_PFLICHT = r"(?:ortsbesichtigung|ortstermin|begehung)[^.\n]{0,60}?(?:verpflichtend|zwingend|obligatorisch|pflicht)"
_PRESENTATION = r"präsentation(?:stermin)?|bemusterung|teststellung|vor-?ort-?termin"

# ── Vertragsstrafe + Skonto: Geld-Signale ─────────────────────────────────────────────────────
# Vertragsstrafe 30 %, Skonto 25 % der Vorgänge. Beide gehen direkt in die Kalkulation.
_PENALTY = re.compile(r"vertragsstrafe[^.\n]{0,80}?(\d{1,2}(?:[,.]\d{1,2})?)\s*(?:%|v\.?\s?h\.)", _FLAGS)
# Wortzahl statt Ziffer — ebenfalls aus parser_gaps: „…Zahlung einer Vertragsstrafe, deren
# Höhe eins von Hundert…" (12×). VOB/B-Standardsatz, den das Ziffern-Muster nicht sieht.
_PENALTY_WORT = re.compile(
    r"vertragsstrafe[^.\n]{0,80}?\b(ein|eins|zwei|drei|vier|fünf)\b\s*(?:vom?\s+hundert|v\.?\s?h\.|prozent)", _FLAGS)
_WORTZAHL = {"ein": 1.0, "eins": 1.0, "zwei": 2.0, "drei": 3.0, "vier": 4.0, "fünf": 5.0}
# Skonto NUR, wo die Ausschreibung wirklich einen Satz nennt. Gemessen: von 425 Skonto-
# Nennungen tragen 385 GAR KEINE Zahl — der Bieter bietet das Skonto an, die Vergabe
# schreibt es nicht vor („unter Abzug des vereinbarten Skontos", „Skontofrist"). Eine
# niedrige Trefferzahl ist hier also die richtige Antwort, kein Regel-Defekt.
_SKONTO = re.compile(r"skonto[^.\n]{0,60}?(\d{1,2}(?:[,.]\d)?)\s*%"
                     r"|(\d{1,2}(?:[,.]\d)?)\s*%[^.\n]{0,30}?skonto", _FLAGS)

# ── Eignung: Nachweise / Zertifikate ──────────────────────────────────────────────────────────
_ELIG_TERMS = [
    r"eigenerklärung", r"präqualifik", r"referenz(?:en|projekt|liste)?", r"berufshaftpflicht",
    r"unbedenklichkeitsbescheinigung", r"handelsregisterauszug", r"gewerbezentralregister",
    r"mindestjahresumsatz|mindestumsatz", r"bilanz", r"tariftreue", r"mindestlohn",
    r"nachweis(?:e|en)?", r"befähigung", r"fachkunde|leistungsfähigkeit|zuverlässigkeit",
]
_CERTS = [
    ("ISO 9001", r"ISO\s*9001|DIN\s*EN\s*ISO\s*9001"),
    ("ISO 14001", r"ISO\s*14001"), ("ISO 27001", r"ISO\s*27001|ISMS"),
    ("ISO 13485", r"ISO\s*13485"), ("SCC/SCP", r"\bSCC\b|\bSCP\b"),
    ("Präqualifikation", r"präqualifi|PQ-?VOB|amtliches verzeichnis"),
    ("EMAS", r"\bEMAS\b"), ("BSI C5", r"\bC5\b|BSI[- ]?C5"),
]

# ── Nachweisdichte (Ticket #23 Vergabestelle-Brücke): wie viele DISTINKTE Nachweis-Arten +
# Formblätter fordern die Unterlagen? Hoher Wert = hoher Bieteraufwand = schreckt KMU ab. Bewusst
# kategorie-distinkt (jede Art zählt 1×), damit Wiederholungen nicht aufblähen. Regelbasiert →
# konsistent über Korpus (Median) UND einen hochgeladenen Vergabestellen-Entwurf anwendbar.
_NACHWEIS_KATEGORIEN = [
    r"eigenerklärung", r"verpflichtungserklärung", r"referenz(?:en|projekt|liste|nachweis)",
    r"mindest(?:jahres)?umsatz", r"berufs-?\s?haftpflicht|betriebshaftpflicht",
    r"handelsregisterauszug", r"unbedenklichkeitsbescheinigung",
    r"gewerbezentralregister|führungszeugnis", r"tariftreue|mindestlohn",
    r"präqualifik|amtliches verzeichnis", r"bilanz|jahresabschluss",
    r"versicherungsbestätigung|deckungssumme", r"fachkunde|befähigung|qualifikationsnachweis",
    r"russland-?sanktion|art\.?\s*5k|833/2014", r"iso\s*900\d|iso\s*1400\d|iso\s*2700\d",
    r"präsentation(?:stermin)?|teststellung|bemusterung|vor-?ort-?termin",
]
_FORMBLATT = re.compile(r"form(?:blatt|ular)\s*[-\s]?(\d{2,3})", _FLAGS)


def nachweis_count(text: str) -> int:
    """Anzahl DISTINKTER geforderter Nachweis-Arten + Formblätter im Text (Nachweisdichte, §B.2)."""
    if not text:
        return 0
    n = sum(1 for pat in _NACHWEIS_KATEGORIEN if re.search(pat, text, _FLAGS))
    n += len({m for m in _FORMBLATT.findall(text)})
    return n


# ── Zuschlagsgewichte ─────────────────────────────────────────────────────────────────────────
_WEIGHT = re.compile(r"(preis|qualität|kosten|leistung|wirtschaftlichkeit)[^%\n]{0,25}?(\d{1,3})\s*%", _FLAGS)

# ── Nebenangebote / Rahmenvertrag ─────────────────────────────────────────────────────────────
_VARIANTS_YES = r"nebenangebote?\s+(?:sind\s+)?zugelassen|nebenangebote?\s+erwünscht"
_VARIANTS_NO = r"nebenangebote?\s+(?:sind\s+)?nicht\s+zugelassen|keine nebenangebote"
_FRAMEWORK = r"rahmen(?:verein)?(?:barung|vertrag)|rahmenvereinbarung|abrufvertrag"


# ── Anker je Signal: „wo MÜSSTE etwas stehen?" ────────────────────────────────────────────────
# Bewusst HIER, direkt neben den Regeln — nicht im Auswertungsskript. Beim ersten Anlauf lagen
# die Anker in `scripts/parser_gaps.py` und waren enger als die Regeln; die Lückenmetrik meldete
# daraufhin negative Lücken (die Regel fand mehr als der Anker). Wer die Regel ändert, sieht den
# Anker jetzt in derselben Datei.
#
# Der Anker ist absichtlich WEITER als die Extraktionsregel: er fragt „ist das Thema überhaupt
# im Dokument?", die Regel fragt „steht ein verwertbarer Wert da?". Die Differenz ist die
# Trefferlücke — und damit die Arbeitsliste für den Parser.
ANKER: dict[str, str] = {
    "guarantee_required":    r"bürgschaft|sicherheitsleistung|sicherheitseinbehalt",
    "binding_until":         _BIND,
    "binding_days":          _BIND,
    "eligibility_count":     r"eignung|nachweis|referenz",
    "award_weights":         r"zuschlagskriteri|wertungskriteri|gewichtung|wertungsformel",
    "variants_allowed":      r"nebenangebot",
    "framework":             _FRAMEWORK,
    "penalty_pct":           r"vertragsstrafe",
    "skonto_pct":            r"\bskonto",
    "site_visit":            _SITE_VISIT,
    "presentation_required": _PRESENTATION,
}

def extract_signals(text: str) -> dict:
    """Volltext eines Vorgangs (alle Dokumente konkateniert) → strukturierte Signale + Belege."""
    if not text:
        return {}
    t = text
    out: dict = {}

    # Bürgschaft: explizites Nein sticht (Verzicht), sonst Ja bei Fund, sonst unbekannt.
    if re.search(_GUAR_NO, t, _FLAGS):
        out["guarantee_required"] = False
    elif re.search(_GUAR_YES, t, _FLAGS):
        out["guarantee_required"] = True
        out["guarantee_evidence"] = _find(t, _GUAR_YES)

    # Bindefrist — erst die Tageszahl (selten, aber eindeutig), dann das Datum (Regelfall).
    md = _BIND_DAYS.search(t)
    if md:
        days = int(md.group(1) or md.group(2))
        if 5 <= days <= 365:                       # plausible Bindefrist
            out["binding_days"] = days
            out["binding_evidence"] = re.sub(r"\s+", " ", md.group(0)).strip()
    else:
        mdate = _BIND_DATE.search(t)
        if not mdate:
            mt = _BIND_TABELLE.search(t)
            if mt:
                kand = []
                for tg, mo, jr in _DATUM.findall(mt.group(1)):
                    jr = int(jr) + (2000 if int(jr) < 100 else 0)
                    try:
                        kand.append(_date(jr, int(mo), int(tg)))
                    except ValueError:
                        pass
                if kand:
                    spaet = max(kand)
                    if 2020 <= spaet.year <= 2035:
                        out["binding_until"] = spaet.isoformat()
                        out["binding_evidence"] = re.sub(r"\s+", " ", mt.group(0))[:160].strip()
        if mdate:
            tag, monat, jahr = (int(x) for x in mdate.groups())
            jahr += 2000 if jahr < 100 else 0
            try:
                d = _date(jahr, monat, tag)
            except ValueError:
                d = None                            # 31.02. o. Ä. — lieber nichts als Unsinn
            if d and 2020 <= jahr <= 2035:
                # Als ISO-Datum ablegen, NICHT in Tage umrechnen: der Bezugspunkt (Angebots-
                # frist) steht hier nicht zuverlässig daneben. Ein Datum ist ohnehin die
                # nützlichere Angabe — „bis wann bin ich gebunden" ist die Frage des Bieters.
                out["binding_until"] = d.isoformat()
                out["binding_evidence"] = re.sub(r"\s+", " ", mdate.group(0)).strip()

    # Pflichttermine — Ortsbesichtigung und Präsentation/Bemusterung.
    if re.search(_SITE_VISIT, t, _FLAGS):
        out["site_visit"] = True
        out["site_visit_mandatory"] = bool(re.search(_SITE_PFLICHT, t, _FLAGS))
        out["site_visit_evidence"] = _find(t, _SITE_VISIT)
    if re.search(_PRESENTATION, t, _FLAGS):
        out["presentation_required"] = True
        out["presentation_evidence"] = _find(t, _PRESENTATION)

    # Vertragsstrafe und Skonto — gehen direkt in die Kalkulation.
    mp = _PENALTY.search(t)
    if not mp:
        mw = _PENALTY_WORT.search(t)
        if mw:
            out["penalty_pct"] = _WORTZAHL[mw.group(1).lower()]
            out["penalty_evidence"] = re.sub(r"\s+", " ", mw.group(0)).strip()
    if mp:
        pct = float(mp.group(1).replace(",", "."))
        if 0 < pct <= 20:                          # ueber 20 % ist keine Vertragsstrafe mehr
            out["penalty_pct"] = pct
            out["penalty_evidence"] = re.sub(r"\s+", " ", mp.group(0)).strip()
    ms = _SKONTO.search(t)
    if ms:
        pct = float((ms.group(1) or ms.group(2)).replace(",", "."))
        if 0 < pct <= 10:
            out["skonto_pct"] = pct

    # Eignung: distinkte Nachweis-Begriffe zählen (Intensität) + konkrete Zertifikate
    hits = {lab for lab in _ELIG_TERMS if re.search(lab, t, _FLAGS)}
    certs = [name for name, pat in _CERTS if re.search(pat, t, _FLAGS)]
    if hits or certs:
        out["eligibility_count"] = len(hits) + len(certs)
        out["certificates"] = certs

    # Zuschlagsgewichte (Kriterium → %)
    weights = {}
    for crit, pct in _WEIGHT.findall(t):
        c = crit.lower()
        p = int(pct)
        if p <= 100 and c not in weights:
            weights[c] = p
    if weights:
        out["award_weights"] = weights

    # Nebenangebote
    if re.search(_VARIANTS_NO, t, _FLAGS):
        out["variants_allowed"] = False
    elif re.search(_VARIANTS_YES, t, _FLAGS):
        out["variants_allowed"] = True

    if re.search(_FRAMEWORK, t, _FLAGS):
        out["framework"] = True

    return out


# ══ ENDE DER REGELN ══ Alles OBERHALB dieser Marke bestimmt, WAS extrahiert wird, und geht in
# den Regel-Fingerabdruck ein; alles darunter ist Mechanik (lesen, stapeln, mischen, schreiben).
# Wer eine Regel ändert, löst damit automatisch einen Voll-Lauf aus — wer nur die Stapelgröße
# anfasst, nicht. Die Marke darf NICHT umformuliert werden, `_regel_version` schneidet an ihr.
_REGEL_MARKE = "# ══ ENDE DER REGELN ══"


def _regel_version() -> str:
    """Fingerabdruck der EXTRAKTIONSREGELN — alles oberhalb von ``_REGEL_MARKE``.

    Ändert sich eine Regel, ist jeder gespeicherte Signalsatz überholt und muss neu — ändert
    sich nur die Mechanik, wäre ein Voll-Lauf über 1,4 Mrd. Zeichen reine Verschwendung.
    Diese Unterscheidung ist der Grund, warum der Schritt überhaupt inkrementell sein DARF:
    ohne sie müsste man nach jeder Änderung raten, ob der Bestand noch gilt — und die ehrliche
    Antwort auf ein Raten wäre „immer alles neu".
    """
    import hashlib
    import pathlib

    quelle = pathlib.Path(__file__).read_text(encoding="utf-8")
    kopf, marke, _ = quelle.partition("\n" + _REGEL_MARKE)
    # Ohne Marke lieber ein Voll-Lauf als ein stiller Fehl-Fingerabdruck: eine umbenannte
    # Marke würde sonst dauerhaft dieselbe Version melden, egal wie sich die Regeln ändern.
    if not marke:
        raise RuntimeError("_REGEL_MARKE fehlt in docsignals.py — Regel-Version nicht bestimmbar")
    return hashlib.sha256(kopf.encode("utf-8")).hexdigest()[:16]


# Wie viele Vorgänge auf einmal in den Speicher geholt werden. Ein Vorgang trägt im Mittel
# ~400.000 Zeichen; der ganze Bestand sind 1,38 Mrd. Die alte Fassung zog ihn in EINEM
# `fetchall()` — bei einem Voll-Lauf also gut ein Gigabyte Python-Strings gleichzeitig.
_STAPEL = 40

_STAND = "doc_signals_stand.parquet"


def _fingerabdruecke(con, src) -> dict[str, str]:
    """Je Vorgang ein billiger Abdruck seines Text-Eingangs — OHNE den Text zu lesen.

    `n_chars` und `file` stehen als eigene Spalten in der Parquet; ein Spalten-Scan darüber
    kostet unter einer Sekunde, während `text` (312 MB komprimiert) gar nicht angefasst wird.
    Der Abdruck ändert sich, wenn Dateien dazukommen, wegfallen, umbenannt werden oder ihre
    Länge sich ändert — genau die Fälle, in denen die Signale neu gerechnet gehören.
    """
    return {nid: fp for nid, fp in con.execute(
        f"""SELECT notice_id,
                   count(*) || ':' || coalesce(sum(n_chars), 0) || ':'
                   || md5(string_agg(file, '|' ORDER BY file)) AS fp
            FROM read_parquet('{src.as_posix()}') WHERE status='ok'
            GROUP BY notice_id""").fetchall()}


def build_signals(cfg, country: str = "DE", neu_aufbauen: bool = False) -> dict:
    """``docs/<country>/doc_text.parquet`` → ``doc_signals.parquet`` (ein Datensatz je notice_id,
    Volltext aller Dokumente des Vorgangs zusammengefasst). Gibt eine Abdeckungs-Zusammenfassung.

    **Inkrementell.** Gerechnet wird nur, was neu oder verändert ist; der Rest wird aus dem
    letzten Lauf übernommen. Gemessen am 2026-08-15 brauchte der Voll-Lauf **232 Minuten** —
    40 % des gesamten Tageslaufs — obwohl sich pro Tag nur eine Handvoll Vorgänge ändert.
    Die Kosten stecken nicht in der Menge der Vorgänge (3.437), sondern in ihrer Textmasse:
    ~30 Regexe mit `DOTALL` über 1,38 Mrd. Zeichen.

    Ein Voll-Lauf passiert weiterhin automatisch, sobald sich die Regeln ändern (s.
    `_regel_version`) — oder auf Ansage per ``neu_aufbauen=True``. Das ist wichtig: ein
    inkrementeller Schritt, der eine Regeländerung verschläft, trüge halb altes, halb neues
    Verhalten, und das fiele niemandem auf.
    """
    import json

    import duckdb
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    root = cfg.data_dir / "docs" / country
    src = root / "doc_text.parquet"
    if not src.exists():
        print(f"docsignals: kein {src} — erst `index-docs` laufen lassen.")
        return {}
    out = root / "doc_signals.parquet"
    stand_datei = root / _STAND

    con = duckdb.connect()
    version = _regel_version()
    jetzt = _fingerabdruecke(con, src)

    # ── Was ist zu tun? ────────────────────────────────────────────────────────────────────
    frueher: dict[str, str] = {}
    grund = "Neuaufbau erzwungen" if neu_aufbauen else None
    if not neu_aufbauen and stand_datei.exists() and out.exists():
        alt = pq.read_table(stand_datei)
        if alt.num_rows and alt.column("regel_version")[0].as_py() != version:
            grund = "Regeln geändert → alles neu"
        else:
            frueher = dict(zip(alt.column("notice_id").to_pylist(),
                               alt.column("fingerabdruck").to_pylist()))
    elif not neu_aufbauen:
        grund = "kein früherer Stand"

    todo = sorted(nid for nid, fp in jetzt.items() if frueher.get(nid) != fp)
    behalten = [nid for nid in frueher if nid in jetzt and nid not in set(todo)]
    verschwunden = len(frueher) - len(behalten) - sum(1 for n in todo if n in frueher)

    if grund:
        print(f"docsignals {country}: {grund} — {len(todo):,} Vorgänge")
    else:
        print(f"docsignals {country}: {len(todo):,} neu/geändert, {len(behalten):,} übernommen"
              + (f", {verschwunden:,} entfallen" if verschwunden else ""))

    if not todo and out.exists():
        # Nichts zu rechnen. Der Zwischenstand wird trotzdem geschrieben, damit entfallene
        # Vorgänge auch aus der Ausgabe fallen — sonst hinge eine Zeile ohne Beleg herum.
        alt_t = pq.read_table(out)
        if verschwunden:
            alt_t = alt_t.filter(pc.is_in(alt_t.column("notice_id"), pa.array(behalten)))
            pq.write_table(alt_t, out, compression="zstd")
        _schreibe_stand(stand_datei, jetzt, version)
        print(f"  unverändert: {alt_t.num_rows:,} Vorgänge mit Signalen")
        return {"docs": alt_t.num_rows, "coverage": _abdeckung(alt_t), "gerechnet": 0}

    # ── Nur die fälligen Vorgänge rechnen ──────────────────────────────────────────────────
    out_rows = []
    for i in range(0, len(todo), _STAPEL):
        stapel = todo[i:i + _STAPEL]
        # Registriertes Arrow-Tabellchen statt einer zusammengebauten IN-Liste: die
        # notice_id kommt aus fremden Quellen (DÖE-UUIDs u. a.) und gehört nie in SQL-Text.
        con.register("_faellig", pa.table({"notice_id": pa.array(stapel, pa.string())}))
        rows = con.execute(
            f"""SELECT d.notice_id, string_agg(d.text, '\n\n' ORDER BY d.file) AS full
                FROM read_parquet('{src.as_posix()}') d
                JOIN _faellig f USING (notice_id)
                WHERE d.status='ok' GROUP BY d.notice_id""").fetchall()
        con.unregister("_faellig")
        for nid, full in rows:
            sig = extract_signals(full or "")
            if not sig:
                continue
            out_rows.append({
                "notice_id": nid,
                "guarantee_required": sig.get("guarantee_required"),
                "binding_days": sig.get("binding_days"),
                # Regelform der Bindefrist ist ein DATUM, nicht eine Tageszahl (gemessen 424:5).
                "binding_until": sig.get("binding_until"),
                "eligibility_count": sig.get("eligibility_count"),
                "certificates": ",".join(sig.get("certificates", [])) or None,
                "variants_allowed": sig.get("variants_allowed"),
                "framework": sig.get("framework"),
                "award_weights": json.dumps(sig.get("award_weights"), ensure_ascii=False) if sig.get("award_weights") else None,
                # Pflichttermine und Geld-Signale — am Korpus gemessen, nicht geraten.
                "site_visit": sig.get("site_visit"),
                "site_visit_mandatory": sig.get("site_visit_mandatory"),
                "presentation_required": sig.get("presentation_required"),
                "penalty_pct": sig.get("penalty_pct"),
                "skonto_pct": sig.get("skonto_pct"),
                "evidence": json.dumps({k: v for k, v in sig.items() if k.endswith("_evidence")}, ensure_ascii=False),
            })
        if len(todo) > _STAPEL:
            print(f"  … {min(i + _STAPEL, len(todo)):,}/{len(todo):,} Vorgänge gerechnet", flush=True)

    # ACHTUNG: feste Spaltenliste. Sie ist der Grund, warum neue Signale zweimal eingetragen
    # werden muessen — einmal oben in `out_rows`, einmal hier. Wer das vergisst, baut Regeln,
    # die messbar greifen und deren Werte trotzdem nie in der Parquet landen (heute passiert,
    # zweimal). Ein `from_pylist` ohne Schema waere fehleranfaelliger (Typ raten bei lauter
    # None-Spalten), deshalb bleibt die Liste — aber mit dieser Warnung.
    schema = pa.schema([
        ("notice_id", pa.string()),
        ("guarantee_required", pa.bool_()),
        ("binding_days", pa.int32()),
        ("binding_until", pa.string()),          # ISO-Datum, Regelform der Bindefrist
        ("eligibility_count", pa.int32()),
        ("certificates", pa.string()),
        ("variants_allowed", pa.bool_()),
        ("framework", pa.bool_()),
        ("award_weights", pa.string()),
        ("site_visit", pa.bool_()),
        ("site_visit_mandatory", pa.bool_()),
        ("presentation_required", pa.bool_()),
        ("penalty_pct", pa.float64()),
        ("skonto_pct", pa.float64()),
        ("evidence", pa.string()),
    ])
    neu = pa.Table.from_pylist(out_rows, schema=schema)

    # ── Alt + neu zusammenführen ───────────────────────────────────────────────────────────
    # Übernommen wird nur, was noch im Eingang steht UND nicht gerade neu gerechnet wurde.
    # Beide Bedingungen sind nötig: die erste wirft entfallene Vorgänge raus, die zweite
    # verhindert Doppelzeilen für einen Vorgang, dessen Dokumente sich geändert haben.
    tabelle = neu
    if behalten and out.exists():
        alt = pq.read_table(out, schema=schema)
        alt = alt.filter(pc.is_in(alt.column("notice_id"), pa.array(behalten, pa.string())))
        tabelle = pa.concat_tables([alt, neu]) if neu.num_rows else alt

    if not tabelle.num_rows:
        print("docsignals: keine Signale extrahiert.")
        return {}

    pq.write_table(tabelle, out, compression="zstd")
    _schreibe_stand(stand_datei, jetzt, version)
    cov = _abdeckung(tabelle)
    print(f"docsignals {country}: {tabelle.num_rows:,} Vorgänge mit Signalen → {out.name} "
          f"({len(out_rows):,} davon in diesem Lauf gerechnet)")
    print("  Abdeckung: " + " | ".join(f"{k}={v}" for k, v in sorted(cov.items())))
    return {"docs": tabelle.num_rows, "coverage": cov, "gerechnet": len(out_rows)}


def _schreibe_stand(pfad, abdruecke: dict[str, str], version: str) -> None:
    """Merkzettel für den nächsten Lauf: welcher Eingang lag vor, unter welchen Regeln.

    Er führt bewusst ALLE Vorgänge, auch die ohne einen einzigen Signalfund. Stünden nur die
    Fundstellen drin, würde jeder signalfreie Vorgang bei jedem Lauf erneut durch alle Regexe
    geschickt — und genau die sind oft die textreichsten (Plansätze, Fotoanhänge).
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    ids = sorted(abdruecke)
    pq.write_table(pa.table({
        "notice_id": pa.array(ids, pa.string()),
        "fingerabdruck": pa.array([abdruecke[i] for i in ids], pa.string()),
        "regel_version": pa.array([version] * len(ids), pa.string()),
    }), pfad, compression="zstd")


def _abdeckung(tabelle) -> dict[str, int]:
    """Wie oft trägt jedes Signal einen Wert — über die GANZE Ausgabe, nicht nur den Zulauf.

    Wichtig fürs Inkrementelle: würde die Abdeckung nur die frisch gerechneten Vorgänge
    zählen, fiele sie von Lauf zu Lauf auf eine Handvoll und sähe aus wie ein Einbruch.
    """
    felder = ("guarantee_required", "binding_days", "binding_until", "eligibility_count",
              "award_weights", "variants_allowed", "framework", "site_visit",
              "site_visit_mandatory", "presentation_required", "penalty_pct", "skonto_pct")
    return {f: tabelle.column(f).length() - tabelle.column(f).null_count
            for f in felder if f in tabelle.schema.names}
