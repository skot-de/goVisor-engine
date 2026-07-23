"""Das normalisierte Silber-Schema — echte Tabellen, kein JSON.

Drei Schema-Generationen (vor-2014, 2014er, eForms) bilden auf *ein*
gemeinsames relationales Modell ab. Jede Tabelle ist eine eigene Parquet-
Datei, partitioniert nach Land/Jahr, verknüpft über ``notice_id``:

    notices        ── eine Zeile pro Notice (Kern)
    notice_parties ── jede Organisation: Käufer, Gewinner, Nachprüfstelle …
    lots           ── eine Zeile pro Los
    notice_cpv     ── CPV je Notice        (n:m)
    lot_cpv        ── CPV je Los           (n:m)
    award_criteria ── Zuschlagskriterien

Verlustfreiheit liegt in **Bronze** (unverändertes Original-XML), nicht hier.
Ein seltenes, noch nicht gemapptes Feld ist aus Bronze nachziehbar — deshalb
braucht Silber keinen JSON-Blob und kann sauber typisiert bleiben.
"""

from __future__ import annotations

import pyarrow as pa

# Bumpt, wenn sich eine Tabellenstruktur ändert.
MODEL_VERSION = 3

NOTICES = pa.schema([
    ("notice_id", pa.string()),
    ("publication_number", pa.string()),
    ("oj_ref", pa.string()),
    ("publication_date", pa.date32()),
    ("ted_url", pa.string()),
    ("country", pa.string()),               # führender Käufer
    ("buyer_countries", pa.list_(pa.string())),
    ("year", pa.int16()),
    ("month", pa.int8()),
    ("schema_gen", pa.string()),            # 'legacy' | 'eforms'
    ("form_type", pa.string()),
    ("notice_kind", pa.string()),           # 'cn' | 'can' | 'pin' | 'corrigendum' | 'other'
    ("language", pa.string()),
    ("title", pa.string()),
    ("description", pa.string()),
    ("description_field", pa.string()),
    ("cpv_main", pa.string()),
    ("performance_nuts", pa.string()),
    ("contract_nature", pa.string()),       # works | supplies | services (TED BT-23)
    ("procedure_type", pa.string()),
    ("submission_deadline", pa.date32()),
    ("portal_url", pa.string()),
    ("estimated_value", pa.float64()),
    ("final_value", pa.float64()),
    ("value_currency", pa.string()),
    ("award_date", pa.date32()),
    ("start_date", pa.date32()),
    ("end_date", pa.date32()),
    ("lot_count", pa.int32()),
    ("text_chars", pa.int32()),
    # Verweis auf die referenzierte Notice (Vergabe → ihre Bekanntmachung)
    ("ref_publication_number", pa.string()),
    ("ref_ted_url", pa.string()),
    # Qualitätsmarken — leer heißt: sauber durchgelaufen
    ("flags", pa.list_(pa.string())),
    ("unknown_country_codes", pa.list_(pa.string())),
])

# Jede Organisation, die in einer Notice vorkommt, mit ihrer Rolle.
NOTICE_PARTIES = pa.schema([
    ("notice_id", pa.string()),
    ("role", pa.string()),                  # 'buyer' | 'winner' | 'review' | 'mediation'
    ("seq", pa.int16()),                    # Reihenfolge innerhalb der Rolle
    ("name", pa.string()),
    ("national_id", pa.string()),
    ("town", pa.string()),
    ("postal_code", pa.string()),
    ("country", pa.string()),
    ("nuts", pa.string()),
    ("email", pa.string()),
    ("phone", pa.string()),
    ("contact_person", pa.string()),
    ("url", pa.string()),
    ("is_sme", pa.bool_()),
    ("in_consortium", pa.bool_()),
])

LOTS = pa.schema([
    ("notice_id", pa.string()),
    ("lot_id", pa.string()),
    ("title", pa.string()),
    ("description", pa.string()),
    ("value_amount", pa.float64()),
    ("value_currency", pa.string()),
    ("start_date", pa.date32()),
    ("end_date", pa.date32()),
    ("performance_nuts", pa.string()),
    # Kategorie 6: Laufzeit, Optionen, Verlängerung
    ("duration_months", pa.int32()),
    ("has_options", pa.bool_()),
    ("options_description", pa.string()),
    ("has_renewal", pa.bool_()),
    ("renewal_description", pa.string()),
    ("max_renewals", pa.int32()),
])

# Kategorie 9: Eignungs-/Teilnahmebedingungen — wer darf bieten.
REQUIREMENTS = pa.schema([
    ("notice_id", pa.string()),
    ("lot_id", pa.string()),
    ("kind", pa.string()),        # suitability|economic|technical|performance|exclusion|profession|deposit
    ("type_code", pa.string()),
    ("text", pa.string()),
])

# Kategorie 5: Wettbewerb je vergebenem Los — Bieterzahl = Verdrängbarkeit.
AWARDS = pa.schema([
    ("notice_id", pa.string()),
    ("lot_id", pa.string()),
    ("winner_name", pa.string()),
    ("winner_national_id", pa.string()),
    ("num_tenders", pa.int32()),
    ("num_tenders_sme", pa.int32()),
    ("num_tenders_other_eu", pa.int32()),
    ("num_tenders_non_eu", pa.int32()),
    ("num_tenders_electronic", pa.int32()),
])

NOTICE_CPV = pa.schema([
    ("notice_id", pa.string()),
    ("cpv_code", pa.string()),
    ("is_main", pa.bool_()),
])

LOT_CPV = pa.schema([
    ("notice_id", pa.string()),
    ("lot_id", pa.string()),
    ("cpv_code", pa.string()),
    ("is_main", pa.bool_()),
])

AWARD_CRITERIA = pa.schema([
    ("notice_id", pa.string()),
    ("lot_id", pa.string()),
    ("kind", pa.string()),                  # 'price' | 'quality' | 'cost'
    ("name", pa.string()),
    ("weight", pa.string()),                # roh: mal Zahl, mal Text
    # eForms-ParameterCode. Entscheidet, WIE die Zahl zu lesen ist: per-* = Prozent,
    # poi-*/dec-* = Punkte (auf die Los-Summe zu normieren), ord-imp = Rang, kein
    # Gewicht. NULL bei Legacy (dort ist AC_WEIGHTING durchgaengig Prozent).
    ("weight_kind", pa.string()),
])

# Auffang-Tabelle: JEDER Blattwert jeder Notice, adressiert über seinen Pfad.
# Redundant zu den typisierten Tabellen, aber die Verlust-Garantie: nichts wird
# weggeworfen, alles ist per SQL auffindbar (WHERE path LIKE ...). Exotisches
# landet hier unter seinem Pfad statt in einer Kategorie.
ATTRIBUTES = pa.schema([
    ("notice_id", pa.string()),
    ("path", pa.string()),
    ("value", pa.string()),
])

# Tabellenname → Schema. Der Silber-Builder schreibt je eine Parquet-Datei.
TABLES = {
    "notices": NOTICES,
    "notice_parties": NOTICE_PARTIES,
    "lots": LOTS,
    "notice_cpv": NOTICE_CPV,
    "lot_cpv": LOT_CPV,
    "award_criteria": AWARD_CRITERIA,
    "awards": AWARDS,
    "requirements": REQUIREMENTS,
    "attributes": ATTRIBUTES,
}
