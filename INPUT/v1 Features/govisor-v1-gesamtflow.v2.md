# goVisor V1 – Gesamtflow (v2)

**Produkt:** goVisor
**Version:** V1
**Status:** Überarbeitet gegen echte Datenlage (2026-07-20)
**Basis:** `govisor-v1-gesamtflow.md` (Original unverändert)

> **Was v2 ändert (gegenüber Original):** Preismodell ausgelagert (§Monetarisierung);
> Incumbent-Churn-Richtung korrigiert; Scores als Bänder statt Prozent; Schätz-Flags
> (`band_source`) durchgängig ins UI; Incumbent nur mit Confidence-Gate; User-Firma
> nutzer-bestätigt + graceful degradation; Anforderungs-Check auf real Machbares
> entschärft; Vertragslaufzeit echt-oder-geschätzt; eForms-Terminologie.

---

## Übersicht

goVisor hilft IT-Systemhäusern, öffentliche Aufträge zu finden und zu bewerten.

**Geschäftsmodell:** Basis-Fee (Abo) + Success-Fee (Erfolgsprämie).
→ **Mechanik & Beträge: siehe [`docs/pricing-modell.md`](../../docs/pricing-modell.md).**
Das Preismodell wird separat entwickelt und ist hier bewusst nicht festgeschrieben.
Für V1-Zwecke gilt nur die Mechanik: **monatliche Basis-Fee + erfolgsabhängige
Prämie bei gewonnenem Auftrag** (Höhe offen).

---

## Kern-Prinzip (v2): Ehrlichkeit im UI

Die Datenanalyse hat gezeigt: viele unserer Werte sind **geschätzt, nicht gemessen**
(nur 37 % der Auftragswerte echt; Incumbent-Auflösung teils unsicher;
Wechsel-Scores unkalibriert). Leitregel fürs gesamte UI:

> **Was geschätzt ist, wird sichtbar als geschätzt gekennzeichnet. Was wir nicht
> sicher wissen, raten wir nicht — wir zeigen „unbekannt".**

Das ist kein Schönheitsfehler, sondern der Vertrauens-Moat: TED zeigt Rohdaten,
wir zeigen ehrliche Einordnung.

---

## User Journey

Struktur unverändert zum Original (Landing → Registrierung → Onboarding →
Lead Explorer → Lead Detail → Upgrade → Paid). Änderungen betreffen **Inhalte**
der Screens, nicht den Fluss.

---

## Freemium / Zugang

Der Abo-Zugang (Free-Tier-Limits etc.) bleibt wie im Original — **aber** die
Monetarisierung ist jetzt Basis-Fee + Success-Fee (s.o.), nicht das ursprüngliche
reine `€29/Mo`-Freemium. Konkrete Gating-Logik wird mit dem Preismodell final
festgelegt.

**Unverändert gut:** Kein Trial (kein Trial-Abuse), Liste offen (Wert erleben),
Intelligence limitiert (Moat), bewusster Klick für Analyse-Verbrauch.

---

## Lead Detail: Zwei Tabs

### Tab: Übersicht (Free ∞)

```
┌────────────────────────────────────────────────────────────┐
│  [ÜBERSICHT]    [🔒 ANALYSE · 2 von 3 übrig]              │
├────────────────────────────────────────────────────────────┤
│  LEAD                                                      │
│  CPV           72212 · Cloud & Managed Services           │
│  Region        Bund                                        │
│  Volumen       ~12 Mio € (geschätzt ⓘ)                    │
│  Timing        ~4 Monate bis Auslauf (geschätzt ⓘ)        │
│  Vertragsart   Rahmenvertrag                              │
│                                                            │
│  BUYER                                                     │
│  Bundesministerium des Innern                              │
│                                                            │
│  INCUMBENT                                                 │
│  Bechtle AG · seit 2020        [nur bei hoher Confidence]  │
└────────────────────────────────────────────────────────────┘
```

**v2-Änderungen im Übersicht-Tab:**
- **Volumen** trägt *immer* das `band_source`-Flag: „echt" ohne Zusatz,
  sonst „(geschätzt ⓘ)" mit Tooltip „CPV-Median, kein veröffentlichter Wert".
  (Nur 37 % der Werte sind echt.)
- **Timing „bis Auslauf"**: explizites `end_date` gibt es nur bei **~18 %** der
  Vergaben. Wo vorhanden → echt zeigen. Sonst → **CPV-Median-Laufzeit als Schätzung**,
  geflaggt (gleiches Muster wie Volumen). Nie eine harte Zahl ohne Kennzeichnung.
- **Incumbent nur mit Confidence-Gate** (s. nächster Abschnitt).

### Incumbent-Anzeige: Confidence-Gate (P6)

Gemessen: Incumbent-Identifikation ist probabilistisch (Entity-Auflösung teils nur
`nur_name`; Nachfolge-Confidence variabel). Regel:

| Auflösungs-Güte | Anzeige |
|---|---|
| **Hoch** (`handelsregister_exakt`/`ted_nationalid` + starke Nachfolge) | „Bechtle AG · seit 2020" |
| **Mittel** (`nur_name`) | „Aktueller Auftragnehmer: Bechtle AG" (ohne „seit"-Tenure) |
| **Niedrig / `nicht_aufgeloest`** | „Auftragnehmer nicht eindeutig" / Block weglassen |

> **Lieber „unbekannt" zeigen als falsch.** Ein falscher Incumbent im kostenlosen
> Tab ist ein Vertrauensbruch beim ersten Eindruck.

### Tab: Analyse (Free 3/30T)

```
┌────────────────────────────────────────────────────────────┐
│  SCORES                                                    │
│  🎯 Relevanz         hoch     CPV ✓ · Region ✓ · Volumen ✓ │
│  ⚡ Wechsel-Chance   hoch     Lange Dauer, Buyer wechselt  │
│                                                            │
│  DEINE ERFAHRUNG        [nur bei zugeordneter User-Firma]  │
│  • 2 Wins bei BMI (letzter: 2022)                         │
│  • 1 laufender Vertrag · 3 passende Referenzen             │
│                                                            │
│  DIREKTVERGLEICH        [nur bei zugeordneter User-Firma]  │
│                  DU          BECHTLE                       │
│  Wins bei BMI    2           5                            │
│  Wins in Cloud   34          47                           │
│  Marktanteil*    8%          12%   (*Anteil n. Win-Anzahl) │
│                                                            │
│  ANFORDERUNGS-CHECK (V1: CPV-basiert)                      │
│  ✓ Haupt-CPV 72212 passt zu deinem Profil                 │
│  ⓘ Detail-Anforderungen (Zertifikate etc.): V2            │
│                                                            │
│  BUYER-STATISTIK · INCUMBENT-PROFIL · MARKT-STATS          │
└────────────────────────────────────────────────────────────┘
```

**v2-Änderungen im Analyse-Tab:**

1. **Scores als Bänder, nicht als Prozent (P4).** „🎯 92 %" / „⚡ 74 %" suggeriert
   kalibrierte Wahrscheinlichkeit, die wir nicht haben (heuristisches Score-Modell).
   → **hoch / mittel / niedrig**. Der Breakdown (CPV ✓, Region ✓ …) bleibt, weil er
   die konkrete, belegbare Begründung liefert.

2. **„Deine Erfahrung" / „Direktvergleich" nur bei zugeordneter User-Firma (P7).**
   Beides braucht die Auflösung der eigenen Firma zu einer Entity. Ist sie nicht
   sicher zugeordnet → Block ausblenden mit „verfügbar, sobald wir deine Firma
   zugeordnet haben" statt Fantasiezahlen. Die markt-seitige Analyse (Buyer/Incumbent/
   Markt) läuft trotzdem — sie braucht die User-Entity nicht.

3. **„Marktanteil" explizit definiert:** Anteil nach **Anzahl Wins** in der
   CPV-Klasse des Leads (nicht Volumen — das ist zu 58 % geschätzt). Sternchen im UI.

4. **Anforderungs-Check auf real Machbares entschärft (P3).** Wir haben strukturiert
   nur **`cpv_main`** (einen CPV), keine zusätzliche CPV-Liste und keine
   Vergabeunterlagen. Der V1-Check ist daher **CPV-basiert** (Haupt-CPV vs. Profil).
   Der detaillierte Anforderungs-Abgleich (Zertifikate, Eignungskriterien) braucht
   F02/Vergabeunterlagen-Extraktion → **V2** (s. Out of Scope).

### Incumbent-Profil: Churn-Richtung korrigiert (P2)

```
INCUMBENT-PROFIL
• Rang #3 in Cloud · 47 Wins
• Verliert die Mehrheit seiner Wiedervergaben*
  (*gemessen: Incumbent hält nur ~19 %, verliert ~81 % — s. Caveat)
```

**Korrektur:** Das Original schrieb „Verliert 28 % seiner Verträge". Gemessen an
80.899 Nachfolge-Paaren (beidseitig aufgelöster Gewinner) ist es **umgekehrt**:

| | gemessen |
|---|---|
| Incumbent **hält** | **18,7 %** |
| Incumbent **verliert** | **81,3 %** |

**Caveat (ehrlich mitführen):** Die 81 % sind vom Nachfolge-Modell vermutlich nach
oben verzerrt (Titel-Matching + Entity-Auflösung verpassen echte Wiedervergaben →
Scheinwechsel). Wahre Quote liegt darunter, aber es ist eindeutig ein
**Mehrheits-Wechsel-Markt**. Fürs Produkt sogar besser: hohe Wechselquote =
viel Chance für den Herausforderer → „Outside" ist zu Recht der Default-View.

---

## Inside / Outside View

Unverändert zum Original — und durch die Datenlage **bestätigt**: bei ~81 %
Wechselquote ist „Outside" (Herausforderer) der dominante Use-Case, korrekt als
Default gesetzt.

---

## Datenquellen (Terminologie korrigiert, P8)

| Quelle | Was |
|--------|-----|
| **TED — eForms** (seit Okt 2023) | Ausschreibungen, Vergaben, Vorinformationen |
| **TED — Legacy** (TED_EXPORT, bis 2023) + text/ojs | historische Bekanntmachungen |
| Gold Layer | Leads, Entities, Scores, Party_Entity, `value_band_effektiv` |
| User-Profil | CPVs, Regionen, Gruppen, Zertifikate, **bestätigte Entity** |

> Hinweis: Die alten TED-Formularnummern F01/F02/F03 wurden ab Okt 2023 durch
> **eForms** ersetzt — ein Großteil der aktuellen Daten ist bereits eForms.

---

## Out of Scope (V1) — mit Begründung

| Was | Wann | Warum |
|-----|------|-------|
| **F02-Anforderungs-Extraktion** | V2 | Blocker ist nicht der Parser, sondern dass wir die **Vergabeunterlagen nicht haben** (nur `portal_url`-Link). „Leicht" (LLM über `description`) liefert dünne Ergebnisse; „echt" (Portale crawlen) = Wochen, brüchig. |
| Ausschreibungsvorbereitung, Partner-Empfehlung, Chat (LLM), OAuth, Team-Accounts, Scheduled Exports | V2 | wie Original |

---

## Metriken (Tracking)

Wie Original, plus modell-spezifisch:

| Metrik | Beschreibung |
|--------|--------------|
| `firm_resolved` | User-Firma sicher zu Entity zugeordnet (ja/nein) — Gate für Direktvergleich |
| `estimate_flag_shown` | Schätz-Flag auf Volumen/Timing angezeigt |
| `win_reported` | Nutzer-Bestätigung „Auftrag gewonnen" (Success-Fee-Auslöser) |
| *(sonst wie Original: leads_viewed, analyses_used, conversion_rate, …)* | |

---

## Offene Punkte (aus v2-Review)

1. **Preismodell** — separat in `docs/pricing-modell.md`, Beträge offen.
2. **Success-Fee-Attribution** — wie Kausalität „Lead → Zuschlag" rechtssicher
   abrechnen? (Nutzer-Bestätigung als Kern, s. Pricing-Doc §7.)
3. **Laufzeit-Schätzung** — CPV-Median-Laufzeit als Builder umsetzen (analog Wert).
4. **Score-Kalibrierung** — mittelfristig echte Wahrscheinlichkeiten statt Bänder,
   sobald genug Feedback-Daten da sind.
