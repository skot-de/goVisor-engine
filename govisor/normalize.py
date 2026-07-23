"""Eine geparste Notice → Zeilen für die normalisierten Tabellen.

Kein JSON. Jede Notice zerfällt in Zeilen über mehrere Tabellen, verknüpft
über ``notice_id``. Verlustfreiheit liegt in Bronze; hier wird sauber
strukturiert, was Bedeutung trägt.
"""

from __future__ import annotations

import datetime as _dt

from . import flatten, schema


def _date(iso: str | None) -> _dt.date | None:
    if not iso:
        return None
    try:
        return _dt.date.fromisoformat(iso)
    except ValueError:
        return None


def rows(notice: schema.Notice, raw: bytes, country: str, year: int, month: int) -> dict[str, list[dict]]:
    """Zeilen je Tabelle für eine Notice."""
    nid = notice.notice_id

    notices = [{
        "notice_id": nid,
        "publication_number": notice.publication_number,
        "oj_ref": notice.oj_ref,
        "publication_date": _date(notice.publication_date),
        "ted_url": notice.ted_url,
        "country": country,
        "buyer_countries": notice.buyer_countries,
        "year": year,
        "month": month,
        "schema_gen": notice.schema,
        "form_type": notice.form_type,
        "notice_kind": notice.notice_kind,
        "language": notice.language,
        "title": notice.title,
        "description": notice.description,
        "description_field": notice.description_field,
        "cpv_main": notice.cpv_main,
        "estimated_value": notice.estimated_value,
        "final_value": notice.final_value,
        "value_currency": notice.value_currency,
        "award_date": _date(notice.award_date),
        "start_date": _date(notice.start_date),
        "end_date": _date(notice.end_date),
        "lot_count": len(notice.lots),
        "performance_nuts": notice.performance_nuts,
        "contract_nature": notice.contract_nature,
        "procedure_type": notice.procedure_type,
        "submission_deadline": _date(notice.submission_deadline),
        "portal_url": notice.portal_url,
        "text_chars": notice.text_length,
        "ref_publication_number": notice.ref_publication_number,
        "ref_ted_url": notice.ref_ted_url,
        "flags": notice.flags,
        "unknown_country_codes": notice.unknown_country_codes,
    }]

    parties = []
    by_role: dict[str, int] = {}
    for party in notice.parties:
        seq = by_role.get(party.role, 0)
        by_role[party.role] = seq + 1
        parties.append({
            "notice_id": nid, "role": party.role, "seq": seq,
            "name": party.name, "national_id": party.national_id,
            "town": party.town, "postal_code": party.postal_code,
            "country": party.country, "nuts": party.nuts,
            "email": party.email, "phone": party.phone,
            "contact_person": party.contact_person, "url": party.url,
            "is_sme": party.is_sme,
            "in_consortium": party.in_consortium,
        })

    lots = [{
        "notice_id": nid, "lot_id": lot.lot_id, "title": lot.title,
        "description": lot.description, "value_amount": lot.value_amount,
        "value_currency": lot.value_currency,
        "start_date": None, "end_date": None,
        "performance_nuts": lot.performance_nuts,
        "duration_months": lot.duration_months,
        "has_options": lot.has_options,
        "options_description": lot.options_description,
        "has_renewal": lot.has_renewal,
        "renewal_description": lot.renewal_description,
        "max_renewals": lot.max_renewals,
    } for lot in notice.lots]

    requirements = [{
        "notice_id": nid, "lot_id": r.lot_id, "kind": r.kind,
        "type_code": r.type_code, "text": r.text,
    } for r in notice.requirements]

    awards = [{
        "notice_id": nid, "lot_id": a.lot_id,
        "winner_name": a.winner_name, "winner_national_id": a.winner_national_id,
        "num_tenders": a.num_tenders, "num_tenders_sme": a.num_tenders_sme,
        "num_tenders_other_eu": a.num_tenders_other_eu,
        "num_tenders_non_eu": a.num_tenders_non_eu,
        "num_tenders_electronic": a.num_tenders_electronic,
    } for a in notice.awards]

    notice_cpv = [
        {"notice_id": nid, "cpv_code": code, "is_main": (i == 0)}
        for i, code in enumerate(notice.cpv_all)
    ]

    lot_cpv = [
        {"notice_id": nid, "lot_id": lot.lot_id, "cpv_code": code, "is_main": (i == 0)}
        for lot in notice.lots for i, code in enumerate(lot.cpv_all)
    ]

    award_criteria = [{
        "notice_id": nid, "lot_id": c.lot_id, "kind": c.kind,
        "name": c.name, "weight": c.weight,
    } for c in notice.criteria]

    return {
        "notices": notices,
        "notice_parties": parties,
        "lots": lots,
        "notice_cpv": notice_cpv,
        "lot_cpv": lot_cpv,
        "award_criteria": award_criteria,
        "awards": awards,
        "requirements": requirements,
        "attributes": [
            {"notice_id": nid, "path": path, "value": value}
            for path, value in flatten.leaves(raw)
        ],
    }
