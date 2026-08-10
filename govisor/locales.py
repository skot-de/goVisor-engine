"""Länder-Profile — die eine Stelle, an der Sprache & Institutionen sitzen.

Der Rest der Pipeline (Ingest, Silber, Gold-Struktur, Successions, Score-Mechanik,
CPV→Branche) ist länder-generisch. Alles Sprach-/Institutionsspezifische steckt
HIER in einem ``Locale``: Rechtsformen, Behörden-/Konsortial-Muster, Freitext-
Gewinner-Marker (Text-Ära), contract_kind-Stichworte, Firmenregister, Deflator,
NUTS→Region.

Ein neues Land onboarden = **ein Profil ausfüllen** (+ Firmenregister anschließen)
+ Daten laden. Kein Code-Eingriff an verstreuten Stellen.

    locales.use("FR")     # aktiviert das FR-Profil für den laufenden Prozess
    locales.active()      # das gerade aktive Profil (Default: DE)

DE ist das Referenzprofil und reproduziert das bisherige Verhalten 1:1.
FR ist ein vorbereiteter STUB — Werte sind best-effort und vor dem Live-Gang
zu prüfen (insb. Register + Deflator).
"""

from __future__ import annotations

import re

_NEVER = r"(?!x)x"   # kompiliert zu einem Muster, das nie matcht (für „gibt's hier nicht")


class Locale:
    """Alle länderspezifischen Regeln als ein austauschbares Profil."""

    def __init__(self, code, *, name, legal_forms, representation, subdivision,
                 unit_numbers, lead_articles, consortium, association, public,
                 trade_word, person, text_winner_marker, text_skip, text_not_awarded,
                 freemail, public_domain_slds, public_name,
                 kind_framework_kw, kind_recurring_kw, kind_oneoff_kw,
                 register_path, cpi, nuts_region, succ_stopwords):
        self.code = code
        self.name = name
        # -- Entity-Normalisierung / -Klassifikation (Text bereits klein + akzentfrei) --
        self.legal_forms = tuple(legal_forms)
        self.re_legal = re.compile("|".join(legal_forms) if legal_forms else _NEVER)
        self.re_representation = re.compile(representation or _NEVER)
        self.re_subdivision = re.compile(subdivision or _NEVER)
        self.re_unit = re.compile(unit_numbers or _NEVER)
        self.re_lead_article = re.compile(lead_articles or _NEVER)
        self.re_consortium = re.compile(consortium or _NEVER)
        self.re_association = re.compile(association or _NEVER)
        self.re_public = re.compile(public or _NEVER)
        self.re_trade_word = re.compile(trade_word or _NEVER)
        self.re_person = re.compile(person)
        # -- Text-Ära (vor-XML): Freitext-Gewinner --
        self.re_text_winner = re.compile(text_winner_marker, re.I)
        self.re_text_skip = re.compile(text_skip, re.I)
        self.text_not_awarded = text_not_awarded
        # -- Firmengruppen (Gold) --
        self.freemail = frozenset(freemail)
        self.public_domain_slds = frozenset(public_domain_slds)
        self.re_public_name = re.compile(public_name or _NEVER)
        # -- contract_kind (Gold): rohe Regex-Alternationen für DuckDB regexp_matches --
        self.kind_framework_kw = kind_framework_kw     # z. B. "rahmen"
        self.kind_recurring_kw = kind_recurring_kw
        self.kind_oneoff_kw = kind_oneoff_kw
        # -- externe Quellen / Dimensionen --
        self.register_path = register_path             # Firmenregister-Extrakt oder None
        self.cpi = dict(cpi)                           # Jahr → VPI (Deflator)
        self.nuts_region = dict(nuts_region)           # NUTS-1-Präfix → Region/Bundesland
        # Stoppwörter für die Titel-Ähnlichkeits-Blockung der Successions
        self.succ_stopwords = frozenset(succ_stopwords)


# ===========================================================================
# DE — Referenzprofil (verbatim aus entities.py / gold.py, Verhalten unverändert)
# ===========================================================================
_DE_LEGAL = (
    r"gesellschaft mit beschraenkter haftung", r"kommanditgesellschaft auf aktien",
    r"gemeinnuetzige gmbh", r"aktiengesellschaft", r"kommanditgesellschaft",
    r"eingetragener verein", r"eingetragene genossenschaft", r"unternehmergesellschaft",
    r"offene handelsgesellschaft", r"anstalt des oeffentlichen rechts",
    r"koerperschaft des oeffentlichen rechts", r"gesellschaft buergerlichen rechts",
    r"societas europaea", r"haftungsbeschraenkt", r"gmbh\s+und\s+co\.?\s*kga?a?",
    r"gmbh", r"\bag\b", r"\bkgaa\b", r"\bkg\b", r"\bohg\b", r"\bug\b", r"\bse\b",
    r"\bmbh\b", r"\bggmbh\b", r"\be\.? ?v\b", r"\be\.? ?g\b", r"\bgbr\b", r"\baor\b",
    r"\bko?dr\b", r"\bco\b", r"\be\.? ?k\b",
)
_NAME_PART = r"[A-ZÄÖÜ][a-zäöüß']+(?:-[A-ZÄÖÜ][a-zäöüß']+)*"

DE = Locale(
    "DE", name="Deutschland",
    legal_forms=_DE_LEGAL,
    representation=r"\s*[,/;–-]?\s*vertreten durch\b.*$",
    subdivision=(r"\s*[,/|;–-]\s*(geschaeftsbereich|geschaeftsstelle|referat|dezernat|"
                 r"fachbereich|sachgebiet|der magistrat|der oberbuergermeister|der landrat|"
                 r"zentrale vergabestelle|zentraler einkauf|abteilung|sachbearbeitung)\b.*$"),
    unit_numbers=r"\b(bukr|buk|vgst)\s*\d+\b",
    lead_articles=r"^(das|der|die|den|dem)\s+",
    consortium=(r"\b(arge\b|arbeitsgemeinschaft|bietergemeinschaft|konsortium|"
                r"gemeinschaft der|multi-vendor)"),
    association=(r"\b(e\.? ?v\b|verein\b|verband\b|gewerkschaft\b|gemeinnuetzig)"
                 r"|\bstiftung\b(?!\s*(&|und)\s*co)"),
    public=(r"(bundesrepublik|bundesamt|bundesministerium|bundesanstalt|landesamt|"
            r"landesbetrieb|landkreis|zweckverband|eigenbetrieb|stadtverwaltung|"
            r"gemeindeverwaltung|kreisverwaltung)|^(stadt|gemeinde)\s"),
    trade_word=(r"(elektro|taxi|autohaus|service|technik|technolog|handel|transport|"
                r"garten|malerfach|dachdeck|sanitaer|heizung|schreinerei|tischlerei|"
                r"schlosserei|druckerei|reinigung|logistik|beratung|consulting|software|"
                r"system|solution|engineering|planung|architekt|ingenieur|buero|apotheke|"
                r"verlag|gebaeude|facility|catering|security|entsorgung|recycling|"
                r"fachbetrieb|werkstatt|handwerk|installat|montage|vertrieb|zentrum)"),
    person=rf"^(?:dr\.|prof\.|dipl\.[-\w]*)?\s*{_NAME_PART}(?:\s+{_NAME_PART}){{1,2}}$",
    text_winner_marker=r"wirtschaftsteilnehmer",
    text_skip=r"^(wurde|vergeben|los|bezeichnung|v\.|abschnitt|name und|ursprüng|—|-|siehe|nummer)",
    text_not_awarded="nicht vergeben",
    freemail={"gmail", "googlemail", "gmx", "web", "t-online", "outlook", "hotmail",
              "yahoo", "aol", "freenet", "mail", "posteo", "protonmail", "proton",
              "icloud", "me", "live", "msn", "mailbox", "online", "email", "1und1",
              "ionos", "kabelmail", "arcor", "ewetel"},
    public_domain_slds={"bund", "bayern", "nrw", "berlin", "hamburg", "bremen", "hessen",
                        "sachsen", "sachsen-anhalt", "thueringen", "niedersachsen",
                        "brandenburg", "saarland", "rlp", "bwl", "schleswig-holstein",
                        "mecklenburg-vorpommern", "mv-regierung", "deutschebahn", "bahn",
                        "bundeswehr", "autobahn", "aok", "europa", "bva", "bafin",
                        "bundestag", "bundesrat", "landtag", "bundesbank", "kbv"},
    public_name=(r"landeshauptstadt|\bstadt\b|\bgemeinde\b|landkreis|landratsamt|"
                 r"bezirksamt|bezirksregierung|\bland\b|freistaat|ministerium|"
                 r"landesbetrieb|landesamt|bundesamt|bundesministerium|bundesanstalt|"
                 r"\bregierung\b|vergabekammer|vergabestelle|beschaffungsamt|\bbehoerde\b|"
                 r"universitaet|hochschule|klinik|studierendenwerk|studentenwerk|"
                 r"zweckverband|eigenbetrieb|landschaftsverband|\bpolizei\b|finanzamt|"
                 r"jobcenter|kreisverwaltung|stadtverwaltung|gemeindeverwaltung|"
                 r"\bkreis\b|senatsverwaltung|magistrat|\bregion\b|kommunal|sparkasse|"
                 r"stadtwerke|abwasser|wasserverband|verkehrsbetrieb|verkehrsgesellschaft|"
                 r"nahverkehr|\banstalt\b|koerperschaft|diakonie|caritas|\bkirche|bistum"),
    kind_framework_kw="rahmen",
    kind_recurring_kw=("wartung|pflege|lizenz|reinigung|bewirtschaft|unterhalt|betreib|"
                       "betrieb|entsorgung|catering|bewachung|winterdienst|support|hosting|"
                       "miete|leasing|verpflegung|instandhalt|dienstleistung|service|beratung|gala"),
    kind_oneoff_kw=("neubau|sanierung|umbau|abbruch|errichtung|rohbau|ausbau|modernisierung|"
                    "fassad|dachsanierung|erweiterungsbau|anbau"),
    register_path="/Users/svko_macmini/PROJEKTE/claude_code/C10_ipv4analyse/de_companies_ocdata.jsonl.bz2",
    cpi={2004: 79.4, 2005: 80.6, 2006: 81.9, 2007: 83.8, 2008: 86.0, 2009: 86.3,
         2010: 87.2, 2011: 89.0, 2012: 90.8, 2013: 92.2, 2014: 93.0, 2015: 93.5,
         2016: 94.0, 2017: 95.4, 2018: 97.1, 2019: 98.5, 2020: 100.0,
         2021: 103.1, 2022: 110.2, 2023: 116.7, 2024: 119.5, 2025: 121.9, 2026: 124.3},
    nuts_region={"DE1": "Baden-Württemberg", "DE2": "Bayern", "DE3": "Berlin",
                 "DE4": "Brandenburg", "DE5": "Bremen", "DE6": "Hamburg", "DE7": "Hessen",
                 "DE8": "Mecklenburg-Vorpommern", "DE9": "Niedersachsen",
                 "DEA": "Nordrhein-Westfalen", "DEB": "Rheinland-Pfalz", "DEC": "Saarland",
                 "DED": "Sachsen", "DEE": "Sachsen-Anhalt", "DEF": "Schleswig-Holstein",
                 "DEG": "Thüringen"},
    succ_stopwords=("der die das und fur von zur zum den im am auf mit los bau neubau sanierung "
                    "lieferung leistungen arbeiten ausschreibung offentliche vergabe beschaffung "
                    "stadt gemeinde landkreis kreis amt landratsamt ex post objekt").split(),
)


# ===========================================================================
# FR — vorbereiteter STUB. Werte best-effort, VOR Live-Gang prüfen.
#   TODO: Firmenregister (SIRENE/INSEE) anschließen  ·  FR-VPI/HICP eintragen
#   ·  Behörden-/Handwerks-Muster vervollständigen  ·  Gewinner-Marker verifizieren
# ===========================================================================
FR = Locale(
    "FR", name="Frankreich (Stub — vor Live-Gang prüfen)",
    legal_forms=(r"\bsociete anonyme\b", r"\bsas\b", r"\bsasu\b", r"\bsarl\b", r"\beurl\b",
                 r"\bsa\b", r"\bsci\b", r"\bscop\b", r"\bscic\b", r"\bgie\b", r"\bsnc\b",
                 r"\bsem\b", r"\bepic\b", r"\bepa\b"),
    representation=r"\s*[,/;–-]?\s*(represente|representee|agissant) par\b.*$",
    subdivision=(r"\s*[,/|;–-]\s*(direction|service|departement|pole|bureau|"
                 r"cellule des marches|centrale d achat)\b.*$"),
    unit_numbers=_NEVER,
    lead_articles=r"^(le|la|les|l|du|de la|des)\s+",
    consortium=r"\b(groupement|cotraitance|mandataire|conjoint|solidaire)",
    association=r"\b(association|loi 1901|fondation|federation|syndicat)",
    public=(r"(prefecture|region\b|departement|commune|communaute|ministere|mairie|"
            r"conseil (regional|departemental|general)|etablissement public|"
            r"metropole|agglomeration|syndicat mixte)|^(ville|mairie) d"),
    trade_word=(r"(electric|informatique|batiment|travaux|nettoyage|transport|entretien|"
                r"maintenance|conseil|ingenierie|architecte|logiciel|securite|restauration)"),
    person=rf"^(?:dr\.|prof\.|m\.|mme\.?)?\s*{_NAME_PART}(?:\s+{_NAME_PART}){{1,2}}$",
    text_winner_marker=r"operateur economique|titulaire",
    text_skip=r"^(a ete|attribue|lot|designation|section|nom et|v\.|—|-|voir|numero)",
    text_not_awarded="non attribue",
    freemail={"gmail", "googlemail", "orange", "wanadoo", "free", "sfr", "laposte",
              "hotmail", "outlook", "yahoo", "live", "bbox", "numericable", "icloud"},
    public_domain_slds={"gouv", "prefecture", "interieur", "sante", "education",
                        "defense", "justice", "finances", "sncf", "ratp", "poste"},
    public_name=(r"prefecture|\bregion\b|departement|\bcommune\b|communaute|ministere|"
                 r"mairie|\bville\b|conseil|etablissement public|metropole|agglomeration|"
                 r"syndicat|hopital|chu\b|universite|academie|rectorat|gendarmerie|police"),
    kind_framework_kw="accord.?cadre|accord cadre",
    kind_recurring_kw=("maintenance|entretien|nettoyage|hebergement|licence|prestation|"
                       "exploitation|gestion|surveillance|gardiennage|restauration|assistance|"
                       "support|location|abonnement"),
    kind_oneoff_kw=("construction|renovation|rehabilitation|demolition|amenagement|"
                    "extension|refection|travaux neufs|gros oeuvre"),
    register_path=None,   # TODO: SIRENE/INSEE-Extrakt anschließen
    cpi={},               # TODO: FR-VPI (INSEE) oder Eurozonen-HICP eintragen
    nuts_region={"FR1": "Île-de-France", "FRB": "Centre-Val de Loire",
                 "FRC": "Bourgogne-Franche-Comté", "FRD": "Normandie",
                 "FRE": "Hauts-de-France", "FRF": "Grand Est", "FRG": "Pays de la Loire",
                 "FRH": "Bretagne", "FRI": "Nouvelle-Aquitaine", "FRJ": "Occitanie",
                 "FRK": "Auvergne-Rhône-Alpes", "FRL": "Provence-Alpes-Côte d'Azur",
                 "FRM": "Corse"},
    succ_stopwords=("le la les l du de des et pour avec sur lot marche travaux fourniture "
                    "prestation prestations ville commune departement region conseil mairie "
                    "public appel offre offres services").split(),
)


# ---------------------------------------------------------------------------
CH = Locale(
    "CH", name="Schweiz (erste Fassung — an TED-CHE-Daten geprüft, nicht abschließend)",
    # Dreisprachig: eine Locale muss DE, FR und IT zugleich treffen. Deshalb sind alle
    # Muster die Vereinigung der drei Sprachen, nicht eine Auswahl.
    legal_forms=(r"\bag\b", r"\bgmbh\b", r"\bsa\b", r"\bsarl\b", r"\bsagl\b",
                 r"\bspa\b", r"\bsnc\b", r"\bkg\b", r"\bgenossenschaft\b",
                 r"\bcooperative\b", r"\bcooperativa\b", r"\bverein\b",
                 r"\bassociation\b", r"\bassociazione\b", r"\bstiftung\b",
                 r"\bfondation\b", r"\bfondazione\b"),
    representation=r"\s*[,/;–-]?\s*(vertreten durch|represente(e)? par|rappresentat[oa] da)\b.*$",
    subdivision=(r"\s*[,/|;–-]\s*(abteilung|amt für|direktion|dienststelle|fachstelle|"
                 r"direction|service|office|ufficio|servizio|divisione)\b.*$"),
    unit_numbers=_NEVER,
    lead_articles=r"^(der|die|das|le|la|les|l|il|lo|gli)\s+",
    consortium=r"\b(arbeitsgemeinschaft|arge|bietergemeinschaft|groupement|consorzio|consortium)",
    association=r"\b(verein|association|associazione|stiftung|fondation|fondazione|verband)",
    # Öffentliche Hand: Bund/Kanton/Gemeinde in allen drei Sprachen. „Kanton" und
    # „commune/comune" tragen die Hauptlast — die Schweiz vergibt stark föderal.
    public=(r"(kanton|gemeinde|stadt\b|bundesamt|eidgenoss|schweizerische eidgenossenschaft|"
            r"canton|commune|ville de|confederation|comune|citta|cantone|"
            r"armasuisse|sbb|cff|ffs|swisscom|die post|la poste|la posta)"),
    trade_word=(r"(elektro|informatik|bau\b|tiefbau|hochbau|reinigung|transport|unterhalt|"
                r"planung|ingenieur|architekt|software|sicherheit|"
                r"electric|informatique|batiment|travaux|nettoyage|entretien|ingenierie|"
                r"elettric|informatica|edilizia|pulizia|manutenzione)"),
    person=rf"^(?:dr\.|prof\.|herr|frau|m\.|mme\.?)?\s*{_NAME_PART}(?:\s+{_NAME_PART}){{1,2}}$",
    text_winner_marker=r"zuschlagsempfanger|adjudicataire|aggiudicatario|anbieter",
    text_skip=r"^(wurde|zuschlag|los|bezeichnung|abschnitt|name und|v\.|—|-|siehe|nummer)",
    text_not_awarded="kein zuschlag|non adjuge|non aggiudicato",
    # Schweizer Provider zusätzlich zu den internationalen — bluewin/hispeed/sunrise sind
    # hier verbreitet, wo in DE t-online steht.
    freemail={"gmail", "googlemail", "bluewin", "hispeed", "sunrise", "swissonline",
              "gmx", "hotmail", "outlook", "yahoo", "live", "icloud", "protonmail", "proton"},
    # admin.ch ist DIE Bundesdomain; Kantone nutzen zweistellige Kürzel (zh.ch, be.ch …),
    # die über public_name greifen, nicht über die SLD.
    public_domain_slds={"admin", "sbb", "post", "swisstopo", "bfs", "seco", "vbs", "eda"},
    public_name=(r"kanton|kantonale|gemeinde|\bstadt\b|bundesamt|eidgenoss|"
                 r"canton|commune|\bville\b|confederation|comune|\bcitta\b|"
                 r"spital|hopital|ospedale|universitat|universite|universita|"
                 r"schule|ecole|scuola|polizei|police|polizia|armasuisse|\bsbb\b"),
    kind_framework_kw="rahmenvertrag|rahmenvereinbarung|accord.?cadre|contratto quadro",
    kind_recurring_kw=("unterhalt|wartung|reinigung|betrieb|lizenz|support|miete|abonnement|"
                       "bewirtschaftung|entretien|maintenance|nettoyage|exploitation|"
                       "manutenzione|pulizia|gestione"),
    kind_oneoff_kw=("neubau|umbau|sanierung|ruckbau|erweiterung|instandsetzung|"
                    "construction|renovation|demolition|amenagement|"
                    "costruzione|ristrutturazione|demolizione"),
    register_path=None,   # TODO: Zefix (Handelsregister CH) — Gegenstück zum deutschen HR
    cpi={},               # TODO: LIK des BFS; ohne ihn bleibt value_real_2020 für CH nominal
    # NUTS-ähnliche Gliederung: die Schweiz nutzt CH0x-Großregionen.
    nuts_region={"CH01": "Genferseeregion", "CH02": "Espace Mittelland",
                 "CH03": "Nordwestschweiz", "CH04": "Zürich",
                 "CH05": "Ostschweiz", "CH06": "Zentralschweiz", "CH07": "Tessin"},
    succ_stopwords=("los", "lot", "lotto", "teil", "partie", "parte", "phase", "etappe",
                    "bkp", "ccc", "objekt", "objet", "oggetto"),
)


LOCALES = {loc.code: loc for loc in (DE, FR, CH)}
_active = DE


def get(code: str) -> Locale:
    """Profil eines Landes (KeyError, wenn nicht vorbereitet)."""
    return LOCALES[code]


def use(code: str) -> Locale:
    """Aktives Profil für den laufenden Prozess setzen (CLI ruft das je Land)."""
    global _active
    _active = LOCALES[code]
    return _active


def active() -> Locale:
    """Das gerade aktive Profil (Default: DE — bisheriges Verhalten)."""
    return _active
