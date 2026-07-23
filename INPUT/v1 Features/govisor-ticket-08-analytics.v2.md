# Feature #8: Analytics (v2)

**Produkt:** goVisor
**Version:** V1
**Status:** Überarbeitet gegen v2-Entscheidungen (2026-07-20)
**Basis:** `govisor-ticket-08-analytics.md` (Original unverändert)

> **Was v2 ändert:** Revenue/Success-Fee-Events auf das **Rechnung-+-HITL-Modell**
> (Ticket 06 v2) umgestellt; **Wins aus TED gemessen**, nicht aus Selbstauskunft
> (`win_reported` ist durch die Prämie verzerrt); Success-Fee-Funnel um Attribution/
> Wert/HITL ausgebaut; kleinere Präzisierungen. **Alle anderen Event-Kategorien
> (Acquisition, Activation, Engagement, Feature Adoption, Content Quality, Match
> Quality, Retention, Performance, Errors, GDPR) bleiben unverändert übernommen.**

---

## Kern-Korrektur: Revenue-Events (Ticket-06-v2-Modell)

Die Erfolgsprämie wird **nicht automatisch abgebucht**, sondern als Rechnung mit
Human-in-the-Loop erstellt. Die Events müssen genau diesen Flow abbilden:

| Event | Properties | Beschreibung |
|-------|------------|--------------|
| `subscription_started` / `_renewed` / `_cancelled` | `plan`, `amount`, `reason`, `tenure_days` | wie Original |
| `grace_period_ended` | `user_id` | Schonfrist vorbei |
| `award_matched_to_user` | `award_notice_id`, `tender_pub_number`, `group_id` | **NEU:** TED-Zuschlag auf bestätigte User-Gruppe gematcht |
| `success_fee_attributed` | `lead_id`, `days_since_click` | **NEU:** geklickte Ausschreibung → Zuschlag, im 12-Mo-Fenster |
| `success_fee_value_resolved` | `value_source` (`echt`/`kunde_bestaetigt`/`kunde_offen`), `band` | **NEU:** Wert-Ermittlung |
| `success_fee_needs_confirmation` | `lead_id`, `anchor_band` | **NEU:** kein echter Wert → Kunde bestätigt Band |
| `success_fee_anchor_flagged` | `lead_id`, `claimed_band`, `anchor_band` | **NEU:** Lowball-Wächter schlägt an (≥2 Bänder unter Anker) |
| `success_fee_invoice_drafted` | `lead_id`, `band`, `amount`, `value_source` | **ERSETZT** `success_fee_triggered` |
| `success_fee_hitl_approved` | `lead_id`, `reviewer` | **NEU:** menschliche Freigabe |
| `success_fee_invoice_sent` | `lead_id`, `amount` | **ERSETZT** `success_fee_charged` |
| `success_fee_paid` | `lead_id`, `amount` | Zahlung eingegangen |
| `success_fee_disputed` / `_waived` | `lead_id`, `reason` | **NEU:** Widerspruch / Erlass |

> Entfernt: `success_fee_triggered` („Abbuchung gestartet"), `success_fee_charged`
> („Fee erfolgreich") — beides modellierte die aufgegebene Auto-Abbuchung.

---

## Kern-Korrektur: Wins aus TED, nicht aus Selbstauskunft

**Problem:** `win_reported` (Nutzer meldet Gewinn) löst eine Gebühr aus → Nutzer haben
einen **Anreiz, Wins zu verschweigen**. Als Kern-Metrik systematisch unter-gezählt.

| Metrik | v1 (falsch) | v2 (korrekt) |
|---|---|---|
| „Wins" | `win_reported` (Selbstauskunft) | **TED-Match** (`award_matched_to_user`, 96 % Gewinner publiziert) |
| Rolle von `win_reported` | Primär | Nur für 4 %-Blind-Spot; **bewusst als unter-gemeldet behandeln** |

**North Star „Wins Reported" → „Wins Detected" (TED-basiert).** Der Wert-Proxy bleibt,
aber aus der verlässlichen Quelle.

---

## Kern-Korrektur: Success-Fee-Funnel (ausgebaut)

```
lead_analysis_opened   (geklickte Ausschreibung, Timestamp)
    │
    ▼  Zuschlag in TED
award_matched_to_user          (bestaetigte Gruppe)
    │
    ▼
success_fee_attributed         (via ref_publication_number, <=12 Mo)
    │
    ├─► grace_period_active → kein Fee
    │
    ▼  Schonfrist vorbei
success_fee_value_resolved
    │
    ├─► echt          → invoice_drafted
    └─► kein Wert      → needs_confirmation → (anchor_flagged?) → Kunde bestaetigt
                              │
                              ▼
                        invoice_drafted
    │
    ▼
hitl_approved → invoice_sent → paid    ← REVENUE
                     │
                     └─► disputed / waived
```

Der Funnel misst jetzt die **echten Abbruchstellen** (Attribution, Wert-Bestätigung,
HITL, Zahlung) statt eines nicht existierenden Auto-Charge.

---

## Kleinere Präzisierungen

| Stelle | v2 |
|---|---|
| **MRR-Formel** | nicht `× €29` hardcoden → auf Pricing-Config verweisen (Betrag bewusst offen) |
| **`win_rate_by_cpv` / `_by_buyer`** | „erst ab N Nutzern belastbar" kennzeichnen — bei kleiner Basis rauschig |
| **`competitive_leads`** (viele Nutzer auf einem Lead) | intern ok, aber **nie an Nutzer ausspielen** („15 Firmen schauen das an") — Wettbewerbs-Signal, gleiche Sensibilität wie Preisdaten (s. `produkt-vision.md` §4) |
| **Success-Fee-Revenue-Metrik** | `sum(invoice_paid)` statt `sum(fees_charged)` |

---

## Unverändert übernommen (gut & konsistent)

- **Content Quality** (`estimate_flag_shown`, `incumbent_shown/hidden` mit confidence) —
  implementiert direkt die v2-Ehrlichkeits-Entscheidungen (Schätz-Flags, Incumbent-Gate).
- **`firm_resolved`/`firm_unresolved`** — matcht das Onboarding-Entity-Gate (Ticket 07 v2).
- **`relevance_score` mit `band`** (nicht %) — konsistent „Scores als Bänder".
- **`analysis_to_win`/`win_without_analysis`** — richtige Attributions-Messung.
- **Acquisition / Activation / Engagement / Feature Adoption / Retention / Performance /
  Errors** — Event-Listen wie Original.
- **GDPR** (Pseudonymisierung, Consent, 2-Jahre-Retention, Opt-Out) + **PostHog EU/
  self-host** — solide Privacy-Basis.
- **`analytics_events`-Datenmodell**, Cohorts, Monitoring-Alerts — wie Original.

---

## Akzeptanzkriterien (geänderte)

| # | Kriterium |
|---|-----------|
| 6 | **Revenue-Events im HITL-/Rechnungs-Modell** (drafted → hitl_approved → sent → paid) |
| 6b | **Wins aus TED gemessen** (`award_matched_to_user`), nicht aus `win_reported` |
| 7 | **Success-Fee-Funnel** mit Attribution / Wert-Bestätigung / HITL / Zahlung |
| (1–5, 8–10) | wie Original |

---

## Offene Fragen (ergänzt)

| # | Frage | Vorschlag |
|---|-------|-----------|
| 1 | PostHog vs Mixpanel vs Amplitude | PostHog (EU, self-host) — wie Original |
| 5 | Wie HITL-Review-Schritte tracken (Latenz, Ablehnungsquote)? | eigene Events `hitl_*`, s. Ticket 06 |
| 6 | Wird `success_fee_disputed`-Rate zur Anker-Kalibrierung genutzt? | ja — hohe Dispute-Rate = Anker/Band-Logik nachziehen |
