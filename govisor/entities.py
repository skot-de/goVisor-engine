"""Entity resolution for suppliers and buyers.

The two sides need opposite strategies, because TED equips them differently
(measured on DE 2023-06):

              OFFICIALNAME  TOWN  NUTS  POSTAL_CODE  E_MAIL  NATIONALID
    Buyer         100%      100%  100%     98.6%      100%      3.9%
    Supplier      100%      100%  100%     71.6%      27.6%     0.8%

Buyers resolve from TED's own signals — the e-mail domain is a strong
blocking key. Suppliers have almost none, but they are companies, so an
external register (Handelsregister) supplies a stable ID that TED lacks.

Not every supplier is a company, though. Consortia and natural persons will
never be in a company register; treating them as failed lookups hides the
fact that they are a different kind of thing.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum

from . import locales

# Alle sprach-/institutionsspezifischen Muster (Rechtsformen, Behörden-,
# Konsortial-, Handwerks-Regexes, Namens-Kanonik) liegen im aktiven Länder-
# Profil (govisor/locales.py). classify()/normalize_company() lesen sie über
# ``locales.active()`` — Land wechseln = Profil wechseln, kein Code-Eingriff.


class Kind(str, Enum):
    COMPANY = "company"
    CONSORTIUM = "consortium"
    ASSOCIATION = "association"
    PUBLIC = "public"
    PERSON = "person"


@dataclass(frozen=True)
class Classified:
    kind: Kind
    normalized: str


# Deutsche Umlaut-Konvention: ü→ue etc. VOR dem NFKD-Strip. Ohne das wird „für" zu „fur",
# aber „Fuer" bleibt „fuer" → derselbe Käufer splittet (Landeshauptstadt München/Muenchen,
# Bundesagentur für/Fuer Arbeit — die größten Fragmentierer, ~200k Notices). Die Muster in
# locales.py (DE-Profil) sind entsprechend in der ae/ue-Form gehalten, damit Rechtsform-/
# Behörden-Regex weiter greifen. Muster auf ROHtext (re_person, text_skip) bleiben umlaut-tragend.
UMLAUT_DE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "ae", "Ö": "oe", "Ü": "ue", "ß": "ss"})


def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.translate(UMLAUT_DE))
    return "".join(c for c in text if not unicodedata.combining(c))


def normalize_company(name: str) -> str:
    """Comparable form of a company name: no accents, no legal form, no noise.

    '&' and '+' are written out, because TED and the Handelsregister disagree
    freely: 'Rhiem & Sohn Kies und Sand' vs 'Rhiem und Sohn Kies und Sand' is
    the same firm. Dropping the symbol instead of mapping it would leave the
    two forms different and push the pair into fuzzy matching, which is where
    false positives live.
    """
    loc = locales.active()
    text = strip_accents((name or "").lower())
    text = re.sub(r"\([^)]*\)", " ", text)          # Klammer-Zusätze (Buying-Unit, Rang-Annotation)
    text = loc.re_representation.sub(" ", text)      # Vertretungsklausel
    text = loc.re_subdivision.sub(" ", text)         # Abteilungs-Anhängsel
    text = loc.re_lead_article.sub("", text)         # führender Artikel
    text = re.sub(r"\s*[&+]\s*", " und ", text)
    text = loc.re_legal.sub(" ", text)               # Rechtsformen
    text = loc.re_unit.sub(" ", text)                # Einkaufs-/Buchungskreis-Nr.
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classify(name: str) -> Classified:
    """What kind of counterparty is this?

    Order matters: a consortium may well contain 'GmbH', and a public body may
    read like a company. The most specific test wins.
    """
    loc = locales.active()
    raw = (name or "").strip()
    lowered = strip_accents(raw.lower())
    normalized = normalize_company(raw)

    if loc.re_consortium.search(lowered):
        kind = Kind.CONSORTIUM
    elif loc.re_public.search(lowered):
        kind = Kind.PUBLIC
    elif loc.re_association.search(lowered):
        kind = Kind.ASSOCIATION
    elif (
        loc.re_person.match(raw)
        and not loc.re_legal.search(lowered)
        and not loc.re_trade_word.search(lowered)
    ):
        kind = Kind.PERSON
    else:
        kind = Kind.COMPANY
    return Classified(kind=kind, normalized=normalized)


def blocking_key(name: str) -> str:
    """First significant token — cheap candidate filter against a big register."""
    normalized = normalize_company(name)
    tokens = [t for t in normalized.split() if len(t) > 2]
    return tokens[0] if tokens else normalized
