# Feature #6: Auth & Registrierung (v2)

**Produkt:** goVisor
**Version:** V1
**Status:** Überarbeitet gegen echte Datenlage (2026-07-20)
**Basis:** `govisor-ticket-06-auth.md` (Original unverändert)

> **Was v2 ändert:** Auto-Abbuchung → **Rechnung + Human-in-the-Loop**; abrechnen nur
> auf echtem Wert, Rest über **Kunden-Bestätigung mit Anker-Wächter**; Attribution auf
> die geklickte Ausschreibung (nicht die unsichere Nachfolge); `entity_id`+Confidence
> im Profil; 12-Monats-Fenster; RLS + E-Mail-Verifikation. Auth-Teile unverändert.
> **Preismodell-Mechanik/Beträge:** siehe [`docs/pricing-modell.md`](../../docs/pricing-modell.md).

---

## Datengrundlage (gemessen, DE)

Diese Zahlen begründen jede Design-Entscheidung unten:

| Messung | Wert |
|---|---|
| Vergaben mit publiziertem Gewinner | ~96 % |
| Vergaben mit **echtem** Auftragswert (`final_value`) | **64,8 %** |
| Vergaben **ohne** jeden Wert | **33,5 %** |
| Wert-Schätzung trifft exakt richtiges Band (bestes Modell) | **~42 %** → **nicht abrechnungstauglich** |
| Anker trifft richtiges Band ±1 (Wächter-Tauglichkeit) | ~68–71 % |
| Zuschlag → Ausschreibung verknüpfbar (`ref_publication_number`) | 51 %, davon 99,9 % auflösbar |
| Dauer Ausschreibung → Zuschlag (Median / p90) | 87 / 186 Tage |

**Kernkonsequenz:** Wir haben *bewiesen*, dass eine Wert-Schätzung nur ~42 % trifft.
→ **Auf einer Schätzung wird niemals abgerechnet.** Echter Wert = Fakt; sonst
Kunden-Bestätigung.

---

## Account States

| State | Basis | Analysen | Export/Alerts | Success Fee |
|-------|-------|----------|---------------|-------------|
| Anonym | — | — | — | — |
| Free | €0 | 3/30T | ✗ | ✗ |
| Paid | €29/Mo | ∞ | ✓ | ✓ (nach 6 Mo) |
| Paid + Schonfrist | €29/Mo | ∞ | ✓ | ✗ (erste 6 Mo) |

> **€29/Mo bewusst beibehalten (V1-Strategie):** Markt-Anker läge bei ~49 €
> (Deutsches Ausschreibungsblatt), aber V1 zielt auf **Marktanteil** → niedrige
> Einstiegshürde + Erfolgsprämie schlägt hohen Preis ohne Prämie. Beträge/Staffel:
> siehe Pricing-Doc.

---

## Success-Fee: Abrechnungs-Mechanik (v2 — der Kern-Umbau)

### Flow: keine Auto-Abbuchung, sondern Rechnung + menschliche Freigabe

```
Gewinner in TED publiziert
   │
   ▼  in unsere DB
Abgleich mit aktiver Kundenliste (über bestätigte user.entity_id)
   │
   ▼
Attribution: hat der Kunde die zugehoerige Ausschreibung
             VOR dem Zuschlag als Lead-Detail geklickt?
   │  ja
   ▼
Wert-Ermittlung (siehe Waterfall unten)
   │
   ▼
Rechnung wird AUTOMATISCH VORBEREITET (Entwurf, status='draft')
   │
   ▼
── HUMAN IN THE LOOP ──  Prüfer sieht: Kunde, Auftrag, Wert-Quelle, Band, Gebühr
   │
   ▼  „Absenden" gedrückt
Rechnung an Kunden (Zahlungsziel + Widerspruchsfrist), status='sent'
```

**Warum kein Auto-Abbuchen:** unsicheres Entity-Matching + zu 33,5 % fehlende Werte
+ SCA/Chargeback-Risiko bei Off-Session-Charges. Die einzige unumkehrbare Aktion
(Rechnung raus) hat ein menschliches Gate. Automatische **Vorbereitung** bleibt.

### Wert-Ermittlung: echt = Fakt, sonst Kunden-Bestätigung

| Datenlage | Anteil | Vorgehen |
|---|---|---|
| `final_value` echt | ~65 % | Band = **Fakt**, Rechnung auto-vorbereitet |
| kein Wert | ~35 % | Kunde bestätigt Band; **Anker als Wächter** (s.u.); Widerspruch nach unten = Beleg-Pflicht |

### Der Anker-Wächter (nicht Orakel)

Bei fehlendem Wert schätzt ein **Waterfall** die Größenordnung — **nur zur
Plausibilitätsprüfung** der Kundenangabe, nicht als Rechnungsbasis:

```
Anker = coalesce(
  verlinkte Ausschreibungssumme,     # ~66% ±1
  Vorgaenger-Vertrag (Retender),     # ~57% exakt
  Buyer × CPV-Median,                # ~51% exakt  (staerkstes Median-Signal)
  Buyer-Median,                      # 90% Abdeckung
  CPV-Median                         # schwacher Fallback
)   # kombiniert ~68% ±1 Band
```

**Wächter-Regel:**
- Kundenangabe **innerhalb ±1 Band** des Ankers → durchwinken.
- Kundenangabe **≥2 Bänder unter** dem Anker → Flag an HITL + **Nachweis-Pflicht**
  (Zuschlagsschreiben/Vertrag hochladen).

> Wir behaupten keine Präzision, die die Daten nicht hergeben (Schätzung trifft nur
> ~42 % exakt). Der Anker fängt grobes Lowballing, der Kunde liefert die echte Zahl,
> der Mensch entscheidet Grenzfälle.

### Bedingungen für Success Fee (unverändert gültig, präzisiert)

1. Paid-Account **bei Zuschlag** (oder war Paid bei Analyse — s. Edge 10)
2. > 6 Monate seit Upgrade (Schonfrist vorbei)
3. Zugehörige Ausschreibung **als Lead-Detail geklickt VOR** dem Zuschlag
4. **NEU: innerhalb 12 Monaten** nach dem Klick (Cutoff, s.u.)

---

## Attribution: auf die geklickte Ausschreibung, nicht die Nachfolge

**Wichtige Klarstellung:** „Bewirb dich"-Ausschreibung und „abgeschlossen"-Zuschlag
sind **zwei getrennte TED-Dokumente**, aber zu **51 % via `ref_publication_number`
verknüpft** (davon 99,9 % auflösbar).

- **Billing-Attribution** hängt an der **tatsächlich geklickten Ausschreibung → deren
  eigenem Zuschlag** (via `ref_publication_number` + unser Klick-Timestamp). Das ist
  sauber und unabhängig vom unsicheren Nachfolge-Modell.
- **Das Nachfolge-Modell bleibt in der Vorhersage-Ebene** („dieser Vertrag läuft aus,
  hier kommt die Chance") — es fasst die Abrechnung **nie** an.
- Voraussetzung: goVisor zeigt dem Nutzer die **echte Ausschreibung, wenn sie öffnet**,
  nicht nur die Prognose.

**12-Monats-Cutoff:** Leads schließen im Median in 87 Tagen, p90 = 186 Tage. Ein
Fenster von 12 Monaten deckt weit über p90 und begrenzt die Kunden-Haftung. Gewinnt
jemand > 12 Mo nach dem Klick → fast sicher nicht dieselbe Vergabe → keine Fee.

---

## Datenmodell (Änderungen)

### `user_profiles` — erweitert

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| … (wie Original) | | |
| **`entity_id`** | string | **NEU:** bestätigte Gold-Entity (aus Onboarding „Das bin ich") |
| **`entity_confidence`** | enum | **NEU:** `confirmed`/`probable`/`none` — Gate fürs Winner-Matching |

> Ohne bestätigte `entity_id` kann **kein** Winner-Matching laufen → kein Success-Fee.
> Das Onboarding muss die Entity-Bestätigung erzwingen.

### `success_fee_charges` — erweitert

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id`, `user_id`, `lead_id`, `award_date`, `stripe_charge_id`, `charged_at` | | wie Original |
| `tender_publication_number` | string | **NEU:** die geklickte Ausschreibung (Attributions-Link) |
| `value_source` | enum | **NEU:** `echt`/`kunde_bestaetigt`/`kunde_offen` |
| `award_value_band` | string | Band (aus `value_band_effektiv`-Logik / Kundenangabe) |
| `anchor_band` | string | **NEU:** Wächter-Anker (für HITL-Vergleich) |
| `fee_amount` | decimal | Pauschale nach Staffel (Pricing-Doc) |
| `status` | enum | `draft`/**`needs_confirmation`**/**`disputed`**/`sent`/`paid`/`waived`/`failed` |

### `user_lead_interactions` — unverändert
Klick-Telemetrie (`first_analysis_at`) ist unsere App-Daten → 100 % zuverlässig.

---

## Sicherheit (NEU — Pflicht bei Geld-Bewegung)

| Anforderung | Warum |
|---|---|
| **Row Level Security (RLS)** auf allen User-Tabellen | Multi-Tenant, Geld-relevante Daten |
| **E-Mail-Verifikation vor Zahlungsfähigkeit** | kein Upgrade/Fee mit unbestätigter E-Mail |
| Turnstile, Rate-Limit 5/IP/h, Passwort ≥8 | wie Original (solide) |

---

## API / Logik (Änderung Success-Fee)

```javascript
// Kein Auto-Charge mehr — bereitet Rechnungs-ENTWURF vor.
async function prepareSuccessFeeInvoice(userId, awardNoticeId) {
  const user = await getUser(userId);
  if (user.entity_confidence !== 'confirmed') return null;      // Gate: bestaetigte Entity
  if (user.subscription_status !== 'paid' &&
      !wasPaidAtAnalysis(userId, awardNoticeId)) return null;   // Edge 10
  if (new Date() < user.grace_period_ends_at) return null;      // Schonfrist

  // Attribution: geklickte Ausschreibung -> dieser Zuschlag
  const tender = resolveTenderForAward(awardNoticeId);          // via ref_publication_number
  const interaction = await getLeadInteraction(userId, tender.pubNumber);
  if (!interaction?.first_analysis_at) return null;             // nicht analysiert
  if (interaction.first_analysis_at > awardDate(awardNoticeId)) return null; // nach Zuschlag
  if (monthsBetween(interaction.first_analysis_at, now) > 12) return null;   // 12-Mo-Cutoff

  // Wert-Ermittlung
  const real = getPublishedFinalValue(awardNoticeId);
  if (real != null) {
    return draftInvoice({ valueSource:'echt', band: bandOf(real), status:'draft' });
  }
  // kein Wert -> Kunden-Bestaetigung mit Waechter
  const anchor = anchorWaterfall(awardNoticeId, tender);        // ~68% ±1
  return draftInvoice({ valueSource:'kunde_offen', anchorBand: bandOf(anchor),
                        status:'needs_confirmation' });         // Kunde bestaetigt Band
}
// Danach IMMER: menschliche Pruefung -> „Absenden" -> status='sent'
```

---

## Akzeptanzkriterien (geändert/ergänzt)

| # | Kriterium |
|---|-----------|
| 1–6, 13–15 | Auth wie Original (Registrierung, Turnstile, Login, Reset, Session) |
| 7 | Karte für spätere Rechnung/SetupIntent hinterlegt |
| 8 | Schonfrist 6 Monate ab Upgrade |
| 9 | Lead-Klick getrackt (Timestamp + user_id) |
| 10 | Attribution: nur bei Klick VOR Zuschlag **und** ≤12 Mo |
| 11 | **Rechnung wird auto-VORBEREITET, nicht abgebucht** |
| 12 | **HITL-Freigabe vor Versand** |
| 16 | **Abrechnung nur auf echtem Wert; sonst Kunden-Bestätigung + Anker-Wächter** |
| 17 | **`entity_id` bestätigt als Gate fürs Matching** |
| 18 | **RLS + E-Mail-Verifikation aktiv** |

---

## Edge Cases (geänderte)

| # | Case | Verhalten (v2) |
|---|------|-----------|
| 6 | Paid, Monat 3, gewinnt | Keine Fee (Schonfrist) |
| 9 | ~~Karte abgelehnt~~ | **entfällt** — Rechnungsmodell, kein Karten-Dunning |
| 10 | Kündigt vor Zuschlag | Fee ja, **aber nur ≤12 Mo nach Analyse** (Cutoff) |
| 11 | TED publiziert Wert nicht (33,5 %) | **Kunden-Bestätigung**, nicht Verlust; Anker-Wächter |
| 15 | Kunde lowballt Band | Anker-Flag → HITL → Nachweis-Pflicht |
| 16 | Entity nicht bestätigt | Kein Matching, keine Fee (Onboarding nachholen) |

---

## Out of Scope (V1) — unverändert + präzisiert

| Was | Wann | Anmerkung |
|-----|------|-----------|
| Auto-Abbuchung (statt Rechnung) | später | erst wenn Attribution/Recht abgesichert |
| Self-Report-UI für 4 % ohne Gewinner | V2 | |
| OAuth, Magic Link, 2FA, Team-Accounts, Jahres-Abo | V2 | wie Original |

---

## Abhängigkeiten (ergänzt)

| Abhängigkeit | Status |
|--------------|--------|
| Supabase, Turnstile, Stripe | ⬜ Setup |
| **TED-Winner-Matching auf `entity_id`** | ⬜ Gold Layer |
| **Ausschreibung↔Zuschlag-Auflösung (`ref_publication_number`)** | ⬜ Gold Layer |
| **Anker-Waterfall (Buyer×CPV / Vorgänger / Median)** | ⬜ Gold Layer |
| **Rechnungs-Tool + HITL-Review-UI** | ⬜ neu |

---

## Offene Fragen

| # | Frage | Vorschlag |
|---|-------|-----------|
| 1 | Success-Fee rechtlich (BGH-Signal) | vor Launch anwaltlich prüfen (s. Pricing-Doc §7) |
| 2 | Kündigung: sofort/Periodenende | Periodenende |
| 3 | Bezugsgröße Prämie: geschätzt vs. Zuschlagswert | echter Wert wo da, sonst Kunden-Band |
| 4 | Rechnungs-Zahlungsziel + Widerspruchsfrist | z. B. 14 Tage |
