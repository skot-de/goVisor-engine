# Feature #4: Auto-Dossier — v2 (engine-verdrahtet)

**Produkt:** goVisor  
**Version:** V1  
**Status:** Draft (korrigiert gegen das reale Gold + geerbte #3-Korrekturen)  
**Erstellt:** 2026-07-19

---

## Korrektur-Block (gemessen 2026-07-19)

Das Dossier fasst die #3-Sektionen in ein Dokument — es **erbt alle #3/#3-Erweiterung-Korrekturen**
und hat eigene Feld-/Verfügbarkeits-Probleme. Verbindlich:

| # | Befund | Konsequenz |
|---|--------|------------|
| D1 | Feldnamen (wie #5): `title`→**`titel`**, `timing_months`→**`months_to_expiry`**, `cpv_label`→**Join `dim_cpv`**, `scores.switch`→**`displaceability`** (NULL→„nicht verfügbar", Edge Case 2 ✓), `scores.relevance`→**user-spezifisch** (`lead_relevance`, #1) | im Template-Code korrigieren |
| D2 | Buyer **„Ø Dauer 4.2 Monate"** (`avg_decision_days`) ist **nicht gebaut** (deferred, braucht cn→can-Link 58 %, 🟡) | in v1 weglassen oder „—" |
| D3 | Buyer **„Treue 67 %"** = `incumbent_loyalty` — **existiert jetzt** (`buyer_loyalty.parquet`), aber 🔴 (Nachfolge-Modell) → **mit `n` + Konfidenz**, nicht als blanker Fakt |
| D4 | Incumbent **„Seit 2020 (4 Jahre)"** — kein gespeichertes Feld; **jetzt herleitbar** aus `contract_succession` (100k verifizierte Nachfolgen) — sonst weglassen |
| D5 | **Direktvergleich** erbt #3-Erweiterung K2/K3/K4 (kein `party_entity.lead_id`; Multi-Entity-Wins erst summieren; Region-Coverage); Wins bei fragmentiertem Incumbent = **Floor** |
| D6 | **Anforderungs-Check** (K1 korrigiert): alle Lead-CPVs aus **`silver/notice_cpv`** (join `notice_id`) → die Mehr-CPV-Prüfung („✗ CPV 48440 fehlt") ist **sofort** möglich. Labels aus `dim_cpv_label` (97 % Coverage) |

**Durchgängig:** jede aus KPIs abgeleitete Zahl im Dossier trägt ihren Konfidenz-/Coverage-Zustand
sichtbar (das Dokument geht an Chef/Vertrieb — ein falscher „Fakt" ist teuer). „Ehrlich statt hübsch."

---

## Kontext

User sieht Lead-Detail und will:

> "Gib mir ein Briefing, das ich meinem Team / Chef / Vertrieb schicken kann."

Auto-Dossier = Lead-Detail als **kurzes, bearbeitbares Dokument** – Entscheidungshilfe für Go/No-Go.

**Nicht in V1:** Ausschreibungsvorbereitung (Referenz-Builder, Checklisten, Preis-Kalkulation) → V2.

---

## User Story

> **Als** Anbieter  
> **will ich** ein kurzes Briefing zu einem Lead generieren  
> **um** intern eine Go/No-Go Entscheidung zu treffen, ohne alles manuell zusammenzufassen.

---

## Output

| Aspekt | V1 |
|--------|-----|
| **Zweck** | Entscheidungshilfe |
| **Umfang** | 1-2 Seiten |
| **Formate** | DOCX, Markdown |
| **Bearbeitbar** | Ja |

---

## Inhalt

| Sektion | Inhalt | Länge |
|---------|--------|-------|
| **Zusammenfassung** | Was, wer, wann, Chance – in 2-3 Sätzen | 3 Zeilen |
| **Lead-Übersicht** | CPV, Region, Volumen, Timing, Vertragsart | Tabelle |
| **Scores** | Relevanz + Wechsel-W. mit kurzer Erklärung | 2 Zeilen |
| **Buyer** | Name, Kontakt, Vergabe-Statistik | 5 Zeilen |
| **Incumbent** | Wer, seit wann, Marktposition | 5 Zeilen |
| **Direktvergleich** | Tabelle: Wir vs. Incumbent (Wins, Marktanteil, Trend) | Tabelle |
| **Unsere Position** | Track Record beim Buyer, laufende Verträge, ähnliche Referenzen | 5-10 Zeilen |
| **Anforderungs-Check** | Was matcht, was fehlt | Liste |
| **Quellen** | TED-Link, Datenstand | Footer |

**Nicht enthalten (V2):**
- Empfehlung/Go-No-Go Text
- Handlungsempfehlungen
- Preis-Einschätzung
- Team-Vorschlag

---

## UI

### Trigger im Lead-Detail

```
┌────────────────────────────────────────────────────────────┐
│  BMI – Managed Services Bund           [TED ↗] [📄 Briefing]│
│                                                            │
│  [Outside]                                                 │
├────────────────────────────────────────────────────────────┤
│  ...                                                       │
```

### Modal nach Klick

```
┌─────────────────────────────────────────────────────────────┐
│  Briefing erstellen                             [×]        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Format:                                                    │
│  ● Word (.docx)                                            │
│  ○ Markdown (.md)                                          │
│                                                             │
│  [Abbrechen]                        [Briefing erstellen →] │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Keine Sektions-Auswahl in V1 – alles drin, kurz gehalten.

---

## Beispiel-Output

### DOCX / Markdown

```
═══════════════════════════════════════════════════════════════
LEAD-BRIEFING
BMI – Managed Services Bund
═══════════════════════════════════════════════════════════════

Erstellt: 19.07.2026
Quelle: goVisor

───────────────────────────────────────────────────────────────
ZUSAMMENFASSUNG
───────────────────────────────────────────────────────────────

Rahmenvertrag für Cloud & Managed Services beim BMI (€12M).
Incumbent Bechtle seit 4 Jahren. Auslauf in 4 Monaten.
Relevanz 92%, Wechsel-Wahrscheinlichkeit 74%.
Wir haben 2 Wins bei diesem Buyer und kennen den Kunden.

───────────────────────────────────────────────────────────────
LEAD-ÜBERSICHT
───────────────────────────────────────────────────────────────

CPV             72212 · Cloud & Managed Services
Region          Bund
Volumen         €12M (geschätzt)
Timing          4 Monate bis Auslauf
Vertragsart     Rahmenvertrag
Quelle          Auslauf-Radar

───────────────────────────────────────────────────────────────
SCORES
───────────────────────────────────────────────────────────────

🎯 Relevanz         92%     CPV ✓ · Region ✓ · Volumen ✓
⚡ Wechsel-W.       74%     Lange Vertragsdauer, Buyer wechselt

───────────────────────────────────────────────────────────────
BUYER: BUNDESMINISTERIUM DES INNERN
───────────────────────────────────────────────────────────────

Adresse         Alt-Moabit 140, 10557 Berlin
Kontakt         vergabestelle@bmi.bund.de
Vergaben (5J)   34
Ø Dauer         4.2 Monate
Treue           67% Incumbent-Verlängerung

───────────────────────────────────────────────────────────────
INCUMBENT: BECHTLE AG
───────────────────────────────────────────────────────────────

Seit            2020 (4 Jahre)
Wins Cloud      47
Marktanteil     12%
Trend           ↗ +12% vs. Vorjahr

───────────────────────────────────────────────────────────────
DIREKTVERGLEICH
───────────────────────────────────────────────────────────────

                        WIR         BECHTLE
Wins bei BMI            2           5           
Wins in Cloud           34          47          
Marktanteil             8%          12%         
Trend                   ↗ +15%      ↘ -3%       

───────────────────────────────────────────────────────────────
UNSERE POSITION
───────────────────────────────────────────────────────────────

Track Record beim BMI:
• 2 Wins in den letzten 5 Jahren
• Letzter Win: 2022 (IT-Beratung, €2M)
• 1 laufender Vertrag (IT-Beratung, bis 2025)

Ähnliche Referenzen:
• 2023: BA – Cloud Modernisierung (€8M)
• 2022: BMF – Managed Services (€14M)
• 2021: Finanzamt NRW – IT-Betrieb (€6M)

───────────────────────────────────────────────────────────────
ANFORDERUNGS-CHECK
───────────────────────────────────────────────────────────────

✓ CPV 72212 (Cloud)             In unserem Profil
✓ CPV 72310 (Datenverarbeitung) In unserem Profil
✗ CPV 48440 (SAP)               FEHLT
✓ Region Bund                   In unserem Profil
✓ Volumen €12M                  In unserer Range

Lücke: SAP-Kompetenz fehlt.

───────────────────────────────────────────────────────────────

TED: https://ted.europa.eu/...
Datenstand: 19.07.2026
Generiert von goVisor

═══════════════════════════════════════════════════════════════
```

---

## Zusammenfassung-Generierung

**V1: Template-basiert**

```python
def generate_summary(lead, relevance, user_position, incumbent, cpv_label):
    # D1: value_source-ehrlich; cpv_label kommt aus dim_cpv-Join (kein lead.cpv_label)
    volume_text = format_volume(lead.value_real_2020, lead.value_source)  # "unbekannt" → "Volumen unbekannt"
    # D4: incumbent-„seit" aus contract_succession herleiten (kein gespeichertes Feld); sonst nur Name
    incumbent_text = (f"Incumbent {incumbent.name} seit {incumbent.since_year}."
                      if incumbent and incumbent.since_year else
                      (f"Incumbent {incumbent.name}." if incumbent else "Erstausschreibung – kein Incumbent."))

    if user_position.wins_at_buyer > 0:
        position_text = f"Wir haben {user_position.wins_at_buyer} Wins bei diesem Buyer und kennen den Kunden."
    elif user_position.wins_in_region > 0:
        position_text = f"Wir haben {user_position.wins_in_region} Wins in dieser Region."
    else:
        position_text = "Neuer Buyer und neue Region für uns."

    # D1: displaceability, NULL → nicht verfügbar (nicht 0)
    switch_text = (f"Wechsel-Wahrscheinlichkeit {lead.displaceability}%"
                   if lead.displaceability is not None else "Wechsel-Wahrscheinlichkeit nicht verfügbar")

    # D1: titel/months_to_expiry; relevance ist user-spezifisch (lead_relevance)
    return f"""{lead.contract_kind} für {cpv_label} bei {lead.buyer_name} ({volume_text}).
{incumbent_text} Auslauf in {lead.months_to_expiry} Monaten.
Relevanz {relevance}%, {switch_text}.
{position_text}"""
```

**V2:** LLM-generierte Zusammenfassung (natürlicher Text)

---

## Akzeptanzkriterien

| # | Kriterium |
|---|-----------|
| 1 | Button "Briefing" im Lead-Detail Header |
| 2 | Modal mit Format-Auswahl (DOCX, Markdown) |
| 3 | DOCX-Download funktioniert, Datei öffnet in Word |
| 4 | Markdown-Download oder Copy-to-Clipboard |
| 5 | Zusammenfassung automatisch generiert (Template) |
| 6 | Alle Sektionen enthalten (keine Auswahl in V1) |
| 7 | Datenstand/Zeitstempel im Dokument |
| 8 | TED-Link enthalten |
| 9 | goVisor-Branding im Footer |
| 10 | Dateiname: `Briefing_{Buyer}_{Lead-Titel}_{Datum}.docx` |

---

## Edge Cases

| # | Case | Verhalten |
|---|------|-----------|
| 1 | Kein Incumbent | "Erstausschreibung – kein Incumbent", Direktvergleich ausblenden |
| 2 | Scores n/a | "Wechsel-Wahrscheinlichkeit: nicht verfügbar" |
| 3 | Keine Kontaktdaten | Buyer-Sektion ohne Kontakt |
| 4 | User hat keine Wins bei Buyer | "Kein Track Record bei diesem Buyer" |
| 5 | User hat keine ähnlichen Wins | "Keine ähnlichen Referenzen" |
| 6 | Volumen unbekannt | "Volumen: unbekannt" |
| 7 | Lücken vorhanden | Liste der fehlenden CPVs |
| 8 | Keine Lücken | "Vollständiger Match ✓" |
| 9 | Inside View (eigener Vertrag) | Zusammenfassung anpassen: "Unser Vertrag läuft aus..." |

---

## Out of Scope

| Was | Wann |
|-----|------|
| PDF-Format | Nie (nicht bearbeitbar) |
| Sektions-Auswahl | V2 |
| LLM-generierte Zusammenfassung | V2 |
| Go/No-Go Empfehlung | V2 |
| Ausschreibungsvorbereitung (Checklisten, Referenz-Builder) | V2 |
| Batch-Export (mehrere Leads) | V2 |
| E-Mail-Versand aus App | V2 |

---

## Abhängigkeiten

| Abhängigkeit | Status |
|--------------|--------|
| Lead-Detail API (#3) | Ticket #3 |
| DOCX-Generierung (z.B. docx.js, python-docx) | ⬜ Setup |
| Markdown trivial | 🟢 |

---

## Testfälle

| # | Test | Erwartung |
|---|------|-----------|
| 1 | Klick auf Briefing-Button | Modal öffnet |
| 2 | DOCX auswählen + erstellen | DOCX Download startet |
| 3 | Markdown auswählen | Markdown Download |
| 4 | DOCX in Word öffnen | Formatierung korrekt, bearbeitbar |
| 5 | Lead ohne Incumbent | Zusammenfassung angepasst, Direktvergleich fehlt |
| 6 | Lead mit allen Daten | Vollständiges Briefing |
| 7 | Lead mit Lücken | Anforderungs-Check zeigt fehlende CPVs |
| 8 | Inside View | Zusammenfassung: "Unser Vertrag..." |
| 9 | Dateiname | Korrekt formatiert mit Buyer, Titel, Datum |

---

## Offene Fragen

| # | Frage | Vorschlag |
|---|-------|-----------|
| 1 | DOCX-Library? | docx.js (Frontend) oder python-docx (Backend) |
| 2 | Branding: Logo? | Ja, Header oder Footer |
| 3 | Sprache? | Deutsch |
| 4 | Max. Referenzen anzeigen? | 3-5 |
| 5 | Inside View: separates Template? | Ja, leicht angepasst |
