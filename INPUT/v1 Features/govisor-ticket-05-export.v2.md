# Feature #5: Export — v2 (engine-verdrahtet)

**Produkt:** goVisor  
**Version:** V1  
**Status:** Draft (korrigiert gegen das reale `leads`-Schema)  
**Erstellt:** 2026-07-19

---

## Korrektur-Block: Feld-Mapping gegen das echte Gold-`leads` (gemessen 2026-07-19)

Verbindlich. Die Spalten-/Score-Namen im Ticket sind teils erfunden — hier die echten Felder:

| Ticket-Annahme | Real im Gold | Hinweis |
|----------------|--------------|---------|
| `lead.title` | **`lead.titel`** | deutscher Feldname |
| `lead.cpv_label` | **jetzt: `dim_cpv_label`** (9.454 Codes, 97 % Coverage / 100 % ab 2016) join `cpv_main` | ✅ verfügbar |
| `lead.timing_months` | **`lead.months_to_expiry`** (nur `auslauf`) | f01/f02-Leads haben anderes Timing (#1); Spalte quellenabhängig |
| `scores.relevance` | **user-spezifisch** aus `lead_relevance` (#1), NICHT `lead.*` | Export braucht den berechneten Relevanz-Wert des Users |
| `scores.switch` | **`lead.displaceability`** | **NULL bei 31,4 %** (Einmal-Werk) → Zelle leer (Edge Case 4 deckt das ✓) |
| `lead.incumbent_years` | **kein Feld** — herleiten aus `contract_succession`/`vergabe_datum` oder weglassen | „Incumbent seit" ist nicht gespeichert |
| `lead.value_real_2020` / `value_source` / `value_band` | ✓ existiert | deflationiert; leer bei `value_source='unbekannt'` (Edge Case 3 ✓) |

**Ergänzung:** zusätzlich `value_used` (nominal) **und** `value_band` exportieren (CRM will oft beides),
sowie `incumbent_conf` — sonst liest sich „Incumbent = X" als Fakt, obwohl 10 % `< 0.5` sind.

---

## Kontext

User sieht Lead-Liste und will:

> "Gib mir die Leads als Excel, damit ich sie in meinem CRM / Reporting / Team-Meeting nutzen kann."

Export = Lead-Liste als **Datei** – gefiltert wie in der aktuellen Ansicht.

---

## User Story

> **Als** Anbieter  
> **will ich** meine gefilterte Lead-Liste exportieren  
> **um** sie offline zu bearbeiten, ins CRM zu importieren oder intern zu teilen.

---

## Was wird exportiert?

**Aktuelle Ansicht** – was der User sieht, bekommt er.

| Aspekt | Verhalten |
|--------|-----------|
| **Filter** | Angewendet (nur gefilterte Leads) |
| **Sortierung** | Angewendet |
| **View** | Outside oder Inside (je nach Toggle) |
| **Spalten** | Alle aus Liste + Details |

---

## Spalten

| Spalte | Quelle (korrigiert) | Typ |
|--------|---------------------|-----|
| Titel | `lead.titel` | Text |
| Buyer | `lead.buyer_name` | Text |
| CPV | `lead.cpv_main` | Text |
| CPV-Bezeichnung | Join `dim_cpv_label` (`cpv_code`=`cpv_main`) | Text |
| Region | `lead.buyer_nuts` | Text |
| Volumen (real 2020) | `lead.value_real_2020` | Zahl |
| Volumen (nominal) | `lead.value_used` | Zahl |
| Volumen-Band | `lead.value_band` | Text |
| Volumen-Quelle | `lead.value_source` | Text |
| Timing (Monate) | `lead.months_to_expiry` (auslauf) | Zahl |
| Vertragsart | `lead.contract_kind` | Text |
| Quelle | `lead.source` | Text |
| Relevanz (%) | `lead_relevance.relevance_score` (user-spezifisch, #1) | Zahl |
| Wechsel-W. (%) | `lead.displaceability` (leer wenn NULL) | Zahl |
| Incumbent | `lead.incumbent_name` | Text |
| Incumbent-Konfidenz | `lead.incumbent_conf` | Zahl |
| TED-Link | `lead.ted_url` | URL |

---

## Formate

| Format | Use Case |
|--------|----------|
| **Excel (.xlsx)** | Bearbeitung, Pivot, Filter |
| **CSV (.csv)** | CRM-Import, Programmatisch |

---

## UI

### Button im Lead Explorer

```
┌─────────────────────────────────────────────────────────────┐
│  [Filter ▼]  [Sortierung ▼]        47 Leads    [📥 Export] │
├─────────────────────────────────────────────────────────────┤
│  ...                                                        │
```

### Dropdown nach Klick

```
┌─────────────────────┐
│  📥 Export als...   │
├─────────────────────┤
│  Excel (.xlsx)      │
│  CSV (.csv)         │
└─────────────────────┘
```

Kein Modal, direkt Download.

---

## Dateiname

```
goVisor_Leads_{View}_{Datum}.xlsx
goVisor_Leads_{View}_{Datum}.csv
```

Beispiele:
- `goVisor_Leads_Outside_2026-07-19.xlsx`
- `goVisor_Leads_Inside_2026-07-19.csv`

---

## Akzeptanzkriterien

| # | Kriterium |
|---|-----------|
| 1 | Export-Button im Lead Explorer Header |
| 2 | Dropdown mit Format-Auswahl (Excel, CSV) |
| 3 | Export enthält nur gefilterte Leads |
| 4 | Sortierung wird übernommen |
| 5 | Alle definierten Spalten enthalten |
| 6 | Excel öffnet korrekt in Excel/Google Sheets |
| 7 | CSV ist UTF-8, Semikolon-getrennt (DE-Standard) |
| 8 | Download startet sofort (kein Modal) |
| 9 | Dateiname enthält View + Datum |
| 10 | Max. 1000 Leads pro Export (Performance) |
| 11 | Zahlen als Zahlen formatiert (nicht Text) |
| 12 | URLs als klickbare Links (Excel) |

---

## Edge Cases

| # | Case | Verhalten |
|---|------|-----------|
| 1 | 0 Leads (Filter zu eng) | Button disabled + Tooltip "Keine Leads zum Exportieren" |
| 2 | >1000 Leads | Warnung: "Nur die ersten 1000 Leads werden exportiert" + Export |
| 3 | Volumen unbekannt | Leer (nicht "0", nicht "unbekannt") |
| 4 | Score n/a | Leer |
| 5 | Kein Incumbent | Leer |
| 6 | Sonderzeichen in Titel | Korrekt escaped (ä, ö, ü, ß, etc.) |
| 7 | Sehr lange Titel | Nicht abgeschnitten |
| 8 | Komma im Titel (CSV) | Korrekt quoted |
| 9 | Export während Laden | Button disabled bis Daten geladen |

---

## CSV-Spezifikation

| Aspekt | Wert |
|--------|------|
| Encoding | UTF-8 (mit BOM für Excel-Kompatibilität) |
| Trennzeichen | Semikolon `;` |
| Textqualifizierer | Doppeltes Anführungszeichen `"` |
| Zeilenende | CRLF (`\r\n`) |
| Header | Ja, erste Zeile |

Beispiel:
```csv
Titel;Buyer;CPV;Volumen;Relevanz
"Managed Services Bund";BMI;72212;12000000;92
"IT-Beratung";AA;72211;;85
```

---

## Excel-Spezifikation

| Aspekt | Wert |
|--------|------|
| Format | XLSX (Office Open XML) |
| Sheet-Name | "Leads" |
| Header | Erste Zeile, fett |
| Spaltenbreite | Auto-fit |
| Zahlen | Als Zahl formatiert |
| URLs | Als Hyperlink |
| Datum im Footer | "Exportiert am {Datum}" |

---

## Out of Scope

| Was | Wann |
|-----|------|
| Spalten-Auswahl | V2 |
| Scheduled Exports (täglich/wöchentlich) | V2 |
| E-Mail-Versand | V2 |
| API-Export (JSON) | V2 |
| Export >1000 Leads | V2 (Pagination oder async) |
| Batch-Dossier (mehrere Briefings) | V2 |
| PDF-Export der Liste | Nie |

---

## Abhängigkeiten

| Abhängigkeit | Status |
|--------------|--------|
| Lead Explorer API (#1) | Ticket #1 |
| Filter-Logik (#1) | Ticket #1 |
| Excel-Library (SheetJS oder exceljs) | ⬜ Setup |
| CSV trivial | 🟢 |

---

## Testfälle

| # | Test | Erwartung |
|---|------|-----------|
| 1 | Klick auf Export | Dropdown öffnet |
| 2 | Excel wählen | XLSX Download startet |
| 3 | CSV wählen | CSV Download startet |
| 4 | Filter aktiv (z.B. nur Bund) | Nur gefilterte Leads im Export |
| 5 | Sortierung aktiv (z.B. nach Relevanz) | Sortierung übernommen |
| 6 | Excel in Excel öffnen | Spalten korrekt, keine Fehler |
| 7 | Excel in Google Sheets öffnen | Spalten korrekt |
| 8 | CSV in Excel öffnen | Encoding korrekt (Umlaute), Spalten getrennt |
| 9 | 0 Leads | Button disabled + Tooltip |
| 10 | 1001 Leads | Warnung + nur 1000 exportiert |
| 11 | 500 Leads | Download < 5 Sekunden |
| 12 | Dateiname prüfen | View + Datum enthalten |
| 13 | Volumen leer | Zelle leer, nicht "0" |
| 14 | Titel mit Sonderzeichen | Korrekt dargestellt |
| 15 | TED-Link in Excel | Klickbar |

---

## Offene Fragen

| # | Frage | Vorschlag |
|---|-------|-----------|
| 1 | CSV-Trennzeichen? | Semikolon (DE-Standard) |
| 2 | Excel-Library? | SheetJS (Frontend) oder exceljs (Backend) |
| 3 | Max. Leads? | 1000 |
| 4 | Spalten erweiterbar? | V2 mit Auswahl |
| 5 | Export-Counter (Analytics)? | Ja, für Usage-Tracking |
