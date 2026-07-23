# goVisor — Mehrwert-Roadmap (KPIs, Features, externe Quellen)

**Erstellt:** 2026-07-19 · Grundlage: 3 Markt-/Quellen-Recherchen + granulare Datenmessung am echten Bestand.

**Zweck:** Ideenlandkarte mit *gemessenem* Mehrwert und ehrlicher Machbarkeit, damit Versionen (V1/V2/…)
zugeordnet werden können. Spalte „Version" bewusst leer — die füllst du.

**Leitbefund:** Der schwere analytische Kern steht bereits (Nachfolge-Modell, Verdrängbarkeit, Markt-/
Buyer-/Contractor-Statistik, Direktvergleich). Die wertvollsten Ergänzungen sind entweder **reine
Verdrahtung vorhandener Daten** oder eine **kostenlose** externe Quelle. Alles unten mit gemessenen Zahlen.

---

## Bereits vorhanden (Baseline)
Auslauf-Radar (`leads`) · Verdrängbarkeits-Score (AUC 0,767, Stand 2026-07-23) · Nachfolge-Modell (100k verifizierte Ketten) ·
Nachfolge-KPIs (head_to_head, loss_rate, switch_rate, buyer_loyalty, contractor_loss) · Markt-Views
(buyer/contractor/market_stats) · avg_decision_days · incumbent_tenure · prospective Leads (F01/F02) ·
CPV-Match + `dim_cpv_label` · kuratierte Buyer-Aliase.

---

## ⭐ FLAGSHIP — Marktchancen-Radar (White-Space Explorer)

**Die strategische Erhebung von goVisor: vom Lead-Tool zum C-Level-Werkzeug.** Beantwortet nicht
„welchen Auftrag hole ich?", sondern **„welchen MARKT sollte ich erschließen — und wie (Make/Buy/Partner)?"**

**An echten Daten validiert (2021+, gemessen):** Es gibt reale Hochwert-Segmente mit fast keinem
Wettbewerb — z. B. CPV 8021 (berufl. Unterricht): **665 Awards, 75 % Single-Bidder, Median 53 Mio €,
nur 19 Firmen**; CPV 3462 (Schienenfahrzeuge): **26 % erfolglos** (Käufer finden keinen Anbieter).

**Opportunity-Score je Segment** (CPV-Klasse × opt. Region), aus fünf Achsen:
| Achse | Signal (haben wir) | Richtung |
|-------|--------------------|----------|
| **Nachfrage** | Award-Zahl + Volumen + Wiederkehr | mehr = besser |
| **Schwäche** | `verfahren_status='erfolglos'`-Rate + Single-Bidder + Ø-Bieter (**A2-Kern!**) | schwächer = besser |
| **Wert** | Median/Gesamt-Volumen | höher = besser |
| **Nähe** | Skill-Adjacency zum eigenen CPV-Footprint | näher = leichter |
| **Struktur** | **HHI / Top-N-Share** — bestimmt die STRATEGIE, nicht die Attraktivität | s. u. |

**Make / Buy / Partner — Decision-Support** (der strategische Kern):
- **Struktur fragmentiert + dünn** (Bsp. 8021) → **Make** (selbst aufbauen, niedrige Barriere) oder **Buy** (regionalen Player kaufen).
- **Struktur Oligopol** (Bsp. 3463: Siemens/Hitachi) → **Buy-Spezialist** oder **Partner** (Teaming).
- **Buy**: `contractor_stats` liefert die **konkreten Nischen-Dominatoren = Übernahmeziele** (die 19 Firmen bei 8021).
- **Make**: Gap-Analyse — welche Sub-CPVs/Fähigkeiten fehlen vs. Segment-Anforderungsprofil.
- **Partner**: Teaming-Graph (T1.4).

**Datenbasis: ~90 % vorhanden** (market_stats, contractor_stats, `verfahren_status`, num_tenders, Teaming-Graph).
**✅ Gebaut (2026-07-19):** `gold.market_opportunity` — Segmente gescort (Nachfrage×Schwäche×Wert, 3-J-Fenster,
Jahre transparent), Struktur (fragmentiert/moderat/oligopol) + Top-Dominatoren (Buy-Longlist) + `opportunity_score`.
Plus **`gold.retender_signal`** — chronische Fehl-Ausschreibungen inhaltsgeclustert („Trier: Schulzentrum 4× über
4 Jahre erfolglos"), 282 aktuell relevante Bedarfe, als `chronic_needs` je Segment. **Der stärkste Kauf-Hinweis.**
Plus **`gold.cpv_adjacency`** (Firmen-Co-Occurrence → „Nähe"-Achse) und die **Streamlit-App** `app/marktchancen.py`
(Segment-Chancen · Chronik · „Für dich" = Fit = Chance × Nähe · konkrete Aufträge je Segment).
**Noch offen:** Make-Gap-Analyse · Firmen-Financials on-demand (T3.2) · Produktions-UI (statt lokalem Streamlit).
**Perspektive: Strategie/C-Level — neue, höherwertige Zielgruppe.**

**Warum das ein Moat ist:** Wettbewerber (Tussell/Stotles/GovWin) liefern Leads &amp; Wettbewerbsanalyse —
aber **kein Produkt macht die Markteintritts-/M&A-Entscheidung** aus Vergabedaten. Das wäre Alleinstellung.

---

## Tier 1 — hoher Hebel, machbar mit unseren Daten (heute / freie API)

| # | Feature / KPI | Mehrwert (Nutzersicht) | Datenbasis (haben wir) | Perspektive | Aufwand | Version |
|---|---------------|------------------------|------------------------|-------------|---------|---------|
| T1.1 | **„Erfolglos/2. Versuch"-Radar** | Ein Verfahren fand beim 1. Mal keinen Bieter → Re-Tender kommt mit **weniger Konkurrenz, besserer Marge, Markteintritts-Chance**. Frühindikator *vor* der Re-Ausschreibung. **Gemessen: 58.660 erfolglose Verfahren, 52 % (30.283) mit erkennbarem Re-Tender.** | `verfahren_status='erfolglos'` (schon gebaut) + Nachfolge-Matching für Re-Tender | Verkäufer | klein-mittel | |
| T1.2 | **Contestedness-Score** (2. Opportunity-Achse) | „Wie umkämpft ist das Feld?" neben „Wie ersetzbar der Amtsinhaber?". **Single-Bidder-Rate 21 %**, ganze Segmente mit Ø 2–3 Bietern (CPV 38/48/73). Zeigt strukturell offene Märkte. | `num_tenders`, single_bidder, Segment-Ø-Bieterzahl | Verkäufer/Markt | klein | |
| T1.3 | **Win-Probability-Score** | „Radar → Prognose": wie wahrscheinlich gewinne *ich*? Höchster wahrgenommener Wert (GovWin-Vorbild). | Verdrängbarkeits-Modell + Nachfolge als Trainingslabel + Fit-Score | Verkäufer | mittel | |
| T1.4 | **Teaming-/Konsortial-Partner-Empfehlung** | „Mit wem solltest du bieten, um X zu verdrängen?" **Echte EU-Marktlücke.** Co-Award-Graph aus Bietergemeinschaften — **die ARGE-Daten sind aus der G-Studie bereits geparst** (115k in_consortium-Gewinner). | in_consortium-Parteien + Firmen-Fähigkeiten (CPV-Footprint) | Partner | mittel | |
| T1.5 | **Buyer-Intelligence-Profil + Peer-Benchmarking** | Vergabefrequenz, Verfahrenspräferenz, Incumbent-Treue, Wettbewerbsintensität, Ø-Vergabedauer. **Öffnet die 2. Zielgruppe: Behörden als Kunden** (Audit-Sicht: hohe Single-Bidder-Rate = Risiko). | `buyer_stats`, `buyer_loyalty`, `avg_decision_days` | Buyer | klein | |
| T1.6 | **Markt-Trend/Forecast** | CPV-Segment-Wachstum + einfache Extrapolation → „welcher Markt wächst?". | Award-Volumen-Zeitreihen 2004–2026 + Deflator | Markt | klein | |
| T1.7 | **AI Bid/No-Bid-Report** | LLM-Kurzgutachten „bieten oder nicht?" über Tender + Fit. Conversion-Feature bei Stotles/Tussell. | Relevanz + Anforderungs-Match + der LLM-Stack (aus Nachfolge vorhanden) | Verkäufer | mittel | |
| T1.8 | **PIN-Frühsignal-Ausbau via DÖE-API** | Vorinformationen als eigene Lead-Kategorie — Signal Monate vor der Ausschreibung. | `build_prospective_leads` (F01) + **DÖE-API** (frei) | Verkäufer | mittel | |

## Tier 2 — freie externe Quelle, gezielt gegen bekannte Lücken

| # | Quelle (frei) | Mehrwert | Schließt | Perspektive | Version |
|---|---------------|----------|----------|-------------|---------|
| T2.1 | **DÖE Open-Data-API** (`oeffentlichevergabe.de`, CC0) | eForms-DE + OCDS inkl. **Eignungskriterien** + PIN. Die saubere TED-Erweiterung. | #2-Zertifikate, #3-Anforderungen, Frühsignale | alle | |
| T2.2 | **GLEIF/LEI** (Bulk, kostenlos) | HR-Nr.-Verifikation + **Konzernhierarchie** + Status | Entity-Lücke (68 % ohne ID), Supplier-Group-Rollup | Wettbewerber | |
| T2.3 | **Wikidata** (SPARQL) | **Umbenennungen/Fusionen** (P1366/P1448) — löst DB Netz→InfraGO *automatisch* | ersetzt manuelle Alias-CSV (E) | — | |
| T2.4 | **Insolvenzbekanntmachungen.de** (Scrape) | **Insolvenz-Signal** → Risiko-Layer | „Incumbent finanziell angeschlagen = leichter verdrängbar" | **Risiko** (neu) | |
| T2.5 | **Haushaltspläne** (OffenerHaushalt) | grobes Budget-Frühsignal je Behörde/Kategorie | Account-Scoring | Markt | |

## Tier 3 — großer Wert, aber teuer/aufwändig (bewusster Entscheid)

| # | Thema | Bewertung | Version |
|---|-------|-----------|---------|
| T3.1 | **Unterschwellen-Markt** (das eigentliche Volumen) | Fragmentiert über 15+ Länder-Portale. Multi-Portal-Scraping *oder* kommerzieller Aggregator (tendigo/patterno). Wandert über Jahre in DÖE-API → **Timing-/Buy-vs-Build-Entscheid**. | |
| T3.2 | **Firmen-Financials on-demand** (Umsatz/Größe/Bonität) | **Button auf der Detailseite** (Sven-Idee): feuert per Klick GLEIF+Insolvenz (frei) sofort, North Data/Creditreform (bezahlt **pro Abruf**) optional. **Umgeht das Bulk-Lizenzproblem**, skaliert mit Nutzern. Ideal für den Start. | |
| T3.3 | **Quote-Level-Preis-Benchmark** | **In der EU nicht sauber machbar** — TED/eForms haben keine Stückpreise. Nur grobe Wert/Menge-Ratios. Nicht als Kernfeature versprechen. | — |

---

## Querschnitt: Preismodell-Basis (Volumen-Bänder für Erfolgsgebühr)

**Gemessene Realität:** Volumen ist zeitpunktabhängig — Live-Ausschreibung **13 %**, Vergabe (Award) **57 %**.
Die Erfolgsgebühr fällt aber **zum Award-Zeitpunkt** an → dort liegt für die Mehrheit ein echter Wert vor.

**Vorschlag `value_band_effektiv` (Gold-Feld):**
- echter Wert wo vorhanden (57 %),
- sonst **Band-Imputation aus CPV-Klassen-Median** (547 Klassen mit ≥20 Werten decken 306k Verträge),
- sonst „unbekannt" → konservatives Default-Band;
- plus `band_source` ∈ {`final`, `imputiert`, `default`} als Ehrlichkeits-Kennzeichnung.

**Gebührenmodelle:** (a) **Fixgebühr je Band** (vorhersehbar) oder (b) **Hybrid** (echter Wert → % gedeckelt,
sonst Fixgebühr je Band). **Rückenwind:** eForms/DÖE erzwingt mehr Wertfelder → Coverage steigt künftig.

---

## Die drei stärksten Einzel-Empfehlungen
1. **DÖE-API integrieren** (T2.1) — kostenlos, sofort, bringt Eignungskriterien + PIN-Frühsignale.
2. **Teaming/Partner-Empfehlung** (T1.4) — EU-Marktlücke, Datengrundlage liegt aus G bereits geparst vor.
3. **Win-Probability-Score** (T1.3) — „Radar → Prognose", baut auf dem Verdrängbarkeits-Modell auf.

## Perspektiven-Abdeckung (Wettbewerber-Benchmark)
Verkäufer ✅ (stark) · Wettbewerber ✅ · **Buyer** ⚠️ (T1.5 öffnet 2. Zielgruppe) · Markt ✅ ·
**Partner** ❌→✅ (T1.4, EU-Lücke) · **Risiko/Financial** ❌→✅ (T2.4/T3.2, Differenzierung).

## Quellen
- DÖE / Bekanntmachungsservice: https://oeffentlichevergabe.de/ui/de/Open-Data-Richtlinie · Swagger: https://oeffentlichevergabe.de/documentation/swagger-ui/opendata/index.html
- GLEIF: https://www.gleif.org/en/lei-data/gleif-golden-copy/download-the-golden-copy · Level-2: https://www.gleif.org/en/lei-data/access-and-use-lei-data/level-2-data-who-owns-whom
- Wikidata: https://query.wikidata.org/ · Insolvenzbekanntmachungen: https://www.insolvenzbekanntmachungen.de/
- North Data: https://www.northdata.com/_data · OffenerHaushalt: https://offenerhaushalt.de/
- Wettbewerber: Tussell, Stotles, GovWin IQ, GovSpend, Mercell, Spend Network (Feature-Vorbilder)
