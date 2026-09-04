"""Sicherheit & Quote für die geteilte Vergabeunterlagen-Analyse (Ticket #23, §12/§14).

Der Kern-Risikofall: im selben Lead sitzen konkurrierende Bieter, eine manipulierte Checkliste
(falsche Frist, fehlende Pflichtanforderung) kann Wettbewerber schädigen (§12.2). Gegenmittel:
**Plausibilitätsabgleich** gegen TED/DÖE + **Bestätigungsschwelle** (erst nach zweitem
unabhängigem Upload ODER widerspruchsfreiem Abgleich mit exakter Angebotsfrist wird die
Checkliste für andere sichtbar). Dazu die Free/Pro-Quote (§14) und der Zeitkanal-Schutz (§12.4).

Reine, testbare Logik — Persistenz/RLS liegt im Datenmodell (supabase/0006), das Timing im Endpunkt.

⚠ **RUHEND — NICHTS HIERAUS WIRD HEUTE AUFGERUFEN.** Gemessen am 2026-09-04: keine einzige
Funktion dieses Moduls hat einen Aufrufer ausserhalb von `tests/test_docsafety.py`. Es ist
das einzige Modul in `govisor/`, auf das das zutrifft. Der Upload laeuft trotzdem:

    /api/lead-docs      jeder angemeldete Nutzer, beliebige notice_id, keine Nutzerpruefung
          ↓
    process_upload.py   schreibt web/data/doc-analysis/<id>.json  (GETEILTE Produktdaten)
          ↓
    /api/lead-detail    liest genau die und zeigt sie ALLEN Nutzern dieses Leads

Damit ist der Fall, gegen den §12.2 geschrieben wurde, offen: ein Bieter kann die Analyse,
die seine Mitbewerber im selben Lead sehen, ueberschreiben. Der Schritt, der das erlaubt,
war eine fuer sich richtige Entscheidung — der Kommentar an der Schreibstelle in
`process_upload.py` begruendet sie mit der Sichtbarkeit fuer andere. Zwei getrennt
getroffene, je richtige Entscheidungen heben einander auf.

**DER ANKER IST DA — die Sperre ist heute baubar.** `visibility_after` haengt an
`deadline_exact`, dem exakten Vergleich der Angebotsfrist. Gemessen an 400 zufaelligen
Analysen aus `web/data/doc-analysis/`: **268 (67 %)** tragen ein Datum in
``fristen[].wert`` (``"2026-10-16"``, ``"01.01.2027"``, ``"2026-08-18 10:00"``). Die
uebrigen 33 % fielen auf ``private`` — genau das Verhalten, das §12.2 als bekannte Grenze
beschreibt, und die sichere Richtung.

⚠ Beim Messen selbst danebengegriffen: der erste Versuch suchte ein Feld ``datum``, das es
nicht gibt, und meldete **0 von 400**. Daraus waere der Schluss „die Sperre kann gar nicht
tragen" geworden — die bequemste aller falschen Antworten. Die Werte stehen unter ``wert``.

Was zum Anschliessen fehlt, ist keine Extraktion mehr, sondern zwei Entscheidungen:
woher `process_upload.py` die Frist des Leads bekommt, und was ``private`` ohne
nutzereigenen Speicher heisst (naheliegend: dem Hochladenden antworten, aber NICHT nach
`web/data/doc-analysis/` schreiben). Beides ist Produktentscheidung, nicht Technik.
"""
from __future__ import annotations

import re

# ── §14 Free/Pro-Quote ───────────────────────────────────────────────────────────────────────
FREE_ANALYSES_PER_MONTH = 3


def quota_remaining(used_this_month: int, is_pro: bool) -> int | None:
    """Verbleibende Analysen; ``None`` = unbegrenzt (Pro). Eine Lead-Beschäftigung = eine Analyse (§14)."""
    if is_pro:
        return None
    return max(0, FREE_ANALYSES_PER_MONTH - used_this_month)


def can_analyze(used_this_month: int, is_pro: bool) -> bool:
    return is_pro or used_this_month < FREE_ANALYSES_PER_MONTH


# ── §12.2 Plausibilitätsabgleich (Dokument ↔ TED/DÖE) ─────────────────────────────────────────
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _tok(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{4,}", (s or "").lower())}


def plausibility_check(doc_meta: dict, lead_meta: dict) -> dict:
    """Frist/Wert/Vergabestelle/CPV aus dem Dokument gegen TED/DÖE (§12.2 Maßnahme 1).

    Bekannte Grenze (§12.2): nur ~65 % tragen einen echten Wert, Bandtreffer ~42 %; die
    **Angebotsfrist ist der stabilste Anker**. Rückgabe: pro Feld verglichen/übereinstimmend,
    ``deadline_exact``, ``consistent`` (kein Widerspruch auf den prüfbaren Feldern)."""
    checked, mism = [], []
    # Angebotsfrist — exakt (der Anker). Ziffern-only, damit Trenner (ISO-„T", Leerzeichen, „:")
    # keinen Scheinunterschied erzeugen.
    dl_d = re.sub(r"\D", "", doc_meta.get("deadline") or "")
    dl_l = re.sub(r"\D", "", lead_meta.get("deadline") or "")
    deadline_exact = bool(dl_d and dl_l and dl_d == dl_l)
    if dl_d and dl_l:
        checked.append("deadline")
        if not deadline_exact:
            mism.append("deadline")
    # CPV-Klasse (erste 4 Stellen)
    cd, cl = (doc_meta.get("cpv") or "")[:4], (lead_meta.get("cpv") or "")[:4]
    if cd and cl:
        checked.append("cpv")
        if cd != cl:
            mism.append("cpv")
    # Vergabestelle — Token-Überschneidung
    bd, bl = _tok(doc_meta.get("buyer")), _tok(lead_meta.get("buyer"))
    if bd and bl:
        checked.append("buyer")
        if len(bd & bl) / max(len(bd | bl), 1) < 0.3:
            mism.append("buyer")
    # Wert-Band (falls beidseitig) — nur grober Bandvergleich
    vd, vl = doc_meta.get("value_band"), lead_meta.get("value_band")
    if vd and vl:
        checked.append("value_band")
        if vd != vl:
            mism.append("value_band")
    return {"checked": checked, "mismatches": mism, "deadline_exact": deadline_exact,
            "consistent": not mism}


def visibility_after(doc_meta: dict, lead_meta: dict, independent_match: bool = False) -> str:
    """Bestätigungsschwelle (§12.2 Maßnahme 2): wann wird die Checkliste für ANDERE sichtbar?

    ``'shared'`` wenn: ein zweiter, unabhängiger Upload dieselbe Extraktion erzeugt (``independent_match``),
    ODER der Plausibilitätsabgleich auf ALLEN verfügbaren Feldern widerspruchsfrei ist UND die
    Angebotsfrist exakt stimmt. Sonst ``'private'`` (nur der hochladende Nutzer)."""
    if independent_match:
        return "shared"
    p = plausibility_check(doc_meta, lead_meta)
    if p["consistent"] and p["deadline_exact"] and p["checked"]:
        return "shared"
    return "private"


# ── §12.4 Zeitkanal ──────────────────────────────────────────────────────────────────────────
MIN_RESPONSE_SECONDS = 8.0


def padded_delay(elapsed_seconds: float, min_seconds: float = MIN_RESPONSE_SECONDS) -> float:
    """Zusätzliche Wartezeit, damit eine vorhandene (geteilte) Checkliste NICHT über eine kürzere
    Antwortzeit verraten wird (§12.4). Antwortzeit wird auf die Mindestdauer einer Neuanalyse
    angeglichen; nie negativ."""
    return max(0.0, min_seconds - max(0.0, elapsed_seconds))
