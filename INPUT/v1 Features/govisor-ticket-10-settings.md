# Feature #10: Einstellungen (Settings)

**Produkt:** goVisor
**Version:** V1
**Status:** Neu, direkt datengegründet (2026-07-22)
**Autor-Hinweis:** Kein Vorgänger-Draft — geschrieben gegen die echte Datenlage +
die v2-Entscheidungen der Tickets 06/07/09 und `docs/pricing-modell.md`.

---

## Kontext

Screen #10 im Gesamtflow, bisher ohne Ticket. Bündelt alles, was der Nutzer nach
dem Onboarding an seinem Konto steuert: **Profil, Gruppe, Zahlung, Benachrichtigungen,
Account.** P1-kritisch für den Abo-Launch (Kündigung, Zahlungsverwaltung, GDPR-Löschung).

**Leitprinzip (wie überall):** was geschätzt/unsicher ist, wird als solches gezeigt;
Identität und Zahlung sind die sensiblen Bereiche → Bestätigung vor jeder wirksamen
Änderung.

---

## User Story

> **Als** registrierter Nutzer
> **will ich** mein Profil, meine Firmengruppe, Zahlung und Alerts selbst verwalten
> **um** goVisor auf mich zuzuschneiden und die Kontrolle über Kosten & Daten zu behalten.

---

## Sektionen

| # | Sektion | Zweck | Gate |
|---|---|---|---|
| 1 | **Profil** | CPVs / Regionen / Branchen anpassen | alle |
| 2 | **Gruppe** | Firmen-Entities der Identität aktivieren/deaktivieren | nur wenn Entity bestätigt |
| 3 | **Zahlung** | Abo-Status, Zahlungsmittel, Rechnungen | alle |
| 4 | **Benachrichtigungen** | Alert-Typen & Frequenz (→ Ticket 09) | Paid |
| 5 | **Account** | E-Mail, Passwort, Daten-Export, Löschung | alle |

---

## Sektion 1: Profil

- **Bearbeitbar:** CPV-Codes, NUTS-Regionen, Branchen (`dim_cpv.branche`), Firmenname.
- **`known_from_ted`-Zustand sichtbar:** „Auto-Profil aus TED" (bestätigte Firma) vs.
  „manuelles Profil". Für Aspiring Bidder (nicht in `entities`): das manuelle Profil ist
  der **wachsende Keim** (Ticket 07) — Hinweis „schärft sich, je länger du dabei bist".
- Änderungen wirken auf Lead-Matching/Auto-Watchlist (Ticket 09) beim nächsten Lauf.

## Sektion 2: Gruppe (baut auf `entity_identity`)

Das Backend steht: `entity_identity` löst jede bestätigte Entity zur **Identität**
(Gruppe oder `solo:`) auf und liefert alle Schwester-Entities + `group_size`.

```
┌───────────────────────────────────────────────────────────┐
│  Deine Unternehmensgruppe (identity_id …)                 │
│  ─────────────────────────────────────────────────────────│
│  ☑ CANCOM SE                    HR-exakt      23 Wins      │
│  ☑ CANCOM Public GmbH           HR-exakt      18 Wins      │
│  ☑ CANCOM Managed Services      nur Name ⚠     6 Wins      │
│                                                           │
│  ⚠ = Zuordnung unbestätigt (namensbasiert)                │
│  [Speichern]   (mind. 1 aktiv)                            │
└───────────────────────────────────────────────────────────┘
```

- **Confidence-Badge je Entity** aus `entities.method` (`handelsregister_exakt`/
  `ted_nationalid` = sicher; `nur_name`/`nicht_aufgeloest` = ⚠ unbestätigt). Nur ~33 %
  sind sauber aufgelöst — Ehrlichkeit hier verhindert falsche Win-Zuordnung.
- **Aktivieren/Deaktivieren** (min. 1). Die aktiven `entity_id`s sind die Basis fürs
  **Winner-Matching** (Ticket 06/09) und die „Deine Erfahrung"-Analyse.
- **Wins berechnet** aus `party_entity`/`contractor_stats` (es gibt kein
  `entities.total_wins`).
- Gruppe wechseln (falsche Firma bestätigt) → **`entity_confidence` neu setzen**
  (zurück auf `probable`, bis erneut bestätigt) — schützt das Billing-Gate.

## Sektion 3: Zahlung

- **Abo-Status:** `free` / `paid` / `cancelled`; Plan + Betrag (aus Pricing-Config,
  nicht hartkodiert — V1 ~29 €, s. `docs/pricing-modell.md`).
- **Schonfrist-Status** (Ticket 06): „Erfolgsprämien ab TT.MM.JJJJ".
- **Zahlungsmittel:** nur `last4` + Marke (nie volle Kartendaten — die liegen bei Stripe).
- **Rechnungen:** Abo-Rechnungen **und** Erfolgsprämien-Rechnungen im **HITL-Modell**
  (Ticket 06 v2): Status `draft`/`needs_confirmation`/`sent`/`paid`/`disputed`/`waived`.
  Bei `needs_confirmation`: **Kunde bestätigt hier das Auftrags-Band** (Anker-Wächter
  aus `value_anchor` prüft Plausibilität, ≥2 Bänder-Abweichung → Beleg/HITL).
- **Kündigen:** zum Periodenende (Ticket 06 Offene Frage 2). Kündigung entfernt **nicht**
  die Erfolgsprämien-Pflicht für Leads, die während Paid analysiert wurden (12-Mo-Cutoff).

## Sektion 4: Benachrichtigungen

Verweist auf **Ticket 09** (`user_alert_settings`): Toggles (Angebotsfrist / Vertragsende /
Zuschlag), Frequenz (instant/daily/weekly), Zeitzone. **Hier nicht duplizieren** — nur
einbetten. Transaktional vs. Marketing sauber getrennt (Ticket 09 v2).

## Sektion 5: Account

- **E-Mail ändern** → Re-Verifikation der neuen Adresse (Pflicht vor Zahlungsfähigkeit,
  Ticket 06 v2).
- **Passwort ändern** (Supabase Auth).
- **Daten-Export (GDPR Art. 20):** Profil, Watchlist, Interaktionen, Rechnungen als
  Export. **Keine** fremden Daten (keine anderen Nutzer, keine aggregierten Preise).
- **Account löschen (GDPR Art. 17):** harte Löschung mit Kaskade — `user_profiles`,
  `user_watchlist`, `user_lead_interactions`, `user_alert_settings`, Onboarding-State.
  **Ausnahme:** abgeschlossene Rechnungen (`paid`) bleiben aus steuer-/handelsrechtlichen
  Aufbewahrungsgründen (pseudonymisiert). Offene Erfolgsprämien-Pflicht klären (s. Offene
  Fragen).

---

## Datenmodell

Erweitert/nutzt bestehende Tabellen (aus 06/07/09) — keine neue Kern-Tabelle nötig
außer Export-Log.

### `user_profiles` (aus 06/07) — hier bearbeitbare Felder
`cpv_codes`, `nuts_regions`, `branches`, `company_name`, `known_from_ted`,
`confirmed_group_id`/`confirmed_entity_ids`, `active_entity_ids`, `entity_confidence`.

### `user_data_export` (NEU)
| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | uuid | PK |
| `user_id` | uuid | FK |
| `requested_at` | timestamp | |
| `status` | enum | `pending`/`ready`/`failed` |
| `download_url` | string | signiert, kurzlebig |

### Löschung
Kaskade über alle User-Tabellen; `success_fee_charges` mit `status='paid'`
pseudonymisiert behalten (Aufbewahrung), Rest löschen.

---

## API / Logik (Kern)

```javascript
// Gruppe: Entity aktivieren/deaktivieren (min. 1)
async function setActiveEntities(userId, entityIds) {
  if (!entityIds.length) throw new Error("Mindestens eine Firma aktiv halten");
  // Alle müssen zur bestätigten Identität gehören (entity_identity)
  const identity = await getConfirmedIdentity(userId);
  const members = await getIdentityMembers(identity);          // aus entity_identity
  if (!entityIds.every(e => members.includes(e)))
    throw new Error("Firma gehört nicht zu deiner Gruppe");
  await updateProfile(userId, { active_entity_ids: entityIds });
}

// Gruppe wechseln -> Billing-Gate zuruecksetzen
async function changeConfirmedGroup(userId, newIdentityId) {
  await updateProfile(userId, {
    confirmed_group_id: newIdentityId,
    entity_confidence: 'probable',   // erneut bestaetigen noetig
  });
}

// Account loeschen (GDPR) — Kaskade, bezahlte Rechnungen pseudonymisiert behalten
async function deleteAccount(userId) {
  await pseudonymizePaidCharges(userId);
  await cascadeDeleteUserData(userId);   // profiles, watchlist, interactions, alerts, onboarding
  await supabase.auth.admin.deleteUser(userId);
}
```

---

## Akzeptanzkriterien

| # | Kriterium |
|---|-----------|
| 1 | Profil (CPV/Region/Branche/Name) bearbeitbar, wirkt aufs Matching |
| 2 | Gruppe zeigt alle Identitäts-Entities (aus `entity_identity`) mit **Confidence-Badge** |
| 3 | Entity aktivieren/deaktivieren, min. 1 erzwungen |
| 4 | Wins **berechnet**, nicht aus `total_wins` |
| 5 | Gruppenwechsel setzt `entity_confidence` zurück |
| 6 | Zahlung: Status, Schonfrist, `last4`, Rechnungsliste (inkl. HITL-Prämien-Status) |
| 7 | `needs_confirmation`-Prämie: Band-Bestätigung mit Anker-Plausibilitätscheck |
| 8 | Kündigen zum Periodenende |
| 9 | E-Mail-Änderung → Re-Verifikation |
| 10 | GDPR-Export (nur eigene Daten) |
| 11 | Account-Löschung Kaskade; bezahlte Rechnungen pseudonymisiert behalten |
| 12 | Alle Zahlungs-/Identitäts-Änderungen erst nach Bestätigung wirksam |

---

## Edge Cases

| # | Case | Verhalten |
|---|------|-----------|
| 1 | Nur 1 Entity aktiv, User will sie deaktivieren | Fehler „mind. eine aktiv" |
| 2 | Aspiring Bidder (manuelles Profil) öffnet „Gruppe" | Sektion zeigt „noch keine Firma zugeordnet" + Onboarding-Link |
| 3 | Kündigung, dann Win in 12-Mo-Fenster | Prämie trotzdem (war Paid bei Analyse) |
| 4 | Löschung mit offener `needs_confirmation`-Prämie | erst klären/erlassen, dann löschen |
| 5 | E-Mail-Änderung auf bereits existierende Adresse | Fehler |
| 6 | Free-User öffnet Benachrichtigungen | „PRO"-Hinweis, read-only |
| 7 | `nur_name`-Entity in Gruppe | ⚠-Badge, aktivierbar aber gekennzeichnet |

---

## Out of Scope (V1)

| Was | Wann |
|-----|------|
| Team-/Multi-User-Accounts | V2 |
| Rollen & Rechte | V2 |
| Manuelle CPV-Feinauswahl (nur Branchen in V1) | V2 |
| Rechnungs-Adresse / USt-ID-Verwaltung | V2 (mit Prämien-Launch) |
| SSO/OAuth-Verknüpfung | V2 |

---

## Abhängigkeiten

| Abhängigkeit | Status |
|--------------|--------|
| `entity_identity` (Gruppen-Auflösung) | ✅ Gold Layer (P0-3) |
| `contractor_stats`/`party_entity` (Wins berechnen) | ✅ Gold Layer |
| `user_profiles` + `entity_confidence` (Ticket 06/07) | ⬜ App/Supabase |
| `success_fee_charges` (HITL-Rechnungen, Ticket 06 v2) | ⬜ App/Supabase |
| `user_alert_settings` (Ticket 09) | ⬜ App/Supabase |
| Stripe (Zahlungsmittel, Kündigung) | ⬜ Setup |

---

## Offene Fragen

| # | Frage | Vorschlag |
|---|-------|-----------|
| 1 | Löschung bei offener Erfolgsprämien-Pflicht? | erst begleichen/erlassen, sonst blocken (rechtlich prüfen) |
| 2 | Wie lange bezahlte Rechnungen aufbewahren? | 10 Jahre (HGB/AO), pseudonymisiert |
| 3 | Profil-Änderung: sofort neu matchen oder nächster Cron? | nächster `update_auto_watchlists`-Lauf (Ticket 09) |
| 4 | Gruppen-Entity manuell hinzufügen (nicht in `entity_identity`)? | V2 — erst Auflösungsqualität heben |
