"""Schema-aware parsing of TED notices.

TED's archive spans three schema generations that coexist in the same bulk
package. The freetext description — the field the whole extraction layer feeds
on — lives under a different name in each:

===================  ==============================  ==============================
Generation           Root / form                     Description field
===================  ==============================  ==============================
pre-2014 forms       TED_EXPORT > FD_CONTRACT_AWARD  SHORT_CONTRACT_DESCRIPTION
2014 forms           TED_EXPORT > F0x_2014           SHORT_DESCR
eForms (2022+)       UBL ContractAwardNotice etc.    cbc:Description
===================  ==============================  ==============================

A parser that only knows SHORT_DESCR silently drops both ends of the archive.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Iterator

from . import countries
from . import flatten
from . import locales

LEGACY_ROOT = "TED_EXPORT"

# The canonical human-facing notice page. TED still serves the legacy
# `udl?uri=TED:NOTICE:...` links found in URI_DOC, but only via a 301 to this
# form — so we store the target, not a redirect that TED may retire.
TED_URL = "https://ted.europa.eu/{lang}/notice/-/detail/{publication_number}"
TED_XML_URL = "https://ted.europa.eu/{lang}/notice/{publication_number}/xml"
DEFAULT_URL_LANG = "de"

# "2023/S 105-330482" → ("330482-2023", …). The OJ reference is the formal,
# permanent citation; the URL is a convenience that can change.
_RE_OJS = re.compile(r"^(\d{4})/S\s+(\d{1,3})-(\d{4,7})$")


def publication_number_from_ojs(ojs: str | None) -> str | None:
    match = _RE_OJS.match((ojs or "").strip())
    if not match:
        return None
    year, _issue, number = match.groups()
    return f"{int(number)}-{year}"


_NID_RE = re.compile(r"^0*(\d+)[-_](\d{4})$")


def normalize_notice_id(notice_id: str) -> str:
    """Kanonische ``<number>_<year>``-Form (führende Nullen weg, Trenner ``_``).

    Root-Cause des notice_id-Waisen-Bugs: dieselbe TED-Notice kommt im Monats-Archiv als
    ``00450024_2026`` (zero-padded, Unterstrich) und im Live-Feed als ``450024-2026``
    (Bindestrich). Beim Monatswechsel ersetzt das Archiv den Live-Stand → Gold-Zeilen auf
    der Bindestrich-ID verwaisen. Diese Funktion bildet BEIDE auf ``450024_2026`` ab, damit
    Archiv und Live dieselbe ID schreiben (Update statt Waise). Idempotent; unbekannte Formen
    (kein ``<zahl><trenner><jahr>``) bleiben unverändert. Kompatibel mit
    ``publication_number_from_id`` (partitioniert auf ``_``, macht ``int(number)``).
    """
    m = _NID_RE.match(notice_id)
    return f"{m.group(1)}_{m.group(2)}" if m else notice_id


def publication_number_from_id(notice_id: str) -> str | None:
    """Bulk packages name files ``<number>_<year>.xml``, zero-padded."""
    if "_" not in notice_id:
        return None
    number, _, year = notice_id.partition("_")
    if not (number.isdigit() and year.isdigit()):
        return None
    return f"{int(number)}-{year}"


def notice_url(publication_number: str | None, lang: str = DEFAULT_URL_LANG) -> str | None:
    if not publication_number:
        return None
    return TED_URL.format(lang=lang, publication_number=publication_number)

# Cheap byte-level probes, used to skip files before paying for a full parse.
_RE_LEGACY_COUNTRY = re.compile(rb'<ISO_COUNTRY[^>]*VALUE="([A-Z]{2})"')
_RE_EFORMS_COUNTRY = re.compile(rb"<cbc:IdentificationCode[^>]*>([A-Z]{3})<")
_RE_TEXT_COUNTRY = re.compile(rb"^CY:\s*([A-Z]{2})", re.M)   # TED-Plaintext (vor-XML)
# INTERNAL_OJS (opoce, ~2008) trägt das Land als Element-Text, nicht als Attribut:
# ``<ISO_COUNTRY>DE</ISO_COUNTRY>``. Ohne diese Probe fiele jede OJS-Notice vor dem
# Parse durch den Länderfilter (siehe ingest) — der ganze Monat ginge verloren.
_RE_OJS_COUNTRY = re.compile(rb"<ISO_COUNTRY>\s*([A-Z]{2})\s*</ISO_COUNTRY>")


@dataclass
class Lot:
    """One lot of a notice — TED section II.2.

    Lots carry their own description, and that is where most of the freetext
    lives: 92% of DE notices have more than one description block, and the
    lot-level ones hold two thirds of all characters.
    """

    lot_id: str | None
    title: str | None
    description: str | None
    value_amount: float | None = None
    value_currency: str | None = None
    # Kategorie 6: Laufzeit, Optionen, Verlängerung — trägt die Wechsel-Prognose.
    duration_months: int | None = None
    has_options: bool | None = None
    options_description: str | None = None
    has_renewal: bool | None = None
    renewal_description: str | None = None
    max_renewals: int | None = None
    # Los-CPV und Erfüllungsort (Weakness 2, 6)
    cpv_all: list[str] = field(default_factory=list)
    performance_nuts: str | None = None


class Flag:
    """Woran eine Notice nicht sauber durchlief.

    Jede Marke steht für eine Stelle, an der der Parser sonst still eine
    Annahme getroffen hätte. Genau solche Annahmen haben heute dreimal Daten
    gekostet: SHORT_DESCRIPTION, die verschachtelten Pakete, der eForms-
    Organisationsverweis. Alle drei sahen in jeder Statistik unauffällig aus.

    Marken sind kein Fehler — sie sind eine Bitte um Nachsehen.
    """

    UNKNOWN_FORM = "unbekannter Formulartyp"
    NO_DESCRIPTION = "kein Freitext gefunden"
    NO_CPV = "kein CPV-Code"
    NO_ORIGINAL_LANGUAGE = "keine ORIGINAL-Sprachfassung"
    UNKNOWN_COUNTRY_CODE = "Ländercode nicht in der Registry"
    BUYER_ORG_UNRESOLVED = "Käufer-Verweis zeigt ins Leere"
    NO_BUYER_COUNTRY = "kein Käuferland auflösbar"


# Jeder Formulartyp, den wir im DE-Bestand 2016–2026 gesehen und geprüft
# haben. Ein neuer Typ ist kein Fehler, aber ein Anlass hinzusehen: TED führt
# regelmäßig welche ein, und jeder brachte bisher eigene Feldnamen mit.
KNOWN_FORM_TYPES = frozenset({
    # 2014er-Formulare
    *(f"F{n:02d}_2014" for n in range(1, 26)),
    # Vor-2014-Familien
    "CONTRACT", "CONTRACT_AWARD", "CONTRACT_UTILITIES", "CONTRACT_AWARD_UTILITIES",
    "CONTRACT_DEFENCE", "CONTRACT_AWARD_DEFENCE", "PRIOR_INFORMATION",
    "PRIOR_INFORMATION_DEFENCE", "PERIODIC_INDICATIVE_UTILITIES",
    "QUALIFICATION_SYSTEM_UTILITIES", "DESIGN_CONTEST", "RESULT_DESIGN_CONTEST",
    "OTH_NOT", "EEIG", "MOVE", "CONTRACT_MOVE", "PRIOR_INFORMATION_MOVE",
    "VOLUNTARY_EX_ANTE_TRANSPARENCY_NOTICE", "CONCESSION", "BUYER_PROFILE",
    # eForms
    "ContractNotice", "ContractAwardNotice", "PriorInformationNotice",
    "BusinessRegistrationInformationNotice",
})


@dataclass
class Party:
    """Eine Organisation in ihrer Rolle — Käufer, Gewinner, Nachprüfstelle."""

    role: str                        # 'buyer' | 'winner' | 'review' | 'mediation'
    name: str | None = None
    national_id: str | None = None
    town: str | None = None
    postal_code: str | None = None
    country: str | None = None
    nuts: str | None = None
    email: str | None = None
    phone: str | None = None
    contact_person: str | None = None
    url: str | None = None
    is_sme: bool | None = None
    in_consortium: bool | None = None   # Gewinn im Rahmen einer ARGE/Bietergemeinschaft


@dataclass
class Criterion:
    """Ein Zuschlagskriterium — die praktischste Einzelinformation fuer einen Bieter.

    „Preis 100 %" gegen „Qualitaet 70 %, Preis 30 %" entscheidet, ob man ueber den Preis
    oder ueber das Konzept gewinnt.

    ``weight_kind`` ist der eForms-``ParameterCode`` und **entscheidet, ob die Zahl
    ueberhaupt ein Gewicht ist** (gemessen 2026-07-23 an 3.000 eForms):

      number-weight    per-exa 3.947 · poi-exa 2.138 · ord-imp 207 · dec-exa 28   ← Gewicht
      number-fixed     fix-tot 108 · fix-unit 17                                  ← Festbetrag
      number-threshold min-score 66 · max-pass 4                                  ← Schwelle

    ``per-*`` ist bereits Prozent, ``poi-*``/``dec-*`` sind Punkte und muessen auf die
    Summe **innerhalb desselben Loses** normiert werden, ``ord-imp`` ist ein Rang und
    ueberhaupt kein Gewicht. Wer alle ``ParameterNumeric`` unbesehen einsammelt, mischt
    Schwellen und Festbetraege unter die Gewichte — genau das tat die erste Fassung.
    """

    lot_id: str | None
    kind: str                        # 'price' | 'quality' | 'cost'
    name: str | None
    weight: str | None
    weight_kind: str | None = None   # per-exa | poi-exa | ord-imp | … ; None = Legacy


@dataclass
class Requirement:
    """Eignungs-/Teilnahmebedingung — was ein Bieter erfüllen/nachweisen muss.

    ``kind`` vereinheitlicht beide Generationen: suitability | economic |
    technical | performance | exclusion | profession | deposit. ``text`` ist
    der Rohtext ('ISO 9001 erforderlich', '3 Referenzen', 'Umsatz > 350 TEUR').
    TED codiert das *konkrete* Zertifikat nicht — der Text ist die Wahrheit,
    ein späterer LLM-Schritt zieht daraus einzelne Nachweise als Felder.
    """

    lot_id: str | None
    kind: str
    type_code: str | None
    text: str | None


@dataclass
class Award:
    """Kategorie 5: Wettbewerb je Zuschlag — Bieterzahl = Verdrängbarkeit.

    Verknüpft Gewinner mit dem konkreten Los (Weakness 3): eine Zeile =
    ein Los, gewonnen von einem Bieter, mit den Wettbewerbszahlen.
    """

    lot_id: str | None
    winner_name: str | None = None
    winner_national_id: str | None = None
    num_tenders: int | None = None
    num_tenders_sme: int | None = None
    num_tenders_other_eu: int | None = None
    num_tenders_non_eu: int | None = None
    num_tenders_electronic: int | None = None


@dataclass
class Notice:
    notice_id: str
    schema: str                      # 'legacy' | 'eforms'
    form_type: str | None
    country: str | None              # lead buyer, canonical alpha-2
    language: str | None             # original language of the freetext
    title: str | None
    description: str | None          # notice level, TED II.1.4
    description_field: str | None    # which field the text actually came from
    cpv_main: str | None
    cpv_all: list[str] = field(default_factory=list)
    lots: list[Lot] = field(default_factory=list)

    # Money and duration — first-class, because the product is about "how much"
    # and "until when". Both live under different tags in each schema
    # generation, exactly like the description did. Amounts as written; no FX
    # invented, so a non-EUR value keeps its currency and no *_eur is faked.
    estimated_value: float | None = None
    final_value: float | None = None
    value_currency: str | None = None
    award_date: str | None = None        # ISO date; TED's DATE_CONCLUSION / IssueDate
    start_date: str | None = None
    end_date: str | None = None

    # Who — extracted to columns so silver alone can answer "who bought / won"
    # without digging through the JSON blob.
    buyer_name: str | None = None
    buyer_national_id: str | None = None
    winner_names: list[str] = field(default_factory=list)
    performance_nuts: str | None = None   # Erfüllungsort (Weakness 6)
    contract_nature: str | None = None    # works | supplies | services (TED BT-23)
    procedure_type: str | None = None     # open | restricted | negotiated | ...
    submission_deadline: str | None = None
    portal_url: str | None = None

    # Vollständige Parteien, Kriterien, Zuschläge — Grundlage der Tabellen.
    parties: list[Party] = field(default_factory=list)
    criteria: list[Criterion] = field(default_factory=list)
    awards: list[Award] = field(default_factory=list)
    requirements: list[Requirement] = field(default_factory=list)
    notice_kind: str | None = None   # cn | can | pin | corrigendum | other

    # Every buyer's country, not just the lead's. Joint procurements have
    # several, and TED counts the notice towards each of them — so a DE run
    # must keep a Brussels-led notice that buys for an agency in Frankfurt.
    buyer_countries: list[str] = field(default_factory=list)

    # Alles, was nicht sauber durchlief. Leer heißt: keine Annahme nötig.
    flags: list[str] = field(default_factory=list)
    # Ländercodes, die im Dokument stehen, aber die Registry nicht kennt.
    unknown_country_codes: list[str] = field(default_factory=list)

    # Provenance. A claim like "in the last 3 tenders this happened" is only
    # worth anything if the reader can click through to the source.
    publication_number: str | None = None    # '330482-2023'
    oj_ref: str | None = None                # '2023/S 105-330482'
    publication_date: str | None = None      # ISO
    ted_url: str | None = None
    # Backward link to the notice this one refers to — for CANs, their own CN.
    ref_publication_number: str | None = None
    ref_oj: str | None = None
    ref_ted_url: str | None = None

    @property
    def has_description(self) -> bool:
        return bool(self.description) or any(lot.description for lot in self.lots)

    @property
    def descriptions(self) -> list[str]:
        """Notice-level and lot-level freetext, in document order."""
        texts = [self.description] if self.description else []
        texts += [lot.description for lot in self.lots if lot.description]
        return texts

    @property
    def text_length(self) -> int:
        return sum(len(t) for t in self.descriptions)


def _local(elem: ET.Element) -> str:
    tag = elem.tag
    return tag.split("}")[-1] if "}" in tag else tag


# TED-Vertragsnatur (BT-23), kanonisch als works|supplies|services abgelegt.
# Standard-Forms (2014–2021) kodieren NC_CONTRACT_NATURE@CODE: 1=Works, 2=Supplies,
# 4=Services (3=Works+Supplies, selten → kein sauberer Einzelwert). eForms tragen den
# Klartext direkt. Alt-/Textformate (<2014) haben kein sauberes Feld → None (CPV-Fallback in Gold).
_NC_NATURE_CODE = {"1": "works", "2": "supplies", "4": "services"}
_NATURE_CANON = {"works", "supplies", "services"}


def _iter_named(root: ET.Element, name: str) -> Iterator[ET.Element]:
    for elem in root.iter():
        if _local(elem) == name:
            yield elem


def _text_of(elem: ET.Element) -> str:
    return " ".join(t.strip() for t in elem.itertext() if t.strip())


def probe_countries(raw: bytes) -> set[str]:
    """Country codes mentioned anywhere in the file, as canonical alpha-2.

    Deliberately over-inclusive: it matches buyer country and place of
    performance alike. Use it to discard files cheaply, then confirm with
    :func:`parse` — never as the authoritative country of a notice.
    """
    found: set[str] = set()
    for pattern in (_RE_LEGACY_COUNTRY, _RE_EFORMS_COUNTRY, _RE_TEXT_COUNTRY, _RE_OJS_COUNTRY):
        for match in pattern.finditer(raw):
            try:
                found.add(countries.normalize(match.group(1).decode()))
            except KeyError:
                continue
    return found


def detect_schema(raw: bytes) -> str:
    return "legacy" if LEGACY_ROOT.encode() in raw[:400] else "eforms"


def raw_country_codes(raw: bytes) -> list[str]:
    """Every country code in the document, as written — unknown ones included.

    ``probe_countries`` silently drops codes the registry does not list, which
    is exactly what makes a notice unresolvable. For a review queue we need to
    see them: 'UKR' tells a human immediately why the buyer did not resolve.
    """
    codes: list[str] = []
    for pattern in (_RE_LEGACY_COUNTRY, _RE_EFORMS_COUNTRY, _RE_TEXT_COUNTRY, _RE_OJS_COUNTRY):
        for match in pattern.finditer(raw):
            code = match.group(1).decode()
            if code not in codes:
                codes.append(code)
    return codes


def _provenance(root: ET.Element, notice: Notice) -> None:
    """Fill publication number, OJ reference, date and links.

    ``NO_DOC_OJS`` appears twice: once directly under NOTICE_DATA (this
    notice, 100% of the time) and once under NOTICE_DATA/REF_NOTICE (the
    notice being referenced, 58%). Document order happens to put the own one
    first, but relying on that is fragile — select on the parent instead.
    """
    for notice_data in _iter_named(root, "NOTICE_DATA"):
        own, _ = _first_child_text(notice_data, ("NO_DOC_OJS",))
        notice.oj_ref = own
        notice.publication_number = publication_number_from_ojs(own)
        for ref in _iter_named(notice_data, "REF_NOTICE"):
            ref_ojs, _ = _first_child_text(ref, ("NO_DOC_OJS",))
            if ref_ojs:
                notice.ref_oj = ref_ojs
                notice.ref_publication_number = publication_number_from_ojs(ref_ojs)
                break
        break

    for ref_ojs in _iter_named(root, "REF_OJS"):
        date_text, _ = _first_child_text(ref_ojs, ("DATE_PUB",))
        if date_text and len(date_text) == 8 and date_text.isdigit():
            notice.publication_date = f"{date_text[:4]}-{date_text[4:6]}-{date_text[6:]}"
        break

    if not notice.publication_date:
        # eForms tragen KEIN REF_OJS/DATE_PUB — das Publikationsdatum steht in den TED-
        # Metadaten als efbc:PublicationDate (sonst cbc:IssueDate als Ersatzanker).
        # Ohne diesen Fallback fehlte ALLEN Notices ab 2024 das Datum (0 % Coverage),
        # weil TED auf eForms umgestellt hat.
        # WICHTIG: eForms enthalten MEHRERE efbc:PublicationDate (auch geplante Folge-
        # Veröffentlichungen, teils Jahre in der Zukunft — z. B. 2035 bei 508813-2026).
        # Das erste zu nehmen ist falsch. Verlässlich ist das cbc:IssueDate als DIREKTES
        # Kind der Wurzel; PublicationDate nur als Fallback und nur wenn plausibel.
        import datetime as _dt

        def _plausible(text: str) -> bool:
            if not (len(text) == 10 and text[4] == "-" and text[:4].isdigit()):
                return False
            year = int(text[:4])
            return 1990 <= year <= _dt.date.today().year + 1

        for child in root:                       # nur direkte Kinder → kein Nested-Treffer
            if _local(child) == "IssueDate":
                text = (child.text or "").strip()[:10]
                if _plausible(text):
                    notice.publication_date = text
                    break
        if not notice.publication_date:
            for tag in ("PublicationDate", "IssueDate"):
                for elem in _iter_named(root, tag):
                    text = (elem.text or "").strip()[:10]
                    if _plausible(text):
                        notice.publication_date = text
                        break
                if notice.publication_date:
                    break

    if not notice.publication_number:
        notice.publication_number = publication_number_from_id(notice.notice_id)
    notice.ted_url = notice_url(notice.publication_number)
    notice.ref_ted_url = notice_url(notice.ref_publication_number)


def _flag(notice: Notice, raw: bytes) -> None:
    """Alles markieren, was eine Annahme nötig machte.

    Bewusst auch für Notices, die wir behalten: 'kein Freitext' ist kein Grund
    zum Wegwerfen, aber ein Grund zum Nachsehen — der Freitext ist der Rohstoff
    der Extraktion.
    """
    if notice.form_type and notice.form_type not in KNOWN_FORM_TYPES:
        notice.flags.append(Flag.UNKNOWN_FORM)
    if not notice.has_description:
        notice.flags.append(Flag.NO_DESCRIPTION)
    if not notice.cpv_main:
        notice.flags.append(Flag.NO_CPV)
    if not notice.buyer_countries:
        notice.flags.append(Flag.NO_BUYER_COUNTRY)

    unknown = [
        code for code in raw_country_codes(raw)
        if not _is_known_country(code)
    ]
    if unknown:
        notice.unknown_country_codes = unknown
        notice.flags.append(Flag.UNKNOWN_COUNTRY_CODE)


def _is_known_country(code: str) -> bool:
    try:
        countries.resolve(code)
    except KeyError:
        return False
    return True


# --- TED-Plaintext (2004–~2012) --------------------------------------------
# Vor dem XML-Zeitalter lieferte TED ein Textformat mit 2-Buchstaben-Feldcodes
# (ND=Notice-ID, TI=Titel, AU=Käufer, PC=CPV, PD=Datum, TD=Dokumenttyp, TX=Body).
# Käufer/Titel/CPV/Datum sind strukturiert; der GEWINNER steht nur im TX-Freitext
# ("Name und Anschrift des Wirtschaftsteilnehmers …") — an DE 2010 zu ~96% sauber
# ziehbar. Wert/Bieterzahl best-effort.
_TD_KIND = {"0": "pin", "2": "corrigendum", "3": "cn", "7": "can", "V": "can",
            "D": "cn", "R": "other", "P": "pin", "1": "pin"}
_RE_TEXT_FIELD = re.compile(r"^([A-Z]{2}):\s?(.*)$")
# Freitext-Gewinner-Marker/Skip/„nicht vergeben" sind sprachspezifisch und liegen
# im aktiven Länder-Profil (locales.active()).


def _text_fields(text: str) -> dict[str, str]:
    """2-Buchstaben-Codes in ein Dict; Fortsetzungszeilen (eingerückt) anhängen."""
    fields: dict[str, list[str]] = {}
    cur: str | None = None
    for line in text.splitlines():
        m = _RE_TEXT_FIELD.match(line)
        if m:
            cur = m.group(1)
            fields.setdefault(cur, []).append(m.group(2))
        elif cur is not None:
            fields[cur].append(line.strip())
    return {k: "\n".join(v).strip() for k, v in fields.items()}


def _text_date(value: str | None) -> str | None:
    v = (value or "").strip()
    if re.fullmatch(r"\d{8}", v):
        return f"{v[:4]}-{v[4:6]}-{v[6:]}"
    return None


def _text_winners(tx: str) -> list[str]:
    """Gewinnernamen aus dem Freitext-Body ziehen (nach dem Wirtschaftsteilnehmer-Marker)."""
    loc = locales.active()
    names: list[str] = []
    for mark in loc.re_text_winner.finditer(tx):
        tail = tx[mark.end():mark.end() + 600]
        for line in (l.strip() for l in tail.splitlines()[1:] if l.strip()):
            if loc.text_not_awarded in line.lower():
                break
            if loc.re_text_skip.match(line) or len(line) < 4:
                continue
            if line not in names:
                names.append(line)
            break
    return names


def _parse_text(raw: bytes, notice_id: str) -> Notice:
    fields = _text_fields(flatten.decode_text(raw))
    nd = (fields.get("ND") or notice_id).split()[0].strip() or notice_id
    td = (fields.get("TD") or "").strip()
    kind = _TD_KIND.get(td[:1], "other")

    country = None
    cy = (fields.get("CY") or "").strip()[:2]
    if cy:
        try:
            country = countries.normalize(cy)
        except KeyError:
            country = None

    cpv_all = [c for c in (fields.get("PC") or "").split() if re.fullmatch(r"\d{8}", c)]
    cpv_main = cpv_all[0] if cpv_all else None
    tx = fields.get("TX") or ""

    parties: list[Party] = []
    au = (fields.get("AU") or "").strip()
    if au:
        parties.append(Party(role="buyer", name=au,
                             town=(fields.get("TW") or "").strip() or None, country=country))

    awards: list[Award] = []
    winner_names: list[str] = []
    if kind == "can":
        for name in _text_winners(tx):
            parties.append(Party(role="winner", name=name))
            winner_names.append(name)
            awards.append(Award(lot_id=None, winner_name=name))

    notice = Notice(
        notice_id=nd, schema="text", form_type=(td or None), notice_kind=kind,
        country=country, language=(fields.get("OL") or None),
        title=(fields.get("TI") or None), description=(tx or None),
        description_field=("TX" if tx else None),
        cpv_main=cpv_main, cpv_all=cpv_all, publication_date=_text_date(fields.get("PD")),
        parties=parties, awards=awards, winner_names=winner_names,
        publication_number=nd, oj_ref=(fields.get("OJ") or None),
        ted_url=notice_url(nd),
    )
    return notice


# INTERNAL_OJS (opoce, ~2008): eigenes OJS-DTD, das TED für einzelne Monate statt
# des Standardschemas auslieferte (gemessen: 2008-05). Mehrsprachig — je eine Datei
# pro Sprache (…_2008.de/.en/…); ``_walk`` wählt beim DE-Ingest die .de-Edition.
# Viele Tags teilt es mit dem Legacy-Schema (ISO_COUNTRY, CPV_CODE, VALUE_COST,
# CONTRACT_AWARD_DATE) → Helfer wiederverwendbar; Land/Werte/Daten aber in eigener
# Notation (Element-Text statt Attribut, YYYYMMDD, „100 000,00").
OJS_ROOT = "INTERNAL_OJS"
_OJS_KIND = {
    "CONTRACT": "cn", "CONTRACT_UTILITIES": "cn", "CONTRACT_DEFENCE": "cn",
    "CONCESSION": "cn", "QUALIFICATION_SYSTEM_UTILITIES": "cn", "DESIGN_CONTEST": "cn",
    "CONTRACT_AWARD": "can", "CONTRACT_AWARD_UTILITIES": "can",
    "CONTRACT_AWARD_DEFENCE": "can", "RESULT_DESIGN_CONTEST": "can",
    "CONTRACT_SUM": "can", "CONTRACT_UTILITIES_SUM": "can",
    "CONTRACT_AWARD_SUM": "can", "CONTRACT_AWARD_UTILITIES_SUM": "can",
    "PRIOR_INFORMATION": "pin", "PERIODIC_INDICATIVE_UTILITIES": "pin",
    "OTH_NOT": "corrigendum", "EEIG": "other",
}
# „D-Schwerin: Personenbeförderung per Bahn" → Präfix (Land) + Ort + Titel.
_RE_OJS_TI = re.compile(r"^[A-Z]{1,3}-[^:]+:\s*(.+)$", re.S)


def _ojs_compact_date(text: str | None) -> str | None:
    """OJS-Datum ``20080502`` / ``20080630 13:00`` → ``2008-05-02``."""
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())[:8]
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return None


def _ojs_amount(text: str | None) -> float | None:
    """OJS-Betrag ``100 000,00`` / ``1.234.567,89`` → float (Leerzeichen/Punkt =
    Tausender, Komma = Dezimal). Das generische ``_to_amount`` wirft hier Komma
    weg und liest das 100-Fache — darum eine eigene, europäische Lesart."""
    if not text:
        return None
    cleaned = text.strip().replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _ojs_addr_field(addr: ET.Element, tag: str) -> str | None:
    for elem in _iter_named(addr, tag):
        val = _text_of(elem)
        if val:
            return val
    return None


def _parse_internal_ojs(root: ET.Element, notice_id: str) -> Notice:
    # Der Formularkörper (erstes Kind nach TECHNICAL_INFO/BIB_INFO) trägt den Typ.
    form_type = None
    for child in root:
        name = _local(child)
        if name not in ("TECHNICAL_INFO", "BIB_INFO"):
            form_type = name
            break

    country = None
    for elem in _iter_named(root, "ISO_COUNTRY"):
        code = (elem.attrib.get("VALUE") or elem.text or "").strip()
        if code:
            try:
                country = countries.normalize(code)
            except KeyError:
                country = None
            break

    language = None
    for elem in _iter_named(root, "LG_ORIG"):
        language = (elem.text or "").strip() or None
        break

    title = None
    town_from_title = None
    for tidoc in _iter_named(root, "TI_DOC"):
        heads = [_text_of(p) for p in tidoc if _local(p) == "P"]
        heads = [h for h in heads if h]
        if heads:
            head = heads[0]
            if "-" in head and ":" in head:
                town_from_title = head.split("-", 1)[1].split(":", 1)[0].strip() or None
            m = _RE_OJS_TI.match(head)
            title = (m.group(1).strip() if m else head) or None
            break

    cpv_all: list[str] = []
    for tag in ("ORIGINAL_CPV", "CPV_CODE"):
        for elem in _iter_named(root, tag):
            code = (elem.attrib.get("CODE") or elem.text or "").strip()
            if re.fullmatch(r"\d{8}", code) and code not in cpv_all:
                cpv_all.append(code)

    performance_nuts = None
    for elem in _iter_named(root, "ORIGINAL_NUTS"):
        performance_nuts = (elem.attrib.get("CODE") or elem.text or "").strip() or None
        if performance_nuts:
            break

    publication_date = None
    for elem in _iter_named(root, "DATE_PUB"):
        publication_date = _ojs_compact_date(elem.text)
        if publication_date:
            break
    submission_deadline = None
    for tag in ("DEADLINE_REC", "DEADLINE_REQ"):
        for elem in _iter_named(root, tag):
            submission_deadline = _ojs_compact_date(elem.text)
            if submission_deadline:
                break
        if submission_deadline:
            break
    award_date = _legacy_composite_date(root, "CONTRACT_AWARD_DATE")

    # Gewinner: ORGANISATION unter jedem AWARD_OF_CONTRACT (ECONOMIC_OPERATOR…).
    award_org_ids: set[int] = set()
    winners: list[str] = []
    awards: list[Award] = []
    parties: list[Party] = []
    final_total = 0.0
    currency = None
    for aoc in _iter_named(root, "AWARD_OF_CONTRACT"):
        for org in _iter_named(aoc, "ORGANISATION"):
            award_org_ids.add(id(org))
        winner_name = None
        for eo in _iter_named(aoc, "ECONOMIC_OPERATOR_NAME_ADDRESS"):
            winner_name = _ojs_addr_field(eo, "ORGANISATION")
            if winner_name:
                break
        if winner_name and winner_name not in winners:
            winners.append(winner_name)
            parties.append(Party(role="winner", name=winner_name,
                                 town=None, country=None))
        awards.append(Award(lot_id=None, winner_name=winner_name))
        for costs in _iter_named(aoc, "COSTS_RANGE_AND_CURRENCY_WITH_VAT_RATE"):
            # _to_amount liest europäische Beträge („100 000,00") falsch → _ojs_amount.
            for vc in _iter_named(costs, "VALUE_COST"):
                amt = _ojs_amount(vc.text)
                if amt is not None:
                    final_total += amt
                    currency = currency or costs.attrib.get("CURRENCY")
                break
    final_value = final_total or None

    estimated_value = None
    for est in _iter_named(root, "INITIAL_ESTIMATED_TOTAL_VALUE_CONTRACT"):
        for vc in _iter_named(est, "VALUE_COST"):
            estimated_value = _ojs_amount(vc.text)
            currency = currency or est.attrib.get("CURRENCY")
            break
        if estimated_value is not None:
            break

    # Käufer: erste ORGANISATION, die NICHT zu einem Zuschlag (Gewinner) gehört.
    buyer_name = None
    buyer = None
    for org in _iter_named(root, "ORGANISATION"):
        if id(org) in award_org_ids:
            continue
        name = _text_of(org)
        if name:
            buyer_name = name
            buyer = org
            break
    buyer_town = buyer_email = buyer_phone = buyer_postal = None
    if buyer is not None:
        # Adressfelder aus demselben Adressblock (nächster Vorfahr) ziehen.
        parent_map = {c: p for p in root.iter() for c in p}
        block = buyer
        for _ in range(4):
            block = parent_map.get(block, block)
            if block is None:
                break
            if any(_local(c) in ("TOWN", "E_MAIL", "PHONE", "POSTAL_CODE") for c in block.iter()):
                break
        buyer_town = _ojs_addr_field(block, "TOWN") or town_from_title
        buyer_email = _ojs_addr_field(block, "E_MAIL")
        buyer_phone = _ojs_addr_field(block, "PHONE")
        buyer_postal = _ojs_addr_field(block, "POSTAL_CODE")
    parties.insert(0, Party(role="buyer", name=buyer_name, town=buyer_town,
                            postal_code=buyer_postal, country=country,
                            email=buyer_email, phone=buyer_phone))

    description = None
    description_field = None
    for tag in ("SHORT_CONTRACT_DESCRIPTION", "SHORT_DESCR", "SHORT_DESCRIPTION",
                "OBJECT_DESCR", "TOTAL_QUANTITY_OR_SCOPE", "OBJ_NOT", "CONTENTS"):
        for elem in _iter_named(root, tag):
            text = _text_of(elem)
            if text:
                description = text
                description_field = tag
                break
        if description:
            break

    pubnum = notice_id.replace("_", "-") if notice_id else None

    return Notice(
        notice_id=notice_id,
        schema="ojs",
        form_type=form_type,
        country=country,
        language=language,
        title=title,
        description=description,
        description_field=description_field,
        cpv_main=cpv_all[0] if cpv_all else None,
        cpv_all=cpv_all,
        estimated_value=estimated_value,
        final_value=final_value,
        value_currency=currency,
        award_date=award_date,
        buyer_name=buyer_name,
        winner_names=winners,
        performance_nuts=performance_nuts,
        submission_deadline=submission_deadline,
        parties=parties,
        awards=awards,
        notice_kind=_OJS_KIND.get(form_type, "other"),
        buyer_countries=[country] if country else [],
        publication_number=pubnum,
        publication_date=publication_date,
        ted_url=notice_url(pubnum),
    )


def parse(raw: bytes, notice_id: str) -> Notice:
    # TED-Textformat (vor-XML): kein '<' am Anfang → eigener Parser.
    if not raw.lstrip()[:1] == b"<":
        return _parse_text(raw, notice_id)
    root = ET.fromstring(raw)
    if _local(root) == LEGACY_ROOT:
        notice = _parse_legacy(root, notice_id)
    elif _local(root) == OJS_ROOT:
        notice = _parse_internal_ojs(root, notice_id)
    else:
        notice = _parse_eforms(root, notice_id)
    _provenance(root, notice)
    _flag(notice, raw)
    return notice


def _original_form(root: ET.Element) -> tuple[ET.Element | None, str | None]:
    """Return the form body in its original language.

    Most notices carry a single FORM_SECTION child, but ~1% carry translations
    too — up to 24 language variants in one file. Picking the first child there
    yields whatever language happens to come first, so select on CATEGORY.
    """
    for section in _iter_named(root, "FORM_SECTION"):
        children = list(section)
        if not children:
            continue
        for child in children:
            if child.attrib.get("CATEGORY") == "ORIGINAL":
                return child, child.attrib.get("LG")
        return children[0], children[0].attrib.get("LG")
    return None, None


def _first_child_text(parent: ET.Element, names: tuple[str, ...]) -> tuple[str | None, str | None]:
    """Text of the first direct child matching ``names``.

    Direct children only: ``OBJECT_CONTRACT`` holds the notice-level
    description *and* nests one ``OBJECT_DESCR`` per lot, each with its own.
    A descendant search would conflate the two.
    """
    for child in parent:
        name = _local(child)
        if name in names:
            text = _text_of(child)
            if text:
                return text, name
    return None, None


# Every legacy form family names the description differently. Measured against
# DE 2016-01, each family uses exactly one of these, at 100% coverage:
#
#   F0x_2014                                    SHORT_DESCR
#   CONTRACT, CONTRACT_AWARD, *_DEFENCE,
#   CONTRACT_UTILITIES                          SHORT_CONTRACT_DESCRIPTION
#   CONTRACT_AWARD_UTILITIES                    SHORT_DESCRIPTION
#   RESULT_DESIGN_CONTEST                       DESCRIPTION
#   OTH_NOT (corrigenda)                        CONTENTS
#   PRIOR_INFORMATION                           TOTAL_QUANTITY_OR_SCOPE
#
# Order matters. TOTAL_QUANTITY_OR_SCOPE also appears in CONTRACT (81%) as a
# *secondary* field next to the real description, so it must stay last —
# otherwise it overwrites the right answer on the most common form of all.
#   DESIGN_CONTEST                              SHORT_DESCRIPTION_CONTRACT
#   PERIODIC_INDICATIVE_UTILITIES               DESCRIPTION_OF_CONTRACT
#   EEIG                                        TXT_MARK
DESCRIPTION_FIELDS = (
    "SHORT_DESCR",
    "SHORT_CONTRACT_DESCRIPTION",
    "SHORT_DESCRIPTION",
    "SHORT_DESCRIPTION_CONTRACT",
    "DESCRIPTION_OF_CONTRACT",
    "DESCRIPTION",
    "CONTENTS",
    "TXT_MARK",
    "TOTAL_QUANTITY_OR_SCOPE",
)

# Only the 2014 forms carry a notice-level description next to per-lot ones.
# On the older families the notice level is the only level.
NOTICE_LEVEL_FIELDS = ("SHORT_DESCR", "SHORT_CONTRACT_DESCRIPTION")


def _legacy_descriptions(scope: ET.Element) -> tuple[str | None, str | None, list[Lot]]:
    description: str | None = None
    description_field: str | None = None
    lots: list[Lot] = []

    for container in _iter_named(scope, "OBJECT_CONTRACT"):
        description, description_field = _first_child_text(container, NOTICE_LEVEL_FIELDS)
        for lot_elem in _iter_named(container, "OBJECT_DESCR"):
            lot_text, _ = _first_child_text(lot_elem, NOTICE_LEVEL_FIELDS)
            lot_title, _ = _first_child_text(lot_elem, ("TITLE",))
            lot_no, _ = _first_child_text(lot_elem, ("LOT_NO",))
            if lot_text or lot_title:
                lot = Lot(lot_id=lot_no, title=lot_title, description=lot_text)
                _legacy_lot_terms(lot_elem, lot)
                lots.append(lot)
        break

    # Pre-2014 and defence forms use neither OBJECT_CONTRACT nor OBJECT_DESCR;
    # fall back to the first description found anywhere in the form.
    if description is None and not lots:
        for candidate in DESCRIPTION_FIELDS:
            for elem in _iter_named(scope, candidate):
                text = _text_of(elem)
                if text:
                    return text, candidate, lots
    return description, description_field, lots


def _to_int(text: str | None) -> int | None:
    amount = _to_amount(text)
    return int(amount) if amount is not None else None


def _legacy_lot_terms(lot_elem: ET.Element, lot: Lot) -> None:
    """Kategorie 6/2/6 für ein Legacy-Los: Laufzeit, Optionen, CPV, Ort."""
    # Los-CPV (Weakness 2): CPV_CODE innerhalb dieses OBJECT_DESCR.
    for elem in _iter_named(lot_elem, "CPV_CODE"):
        code = (elem.attrib.get("CODE") or elem.text or "").strip()
        if code and code not in lot.cpv_all:
            lot.cpv_all.append(code)
    # Erfüllungsort (Weakness 6): NUTS des Loses.
    for elem in _iter_named(lot_elem, "NUTS"):
        lot.performance_nuts = elem.attrib.get("CODE") or (elem.text or "").strip() or None
        break
    for elem in _iter_named(lot_elem, "DURATION"):
        if elem.attrib.get("TYPE") == "MONTH":
            lot.duration_months = _to_int(elem.text)
        elif elem.attrib.get("TYPE") == "YEAR":
            years = _to_int(elem.text)
            lot.duration_months = years * 12 if years else lot.duration_months
        break
    if any(_local(e) == "OPTIONS" for e in lot_elem.iter()):
        lot.has_options = True
    elif any(_local(e) == "NO_OPTIONS" for e in lot_elem.iter()):
        lot.has_options = False
    lot.options_description = next(
        (_text_of(e) for e in _iter_named(lot_elem, "OPTIONS_DESCR") if _text_of(e)), None)
    if any(_local(e) == "RENEWAL" for e in lot_elem.iter()):
        lot.has_renewal = True
    elif any(_local(e) == "NO_RENEWAL" for e in lot_elem.iter()):
        lot.has_renewal = False
    lot.renewal_description = next(
        (_text_of(e) for e in _iter_named(lot_elem, "RENEWAL_DESCR") if _text_of(e)), None)
    for elem in _iter_named(lot_elem, "NUMBER_POSSIBLE_RENEWALS"):
        lot.max_renewals = _to_int(elem.text)
        break


# Verfahrensart, über beide Generationen vereinheitlicht.
_LEGACY_PROCEDURE = {
    "PT_OPEN": "open",
    "PT_RESTRICTED": "restricted",
    "PT_NEGOTIATED_WITH_PRIOR_CALL": "negotiated",
    "PT_NEGOTIATED_WITH_COMPETITION": "negotiated",
    "PT_INVOLVING_NEGOTIATION": "negotiated",
    "PT_COMPETITIVE_NEGOTIATION": "negotiated",
    "PT_NEGOTIATED_WITHOUT_PUBLICATION": "negotiated_no_call",
    "PT_NEGOTIATED_WITHOUT_COMPETITION": "negotiated_no_call",
    "PT_AWARD_CONTRACT_WITHOUT_CALL": "negotiated_no_call",
    "PT_COMPETITIVE_DIALOGUE": "competitive_dialogue",
    "PT_INNOVATION_PARTNERSHIP": "innovation",
}
_EFORMS_PROCEDURE = {
    "open": "open", "restricted": "restricted",
    "neg-w-call": "negotiated", "neg-wo-call": "negotiated_no_call",
    "comp-dial": "competitive_dialogue", "innovation": "innovation",
    "comp-tend": "negotiated", "oth-mult": "other", "oth-single": "other",
}


def _legacy_procedure_type(scope: ET.Element) -> str | None:
    for elem in scope.iter():
        mapped = _LEGACY_PROCEDURE.get(_local(elem))
        if mapped:
            return mapped
    return None


def _to_amount(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = text.strip().replace(" ", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _to_iso_date(text: str | None) -> str | None:
    """Normalise a TED date to YYYY-MM-DD.

    eForms stamps a timezone (``2024-07-01+02:00``); legacy is already plain.
    We keep the calendar date — the offset never matters for "when does this
    contract end".
    """
    if not text:
        return None
    text = text.strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        candidate = text[:10]
        if candidate[:4].isdigit():
            return candidate
    return None


def _first_amount(scope: ET.Element, tags: tuple[str, ...],
                  currency_attrs: tuple[str, ...]) -> tuple[float | None, str | None]:
    for tag in tags:
        for elem in _iter_named(scope, tag):
            amount = _to_amount(elem.text)
            if amount is None:
                continue
            currency = None
            for attr in currency_attrs:
                if attr in elem.attrib:
                    currency = elem.attrib[attr]
                    break
            return amount, currency
    return None, None


def _first_date(scope: ET.Element, tags: tuple[str, ...]) -> str | None:
    for tag in tags:
        for elem in _iter_named(scope, tag):
            iso = _to_iso_date(elem.text)
            if iso:
                return iso
    return None


def _legacy_composite_date(scope: ET.Element, tag: str) -> str | None:
    """Vor-2014-Datum aus DAY/MONTH/YEAR-Kindern zusammensetzen → ISO."""
    for elem in _iter_named(scope, tag):
        parts: dict[str, int] = {}
        for child in elem:
            loc = _local(child)
            val = (child.text or "").strip()
            if loc in ("DAY", "MONTH", "YEAR") and val.isdigit():
                parts[loc] = int(val)
        if {"DAY", "MONTH", "YEAR"} <= parts.keys():
            try:
                return f"{parts['YEAR']:04d}-{parts['MONTH']:02d}-{parts['DAY']:02d}"
            except (ValueError, KeyError):
                pass
    return None


_RE_ARGE = re.compile(r"\b(arge|arbeitsgemeinschaft|bietergemeinschaft|konsortium)\b", re.I)
# Orgs, die im eForms-SettledContract als SignatoryParty auftauchen können, aber
# NIE der Gewinner sind: Nachprüfstelle (Vergabekammer) und der technische eSender.
_RE_EFORMS_NONWINNER = re.compile(
    r"vergabekammer|beschaffungsamt des bmi|datenservice öffentlicher", re.I)


def _mark_consortium(parties: list[Party]) -> None:
    """Gewinner als Konsortial-Gewinn markieren.

    Ein Gewinn zählt als Konsortium, wenn die Vergabe *mehrere* Gewinner hat
    (der häufige Fall — 10–28% der Vergaben) oder der Gewinnername ARGE/
    Bietergemeinschaft nennt. So lässt sich je Firma auswerten: 'X Wins, davon
    Y im Konsortium' — eine Charakteristik, die wir ausgeben können.
    """
    winners = [p for p in parties if p.role == "winner"]
    multiple = len(winners) > 1
    for w in winners:
        w.in_consortium = bool(multiple or (w.name and _RE_ARGE.search(w.name)))


def _legacy_party(block: ET.Element, role: str) -> Party:
    def g(tag: str) -> str | None:
        return next((_text_of(e) for e in _iter_named(block, tag) if _text_of(e)), None)
    country = None
    for elem in _iter_named(block, "COUNTRY"):
        country = elem.attrib.get("VALUE") or (elem.text or "").strip() or None
        break
    nuts = None
    for elem in _iter_named(block, "NUTS"):
        nuts = elem.attrib.get("CODE")
        break
    if country:
        try:
            country = countries.normalize(country)
        except KeyError:
            pass
    return Party(
        role=role,
        name=g("OFFICIALNAME"),
        national_id=g("NATIONALID"),
        town=g("TOWN"),
        postal_code=g("POSTAL_CODE"),
        country=country,
        nuts=nuts,
        email=g("E_MAIL"),
        phone=g("PHONE"),
        contact_person=g("CONTACT_POINT"),
        url=g("URL_GENERAL") or g("URL_BUYER"),
        is_sme=any(_local(e) == "SME" for e in block.iter()),
    )


def _legacy_parties(root: ET.Element) -> list[Party]:
    # Konsortium wird pro AWARD_CONTRACT-Block gesetzt (siehe unten), nicht
    # notice-weit — mehrere Los-Gewinner sind kein Konsortium.
    return __legacy_parties_impl(root)


def __legacy_parties_impl(root: ET.Element) -> list[Party]:
    parties: list[Party] = []
    # Käufer-Block: 2014er nutzt ADDRESS_CONTRACTING_BODY, vor-2014 (R2.0.x) die
    # NAME_ADDRESSES_CONTACT_*-Blöcke. Erster Treffer gewinnt.
    for buyer_tag in ("ADDRESS_CONTRACTING_BODY", "NAME_ADDRESSES_CONTACT_CONTRACT_AWARD",
                      "NAME_ADDRESSES_CONTACT_CONTRACT", "NAME_ADDRESSES_CONTACT_PRIOR_INFORMATION"):
        block = next(_iter_named(root, buyer_tag), None)
        if block is not None:
            parties.append(_legacy_party(block, "buyer"))
            break

    # Konsortium wird PRO LOS bestimmt: mehrere CONTRACTOR im *selben*
    # AWARD_CONTRACT-Block gewinnen gemeinsam ein Los. Mehrere Blöcke mit je
    # einem Gewinner sind dagegen unabhängige Los-Gewinner — kein Konsortium.
    seen = set()
    for awarded in _iter_named(root, "AWARD_CONTRACT"):
        contractors = list(_iter_named(awarded, "CONTRACTOR"))
        consortium = len(contractors) > 1
        for contractor in contractors:
            seen.add(id(contractor))
            w = _legacy_party(contractor, "winner")
            w.in_consortium = consortium or bool(w.name and _RE_ARGE.search(w.name))
            parties.append(w)
    # CONTRACTOR außerhalb eines AWARD_CONTRACT (seltene Formen): einzeln.
    for contractor in _iter_named(root, "CONTRACTOR"):
        if id(contractor) in seen:
            continue
        w = _legacy_party(contractor, "winner")
        w.in_consortium = bool(w.name and _RE_ARGE.search(w.name))
        parties.append(w)

    # Vor-2014 (R2.0.x): Gewinner stecken in AWARD_OF_CONTRACT →
    # ECONOMIC_OPERATOR_NAME_ADDRESS (andere Struktur als AWARD_CONTRACT/CONTRACTOR).
    # Mehrere Operatoren im selben Block = Konsortium pro Los.
    for awarded in _iter_named(root, "AWARD_OF_CONTRACT"):
        operators = list(_iter_named(awarded, "ECONOMIC_OPERATOR_NAME_ADDRESS"))
        consortium = len(operators) > 1
        for operator in operators:
            w = _legacy_party(operator, "winner")
            if w.name:
                w.in_consortium = consortium or bool(_RE_ARGE.search(w.name))
                parties.append(w)

    for block in _iter_named(root, "ADDRESS_REVIEW_BODY"):
        parties.append(_legacy_party(block, "review"))
        break
    for block in _iter_named(root, "ADDRESS_MEDIATION_BODY"):
        parties.append(_legacy_party(block, "mediation"))
        break
    return parties


# Legacy LEFTI-Feld → vereinheitlichte Art.
_LEGACY_REQ = {
    "SUITABILITY": "suitability",
    "ECONOMIC_FINANCIAL_INFO": "economic",
    "ECONOMIC_FINANCIAL_MIN_LEVEL": "economic",
    "TECHNICAL_PROFESSIONAL_INFO": "technical",
    "TECHNICAL_PROFESSIONAL_MIN_LEVEL": "technical",
    "PERFORMANCE_CONDITIONS": "performance",
    "PARTICULAR_PROFESSION": "profession",
    "DEPOSIT_GUARANTEE_REQUIRED": "deposit",
}
# eForms SelectionCriteria-Code → Art. Die Ausschlussgründe kommen separat.
_EFORMS_SELECTION = {
    "sui-act": "suitability",
    "ef-stand": "economic",
    "tp-abil": "technical",
}


def _legacy_requirements(scope: ET.Element) -> list[Requirement]:
    """Kategorie 9 legacy: die LEFTI-Bedingungen (Notice-Ebene)."""
    reqs: list[Requirement] = []
    for tag, kind in _LEGACY_REQ.items():
        for elem in _iter_named(scope, tag):
            text = _text_of(elem)
            if text:
                reqs.append(Requirement(lot_id=None, kind=kind, type_code=tag, text=text))
    return reqs


def _eforms_requirements(root: ET.Element) -> list[Requirement]:
    """Kategorie 9 eForms: Eignungskriterien + Ausschlussgründe."""
    reqs: list[Requirement] = []
    parents = {c: e for e in root.iter() for c in e}

    def lot_of(elem: ET.Element) -> str | None:
        cur = elem
        for _ in range(8):
            cur = parents.get(cur)
            if cur is None:
                return None
            if _local(cur) == "ProcurementProjectLot":
                return next((_first_child_text(c, ("ID",))[0]
                             for c in cur if _local(c) == "ID"), None)
        return None

    # Keep a requirement if it has text OR a code. A coded ground with no free
    # text is still a real condition ('bankruptcy', 'ef-stand') — dropping it
    # because it lacks prose would hide a constraint a bidder might fail.
    for crit in _iter_named(root, "SelectionCriteria"):
        code = next((_text_of(e) for e in _iter_named(crit, "CriterionTypeCode")
                     if _text_of(e)), None)
        text = next((_text_of(e) for e in _iter_named(crit, "Description")
                     if _text_of(e)), None)
        if text or code:
            reqs.append(Requirement(lot_id=lot_of(crit),
                                    kind=_EFORMS_SELECTION.get(code, "sonstiges"),
                                    type_code=code, text=text))
    for req in _iter_named(root, "SpecificTendererRequirement"):
        code = next((_text_of(e) for e in _iter_named(req, "TendererRequirementTypeCode")
                     if _text_of(e)), None)
        text = next((_text_of(e) for e in _iter_named(req, "Description")
                     if _text_of(e)), None)
        if text or code:
            reqs.append(Requirement(lot_id=lot_of(req), kind="exclusion",
                                    type_code=code, text=text))
    return reqs


def _legacy_awards(root: ET.Element) -> list[Award]:
    """Kategorie 5: je vergebenem Los die Bieterzahlen."""
    awards: list[Award] = []
    for awarded in _iter_named(root, "AWARD_CONTRACT"):
        lot_no, _ = _first_child_text(awarded, ("LOT_NO",))
        tenders = next((t for t in _iter_named(awarded, "TENDERS")), None)
        scope = tenders if tenders is not None else awarded

        def n(tag: str) -> int | None:
            return next((_to_int(e.text) for e in _iter_named(scope, tag)), None)

        # Gewinner dieses Loses (Weakness 3).
        winner_name = winner_id = None
        for contractor in _iter_named(awarded, "CONTRACTOR"):
            winner_name = next((_text_of(e) for e in _iter_named(contractor, "OFFICIALNAME")
                                if _text_of(e)), None)
            winner_id = next((_text_of(e) for e in _iter_named(contractor, "NATIONALID")
                              if _text_of(e)), None)
            break

        award = Award(
            lot_id=lot_no,
            winner_name=winner_name,
            winner_national_id=winner_id,
            num_tenders=n("NB_TENDERS_RECEIVED"),
            num_tenders_sme=n("NB_TENDERS_RECEIVED_SME"),
            num_tenders_other_eu=n("NB_TENDERS_RECEIVED_OTHER_EU"),
            num_tenders_non_eu=n("NB_TENDERS_RECEIVED_NON_EU"),
            num_tenders_electronic=n("NB_TENDERS_RECEIVED_EMEANS"),
        )
        if winner_name or any(getattr(award, f) is not None for f in
               ("num_tenders", "num_tenders_sme", "num_tenders_electronic")):
            awards.append(award)

    # Vor-2014 (R2.0.x): AWARD_OF_CONTRACT mit LOT_NUMBER, OFFERS_RECEIVED_NUMBER
    # und ECONOMIC_OPERATOR_NAME_ADDRESS als Gewinner.
    for awarded in _iter_named(root, "AWARD_OF_CONTRACT"):
        lot_no, _ = _first_child_text(awarded, ("LOT_NUMBER",))
        winner_name = None
        for operator in _iter_named(awarded, "ECONOMIC_OPERATOR_NAME_ADDRESS"):
            winner_name = next((_text_of(e) for e in _iter_named(operator, "OFFICIALNAME")
                                if _text_of(e)), None)
            break
        offers = next((_to_int(e.text) for e in _iter_named(awarded, "OFFERS_RECEIVED_NUMBER")
                       if _to_int(e.text) is not None), None)
        if winner_name or offers is not None:
            awards.append(Award(lot_id=lot_no, winner_name=winner_name, num_tenders=offers))
    return awards


def _legacy_criteria(scope: ET.Element) -> list[Criterion]:
    criteria: list[Criterion] = []
    for kind, tag in (("quality", "AC_QUALITY"), ("cost", "AC_COST"), ("price", "AC_PRICE")):
        for elem in _iter_named(scope, tag):
            name, _ = _first_child_text(elem, ("AC_CRITERION",))
            weight, _ = _first_child_text(elem, ("AC_WEIGHTING",))
            if kind == "price" and name is None:
                name = "Preis"
            criteria.append(Criterion(lot_id=None, kind=kind, name=name, weight=weight))
    return criteria


# Legacy form → notice kind. TED form numbers encode the type.
_LEGACY_KIND = {
    "F01_2014": "pin", "F02_2014": "cn", "F03_2014": "can",
    "F04_2014": "pin", "F05_2014": "cn", "F06_2014": "can",
    "F12_2014": "cn", "F13_2014": "can", "F15_2014": "other",
    "F20_2014": "corrigendum", "F21_2014": "cn", "F22_2014": "cn",
    "F24_2014": "cn", "F25_2014": "can",
    "CONTRACT": "cn", "CONTRACT_AWARD": "can", "PRIOR_INFORMATION": "pin",
    "CONTRACT_AWARD_UTILITIES": "can", "CONTRACT_UTILITIES": "cn",
    "OTH_NOT": "corrigendum",
}
_EFORMS_KIND = {
    "ContractNotice": "cn", "ContractAwardNotice": "can",
    "PriorInformationNotice": "pin",
    "BusinessRegistrationInformationNotice": "other",
}


def _parse_legacy(root: ET.Element, notice_id: str) -> Notice:
    form, language = _original_form(root)
    scope = form if form is not None else root

    form_type = _local(form) if form is not None else None

    country = None
    for elem in _iter_named(root, "ISO_COUNTRY"):
        code = elem.attrib.get("VALUE") or (elem.text or "")
        if code.strip():
            try:
                country = countries.normalize(code)
            except KeyError:
                country = None
            break

    description, description_field, lots = _legacy_descriptions(scope)

    title = None
    for candidate in ("TITLE", "TITLE_CONTRACT", "TI_TEXT"):
        for elem in _iter_named(scope, candidate):
            text = _text_of(elem)
            if text:
                title = text
                break
        if title:
            break

    cpv_all: list[str] = []
    for elem in _iter_named(root, "CPV_CODE"):
        code = (elem.attrib.get("CODE") or elem.text or "").strip()
        if code and code not in cpv_all:
            cpv_all.append(code)

    if language is None:
        for elem in _iter_named(root, "LG_ORIG"):
            language = (elem.text or "").strip() or None
            break

    estimated, cur_e = _first_amount(scope, ("VAL_ESTIMATED_TOTAL",), ("CURRENCY",))
    final, cur_f = _first_amount(scope, ("VAL_TOTAL",), ("CURRENCY",))
    if final is None:
        # Vor-2014: Endwert je Los in COSTS_RANGE_AND_CURRENCY_WITH_VAT_RATE/VALUE_COST.
        total = 0.0
        for costs in _iter_named(scope, "COSTS_RANGE_AND_CURRENCY_WITH_VAT_RATE"):
            amt, cur = _first_amount(costs, ("VALUE_COST",), ("CURRENCY",))
            if amt is not None:
                total += amt
                cur_f = cur_f or cur
        if total:
            final = total
    award_date = (_first_date(scope, ("DATE_CONCLUSION_CONTRACT",))
                  or _legacy_composite_date(scope, "CONTRACT_AWARD_DATE"))
    start_date = _first_date(scope, ("DATE_START",))
    end_date = _first_date(scope, ("DATE_END",))

    performance_nuts = None       # Weakness 6: coded auf Notice-Ebene
    for elem in _iter_named(root, "PERFORMANCE_NUTS"):
        performance_nuts = elem.attrib.get("CODE") or (elem.text or "").strip() or None
        if performance_nuts:
            break

    contract_nature = None        # BT-23: NC_CONTRACT_NATURE@CODE → works|supplies|services
    for elem in _iter_named(root, "NC_CONTRACT_NATURE"):
        contract_nature = _NC_NATURE_CODE.get((elem.attrib.get("CODE") or "").strip())
        if contract_nature:
            break

    procedure_type = _legacy_procedure_type(scope)
    submission_deadline = _first_date(scope, ("DATE_RECEIPT_TENDERS",))
    portal_url = None
    for tag in ("URL_PARTICIPATION", "URL_DOCUMENT"):
        for elem in _iter_named(root, tag):
            portal_url = (elem.text or "").strip() or None
            if portal_url:
                break
        if portal_url:
            break

    buyer_name = None
    for body in _iter_named(root, "ADDRESS_CONTRACTING_BODY"):
        buyer_name, _ = _first_child_text(body, ("OFFICIALNAME",))
        if buyer_name:
            break
    buyer_id = None
    for body in _iter_named(root, "ADDRESS_CONTRACTING_BODY"):
        buyer_id, _ = _first_child_text(body, ("NATIONALID",))
        if buyer_id:
            break
    winners: list[str] = []
    for contractor in _iter_named(root, "CONTRACTOR"):
        # OFFICIALNAME sits under CONTRACTOR/ADDRESS_CONTRACTOR, not directly.
        name = next((_text_of(e) for e in _iter_named(contractor, "OFFICIALNAME")
                     if _text_of(e)), None)
        if name and name not in winners:
            winners.append(name)
    # Vor-2014: Gewinner in ECONOMIC_OPERATOR_NAME_ADDRESS.
    for operator in _iter_named(root, "ECONOMIC_OPERATOR_NAME_ADDRESS"):
        name = next((_text_of(e) for e in _iter_named(operator, "OFFICIALNAME")
                     if _text_of(e)), None)
        if name and name not in winners:
            winners.append(name)

    return Notice(
        notice_id=notice_id,
        schema="legacy",
        form_type=form_type,
        country=country,
        language=language,
        title=title,
        description=description,
        description_field=description_field,
        cpv_main=cpv_all[0] if cpv_all else None,
        cpv_all=cpv_all,
        lots=lots,
        estimated_value=estimated,
        final_value=final,
        value_currency=cur_f or cur_e,
        award_date=award_date,
        start_date=start_date,
        end_date=end_date,
        buyer_name=buyer_name,
        buyer_national_id=buyer_id,
        winner_names=winners,
        performance_nuts=performance_nuts,
        contract_nature=contract_nature,
        procedure_type=procedure_type,
        submission_deadline=submission_deadline,
        portal_url=portal_url,
        parties=_legacy_parties(root),
        criteria=_legacy_criteria(scope),
        awards=_legacy_awards(root),
        requirements=_legacy_requirements(scope),
        notice_kind=_LEGACY_KIND.get(form_type, "other"),
        buyer_countries=[country] if country else [],
    )


def _eforms_org_countries(root: ET.Element) -> dict[str, str]:
    """Map ``ORG-0001`` → country, from the notice's Organizations block.

    eForms does not inline the buyer's address. ContractingParty carries only a
    reference::

        <ContractingParty><Party><PartyIdentification>
            <ID schemeName="organization">ORG-0001</ID>

    and the actual data lives in a separate section::

        <Organizations><Organization><Company>
            <ID schemeName="organization">ORG-0001</ID>
            <IdentificationCode listName="country">DEU</IdentificationCode>

    A parser that looks for the country *inside* ContractingParty finds nothing
    and silently drops the notice. That cost us everything from 2024 on — the
    months where eForms took over went from 13.000 DE notices to 1.
    """
    result: dict[str, str] = {}
    for organisation in _iter_named(root, "Organization"):
        company = next((c for c in organisation if _local(c) == "Company"), None)
        if company is None:
            continue
        org_id = None
        for identification in _iter_named(company, "PartyIdentification"):
            org_id, _ = _first_child_text(identification, ("ID",))
            if org_id:
                break
        if not org_id:
            continue
        for elem in _iter_named(company, "IdentificationCode"):
            if elem.attrib.get("listName") not in COUNTRY_LIST_NAMES:
                continue
            code = (elem.text or "").strip()
            if len(code) != 3:
                continue
            try:
                result[org_id] = countries.normalize(code)
            except KeyError:
                pass
            break
    return result


def _eforms_lot_terms(lot_project: ET.Element, lot: Lot) -> None:
    """Kategorie 6/2/6 für ein eForms-Los: Laufzeit, CPV, Ort, Optionen."""
    # Los-CPV (Weakness 2).
    for elem in _iter_named(lot_project, "ItemClassificationCode"):
        code = (elem.text or "").strip()
        if code and code not in lot.cpv_all:
            lot.cpv_all.append(code)
    # Erfüllungsort (Weakness 6): NUTS aus RealizedLocation des Loses.
    for loc in _iter_named(lot_project, "RealizedLocation"):
        for elem in _iter_named(loc, "CountrySubentityCode"):
            lot.performance_nuts = (elem.text or "").strip() or None
            break
        if lot.performance_nuts:
            break
    for period in _iter_named(lot_project, "PlannedPeriod"):
        for measure in _iter_named(period, "DurationMeasure"):
            unit = measure.attrib.get("unitCode", "")
            val = _to_int(measure.text)
            if val is None:
                continue
            lot.duration_months = val if unit == "MONTH" else val * 12 if unit == "ANN" else val
            break
        break
    for extension in _iter_named(lot_project, "ContractExtension"):
        lot.has_options = True
        desc = next((_text_of(e) for e in _iter_named(extension, "OptionsDescription")
                     if _text_of(e)), None)
        lot.options_description = desc
        lot.renewal_description = desc
        if desc:
            lot.has_renewal = True
        for mx in _iter_named(extension, "MaximumNumberNumeric"):
            lot.max_renewals = _to_int(mx.text)
            break
        break


_EFORMS_STAT = {
    "tenders": "num_tenders", "t-sme": "num_tenders_sme",
    "t-oth-eea": "num_tenders_other_eu", "t-no-eea": "num_tenders_non_eu",
    "t-esubm": "num_tenders_electronic",
}


def _eforms_awards(root: ET.Element, org_names: dict[str, Party] | None = None) -> list[Award]:
    """Kategorie 5 für eForms: Bieterzahlen + Gewinner je Los-Ergebnis."""
    # Gewinner-Kette: LotResult → LotTender(TEN) → TenderingParty(TPA) → Tenderer(ORG).
    tp_to_org: dict[str, str] = {}
    for tp in _iter_named(root, "TenderingParty"):
        tp_id, _ = _first_child_text(tp, ("ID",))
        for tenderer in _iter_named(tp, "Tenderer"):
            oid, _ = _first_child_text(tenderer, ("ID",))
            if tp_id and oid:
                tp_to_org[tp_id] = oid
                break
    tender_to_tp: dict[str, str] = {}
    for lt in _iter_named(root, "LotTender"):
        ten_id, _ = _first_child_text(lt, ("ID",))
        for tp in _iter_named(lt, "TenderingParty"):
            tp_id, _ = _first_child_text(tp, ("ID",))
            if ten_id and tp_id:
                tender_to_tp[ten_id] = tp_id
                break
    awards: list[Award] = []
    for lot_result in _iter_named(root, "LotResult"):
        lot_id = None
        for tl in _iter_named(lot_result, "TenderLot"):
            lot_id, _ = _first_child_text(tl, ("ID",))
            break
        winner_name = winner_id = None
        for lt in _iter_named(lot_result, "LotTender"):
            ten_id, _ = _first_child_text(lt, ("ID",))
            oid = tp_to_org.get(tender_to_tp.get(ten_id))
            party = org_names.get(oid) if (org_names and oid) else None
            if party is not None:
                winner_name, winner_id = party.name, party.national_id
            break
        counts: dict[str, int] = {}
        for stat in _iter_named(lot_result, "ReceivedSubmissionsStatistics"):
            code = next((_text_of(e) for e in _iter_named(stat, "StatisticsCode")
                         if _text_of(e)), None)
            num = next((_to_int(e.text) for e in _iter_named(stat, "StatisticsNumeric")), None)
            field_name = _EFORMS_STAT.get(code)
            if field_name and num is not None:
                counts[field_name] = num
        if counts or winner_name:
            awards.append(Award(lot_id=lot_id, winner_name=winner_name,
                                winner_national_id=winner_id, **counts))
    return awards


def _eforms_party(company: ET.Element) -> Party:
    def g(tag: str) -> str | None:
        return next((_text_of(e) for e in _iter_named(company, tag) if _text_of(e)), None)
    country = None
    for elem in _iter_named(company, "IdentificationCode"):
        if elem.attrib.get("listName") in COUNTRY_LIST_NAMES:
            code = (elem.text or "").strip()
            if len(code) == 3:
                try:
                    country = countries.normalize(code)
                except KeyError:
                    country = None
                break
    nuts = None
    for elem in _iter_named(company, "CountrySubentityCode"):
        nuts = (elem.text or "").strip() or None
        break
    return Party(
        role="unknown",
        name=g("Name"),
        national_id=g("CompanyID"),
        town=g("CityName"),
        postal_code=g("PostalZone"),
        country=country,
        nuts=nuts,
        email=g("ElectronicMail"),
        phone=g("Telephone"),
        url=g("WebsiteURI"),
    )


def _eforms_buyer_org_ids(root: ET.Element) -> list[str]:
    """Every buyer's org reference, in document order.

    A notice can carry several ``ContractingParty`` elements — one per buyer.
    A joint EU procurement led by the Commission in Brussels may buy for
    agencies in Frankfurt, and TED counts that notice towards Germany. Reading
    only the first party files it under Belgium and hides it from a DE run.
    """
    ids: list[str] = []
    for party in _iter_named(root, "ContractingParty"):
        for identification in _iter_named(party, "PartyIdentification"):
            org_id, _ = _first_child_text(identification, ("ID",))
            if org_id and org_id not in ids:
                ids.append(org_id)
            break
    return ids


def _eforms_buyer_org_id(root: ET.Element) -> str | None:
    ids = _eforms_buyer_org_ids(root)
    return ids[0] if ids else None


# eForms notice types whose subject is an organisation rather than a contract.
# BusinessRegistrationInformationNotice (brin-*) is a company registering
# itself — no ContractingParty, no Organizations block, the party sits under
# BusinessParty. TED counts these towards a country's notices, so dropping them
# leaves a permanent gap against the API.
BUSINESS_PARTY_ROOTS = ("BusinessRegistrationInformationNotice",)

# TED tags the country code with two different list names, and both occur in
# the same corpus. Accepting only 'country' silently skipped every notice that
# used 'eforms-country' — including plainly German buyers like the
# 'Landesbetrieb für Küstenschutz' in Husum.
COUNTRY_LIST_NAMES = (None, "country", "eforms-country")


def _eforms_party_country(root: ET.Element, party_name: str) -> str | None:
    """Country of a directly-embedded party.

    Registration notices place the address inconsistently: some use
    ``PostalAddress``, others only
    ``PartyLegalEntity/CorporateRegistrationScheme/JurisdictionRegionAddress``.
    Searching the whole party subtree is safe here — a registration notice
    describes exactly one organisation, so there is no other country to confuse
    it with.
    """
    for party in _iter_named(root, party_name):
        for elem in _iter_named(party, "IdentificationCode"):
            if elem.attrib.get("listName") not in COUNTRY_LIST_NAMES:
                continue
            code = (elem.text or "").strip()
            if len(code) != 3:
                continue
            try:
                return countries.normalize(code)
            except KeyError:
                return None
    return None


def _eforms_criteria(root: ET.Element) -> list[Criterion]:
    """Zuschlagskriterien je **Los** aus eForms (BT-539/540/541/734/5421).

    Drei Dinge, die die erste Fassung falsch machte:

    1. **Die Einheit ist ``SubordinateAwardingCriterion``**, nicht ``AwardingCriterion``.
       Unter einem ``AwardingCriterion`` haengen bis zu 8+ Einzelkriterien; wer nur das
       erste Vorkommen greift, verliert den Rest (gemessen: 1.247 Lose mit 1 Kriterium,
       aber 714 mit 2–8).
    2. **``lot_id`` gehoert dran.** Ohne sie addieren sich bei Mehrlos-Notices die
       Gewichte aller Lose: gemessen summierten 36.824 Notices auf >105 %, davon
       **95,5 % mehrlosig** bei Ø 4,97 Losen. Mit Los-Bezug loest sich das auf.
    3. **Nur ``listName='number-weight'`` ist ein Gewicht** — ``number-threshold``
       (min-score) und ``number-fixed`` (fix-tot) sind es nicht und wuerden jede
       Summe verfaelschen.
    """
    out: list[Criterion] = []

    def _collect(scope: ET.Element, lot_id: str | None) -> None:
        for sub in _iter_named(scope, "SubordinateAwardingCriterion"):
            kind_code = next((_text_of(e) for e in _iter_named(sub, "AwardingCriterionTypeCode")
                              if _text_of(e)), None)
            # Name/Description nur als DIREKTE Kinder — sonst zieht der Scan Texte aus
            # den eingebetteten UBL-Extensions herein.
            name = next((_text_of(e) for e in sub if _local(e) == "Name" and _text_of(e)), None)
            desc = next((_text_of(e) for e in sub
                         if _local(e) == "Description" and _text_of(e)), None)
            weight = weight_kind = None
            for par in _iter_named(sub, "AwardCriterionParameter"):
                code_el = next((e for e in par if _local(e) == "ParameterCode"), None)
                num = next((_text_of(e) for e in par
                            if _local(e) == "ParameterNumeric" and _text_of(e)), None)
                if code_el is None or num is None:
                    continue
                if (code_el.get("listName") or "") != "number-weight":
                    continue                      # Schwelle/Festbetrag → kein Gewicht
                weight, weight_kind = num, _text_of(code_el) or None
                break
            kind = {"price": "price", "cost": "cost", "quality": "quality"}.get(
                (kind_code or "").lower(), "quality")
            out.append(Criterion(lot_id=lot_id, kind=kind, name=name or desc,
                                 weight=weight, weight_kind=weight_kind))

    seen: set[int] = set()
    for lot_elem in _iter_named(root, "ProcurementProjectLot"):
        lot_id, _ = _first_child_text(lot_elem, ("ID",))
        before = len(out)
        _collect(lot_elem, lot_id)
        seen.update(id(e) for e in _iter_named(lot_elem, "SubordinateAwardingCriterion"))
        del before
    # Kriterien ausserhalb jedes Loses (kommt in schlanken Dialekten vor) nicht verlieren.
    rest = [e for e in _iter_named(root, "SubordinateAwardingCriterion") if id(e) not in seen]
    if rest:
        holder = ET.Element("synthetic")
        holder.extend(rest)
        _collect(holder, None)
    return out


def _parse_eforms(root: ET.Element, notice_id: str) -> Notice:
    org_countries = _eforms_org_countries(root)
    buyer_orgs = _eforms_buyer_org_ids(root)
    buyer_countries = [
        org_countries[o] for o in buyer_orgs
        if o in org_countries and org_countries[o]
    ]
    country = buyer_countries[0] if buyer_countries else None
    if country is None:
        # Registration notices carry their party directly, not by reference.
        country = _eforms_party_country(root, "BusinessParty")
        if country:
            buyer_countries = [country]

    # Deliberately no "if only one country appears, use it" fallback. It looks
    # harmless and is not: Welthungerhilfe procuring in Kyiv, Gaziantep and
    # Bangui has buyers whose countries this registry does not list, so the
    # rule reached past them, found a German org elsewhere in the document and
    # declared the notice German. TED does not count those as DE, and neither
    # should we. A buyer whose country we cannot resolve is unknown, not local.

    # The notice-level project is a direct child of the root; every lot nests a
    # ProcurementProject of its own, so a descendant search mixes the levels.
    # Everything else named cbc:Description is boilerplate (appeal terms etc.).
    project = next((c for c in root if _local(c) == "ProcurementProject"), None)
    description = title = None
    if project is not None:
        description, _ = _first_child_text(project, ("Description",))
        title, _ = _first_child_text(project, ("Name",))

    lots: list[Lot] = []
    for lot_elem in _iter_named(root, "ProcurementProjectLot"):
        lot_id, _ = _first_child_text(lot_elem, ("ID",))
        lot_project = next((c for c in lot_elem if _local(c) == "ProcurementProject"), None)
        if lot_project is None:
            continue
        lot_text, _ = _first_child_text(lot_project, ("Description",))
        lot_title, _ = _first_child_text(lot_project, ("Name",))
        if lot_text or lot_title:
            lot = Lot(lot_id=lot_id, title=lot_title, description=lot_text)
            _eforms_lot_terms(lot_project, lot)
            lots.append(lot)

    cpv_all: list[str] = []
    for elem in _iter_named(root, "ItemClassificationCode"):
        code = (elem.text or "").strip()
        if code and code not in cpv_all:
            cpv_all.append(code)

    language = None
    for elem in _iter_named(root, "NoticeLanguageCode"):
        language = (elem.text or "").strip() or None
        break

    estimated = final = value_currency = None
    if project is not None:
        estimated, value_currency = _first_amount(
            project, ("EstimatedOverallContractAmount",), ("currencyID",))

    # Awarded amounts sit in LotTender/LegalMonetaryTotal, one per winning
    # tender. TED writes -1 (or 0) when the value is not disclosed — a real
    # amount, not the sentinel, is what we want.
    lot_amounts: dict[str, float] = {}
    total = 0.0
    for lot_tender in _iter_named(root, "LotTender"):
        lot_ref = None
        for tl in _iter_named(lot_tender, "TenderLot"):
            lot_ref, _ = _first_child_text(tl, ("ID",))
            break
        amount, cur = _first_amount(lot_tender, ("PayableAmount", "TaxExclusiveAmount"),
                                    ("currencyID",))
        if amount is not None and amount > 0:
            value_currency = value_currency or cur
            total += amount
            if lot_ref:
                lot_amounts[lot_ref] = amount
    if total > 0:
        final = round(total, 2)
    for lot in lots:
        if lot.lot_id and lot.lot_id in lot_amounts:
            lot.value_amount = lot_amounts[lot.lot_id]
            lot.value_currency = value_currency

    award_date = _first_date(root, ("IssueDate",))
    # The contract period is usually stated per lot (68% of the time), not on
    # the notice. Fall back to the span across lots: earliest start, latest end.
    start_date = end_date = None
    if project is not None:
        for period in _iter_named(project, "PlannedPeriod"):
            start_date = _first_date(period, ("StartDate",))
            end_date = _first_date(period, ("EndDate",))
            break
    if start_date is None and end_date is None:
        starts, ends = [], []
        for lot_elem in _iter_named(root, "ProcurementProjectLot"):
            for period in _iter_named(lot_elem, "PlannedPeriod"):
                s = _first_date(period, ("StartDate",))
                e = _first_date(period, ("EndDate",))
                if s:
                    starts.append(s)
                if e:
                    ends.append(e)
        start_date = min(starts) if starts else None
        end_date = max(ends) if ends else None

    # Resolve every ORG-id to a full Party once, then assign roles by reference.
    org_parties: dict[str, Party] = {}
    for organisation in _iter_named(root, "Organization"):
        company = next((c for c in organisation if _local(c) == "Company"), None)
        if company is None:
            continue
        oid = None
        for ident in _iter_named(company, "PartyIdentification"):
            oid, _ = _first_child_text(ident, ("ID",))
            break
        if not oid:
            continue
        org_parties[oid] = _eforms_party(company)

    org_names = {oid: p.name for oid, p in org_parties.items() if p.name}

    performance_nuts = None       # Weakness 6: Erfüllungsort auf Notice-Ebene
    if project is not None:
        for loc in _iter_named(project, "RealizedLocation"):
            for elem in _iter_named(loc, "CountrySubentityCode"):
                performance_nuts = (elem.text or "").strip() or None
                break
            if performance_nuts:
                break

    contract_nature = None        # BT-23: direktes ProcurementTypeCode-Kind (nicht die
    if project is not None:       # BT-774-Strategie-Codes unter ProcurementAdditionalType)
        for c in project:
            if _local(c) == "ProcurementTypeCode":
                val = (c.text or "").strip().lower()
                contract_nature = val if val in _NATURE_CANON else None
                break

    procedure_type = None
    for elem in _iter_named(root, "ProcedureCode"):
        procedure_type = _EFORMS_PROCEDURE.get((elem.text or "").strip(), "other")
        break
    submission_deadline = None
    for tp in _iter_named(root, "TenderSubmissionDeadlinePeriod"):
        submission_deadline = _first_date(tp, ("EndDate",))
        break
    portal_url = None
    for tp in _iter_named(root, "TenderingProcess"):
        portal_url = next((_text_of(e) for e in _iter_named(tp, "AccessToolsURI")
                           if _text_of(e)), None)
        if portal_url:
            break

    buyer_org = buyer_orgs[0] if buyer_orgs else None
    buyer_name = org_names.get(buyer_org) if buyer_org else None

    parties: list[Party] = []
    if buyer_org and buyer_org in org_parties:
        bp = org_parties[buyer_org]
        bp.role = "buyer"
        parties.append(bp)
    if not parties:
        # Fallback für eForms-DE-Unterschwellig/Draft (eforms-sdk-0.1, DÖE): kein
        # efac:Organizations-Block — der Käufer steht inline unter ContractingParty/Party.
        for cp in _iter_named(root, "ContractingParty"):
            party = next(iter(_iter_named(cp, "Party")), None)
            if party is None:
                continue
            nm = None
            for pn in _iter_named(party, "PartyName"):
                nm = next((_text_of(e) for e in _iter_named(pn, "Name") if _text_of(e)), None)
                if nm:
                    break
            if not nm:
                continue
            buyer_name = nm
            def _pick(tag):
                return next((_text_of(e) for e in _iter_named(party, tag) if _text_of(e)), None)
            # Kontaktdaten NICHT vergessen: sie stehen inline unter Party/Contact und
            # waren bisher nicht gelesen — gemessen 0 % E-Mail/Telefon/Web bei 258.246
            # DÖE-Käuferzeilen, obwohl im XML zu 60 / 48 / 39 % vorhanden. `contact` ist
            # bei DÖE oft die einzige Spur zur zuständigen Person.
            contact = next(iter(_iter_named(party, "Contact")), None)

            def _from_contact(tag):
                if contact is None:
                    return None
                return next((_text_of(e) for e in _iter_named(contact, tag) if _text_of(e)),
                            None)

            parties.append(Party(
                role="buyer", name=nm,
                national_id=_pick("CompanyID") or _pick("PartyIdentification"),
                town=_pick("CityName"), postal_code=_pick("PostalZone"),
                nuts=_pick("CountrySubentityCode"), country="DE",
                email=_from_contact("ElectronicMail"),
                phone=_from_contact("Telephone"),
                contact_person=_from_contact("Name"),
                url=_pick("WebsiteURI")))
            break

    # Winners: NoticeResult/TenderingParty/Tenderer references a winning org.
    # Konsortium = eine TenderingParty mit MEHREREN Tenderern (mehrere Firmen
    # bieten gemeinsam). Mehrere TenderingParties mit je einem Tenderer sind
    # unabhängige Los-Gewinner — kein Konsortium.
    winners: list[str] = []
    winner_ids: list[str] = []
    consortium_ids: set[str] = set()
    for tendering in _iter_named(root, "TenderingParty"):
        tp_orgs = [_first_child_text(t, ("ID",))[0]
                   for t in _iter_named(tendering, "Tenderer")]
        tp_orgs = [o for o in tp_orgs if o]
        if len(tp_orgs) > 1:
            consortium_ids.update(tp_orgs)
        for oid in tp_orgs:
            if oid not in winner_ids:
                winner_ids.append(oid)
    for oid in winner_ids:
        party = org_parties.get(oid)
        if party is None:
            continue
        winner = Party(role="winner", name=party.name, national_id=party.national_id,
                       town=party.town, postal_code=party.postal_code, country=party.country,
                       nuts=party.nuts, email=party.email, phone=party.phone, url=party.url)
        winner.in_consortium = (oid in consortium_ids) or bool(
            party.name and _RE_ARGE.search(party.name))
        parties.append(winner)
        if party.name and party.name not in winners:
            winners.append(party.name)

    # Fallback: manche eForms-Notices benennen den Gewinner NICHT über
    # TenderingParty/Tenderer, sondern nur als SignatoryParty des SettledContract.
    # Nur greifen, wenn sonst kein Gewinner gefunden — Käufer + Nachprüfstelle +
    # eSender ausgeschlossen (die signieren teils selbst). Gemessen: recovert ~200
    # echte Gewinner (Bellersheim Abfallwirtschaft GmbH, Wolf Ingenieurbüro …),
    # die sonst als „vergeben ohne Gewinner" verloren gingen.
    if not winner_ids:
        for settled in _iter_named(root, "SettledContract"):
            for sp in _iter_named(settled, "SignatoryParty"):
                oid = next((_first_child_text(pi, ("ID",))[0]
                            for pi in _iter_named(sp, "PartyIdentification")), None)
                if not oid or oid == buyer_org or oid in winner_ids:
                    continue
                party = org_parties.get(oid)
                if party is None or not party.name or _RE_EFORMS_NONWINNER.search(party.name):
                    continue
                winner_ids.append(oid)
                w = Party(role="winner", name=party.name, national_id=party.national_id,
                          town=party.town, postal_code=party.postal_code, country=party.country,
                          nuts=party.nuts, email=party.email, phone=party.phone, url=party.url)
                w.in_consortium = bool(_RE_ARGE.search(party.name))
                parties.append(w)
                if party.name not in winners:
                    winners.append(party.name)

    criteria = _eforms_criteria(root)

    return Notice(
        notice_id=notice_id,
        schema="eforms",
        form_type=_local(root),
        country=country,
        language=language,
        title=title,
        description=description,
        description_field="cbc:Description" if description else None,
        cpv_main=cpv_all[0] if cpv_all else None,
        cpv_all=cpv_all,
        lots=lots,
        estimated_value=estimated,
        final_value=final,
        value_currency=value_currency,
        award_date=award_date,
        start_date=start_date,
        end_date=end_date,
        buyer_name=buyer_name,
        winner_names=winners,
        performance_nuts=performance_nuts,
        contract_nature=contract_nature,
        procedure_type=procedure_type,
        submission_deadline=submission_deadline,
        portal_url=portal_url,
        parties=parties,
        criteria=criteria,
        awards=_eforms_awards(root, org_parties),
        requirements=_eforms_requirements(root),
        notice_kind=_EFORMS_KIND.get(_local(root), "other"),
        buyer_countries=list(dict.fromkeys(buyer_countries)),
    )
