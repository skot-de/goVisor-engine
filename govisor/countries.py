"""Country registry.

TED uses two different country encodings depending on the notice schema:
legacy TED_EXPORT carries ISO 3166-1 alpha-2 (``DE``), eForms/UBL carries
alpha-3 (``DEU``). Every country-aware part of the pipeline goes through this
registry so that adding a country stays a one-line change.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Country:
    alpha2: str
    alpha3: str
    name: str


# EU-27 plus EEA/candidate countries that publish to TED.
_COUNTRIES: tuple[Country, ...] = (
    Country("AT", "AUT", "Österreich"),
    Country("BE", "BEL", "Belgien"),
    Country("BG", "BGR", "Bulgarien"),
    Country("CH", "CHE", "Schweiz"),
    Country("CY", "CYP", "Zypern"),
    Country("CZ", "CZE", "Tschechien"),
    Country("DE", "DEU", "Deutschland"),
    Country("DK", "DNK", "Dänemark"),
    Country("EE", "EST", "Estland"),
    Country("EL", "GRC", "Griechenland"),
    Country("ES", "ESP", "Spanien"),
    Country("FI", "FIN", "Finnland"),
    Country("FR", "FRA", "Frankreich"),
    Country("HR", "HRV", "Kroatien"),
    Country("HU", "HUN", "Ungarn"),
    Country("IE", "IRL", "Irland"),
    Country("IS", "ISL", "Island"),
    Country("IT", "ITA", "Italien"),
    Country("LI", "LIE", "Liechtenstein"),
    Country("LT", "LTU", "Litauen"),
    Country("LU", "LUX", "Luxemburg"),
    Country("LV", "LVA", "Lettland"),
    Country("MT", "MLT", "Malta"),
    Country("NL", "NLD", "Niederlande"),
    Country("NO", "NOR", "Norwegen"),
    Country("PL", "POL", "Polen"),
    Country("PT", "PRT", "Portugal"),
    Country("RO", "ROU", "Rumänien"),
    Country("SE", "SWE", "Schweden"),
    Country("SI", "SVN", "Slowenien"),
    Country("SK", "SVK", "Slowakei"),
    Country("UK", "GBR", "Vereinigtes Königreich"),
)

_BY_ALPHA2 = {c.alpha2: c for c in _COUNTRIES}
_BY_ALPHA3 = {c.alpha3: c for c in _COUNTRIES}

# TED publishes Greece as EL, ISO 3166 calls it GR; the UK appears as both
# UK and GB across the archive's 20+ years.
_ALIASES = {"GR": "EL", "GB": "UK"}


def resolve(code: str) -> Country:
    """Look up a country by alpha-2 or alpha-3 code, case-insensitively."""
    key = code.strip().upper()
    key = _ALIASES.get(key, key)
    if key in _BY_ALPHA2:
        return _BY_ALPHA2[key]
    if key in _BY_ALPHA3:
        return _BY_ALPHA3[key]
    raise KeyError(f"Unbekannter Ländercode: {code!r}")


def normalize(code: str) -> str:
    """Return the canonical alpha-2 code for any supported encoding."""
    return resolve(code).alpha2


def all_countries() -> tuple[Country, ...]:
    return _COUNTRIES
