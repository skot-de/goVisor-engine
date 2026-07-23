# Feature #7: Onboarding-Flow (v2)

**Produkt:** goVisor
**Version:** V1
**Status:** Überarbeitet gegen echte Datenlage (2026-07-20)
**Basis:** `govisor-ticket-07-onboarding.md` (Original unverändert)

> **Was v2 ändert:** Domain-Matching **ohne** externe Daten (Namensableitung aus der
> Domain, als bestätigbare Suggestion); `total_wins` berechnet statt angenommen;
> Match-Konfidenz **methoden-abhängig** (Long-Tail-Schutz); „Das bin ich" als
> **Confirmation-Gate für Ticket 06** (Gruppe = Identität); Aspiring-Bidder-Pfad als
> **wachsendes Profil** statt Sackgasse. Flow-Rahmen unverändert.

---

## Datengrundlage (gemessen)

| Messung | Wert | Konsequenz |
|---|---|---|
| entities gesamt | 323.593 | große Autocomplete-Basis |
| sauber aufgelöst (`handelsregister_exakt`+`ted_nationalid`) | **32,6 %** | Rest namensbasiert |
| `nur_name` / `nicht_aufgeloest` | 51 % / 16,5 % | Long-Tail unsicher → Confidence methoden-abhängig |
| Entities mit ≥1 Gewinn | 76 % | Nicht-Gewinner → manueller Pfad |
| Gruppen mit >1 Entität | 24,3 % | Gruppen-Picker ist der Sonderfall |
| Namens-Stamm eindeutig / ≤3 Firmen | 13,3 % / 25,3 % | Domain-Match nur als **Suggestion** |

`entities`-Felder real: `entity_id, canonical_name, national_id, method, confidence`.
**Kein `total_wins`, kein Domain/Website-Feld** — beides beeinflusst die v2.

---

## Firmen-Erkennung: drei Signale (v2)

| Stufe | Signal | Mechanik (v2) | Güte |
|---|---|---|---|
| 1 | **E-Mail-Domain** | **Namensableitung:** `cancom.de` → Stamm „cancom" → Fuzzy-Match gegen `canonical_name`. **Keine** Domain→Entity-Tabelle nötig. | Suggestion |
| 2 | Getippter Name | `normalize_company` → Fuzzy-Match | Suggestion |
| 3 | USt-IdNr | Exakt gegen `national_id` | V2 |

**Warum Namensableitung statt Domain-Tabelle:** wir haben keine Domain-Daten in TED.
Aber Firmen-Mails basieren fast immer auf dem Namen (`cancom.de`, `bechtle.com`). Wir
leiten also den Namens-Stamm aus der Domain ab und matchen ihn gegen unsere Namensliste.

**Drei Leitplanken (gemessen nötig):**
1. **Kandidaten-Cluster deduplizieren** — „cancom" trifft 40 Entity-Varianten derselben
   realen Firma → über `entity_group`/`canonical_name` zu **einem** Vorschlag zusammenfassen.
2. **Generik-/Buyer-Stämme filtern** — Blockliste (`stadt, gemeinde, arge, vergabekammer,
   bietergemeinschaft, firma, mail, wert, …`); das sind keine privaten Bieter.
3. **Freemail bleibt übersprungen** (`@gmail.com` etc. → nur getippter Name).

---

## Matching-UX: bestätigbare Suggestion (v2 — Kern-Änderung)

Kein Auto-Match. Der Ablauf ist **immer** Vorschlag → Bestätigung → dann Profil:

```
Domain/Name -> bester dedup. Kandidat
        │
        ▼
"Arbeitest du bei CANCOM?"        [Ja, das bin ich]  [Nein]
        │ Ja                                   │ Nein
        ▼                                      ▼
Profil-Screen (Gruppe + Stats)        weiterer Vorschlag / manueller Pfad
        │
        ▼  bestätigt
entity_confidence = 'confirmed'   ← GATE fuer Ticket 06 (Erfolgsprämie)
```

**Confidence methoden-abhängig (Long-Tail-Schutz):** ein `nur_name`-Match darf **nie**
still als „das bist du" gelten wie ein `handelsregister_exakt`-Match. Regel:

| Auflösungs-Methode | Verhalten |
|---|---|
| `handelsregister_exakt` / `ted_nationalid` + hoher Score | „Arbeitest du bei X?" (starker Vorschlag) |
| `nur_name`, mittlerer Score | „Meinst du eine dieser Firmen?" (Liste, keine Vorauswahl) |
| unklar / mehrere Stämme | direkt manueller Pfad |

> Der Bestätigungs-Klick filtert False Positives selbst heraus — deshalb ist ein
> 60 %-Vorschlag okay, solange „Nein" sauber in den manuellen Pfad führt.

---

## Kopplung mit Ticket 06 (Billing) — NEU explizit

Das Onboarding ist die **einzige Quelle der bestätigten Identität**, die Ticket 06 fürs
Winner-Matching braucht:

1. **„Das bin ich" setzt `user_profiles.entity_confidence = 'confirmed'`** — das Gate für
   die Erfolgsprämie. Ohne Bestätigung: kein automatisches Fee-Matching.
2. **Gruppe = Identität.** Der User bestätigt eine *Gruppe* (z. B. CANCOM SE + Public +
   Managed Services). Winner-Matching läuft gegen **alle** aktiven `entity_id`s der Gruppe,
   nicht nur eine — sonst verpassen wir Gewinne von Schwester-Entitäten. `user_profiles`
   speichert die bestätigte **Gruppe/Entity-Menge**, nicht ein singuläres `entity_id`.

---

## Screen 3: Firma gefunden (v2-Anpassungen)

- **Normalfall = 1 Entität** (nur 24,3 % der Gruppen sind Mehr-Entitäten-Gruppen).
  Gruppen-Picker nur zeigen, wenn wirklich >1 Entität (Edge 3).
- **„47 Vergaben gewonnen"** wird **berechnet** aus `party_entity`(role=winner)/
  `contractor_stats` — es gibt **kein** `entities.total_wins`. Autocomplete-Ranking
  ebenso (Wins on-the-fly, nicht als Feld).
- Stats ehrlich flaggen, wenn Auflösung `nur_name` ist („unbestätigt").

---

## Aspiring Bidder: wachsendes Profil statt Sackgasse (v2)

76 % der Entities sind Gewinner → wer **nie** gewonnen hat (Neueinsteiger, SME, der
anfangen *will*), ist nicht in `entities` und landet im manuellen Branche/Region-Pfad.
**Das ist kein Fallback zweiter Klasse, sondern der Startpunkt eines wachsenden Profils:**

- Start: Branche (`dim_cpv.branche` ✅) + Region → sofort relevante Leads.
- Anreicherung über die Zeit: verfolgte/analysierte Leads, Interaktionsmuster → das
  Profil schärft sich, je mehr der Nutzer goVisor nutzt.
- Später (v3): eigene historische Angebotsdaten des Bieters (s. Produkt-Vision).

> Leitsatz: „Wir geben aus, was wir wissen — und es wird mehr, je länger du dabei bist."
> `known_from_ted=false` ist ein **Zustand**, kein Endzustand.

---

## Datenmodell (Änderungen)

### `user_onboarding_state` — wie Original, plus
| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `domain_stem` | string | **NEU:** aus E-Mail-Domain abgeleiteter Namens-Stamm |
| `suggested_entity_ids` | string[] | **NEU:** dedup. Kandidaten der Suggestion |

### `user_profiles` — Kopplung Ticket 06
| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `confirmed_group_id` / `confirmed_entity_ids` | string[] | **NEU:** bestätigte Identität (Gruppe!) |
| `entity_confidence` | enum | **NEU:** `confirmed`/`probable`/`none` — Billing-Gate |
| `active_entity_ids` | string[] | im Screen aktivierte Entitäten (min. 1) |

---

## Akzeptanzkriterien (geändert/ergänzt)

| # | Kriterium |
|---|-----------|
| 1 | Autocomplete (Wins **berechnet**, nicht aus `total_wins`) |
| 4 | **Domain-Stamm-Ableitung** + Dedup + Generik-Blockliste |
| 5–7 | Suggestion „Arbeitest du bei X?" → Bestätigung → Profil |
| 7b | **Bestätigung setzt `entity_confidence='confirmed'` + Gruppe** (Ticket-06-Gate) |
| 9 | `nur_name`-Match nie Auto-Confirm; Liste statt Vorauswahl |
| 10–12 | Unbekannte Firma: Branche → Region → Lead Explorer (wachsendes Profil) |
| 16 | **Winner-Matching gegen alle aktiven Gruppen-Entities** |

---

## Edge Cases (ergänzt)

| # | Case | Verhalten (v2) |
|---|------|-----------|
| 9 | Freemail-Domain | Domain-Stamm übersprungen, nur Name |
| 11 | Generik-Stamm (`stadt.de`-artig) | herausgefiltert, kein Vorschlag |
| 12 | Domain-Stamm trifft mehrere reale Firmen (Müller) | „Meinst du eine dieser?" statt Auto |
| 13 | Bestätigte Firma hat mehrere Gruppen-Entities | alle als Identität, User kann abwählen (min. 1) |
| 14 | Firma nicht in entities (Aspiring Bidder) | manueller Pfad = Profil-Keim, kein Dead-End |

---

## Out of Scope (V1)

| Was | Wann | Anmerkung |
|-----|------|-----------|
| USt-IdNr-Matching (Stufe 3) | V2 | |
| Externe Firmendatenbank für echtes Domain→Firma | V2+ | v1 nutzt Namensableitung |
| Logo-Upload, Tutorial, manuelle CPV-Auswahl | V2 | wie Original |

---

## Offene Fragen

| # | Frage | Vorschlag |
|---|-------|-----------|
| 1 | Generik-Blockliste pflegen | aus Top-Kollisions-Stämmen initial befüllen (stadt, gemeinde, arge, …) |
| 2 | Fuzzy-Schwelle Domain-Stamm | konservativ; lieber „nein"-Klick als falscher Auto-Match |
| 3 | Wie Gruppen-Zugehörigkeit visualisieren, wenn Auflösung unsicher | Confidence-Badge je Entität |
