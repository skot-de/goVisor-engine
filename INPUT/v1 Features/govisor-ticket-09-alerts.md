# Feature #9: Alerts & Notifications

**Produkt:** goVisor  
**Version:** V1  
**Status:** Draft  
**Erstellt:** 2026-07-21

---

## Kontext

User wollen nicht täglich einloggen um neue Leads zu finden. Alerts benachrichtigen automatisch, wenn relevante Leads auftauchen.

**Freemium-Gate:** Alerts = Paid Feature

**Kern-Konzept:** Smart Watchlist (Auto + Manuell)

---

## User Story

> **Als** Paid User  
> **will ich** automatisch benachrichtigt werden wenn passende Leads erscheinen oder sich ändern  
> **um** keine Chancen zu verpassen.

---

## Smart Watchlist

### Zwei Quellen

| Quelle | Wie | Wann |
|--------|-----|------|
| **Auto-Match** | System fügt hinzu | Relevanz ≥ 80% + Anforderungen ✓ |
| **Manuell** | User klickt "Beobachten" | Immer (auch wenn Anforderungen ✗) |

### Auto-Match Kriterien

```
Lead kommt auf Auto-Watchlist wenn:

1. Relevanz-Score ≥ 80%

UND

2. Anforderungs-Check: alle erfüllt
   ├── CPV passt zu User-Profil ✓
   ├── Region passt zu User-Profil ✓
   └── Volumen-Band passt zu User-Profil ✓

UND

3. User hat Lead nicht dismissed
```

### Manuell = Override

User kann jeden Lead manuell beobachten, auch wenn:
- Relevanz < 80%
- Anforderungen nicht erfüllt
- Lead schon dismissed war

---

## Alert-Typen

| Typ | Trigger | Scope |
|-----|---------|-------|
| **Neue Leads** | Lead neu auf Auto-Watchlist | Auto-Match |
| **Auslauf-Warnung** | 90d / 30d vor Vertragsende | Gesamte Watchlist |
| **Zuschlag erteilt** | Vergabe publiziert | Gesamte Watchlist |
| **Win detected** | User hat gewonnen | entity_id Match |

---

## Flows

### Flow: Neue Leads (täglich)

```
Täglich 07:00 CET
    │
    ▼
Für jeden Paid User:
    │
    ▼
Neue Auto-Match Leads seit letztem Alert?
    │
    ├─► 0 Leads: keine E-Mail
    │
    └─► 1+ Leads: E-Mail senden
            │
            ▼
        "X neue Leads für dich"
        Top 5 mit Titel, Buyer, Scores
        [Alle ansehen →]
```

### Flow: Auslauf-Warnung

```
Täglich 08:00 CET
    │
    ▼
Leads auf Watchlist (Auto + Manuell) prüfen
    │
    ├─► contract_end - 90 Tage → Warning (einmalig)
    │
    └─► contract_end - 30 Tage → Warning (einmalig)
```

### Flow: Zuschlag erteilt

```
Stündlich: neue TED-Zuschläge prüfen
    │
    ▼
Zuschlag gehört zu Lead auf Watchlist?
    │
    ▼
E-Mail an alle User die diesen Lead beobachten:
    │
    ├─► User = Gewinner: "Glückwunsch!"
    │
    └─► Anderer = Gewinner: "Gewinner: Bechtle AG"
```

### Flow: Win detected

```
TED-Zuschlag publiziert
    │
    ▼
Gewinner entity_id = User entity_id?
    │
    ▼
E-Mail: "Du hast gewonnen!"
    │
    ▼
(Parallel: Success Fee Flow aus #6)
```

---

## UI: Watchlist-Seite ("Meine Leads")

```
┌─────────────────────────────────────────────────────────────┐
│  Meine Leads                                    [Filter ▼] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Für dich ausgewählt (12)                     [Alle/Neu]   │
│  Automatisch basierend auf deinem Profil                   │
│  ─────────────────────────────────────────────────────────│
│  ┌─────────────────────────────────────────────────────┐   │
│  │  BMI – Managed Services          🎯 94%   ⚡ 74%    │   │
│  │  Bund · €12M · 4 Monate                             │   │
│  │  ✓ CPV  ✓ Region  ✓ Volumen         [✗ Entfernen]  │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │  AA – Cloud Migration            🎯 91%   ⚡ 68%    │   │
│  │  Bund · €8M · 6 Monate                              │   │
│  │  ✓ CPV  ✓ Region  ✓ Volumen         [✗ Entfernen]  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Von dir beobachtet (3)                                    │
│  ─────────────────────────────────────────────────────────│
│  ┌─────────────────────────────────────────────────────┐   │
│  │  BMF – SAP Migration             🎯 72%   ⚡ 55%    │   │
│  │  Bund · €5M · 8 Monate                              │   │
│  │  ✓ CPV  ✓ Region  ✗ Volumen   [Nicht mehr beob.]   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ─────────────────────────────────────────────────────────│
│  Vergeben (2)                                   [Archiv]   │
│  └─► BMVg – IT-Betrieb (Gewinner: T-Systems)              │
│  └─► BKA – Security Audit (Gewinner: secunet)             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## UI: Lead-Detail Actions

### Lead nicht auf Watchlist

```
┌────────────────────────────────────────────────────────────┐
│  BMI – Managed Services                                    │
│                                                            │
│  [👁 Beobachten]                                          │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Lead auf Auto-Watchlist

```
┌────────────────────────────────────────────────────────────┐
│  BMI – Managed Services                    [Für dich ✓]   │
│                                                            │
│  Automatisch ausgewählt          [✗ Nicht interessiert]   │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Lead manuell beobachtet

```
┌────────────────────────────────────────────────────────────┐
│  BMI – Managed Services                    [Beobachtet ✓] │
│                                                            │
│                            [✗ Nicht mehr beobachten]      │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## UI: Alert-Einstellungen

```
┌─────────────────────────────────────────────────────────────┐
│  Einstellungen → Benachrichtigungen                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  E-Mail Alerts                                 [PRO]       │
│  ─────────────────────────────────────────────────────────│
│                                                             │
│  Neue passende Leads                           [●] An      │
│  Wenn neue Leads zu deinem Profil passen                   │
│                                                             │
│  Auslauf-Warnungen                             [●] An      │
│  90 und 30 Tage vor Vertragsende                          │
│                                                             │
│  Zuschlag erteilt                              [●] An      │
│  Wenn ein beobachteter Lead vergeben wird                  │
│                                                             │
│  ─────────────────────────────────────────────────────────│
│                                                             │
│  Frequenz für "Neue Leads"                                 │
│  ○ Sofort (bei jedem Match)                               │
│  ● Täglich (07:00 Zusammenfassung)                        │
│  ○ Wöchentlich (Montag 07:00)                             │
│                                                             │
│  [Speichern]                                               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## E-Mail Templates

### Neue Leads (täglich)

```
Betreff: 7 neue Leads für CANCOM

Hi,

7 neue Leads passen zu deinem Profil:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BMI – Managed Services Bund
🎯 94%  ⚡ 74%  |  €12M  |  4 Monate
✓ CPV  ✓ Region  ✓ Volumen
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AA – Cloud Migration
🎯 91%  ⚡ 68%  |  €8M  |  6 Monate
✓ CPV  ✓ Region  ✓ Volumen
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

... und 5 weitere

[Alle 7 Leads ansehen →]

Viel Erfolg!
goVisor

---
[Benachrichtigungen anpassen] · [Abmelden]
```

### Auslauf-Warnung (30 Tage)

```
Betreff: ⏰ Vertrag läuft in 30 Tagen aus

Hi,

ein Lead auf deiner Watchlist läuft bald aus:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BMI – Managed Services Bund

Vertragsende: 15. August 2026 (30 Tage)
Incumbent: Bechtle AG (seit 2020)

🎯 Relevanz: 94%
⚡ Wechsel-W.: 74%

[Lead ansehen →]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tipp: Die Ausschreibung könnte bald veröffentlicht werden.

goVisor

---
[Benachrichtigungen anpassen] · [Abmelden]
```

### Zuschlag erteilt (anderer Gewinner)

```
Betreff: Zuschlag erteilt: BMI – Managed Services

Hi,

ein Lead auf deiner Watchlist wurde vergeben:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BMI – Managed Services Bund

Gewinner: Bechtle AG
Zuschlagswert: €11,2M
Vertragslaufzeit: 4 Jahre

[Details ansehen →]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Nächstes Mal!

goVisor

---
[Benachrichtigungen anpassen] · [Abmelden]
```

### Win detected (User hat gewonnen)

```
Betreff: 🎉 Glückwunsch! Du hast gewonnen!

Hi,

du hast den Zuschlag erhalten:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BMI – Managed Services Bund

Zuschlagswert: €11,2M
Vertragslaufzeit: 4 Jahre

[Details ansehen →]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hinweis: Die Erfolgsprämie wird separat berechnet.

Weiter so!

goVisor

---
[Benachrichtigungen anpassen] · [Abmelden]
```

---

## Datenmodell

### `user_alert_settings`

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `user_id` | uuid | FK, PK |
| `new_leads_enabled` | boolean | Default: true |
| `expiry_warning_enabled` | boolean | Default: true |
| `award_notification_enabled` | boolean | Default: true |
| `frequency` | enum | 'instant', 'daily', 'weekly' |
| `daily_send_time` | time | Default: 07:00 |
| `weekly_send_day` | int | Default: 1 (Montag) |
| `timezone` | string | Default: 'Europe/Berlin' |
| `last_new_leads_alert_at` | timestamp | Für Dedupe |
| `updated_at` | timestamp | |

### `user_watchlist`

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | uuid | PK |
| `user_id` | uuid | FK |
| `lead_id` | string | FK → leads |
| `source` | enum | 'auto', 'manual' |
| `auto_reason` | string | 'profile_match', 'requirements_met' (nullable) |
| `relevance_score` | decimal | Score bei Hinzufügen |
| `added_at` | timestamp | |
| `dismissed` | boolean | Default: false |
| `dismissed_at` | timestamp | |
| `expiry_90d_sent` | boolean | Default: false |
| `expiry_30d_sent` | boolean | Default: false |
| `award_sent` | boolean | Default: false |

### `alert_log`

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | uuid | PK |
| `user_id` | uuid | FK |
| `alert_type` | enum | 'new_leads', 'expiry_90d', 'expiry_30d', 'award', 'win' |
| `lead_ids` | string[] | Betroffene Leads |
| `email_to` | string | E-Mail Adresse |
| `sent_at` | timestamp | |
| `status` | enum | 'sent', 'failed', 'bounced' |
| `error_message` | string | Bei Fehler |

---

## Cron Jobs

| Job | Schedule | Funktion |
|-----|----------|----------|
| `update_auto_watchlists` | 06:00 CET | Auto-Match für alle Paid Users |
| `send_daily_new_leads` | 07:00 CET | Neue Leads E-Mail |
| `send_weekly_new_leads` | Mo 07:00 CET | Wöchentliche Zusammenfassung |
| `check_expiry_warnings` | 08:00 CET | 90d/30d Warnungen |
| `process_new_awards` | stündlich | Zuschläge aus TED prüfen |

---

## API / Logik

### Auto-Watchlist Update

```javascript
async function updateAutoWatchlists() {
  const paidUsers = await getPaidUsers();
  
  for (const user of paidUsers) {
    // Leads die zum Profil passen
    const matchingLeads = await getLeadsMatching({
      cpv_codes: user.cpv_codes,
      regions: user.regions,
      volume_bands: user.volume_bands,
      min_relevance: 0.80,
      requirements_all_met: true,
    });
    
    for (const lead of matchingLeads) {
      // Skip wenn dismissed oder manuell beobachtet
      const existing = await getWatchlistEntry(user.id, lead.id);
      if (existing?.dismissed) continue;
      if (existing?.source === 'manual') continue;
      
      // Upsert Auto-Entry
      await upsertWatchlist({
        user_id: user.id,
        lead_id: lead.id,
        source: 'auto',
        auto_reason: 'profile_match',
        relevance_score: lead.relevance_score,
      });
    }
    
    // Cleanup: Auto-Entries entfernen die nicht mehr matchen
    await removeStaleAutoEntries(user.id, matchingLeads.map(l => l.id));
  }
}
```

### Send Daily New Leads

```javascript
async function sendDailyNewLeadsAlerts() {
  const users = await getPaidUsersWithAlerts('new_leads', 'daily');
  
  for (const user of users) {
    const lastAlert = user.last_new_leads_alert_at || user.created_at;
    
    // Neue Auto-Match Leads seit letztem Alert
    const newLeads = await getNewWatchlistEntries(user.id, {
      source: 'auto',
      added_after: lastAlert,
    });
    
    if (newLeads.length === 0) continue;
    
    await sendEmail({
      to: user.email,
      template: 'new_leads_daily',
      data: {
        user_name: user.company_name,
        leads: newLeads.slice(0, 5),
        total_count: newLeads.length,
      }
    });
    
    await updateLastAlertTime(user.id, 'new_leads');
    await logAlert(user.id, 'new_leads', newLeads.map(l => l.lead_id));
  }
}
```

### Check Expiry Warnings

```javascript
async function checkExpiryWarnings() {
  const watchedLeads = await getWatchlistWithExpiry();
  
  for (const entry of watchedLeads) {
    const daysUntil = daysUntilExpiry(entry.lead.contract_end);
    
    if (daysUntil <= 30 && !entry.expiry_30d_sent) {
      await sendExpiryWarning(entry.user, entry.lead, 30);
      await markExpirySent(entry.id, '30d');
      await logAlert(entry.user_id, 'expiry_30d', [entry.lead_id]);
    } 
    else if (daysUntil <= 90 && !entry.expiry_90d_sent) {
      await sendExpiryWarning(entry.user, entry.lead, 90);
      await markExpirySent(entry.id, '90d');
      await logAlert(entry.user_id, 'expiry_90d', [entry.lead_id]);
    }
  }
}
```

### Process New Awards

```javascript
async function processNewAwards() {
  const newAwards = await getUnprocessedAwards();
  
  for (const award of newAwards) {
    // 1. Alle User benachrichtigen die diesen Lead beobachten
    const watchers = await getWatchersForLead(award.lead_id);
    
    for (const entry of watchers) {
      if (entry.award_sent) continue;
      
      const isWinner = award.winner_entity_id === entry.user.entity_id;
      
      await sendAwardNotification(entry.user, award, isWinner);
      await markAwardSent(entry.id);
      await logAlert(entry.user_id, isWinner ? 'win' : 'award', [award.lead_id]);
    }
    
    // 2. Win Detection (auch für User die Lead nicht beobachtet haben)
    if (award.winner_entity_id) {
      const winner = await getUserByEntityId(award.winner_entity_id);
      if (winner && winner.subscription_status === 'paid') {
        // Check ob schon benachrichtigt (via Watchlist)
        const alreadyNotified = watchers.some(w => 
          w.user_id === winner.id && w.award_sent
        );
        
        if (!alreadyNotified) {
          await sendWinNotification(winner, award);
          await logAlert(winner.id, 'win', [award.lead_id]);
        }
        
        // Trigger Success Fee Flow (separater Prozess)
        await queueSuccessFeeCheck(winner.id, award.id);
      }
    }
    
    await markAwardProcessed(award.id);
  }
}
```

---

## Akzeptanzkriterien

| # | Kriterium |
|---|-----------|
| 1 | Auto-Watchlist füllt sich bei Profil-Match (≥80% + Anforderungen ✓) |
| 2 | User kann Leads manuell beobachten |
| 3 | User kann Auto-Match Leads dismisser ("Nicht interessiert") |
| 4 | User kann manuell beobachtete Leads entfernen |
| 5 | Watchlist-Seite zeigt Auto + Manuell getrennt |
| 6 | Watchlist-Seite zeigt vergebene Leads (Archiv) |
| 7 | Alert-Einstellungen in Settings |
| 8 | Toggles pro Alert-Typ |
| 9 | Frequenz wählbar (instant/daily/weekly) |
| 10 | Täglicher Cron: neue Leads E-Mail |
| 11 | E-Mail zeigt Top 5 + Total Count |
| 12 | Auslauf-Warnungen bei 90d und 30d |
| 13 | Zuschlag-Benachrichtigung für Watchlist |
| 14 | Win-Detection auch ohne Watchlist |
| 15 | Dedupe: keine doppelten E-Mails |
| 16 | Unsubscribe-Link in jeder E-Mail |
| 17 | Alert-Log für Debugging |
| 18 | Nur Paid User bekommen Alerts |
| 19 | Free User sieht "PRO" Badge bei Alerts |

---

## Edge Cases

| # | Case | Verhalten |
|---|------|-----------|
| 1 | User wird Free | Alerts stoppen, Watchlist bleibt (readonly) |
| 2 | User wird wieder Paid | Alerts reaktivieren |
| 3 | 0 neue Leads | Keine E-Mail |
| 4 | 100+ neue Leads | Top 5 + "und 95 weitere" |
| 5 | Lead dismissed, matcht wieder | Bleibt dismissed |
| 6 | Lead manuell + auto | Zählt als manuell (kein Doppel) |
| 7 | Lead wird gelöscht (TED-Korrektur) | Stille Entfernung aus Watchlist |
| 8 | E-Mail bounced | status = 'bounced', nach 3x Alerts pausieren |
| 9 | User löscht Account | Alle Watchlist + Alerts löschen |
| 10 | Doppelter Award (TED-Bug) | Dedupe via award_sent Flag |
| 11 | Timezone: User in USA | Send-Time nach User-Timezone |
| 12 | Instant + viele Events | Max 1 E-Mail pro Stunde pro Typ |
| 13 | Lead auf Watchlist, Profil ändert sich | Auto-Entry bleibt (war mal Match) |
| 14 | Expiry in Vergangenheit | Keine Warnung mehr |

---

## Limits

| Limit | Wert | Grund |
|-------|------|-------|
| Max Watchlist-Einträge | 100 | Performance |
| Max Alerts pro Tag | 10 | Spam-Schutz |
| Max Leads in E-Mail | 5 (Preview) | Lesbarkeit |
| Instant-Throttle | 1/Stunde/Typ | Spam-Schutz |

---

## Out of Scope

| Was | Wann |
|-----|------|
| Push Notifications (Mobile) | V2 |
| Slack/Teams Integration | V2 |
| Custom Alert Criteria (eigene Filter) | V2 |
| Alert für Konkurrenz-Aktivität | V2 |
| SMS Alerts | V2 |
| Digest: mehrere Alert-Typen in einer E-Mail | V2 |

---

## Abhängigkeiten

| Abhängigkeit | Status |
|--------------|--------|
| E-Mail Provider (Resend/Postmark) | ⬜ Setup |
| Cron Infrastructure (Vercel/Supabase) | ⬜ Setup |
| TED Award Processing | ✅ Gold Layer |
| User Profiles mit entity_id | Ticket #6 |
| Relevanz-Score | Ticket #1 |
| Anforderungs-Check | Ticket #3 |

---

## Testfälle

| # | Test | Erwartung |
|---|------|-----------|
| 1 | Neuer Lead matcht Profil (≥80%, alle ✓) | Auf Auto-Watchlist |
| 2 | Neuer Lead matcht nicht (<80%) | Nicht auf Watchlist |
| 3 | User klickt "Beobachten" | Auf Manuell-Watchlist |
| 4 | User dismissed Auto-Lead | dismissed = true |
| 5 | Dismissed Lead matcht wieder | Bleibt dismissed |
| 6 | 5 neue Auto-Leads, daily Alert | E-Mail um 07:00 |
| 7 | 0 neue Leads | Keine E-Mail |
| 8 | Lead 90d vor Expiry | Warning E-Mail |
| 9 | Lead 30d vor Expiry | Warning E-Mail |
| 10 | Zuschlag für Watchlist-Lead | Award E-Mail |
| 11 | User gewinnt (entity_id match) | Win E-Mail |
| 12 | User gewinnt ohne Watchlist | Trotzdem Win E-Mail |
| 13 | Free User | Keine Alerts |
| 14 | Unsubscribe klicken | Alert-Typ deaktiviert |
| 15 | E-Mail bounced | status = 'bounced' |

---

## Offene Fragen

| # | Frage | Vorschlag |
|---|-------|-----------|
| 1 | E-Mail Provider? | Resend (EU, günstig, gut für Transactional) |
| 2 | Auto-Match Schwelle? | 80% Relevanz |
| 3 | Watchlist-Seite: eigene Route? | /app/watchlist oder /app/meine-leads |
| 4 | Weekly: welcher Tag? | Montag 07:00 |
| 5 | Archiv: wie lange aufheben? | 90 Tage nach Zuschlag |
