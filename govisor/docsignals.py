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


def build_signals(cfg, country: str = "DE") -> dict:
    """``docs/<country>/doc_text.parquet`` → ``doc_signals.parquet`` (ein Datensatz je notice_id,
    Volltext aller Dokumente des Vorgangs zusammengefasst). Gibt eine Abdeckungs-Zusammenfassung."""
    import json

    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq

    root = cfg.data_dir / "docs" / country
    src = root / "doc_text.parquet"
    if not src.exists():
        print(f"docsignals: kein {src} — erst `index-docs` laufen lassen.")
        return {}
    con = duckdb.connect()
    # Volltext je Vorgang (alle Dateien konkatenieren, Reihenfolge stabil).
    rows = con.execute(
        f"""SELECT notice_id, string_agg(text, '\n\n' ORDER BY file) AS full
            FROM read_parquet('{src.as_posix()}') WHERE status='ok' GROUP BY notice_id""").fetchall()
    out_rows = []
    cov: dict[str, int] = {}
    for nid, full in rows:
        sig = extract_signals(full or "")
        if not sig:
            continue
        for k in ("guarantee_required", "binding_days", "binding_until", "eligibility_count",
                  "award_weights", "variants_allowed", "framework", "site_visit",
                  "site_visit_mandatory", "presentation_required", "penalty_pct", "skonto_pct"):
            if sig.get(k) is not None:
                cov[k] = cov.get(k, 0) + 1
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
    if not out_rows:
        print("docsignals: keine Signale extrahiert.")
        return {}
    schema = pa.schema([
        ("notice_id", pa.string()), ("guarantee_required", pa.bool_()), ("binding_days", pa.int64()),
        ("eligibility_count", pa.int64()), ("certificates", pa.string()),
        ("variants_allowed", pa.bool_()), ("framework", pa.bool_()),
        ("award_weights", pa.string()), ("evidence", pa.string())])
    out = root / "doc_signals.parquet"
    pq.write_table(pa.Table.from_pylist(out_rows, schema=schema), out, compression="zstd")
    print(f"docsignals {country}: {len(out_rows):,} Vorgänge mit Signalen → {out.name}")
    print("  Abdeckung: " + " | ".join(f"{k}={v}" for k, v in sorted(cov.items())))
    return {"docs": len(out_rows), "coverage": cov}
