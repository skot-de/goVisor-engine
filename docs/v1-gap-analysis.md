# goVisor V1 — Gap-Analyse & Reihenfolge

> ⚠ **STAND 2026-08-21: Die Erfolgsprämie ist gestrichen.** Alles unten zum Thema Success-Fee ist Entscheidungsgeschichte, kein geltendes Modell. Aus dem Produkt ist sie entfernt (Code + Texte), das Schema räumt `supabase/0012_erfolgspraemie_entfernen.sql`.

**Status:** 2026-07-21, nach Review aller 9 Feature-Tickets (v2)
**Kernaussage:** Der analytische Datenmoat steht weitgehend. Was fehlt, ist die
**operative Verdrahtung**, die **Nicht-Ticket-Bereiche** (Settings, Billing-Tooling,
Legal) und der **Produktionsbetrieb**. Die Erfolgsprämie ist der riskanteste, am
wenigsten gebaute Teil.

---

## Strategische Empfehlung: Abo-first, Prämie als Fast-Follow

Die **Erfolgsprämie** braucht am meisten Ungebautes (Attribution, Anker, HITL-Rechnungs-
Tooling, Stripe-Deferred-Charge) **und** eine anwaltliche Klärung eines **Novums**
(§ 298 StGB / Informationsaustausch). Der **Abo-Teil** ist marktvalidiert (~29–49 €) und
nah an launchbar.

→ **V1 launcht Abo-only.** Nutzer + Daten sammeln. Erfolgsprämie als **Fast-Follow**,
sobald Attribution-Plumbing + HITL-Tooling + Rechtsklärung stehen. Nimmt Risiko,
Rechtsunsicherheit und Bau-Last aus dem kritischen Pfad.

---

## Reifegrad

| Bereich | Stand |
|---|---|
| Analytischer Datenmoat (Scores, Nachfolge, Markt) | 🟢 weitgehend da |
| Pricing-Staffel (Config) | 🟢 gebaut |
| Feature-Konzepte (9 Tickets, v2) | 🟢 durchdacht |
| Operatives Gold-Plumbing (Attribution, Anker, Matching) | 🟠 zu bauen |
| Settings / Billing-Tooling / Stripe-Lifecycle | 🔴 kein Ticket |
| Legal (Datenschutz, AGB, Erfolgsprämien-Recht) | 🔴 offen |
| Ingest-Produktionsbetrieb | 🟠 Batch → regelmäßig |

---

## Priorisierte Backlog

### P0 — Gold-Plumbing (entblockt die meisten Tickets, jetzt baubar)

| # | Baustein | Für | Gold-Output | Stand |
|---|---|---|---|---|
| 1 | **Ausschreibung↔Zuschlag-Auflösung** (`ref_publication_number`, 51 %) | 06 Attribution, 09 Award-Alert | `award_tender_link` | ✅ gebaut (373k Links, 0 Dup) |
| 2 | **Anker-Waterfall** (Ausschreibung→Vorgänger→Buyer×CPV→Buyer→CPV) | 06 Wert-Wächter | `value_anchor` | ✅ gebaut (98 % Abdeckung, 96 % im wertlosen Drittel) |
| 3 | **User→Gruppe Winner-Matching** (alle Gruppen-Entities) | 06, 07, 09 | `entity_identity` | ✅ gebaut (323k Entities → 302k Identitäten, „Gruppe=Identität") |
| 4 | **Angebotsfrist-Schätzung** (`submission_deadline` + `pub+~31T`) | 09 primärer Alert | `lead_deadline` | ✅ gebaut (672k, 0 NULL: 53 % echt / 47 % geschätzt) |
| 5 | **Laufzeit-Schätzung** (CPV-Median, wo `end_date` fehlt) | Lead-Detail | `lead_duration` | ✅ gebaut (66,8 % mit Ende, Quelle geflaggt) |
| 6 | **`leads` erweitern:** `band_source`, Deadline, Incumbent-Confidence durchreichen | alle UI-Tickets | `lead_detail` (View) | ✅ gebaut (1:1, alle Flags mit Quelle) |

**→ P0 komplett (6/6).** Alle Gold-Bausteine gebaut, in `cli.py` verdrahtet, FK-geprüft, 98 Tests grün.
Nächste Fronten: **P1 (Abo-Launch: Settings, Stripe, Legal, Landing)** und **P2 (Prämie, nach Rechtsklärung)**.

### P1 — Nicht-Ticket-Bereiche (Abo-Launch-kritisch)

| Baustein | Anmerkung |
|---|---|
| **Settings-Seite** (Profil/Gruppe/Zahlung/Account-Löschung GDPR) | ✅ Ticket 10 geschrieben; Backend bereit (`entity_identity`+`contractor_stats`); App-Bau offen |
| **Stripe-Lifecycle** (Checkout, Webhooks, Renewal, Kündigung) | Abo braucht das voll |
| **Legal**: Datenschutz, AGB, Impressum, Cookie-Consent | Launch-Pflicht |
| **Landing/Marketing-Seite** | Entry Point |
| **Produktions-Ingest** (TED regelmäßig statt Batch) | ✅ vorbereitet: `scripts/refresh.py` + launchd-Job + `docs/ingest-betrieb.md`. **Caveat:** Monatspaket-Latenz (laufender Monat verzögert); echte Tagesfrische bräuchte TED-`daily`-Ingest (nicht impl.) |

### P2 — Erfolgsprämie (Fast-Follow, nach Rechtsklärung)

| Baustein | Anmerkung |
|---|---|
| **Rechnungs-Tool + HITL-Review-UI** | Betrieb der Prämie |
| **Stripe Deferred/SetupIntent** | spätere Rechnung |
| **Anwaltliche Prüfung** § 298 StGB / BGH-Signal | vor erstem Charge |
| **Self-Report-UI** (4 %-Blind-Spot) | v2 im Ticket |

---

## Reihenfolge der Umsetzung

1. **P0-Gold-Plumbing** (1→6) — reiner Backend-Bau, keine Rechts-/Stripe-Abhängigkeit,
   entblockt Frontend + Prämie zugleich. **Start jetzt.**
2. **P1-Abo-Launch** parallel/danach — Settings, Stripe-Abo, Legal, Landing.
3. **P2-Prämie** als Fast-Follow.

Siehe auch: [`produkt-vision.md`], [`pricing-modell.md`].
