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


# ---------------------------------------------------------------------------
# AT — an 401.716 Käufernennungen und 80.597 Firmennamen aus dem eigenen
# TED-AT-Bestand gemessen, nicht aus dem Gedächtnis gesetzt.
#
# Österreich ist deutschsprachig, aber NICHT „DE mit anderer Flagge". Drei
# Unterschiede, die gemessen aufgefallen sind und die Muster tragen:
#   1. Eigene Rechtsformen: GesmbH/Ges.m.b.H. (3.140), e.U. (743, Einzelunternehmer),
#      OG (578, löste 2007 die OHG ab), KEG/OEG (94, Altbestand), GesbR, eGen.
#      Das deutsche `\bmbh\b` greift bei „Ges.m.b.H." NICHT — die Punkte trennen.
#   2. Behörden heißen anders: Magistrat, Bezirkshauptmannschaft, Marktgemeinde,
#      Reinhalteverband, Landesverwaltungsgericht.
#   3. Die großen Auftraggeber firmieren ausgeschrieben. ASFINAG steht in 20.293
#      Nennungen als „Autobahnen- und Schnellstraßen-Finanzierungs-AG" — wer nur
#      auf das Kürzel prüft, verliert den größten Käufer des Landes.
# Gemessene Abdeckung von `public_name` auf Käufernamen: 72,1 %.
# ---------------------------------------------------------------------------
AT = Locale(
    "AT", name="Österreich (erste Fassung — an TED-AT-Daten geprüft, nicht abschließend)",
    legal_forms=(r"gesellschaft mit beschraenkter haftung", r"aktiengesellschaft",
                 r"kommanditgesellschaft", r"offene gesellschaft", r"privatstiftung",
                 r"eingetragene genossenschaft", r"genossenschaft", r"eingetragener verein",
                 # Punkte statt Wortgrenzen: „ges.m.b.h.", „gesmbh", „m.b.h." in einem Muster.
                 # „gesellschaft mbh" MUSS vor „ges.m.b.h." stehen und als GANZES gehen:
                 # sonst frisst das kuerzere Muster nur das „mbh" und laesst das Wort
                 # „gesellschaft" stehen, womit „OeBB-Technische Services-GmbH" und
                 # „OeBB-Technische Services-Gesellschaft mbH" verschiedene Kaeufer bleiben.
                 # Gemessen 2026-08-23 an AT: dieses eine Muster belegt 308 Paare zusaetzlich.
                 r"gesellschaft\s?m\.?\s?b\.?\s?h\.?",
                 r"ges\.?\s?m\.?\s?b\.?\s?h\.?", r"\bm\.?\s?b\.?\s?h\.?\b", r"gmbh",
                 r"\bag\b", r"\bog\b", r"\bkg\b", r"\bohg\b", r"\bkeg\b", r"\boeg\b",
                 r"\bse\b", r"\begen\b", r"\bgesbr\b", r"\be\.? ?u\b", r"\be\.? ?v\b"),
    representation=r"\s*[,/;–-]?\s*vertreten durch\b.*$",
    # „Magistrat der Stadt Wien - Magistratsabteilung 34" → der Käufer ist der Magistrat.
    subdivision=(r"\s*[,/|;–-]\s*(magistratsabteilung|abteilung|referat|fachbereich|"
                 r"gruppe|dienststelle|geschaeftsbereich|geschaeftsstelle|"
                 r"zentrale vergabestelle|zentraler einkauf|stabsstelle)\b.*$"),
    unit_numbers=r"\b(ma|abt|gr)\s*\d+\b",
    lead_articles=r"^(das|der|die|den|dem)\s+",
    consortium=(r"\b(arge\b|arbeitsgemeinschaft|bietergemeinschaft|konsortium|"
                r"gemeinschaft der)"),
    association=(r"\b(e\.? ?v\b|verein\b|verband\b|gewerkschaft\b|gemeinnuetzig)"
                 r"|\b(privat)?stiftung\b(?!\s*(&|und)\s*co)"),
    public=(r"(republik oesterreich|bundesministerium|bundesamt|bundesanstalt|"
            r"landesregierung|landeshauptstadt|bezirkshauptmannschaft|magistrat|"
            r"marktgemeinde|stadtgemeinde|gemeindeverband|reinhalteverband|"
            r"abwasserverband|wasserverband)|^(stadt|gemeinde|land)\s"),
    # Ziviltechniker (ZT) ist die österreichische Sammelbezeichnung für Ingenieur-
    # und Architekturbüros — in DE gibt es dafür kein Gegenstück.
    trade_word=(r"(elektro|installat|spengler|baumeister|zimmerei|tischlerei|schlosserei|"
                r"malerei|dachdeck|sanitaer|heizung|garten|transport|logistik|reinigung|"
                r"entsorgung|recycling|technik|technolog|handel|vertrieb|montage|"
                r"planung|architekt|ingenieur|ziviltechnik|\bzt\b|beratung|consulting|"
                r"software|system|solution|engineering|buero|apotheke|verlag|gebaeude|"
                r"facility|catering|security|bewachung|werkstatt|handwerk|zentrum)"),
    person=rf"^(?:dr\.|prof\.|dipl\.[-\w]*|mag\.|ing\.|di)?\s*{_NAME_PART}(?:\s+{_NAME_PART}){{1,2}}$",
    text_winner_marker=r"wirtschaftsteilnehmer|zuschlagsempfaenger|auftragnehmer",
    text_skip=r"^(wurde|vergeben|los|bezeichnung|v\.|abschnitt|name und|ursprüng|—|-|siehe|nummer)",
    text_not_awarded="nicht vergeben",
    # Gemessen: nur 1,1 % der AT-Gewinnerkontakte nutzen Freemail (DE-Vergleichswert
    # in der Zielgruppe 5,8 %). aon.at führt mit 463 — das österreichische t-online.
    freemail={"gmail", "googlemail", "gmx", "aon", "a1", "chello", "utanet", "inode",
              "liwest", "kabsi", "tele2", "drei", "hotmail", "outlook", "yahoo", "aol",
              "live", "msn", "icloud", "me", "protonmail", "proton", "mail", "email"},
    # `gv` ist die österreichische Behörden-Sammeldomain (bvwg.gv.at, bbg.gv.at,
    # wien.gv.at — 74.445 Kontakte). Sie fiele auch über den 2-Zeichen-Guard in
    # `gold.domain_group_label` heraus; hier steht sie, damit das Absicht ist und
    # nicht Zufall. `ac` ebenso für die Universitäten (tuwien.ac.at).
    public_domain_slds={"gv", "ac", "parlament", "bmlv"},
    public_name=(r"\bstadt\b|\bgemeinde\b|marktgemeinde|stadtgemeinde|landeshauptstadt|"
                 r"magistrat|bezirkshauptmannschaft|\bland\b|bundesland|landesregierung|"
                 r"bundesministerium|bundesamt|bundesanstalt|republik oesterreich|\bbund\b|"
                 r"burghauptmannschaft|nationalbank|bundesforste|"
                 r"reinhalteverband|abwasserverband|wasserverband|gemeindeverband|\bverband\b|"
                 r"krankenanstalt|krankenhaus|klinik|\blkh\b|spital|gesundheitskasse|"
                 r"gebietskrankenkasse|gesundheitsagentur|gesundheitsholding|\bauva\b|\boegk\b|"
                 r"versicherungsanstalt|sozialversicherung|"
                 r"universitaet|fachhochschule|hochschule|\bschule\b|paedagogisch|"
                 r"verwaltungsgericht|\bgericht\b|\bpolizei\b|staatsanwalt|"
                 # Ausgeschriebene Firmennamen der großen öffentlichen Auftraggeber.
                 r"asfinag|schnellstrassen-finanzierungs|\boebb\b|austro control|"
                 r"austrian power grid|oesterreichische post|wiener linien|wiener netze|"
                 r"wien energie|bundesbeschaffung|\bbbg\b|bundesrechenzentrum|\bbrz\b|"
                 r"bundesimmobilien|arbeitsmarktservice|\bams\b|"
                 r"eigenbetrieb|oeffentlichen rechts|koerperschaft|\bkammer\b"),
    kind_framework_kw="rahmen",
    kind_recurring_kw=("wartung|pflege|lizenz|reinigung|bewirtschaft|unterhalt|betreib|"
                       "betrieb|entsorgung|catering|bewachung|winterdienst|support|hosting|"
                       "miete|leasing|verpflegung|instandhalt|betreuung|dienstleistung|"
                       "service|beratung"),
    kind_oneoff_kw=("neubau|sanierung|umbau|abbruch|errichtung|rohbau|ausbau|modernisierung|"
                    "fassad|dachsanierung|erweiterungsbau|zubau|anbau|generalsanierung"),
    register_path=None,   # TODO: Firmenbuch (AT) — anders als das deutsche HR-Extrakt
                          # nicht frei abrufbar; bis dahin bleibt national_id die einzige
                          # belegte Kennung.
    cpi={},               # TODO: VPI der Statistik Austria. Solange leer, bleibt
                          # value_real_2020 für AT NOMINAL — Zeitreihen über Jahre hinweg
                          # sind damit nicht inflationsbereinigt. Der DE-Index wäre ein
                          # Näherungswert, aber geraten ist hier schlimmer als leer.
    # ACHTUNG, Unterschied zu DE: in Deutschland IST NUTS-1 das Bundesland, in
    # Österreich sind das die drei Großregionen — das Bundesland liegt auf NUTS-2.
    # Der heutige Leser (app/dashboard.py) schneidet mit `[:3]`, greift also die
    # Großregionen. Die 4-stelligen Einträge stehen für einen künftigen `[:4]`-Leser
    # bereit; sie stören den 3-stelligen Zugriff nicht.
    nuts_region={"AT1": "Ostösterreich", "AT2": "Südösterreich", "AT3": "Westösterreich",
                 "AT11": "Burgenland", "AT12": "Niederösterreich", "AT13": "Wien",
                 "AT21": "Kärnten", "AT22": "Steiermark", "AT31": "Oberösterreich",
                 "AT32": "Salzburg", "AT33": "Tirol", "AT34": "Vorarlberg"},
    succ_stopwords=("der die das und fur von zur zum den im am auf mit los bau neubau sanierung "
                    "lieferung leistungen ausschreibung offentliche vergabe beschaffung "
                    "stadt gemeinde marktgemeinde land magistrat bezirk amt objekt").split(),
)


# ---------------------------------------------------------------------------
# LU — an 6.142 luxemburgischen Bekanntmachungen (2024-01 bis 2026-06) gemessen:
# 762 Käufernamen, 2.647 Firmennamen. Nicht aus dem Gedächtnis gesetzt.
#
# ⚠ ZUERST: dieser Bestand war beim ersten Einlesen zu 22 % NICHT luxemburgisch.
# Der TED-eSender („Publications Office of the European Union") sitzt in Luxemburg
# und zählte als Käufer — s. schema._eforms_buyer_org_ids. Alle Zahlen hier stehen
# NACH dem Fix; wer sie nachrechnet und höhere findet, misst den alten Fehler mit.
#
# Vier Eigenheiten, die gemessen aufgefallen sind und die Muster tragen:
#
#   1. FRANZÖSISCH IST DIE ARBEITSSPRACHE, nicht Deutsch. Gemessen: fr 4.734,
#      en 1.114, de 266. Ein DE-Profil trifft hier fast nichts.
#   2. S.À R.L. IN SIEBEN SCHREIBWEISEN: sarl (205), sàrl (152), s.à r.l. (145),
#      s. à r. l. (27), s.a.r.l. (21), s.a r.l. (19), s.àr.l. (16). Das ist dieselbe
#      Falle wie „Ges.m.b.H." in Österreich: ein Muster muss ALLE fassen, sonst
#      zerfällt eine Firma in sieben. Deshalb `s\.?\s?a\.?\s?r\.?\s?l\.?` mit
#      optionalen Punkten UND Leerzeichen an jeder Fuge.
#   3. DERSELBE KÄUFER IN ZWEI SPRACHEN. „European Commission, DG ESTAT" und
#      „Commission européenne, OIL" sind dasselbe Haus. Das hat DACH nie gehabt,
#      und `subdivision` muss deshalb die Trennwörter beider Sprachen kennen.
#      ⚠ Die Sprachdublette selbst löst das Profil NICHT — das bliebe Aufgabe der
#      Entity-Resolution und ist hier bewusst offen.
#   4. EU-EINRICHTUNGEN SIND EIN ACHTEL DES MARKTES. EIB (310), Parlament (118),
#      Eurostat (69), Kommission (68), Amt für Veröffentlichungen (63), ESPON
#      (115), EuroHPC (58) — zusammen rund 12 % aller LU-Bekanntmachungen. Sie
#      sitzen wirklich in Luxemburg und gehören dazu; `public_name` führt sie
#      deshalb ausdrücklich, sonst gälte der grösste Auftraggeber als Firma.
#
# ⚠ Akzente sind KEIN Problem: entities.strip_accents macht NFKD und wirft die
# Kombinationszeichen weg, „l'État" und „l'Etat" fallen zusammen (geprüft). Das
# gilt für Französisch — NICHT für Polnisch, wo `Ł` kein Kombinationszeichen ist
# (s. Kapitel 14 der Länder-Bibel).
#
# ⚠ Ein bewusst getragener Fehlgriff: `\bag\b` frisst „AG Insurance" (belgischer
# Versicherer, AG gehört zum Namen). Gemessen: 1 Fall in 3.409 Namen. Dieselbe
# Risikoklasse, die das AT-Profil trägt.
# ---------------------------------------------------------------------------
LU = Locale(
    "LU", name="Luxemburg (erste Fassung — an TED-LUX-Daten geprüft, nicht abschließend)",
    # Die einheimischen Formen zuerst, dann die grenznahen (DE/BE/FR/NL) und die
    # internationalen — Luxemburg vergibt stark an ausländische Bieter.
    legal_forms=(r"societe a responsabilite limitee", r"societe anonyme",
                 r"societe cooperative", r"societe civile immobiliere",
                 r"association sans but lucratif",
                 # ⚠ Die lange Form MUSS vor die kurze: sonst frisst das kürzere
                 # Muster nur das „sarl" und lässt „societe" stehen.
                 r"s\.?\s?a\.?\s?r\.?\s?l\.?", r"\bsarl\b", r"\bsecs\b", r"\bscsp\b",
                 r"\bs\.?c\.?s\.?\b", r"\bs\.?c\.?a\.?\b", r"\bscop\b",
                 r"\basbl\b", r"a\.?\s?s\.?\s?b\.?\s?l\.?",
                 r"\bgie\b", r"\beeig\b", r"\bsepcav\b", r"\bsicav\b", r"\bsicar\b",
                 r"s\.?\s?a\.?(?![a-z])", r"\bsa\b",
                 r"\bgmbh\b", r"\bag\b", r"\bkg\b", r"\bohg\b", r"\bse\b",
                 r"\bsprl\b", r"\bsrl\b", r"\bspa\b", r"\bsnc\b", r"\bsas\b",
                 r"\bb\.?\s?v\.?\b", r"\bn\.?\s?v\.?\b", r"\bltd\b", r"\bplc\b",
                 r"\bgbr\b", r"\bug\b"),
    representation=r"\s*[,/;–-]?\s*(represente(e)? par|vertreten durch|represented by)\b.*$",
    # „Ministère de l'Éducation nationale, de l'Enfance et de la Jeunesse" bleibt
    # ganz — getrennt wird nur an echten Organisationseinheiten.
    subdivision=(r"\s*[,/|;–-]\s*(direction generale|direction|division|departement|"
                 r"service central|service|office|unite|cellule|"
                 r"directorate-general|directorate|department|unit|"
                 r"generaldirektion|abteilung|dienststelle|"
                 # ⚠ Die Kürzel der EU-Dienststellen — dieselbe Regel wie „Magistrat der
                 # Stadt Wien - Magistratsabteilung 34" im AT-Profil: die Generaldirektion
                 # ist eine Abteilung, kein eigener Auftraggeber. Gemessen: fasst 10 Namen
                 # zu 5 Häusern zusammen, bei 0 Fehlgriffen in 3.409 Namen.
                 r"dg|oil|oib|inlo|scic)\b.*$"),
    unit_numbers=_NEVER,
    lead_articles=r"^(le|la|les|l|du|de la|des|der|die|das|the)\s+",
    consortium=(r"\b(groupement|consortium|consorzio|bietergemeinschaft|"
                r"arbeitsgemeinschaft|arge\b|joint venture|momentane)"),
    association=r"\b(asbl|association|fondation|stiftung|verein|federation|syndicat\b)",
    # Luxemburg vergibt auf drei Ebenen: Staat (ministere/administration/etat),
    # Gemeinde (commune/ville/administration communale) und Zweckverband
    # (syndicat intercommunal — 121 Nennungen, eine tragende Bauform).
    # Dazu die EU-Einrichtungen, s. Punkt 4 oben.
    public=(r"(administration communale|administration|ministere|etat du grand|"
            r"grand-?duche|gouvernement|commune de|\bville de\b|syndicat|"
            r"fonds du logement|fonds belval|\bfonds\b|centre hospitalier|"
            r"chambre des|police grand|armee luxembourgeoise|"
            r"european (commission|parliament|investment bank|court|union)|"
            r"commission europeenne|parlement europeen|banque europeenne|"
            r"publications office|eurostat|espon|eurohpc|"
            r"cour de justice|court of justice)"),
    trade_word=(r"(construction|batiment|genie civil|electric|informatique|logiciel|"
                r"nettoyage|entretien|maintenance|transport|ingenierie|architecte|"
                r"securite|conseil|formation|"
                r"bau\b|elektro|reinigung|wartung|planung|"
                r"software|cleaning|engineering|consulting|security)"),
    person=rf"^(?:dr\.|prof\.|m\.|mme\.?|herr|frau|mr\.?|ms\.?)?\s*{_NAME_PART}(?:\s+{_NAME_PART}){{1,2}}$",
    text_winner_marker=r"adjudicataire|attributaire|zuschlagsempfanger|contractor|titulaire",
    text_skip=r"^(le|la|lot|section|denomination|nom et|siehe|nummer|v\.|—|-|adresse)",
    text_not_awarded="non attribue|non adjuge|kein zuschlag|not awarded",
    # ⚠ pt.lu und internet.lu sind die einheimischen Massenanbieter — wo in DE
    # t-online steht. Ohne sie gälte jede Firma mit pt.lu-Adresse als eigene Gruppe.
    freemail={"gmail", "googlemail", "pt", "internet", "vo", "education",
              "gmx", "hotmail", "outlook", "yahoo", "live", "icloud",
              "protonmail", "proton", "hotmail", "orange", "post"},
    # ⚠ Luxemburg hat KEINE eigene Behörden-SLD wie admin.ch oder bund.de: der
    # Staat nutzt <ressort>.public.lu, die Gemeinden <gemeinde>.lu. Deshalb trägt
    # public_name hier die Last fast allein.
    public_domain_slds={"public", "etat", "gouvernement", "europa", "eib", "cec"},
    public_name=(r"administration|ministere|commune|\bville\b|syndicat|etat\b|"
                 r"grand-?duche|gouvernement|fonds\b|"
                 r"centre hospitalier|hopital|clinique|universite|university|"
                 r"lycee|ecole|police|armee|chambre des|"
                 r"european|europeen|europeenne|eurostat|espon|eurohpc|"
                 r"commission|parliament|parlement|investment bank|"
                 r"institute of|luxembourg institute"),
    kind_framework_kw="accord.?cadre|contrat.?cadre|rahmenvertrag|rahmenvereinbarung|framework",
    kind_recurring_kw=("entretien|maintenance|nettoyage|exploitation|licence|support|"
                       "location|abonnement|gestion|surveillance|"
                       "wartung|unterhalt|reinigung|betrieb|lizenz|miete"),
    kind_oneoff_kw=("construction|renovation|demolition|amenagement|transformation|"
                    "extension|assainissement|"
                    "neubau|umbau|sanierung|erweiterung|rueckbau"),
    register_path=None,   # TODO: RCS Luxembourg (Registre de Commerce et des Sociétés)
    cpi={},               # TODO: STATEC-Preisindex; ohne ihn bleibt value_real_2020 nominal
    # ⚠ EINE EINZIGE REGION, und das ist kein Fehler. Der NUTS-Katalog führt für
    # Luxemburg genau vier Codes — LU, LU0, LU00, LU000 — und alle heissen
    # „Luxembourg". Eine Umkreissuche über Regionen ist hier sinnlos; wer Nähe
    # braucht, nimmt die PLZ-Ebene (s. gold._REGION_STELLEN, LU: 3).
    nuts_region={"LU0": "Luxembourg"},
    succ_stopwords=("le la les l du de des et pour avec sur dans lot lots marche marches "
                    "travaux fourniture fournitures prestation prestations service services "
                    "commune ville administration etat public appel offre offres "
                    "der die das und fuer los lose "
                    "the and for of tender lot supply services contract").split(),
)


LOCALES = {loc.code: loc for loc in (DE, FR, CH, AT, LU)}
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
