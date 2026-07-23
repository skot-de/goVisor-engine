# Feature #9: Alerts & Notifications (v2)

**Produkt:** goVisor
**Version:** V1
**Status:** Überarbeitet gegen echte Datenlage + v2-Entscheidungen (2026-07-21)
**Basis:** `govisor-ticket-09-alerts.md` (Original unverändert)

> **Was v2 ändert:** Primärer Timing-Alert **umgedreht** — „Angebotsfrist naht"
> (offene Ausschreibung, gut gedeckt) statt „Vertrag läuft aus" (18 % Datenlücke);
> Win-Matching gegen **Gruppe** statt singuläres `entity_id`; Award↔Lead-Auflösung
> als Abhängigkeit; Scores als **Bänder** + Schätz-Flags; Ingest-Latenz realistisch.
> Smart-Watchlist-Konzept, Dedupe, Freemium-Gate bleiben.

---

## Datengrundlage (gemessen)

| Signal | Abdeckung | Konsequenz |
|---|---|---|
| `submission_deadline` (offene Ausschreibungen) | **49,1 %** | primärer Timing-Alert |
| Bid-Fenster Pub→Frist (Median / p90 / stddev) | **31 / 42 / ±12 Tage** | Schätzung **belastbar** (gesetzl. Mindestfristen) |
| `end_date` (Vertragsende) | **~18 %** | nur sekundär, wo echt |
| `ref_publication_number` (Zuschlag→Ausschreibung) | 51 %, 99,9 % auflösbar | Award↔Lead-Verknüpfung |

---

## Kern-Umbau: „Angebotsfrist naht" als primärer Timing-Alert

**Warum umgedreht:** Der ursprüngliche „Vertrag läuft aus"-Alert (90d/30d vor
`contract_end`) kann für **>80 % der Leads gar nicht feuern** — `end_date` fehlt.
Und ein geschätztes Vertragsende ist schwach. Der **umgedrehte Alert** — „offene
Ausschreibung nähert sich der Angebotsfrist" — ist besser gedeckt **und** verlässlich
schätzbar, weil Angebotsfristen gesetzlich mindestgeregelt sind (enges Fenster,
stddev 12 Tage).

### Timing-Quelle je Lead (Wasserfall)

| Priorität | Quelle | Alert |
|---|---|---|
| 1 | `submission_deadline` echt (49 %) | „Angebotsfrist in **X Tagen**" (exakt) |
| 2 | Schätzung `publication_date + ~31 T` (bzw. CPV-Median) | „Angebotsfrist **voraussichtlich** in ~X Tagen" (geflaggt) |

**Trigger:** z. B. bei ~14 und ~3 Tagen vor (geschätzter) Frist — einmalig, dedupliziert.

### Sekundär (ergänzend, nicht primär): „Vertrag läuft aus"

Bleibt als **Früh-Warnung** für die Retender-Prognose, aber **nur wo `end_date` echt**
(~18 %). Rolle: „eine Chance *kommt*" (der Incumbent-Vertrag endet), nicht „jetzt bieten".
Kein datierter Countdown auf geschätztem Ende.

| Alert | Moment im Funnel | Datenbasis |
|---|---|---|
| **Angebotsfrist naht** (primär) | *jetzt handeln* | `submission_deadline` 49 % + Schätzung |
| Vertrag läuft aus (sekundär) | *Chance kommt* | `end_date` ~18 %, nur echt |

---

## Alert-Typen (v2)

| Typ | Trigger | Datenbasis |
|-----|---------|-----------|
| **Neue Leads** | neuer Auto-Match | Relevanz-Band + CPV/Region (Volumen geflaggt) |
| **Angebotsfrist naht** ⭐ | ~14d/3d vor (gesch.) Frist | `submission_deadline` / Schätzung |
| Vertrag läuft aus | `end_date` echt, 90d/30d | ~18 %, nur echt |
| **Zuschlag erteilt** | Vergabe zu beobachtetem Lead | via `ref_publication_number` |
| **Win detected** | User-**Gruppe** = Gewinner | alle Gruppen-`entity_id`s |

---

## Kern-Korrektur: Win-Matching gegen die Gruppe

`processNewAwards` matchte `winner_entity_id === user.entity_id` (singular). Per
Ticket 06/07 v2 ist die Identität eine **Gruppe**. Winner-Matching läuft gegen **alle
aktiven `entity_id`s** der bestätigten Gruppe — sonst verpassen wir Gewinne von
Schwester-Entitäten (und die Erfolgsprämie).

```javascript
// v2: Gruppe statt singulaerem entity_id
const winnerUser = await getUserByGroupEntities(award.winner_entity_id);
// -> loest winner_entity_id -> group -> bestaetigten Paid-User auf
```

---

## Kern-Korrektur: Award↔Lead-Auflösung ist nicht gegeben

`getWatchersForLead(award.lead_id)` setzt ein direktes `lead_id` auf dem Zuschlag
voraus — das existiert nicht. Ausschreibung und Zuschlag sind getrennte Dokumente;
die Verknüpfung braucht die **`ref_publication_number`-Auflösung** (51 %, sonst
Nachfolge-Logik) aus Ticket 06. → als **Abhängigkeit** aufnehmen, nicht als Feld annehmen.

---

## Konsistenz: Scores als Bänder + Schätz-Flags

- **UI/E-Mails:** `🎯 94 %` / `⚡ 74 %` → **Bänder** (hoch/mittel/niedrig). Der interne
  80 %-Auto-Match-Schwellwert bleibt, nur die *Anzeige* ist ein Band.
- **Auto-Match-Haken „✓ Volumen":** basiert auf zu 58 % geschätztem Wert → **Schätz-Flag**
  („Volumen ~ geschätzt"), kein sicheres ✓.
- **Award-Mail „Zuschlagswert: €X":** 35 % der Vergaben ohne Wert → Flag oder weglassen.

---

## Ingest-Latenz realistisch

„Stündlich neue Zuschläge prüfen" ist nur so frisch wie unser **TED-Ingest** (aktuell
Batch). Der `process_new_awards`-Cron kann stündlich *laufen*, liefert aber neue
Zuschläge erst nach dem Ingest-Zyklus. → Alert-Latenz = Ingest-Kadenz, ehrlich
kommunizieren (nicht „in Echtzeit").

---

## Datenmodell (Änderungen)

### `user_watchlist` — Timing-Felder ersetzt
| Feld | v2 |
|------|-----|
| ~~`expiry_90d_sent` / `expiry_30d_sent`~~ | ersetzt durch: |
| `deadline_14d_sent` / `deadline_3d_sent` | **NEU:** Angebotsfrist-Warnungen |
| `deadline_source` | **NEU:** `echt` / `geschaetzt` |
| `expiry_warn_sent` | optional, nur wo `end_date` echt (sekundär) |

### `user_alert_settings` — Toggle umbenannt
| Feld | v2 |
|------|-----|
| ~~`expiry_warning_enabled`~~ | `deadline_warning_enabled` (Angebotsfrist) + optional `expiry_warning_enabled` (sekundär) |

---

## Cron Jobs (v2)

| Job | Schedule | Funktion |
|-----|----------|----------|
| `update_auto_watchlists` | 06:00 | Auto-Match (Relevanz-Band + CPV/Region) |
| `send_daily_new_leads` | 07:00 | Neue Leads |
| `check_deadline_warnings` | 08:00 | **Angebotsfrist** 14d/3d (echt + Schätzung) |
| `check_expiry_warnings` | 08:00 | Vertragsende 90d/30d — **nur wo `end_date` echt** |
| `process_new_awards` | nach Ingest | Zuschläge (via `ref_publication_number`, Gruppen-Match) |

---

## Akzeptanzkriterien (geänderte)

| # | Kriterium |
|---|-----------|
| 12 | **Angebotsfrist-Warnung** 14d/3d — exakt wo `submission_deadline`, sonst Schätzung (geflaggt) |
| 12b | Vertragsende-Warnung nur wo `end_date` echt (sekundär) |
| 14 | Win-Detection gegen **alle Gruppen-Entities**, nicht singuläres `entity_id` |
| 13 | Zuschlag-Benachrichtigung via `ref_publication_number`-Auflösung |
| 20 | Scores als **Bänder** in E-Mails/UI; Volumen mit Schätz-Flag |
| (1–11, 15–19) | wie Original |

---

## Edge Cases (ergänzt/geändert)

| # | Case | Verhalten (v2) |
|---|------|-----------|
| 13 | Profil ändert sich, Lead war Auto-Match | **entscheiden & konsistent:** Auto-Entry bleibt (war Match), aber neue Matches kommen dazu — `removeStaleAutoEntries` nur für *nie bestätigte* Entries |
| 15 | `submission_deadline` fehlt | Schätzung `pub + ~31T`, Alert als „voraussichtlich" |
| 16 | Geschätzte Frist schon überschritten | keine „naht"-Warnung mehr |
| 17 | Award ohne auflösbaren `ref_publication_number` | Fallback Nachfolge-Logik; sonst kein Watchlist-Award-Alert |

---

## Compliance-Präzisierung

| E-Mail-Typ | Einordnung | Regel |
|---|---|---|
| Neue Leads (Digest) | eher Marketing | Opt-in-Consent, Abmelde-Link |
| Angebotsfrist / Zuschlag / Win | transaktional | Bezug zum beobachteten Lead; Abmelde-Link trotzdem |

---

## Out of Scope (unverändert)

Push/Slack/SMS, Custom-Criteria, Konkurrenz-Aktivität-Alert, Digest-Mix → V2.
(**Hinweis:** „Konkurrenz-Aktivität-Alert" bewusst V2+ und sensibel — s.
`produkt-vision.md` §4, Wettbewerbs-Signale nicht ungefiltert ausspielen.)

---

## Offene Fragen (ergänzt)

| # | Frage | Vorschlag |
|---|-------|-----------|
| 6 | Angebotsfrist-Trigger-Tage | 14d + 3d vor (gesch.) Frist |
| 7 | CPV-spezifische statt globale Fenster-Schätzung? | global ~31T reicht (stddev 12T); CPV-Median als Feinschliff |
| 8 | Schätz-Frist prominent oder dezent flaggen? | dezent, aber sichtbar („voraussichtlich") |
