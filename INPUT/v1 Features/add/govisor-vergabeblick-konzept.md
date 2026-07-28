# goVisor Vergabeblick — Vollständiges Konzept (Vergabestellen-Seite)

**Version:** 1.1
**Stand:** 2026-07-27
**Zweck:** Bau-fertiges Konzept für die Vergabestellen-Plattform. Daten & Logik existieren — dieses Dokument spezifiziert Frontend, Sektionen, Datenbezüge und Grenzen so, dass Claude Code nur noch das Frontend bauen muss.
**Zielgruppe des Dokuments:** Claude Code (Umsetzung) + Product Owner (Entscheidung)
**Changelog:** 1.0 Erstfassung · 1.1 Inventar-Check D.2 — Nachhaltigkeit verworfen (Daten 0–1,2 %, StrategicProcurement=Fahrzeugpflicht), ersetzt durch Preis-vs-Qualität-Benchmark aus `preisquote`

---

## 0. Ausgangslage — was schon da ist

Die Käuferseite ist **kein Datenprojekt, sondern ein Frontend-Projekt**. Der Implementierungsstand belegt: Datenkern und Aggregate sind rollen-agnostisch gebaut (`relevance(entität, ausschreibung)`), und die entscheidenden Käufer-Aggregate existieren bereits:

| Vorhanden | Trägt |
|---|---|
| `agg_buyer_profile` (pro Vergabestelle, 36M rollierend) | fast die ganze Käufer-Marktsicht |
| `agg_buyer_supplier` (bipartite Matrix) | Anbieter-Landschaft je Stelle |
| `agg_supplier_profile` | Anbieter-Detail (Zuverlässigkeit, Trend) |
| `contractor_stats`, `market_opportunity` (511 Segmente) | Wettbewerbsdichte, Marktlücken |
| `retender_signal`, `head_to_head`, `incumbent_tenure` | Markt-Vitalität, Aufhebungen |
| `lead_duration`, `value_band_effektiv` | Vergabe-Vorschau, Wertplausibilität |
| `entity_identity` (302k), `dim_company_group` | belastbare Anbieter-Auflösung |
| `strategie.json` (vorberechnet je Branche) | Muster für käuferseitige Aggregat-Views |

**Konsequenz:** Was fehlt, sind (a) das Frontend, (b) einige käuferseitige Aggregat-Views, die dieselben Rohtabellen anders schneiden, (c) die Erhebungs-Features für den Käufer-Moat (Abschnitt 8).

---

## 1. Produktname & Positionierung

**Arbeitsname: „Vergabeblick"** — der Blick der Vergabestelle auf ihren eigenen Markt.

Positionierung in einem Satz:
> Vergabeblick zeigt der Vergabestelle *vor* der Ausschreibung, wen sie erreicht, *während* des Zuschnitts, wie sie mehr Bieter bekommt, und *nach* der Vergabe, ob sie gut vergeben hat.

**Abgrenzung (kritisch):** Vergabeblick ist **kein Vergabemanagement-System**. Es erstellt keine Ausschreibung, führt keine Vergabeakte, ersetzt cosinex/AI nicht. Es ist die **Marktintelligenz vor und um den Prozess** — die Schicht, die den Vergabemanagement-Systemen fehlt.

---

## 2. Das Leitproblem: Ein-Bieter-Verfahren

Der gesamte Aufbau kreist um den größten Schmerz der Vergabestelle:

> **In vier von zehn Verfahren gibt am Ende nur ein Bieter ab.**

Das ist gesetzlich flankiert (Wettbewerbsgebot § 97 GWB), teuer (schlechtere Angebote, Aufhebungen) und peinlich. goVisor hat als einziges die Daten, es *vorher* zu verhindern. **Das Ein-Bieter-Frühwarnsystem ist der Kern, nicht ein Feature unter vielen.** Alle drei Bereiche zahlen darauf ein.

---

## 3. Struktur: drei Bereiche entlang des Zyklus

```
  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
  │  MARKTERKUNDUNG │   │  ZUSCHNITT      │   │  CONTROLLING    │
  │  (PRE)          │──▶│  (DURING)       │──▶│  (POST)         │
  │                 │   │                 │   │                 │
  │  Wen erreiche   │   │  Wie bekomme    │   │  Habe ich gut   │
  │  ich?           │   │  ich mehr       │   │  vergeben?      │
  │                 │   │  Bieter?        │   │                 │
  └─────────────────┘   └─────────────────┘   └─────────────────┘
```

Dazu ein übergreifender Bereich **Pflichten & Nachhaltigkeit** (rechtlich getrieben) und das **Dashboard** als Einstieg.

---

## 4. Sektion für Sektion (Frontend-Spezifikation)

Jede Sektion: Zweck, Datenquelle (exakt), Darstellung, Gate. Alle Werte tragen die bestehende Herkunfts-Grammatik (gemessen/geschätzt/unbekannt).

### 4.0 Dashboard (Einstieg)

**Zweck:** Sofort-Orientierung: Wie steht meine Stelle da?
**Datenquelle:** `agg_buyer_profile` für die eigene `buyer_entity_id`.
**Darstellung:** Kennzahlen-Kacheln:
- Vergaben letzte 36M (`vergaben_36m`)
- Ø Bieter je Verfahren (`bieter_median`) — **rot, wenn < 2,5** (Ein-Bieter-Warnung)
- Aufhebungsquote (`aufhebungsquote`)
- KMU-Anteil (`kmu_anteil`) — Pflicht-Kontext
- Konzentration Top-Anbieter (`konzentration_top1`)

**Gate:** Einstieg (Teil des kostenlosen Erst-Einblicks, siehe §7).

---

### BEREICH A — MARKTERKUNDUNG (PRE)

#### A.1 Anbieter-Landschaft
**Zweck:** Wer sind die aktiven Anbieter in meinem Beschaffungsfeld?
**Datenquelle:** `agg_buyer_supplier` (für eigene Stelle) + `agg_supplier_profile`.
**Darstellung:** Rangliste der Anbieter je CPV-Bündel: Zuschläge, Marktanteil bei mir vs. Marktdurchschnitt (`ueberperformance`), Trend. Netzwerk-Graph optional.
**Gate:** Pro.

#### A.2 Wettbewerbsdichte
**Zweck:** Wie umkämpft ist mein Feld? Habe ich echten Wettbewerb oder einen festgefahrenen Markt?
**Datenquelle:** `market_opportunity` (511 Segmente), `contractor_stats`, `agg_buyer_profile.neuzugang_pro_jahr`.
**Darstellung:** Ampel je CPV+Region: viele aktive Anbieter (grün) / wenige (gelb) / faktisches Monopol (rot). Zahl der aktiven Anbieter, Neuzugangsrate.
**Gate:** Pro.

#### A.3 Anbieter-Verfügbarkeit (Ein-Bieter-Frühwarnung, Teil 1)
**Zweck:** Gibt es für das, was ich plane, überhaupt genug Anbieter?
**Datenquelle:** `market_opportunity` + `contractor_stats` gefiltert auf geplantes CPV+Region+Größenordnung.
**Darstellung:** „In deinem Zielsegment sind X aktive Anbieter. Bei vergleichbaren Verfahren boten im Median Y." Warnung bei dünnem Markt.
**Gate:** Pro. **Kernstück des Frühwarnsystems.**

#### A.4 Markt-Vitalität
**Zweck:** Ist mein Markt festgefahren (immer derselbe Gewinner)?
**Datenquelle:** `agg_buyer_profile.wechselquote`, `konzentration_top1`, `incumbent_tenure`.
**Darstellung:** „Bei dir gewinnt zu X % derselbe Anbieter. Marktüblich sind Y %." Hoher Wert = festgefahren = Handlungsbedarf.
**Gate:** Pro.

---

### BEREICH B — ZUSCHNITT (DURING)

#### B.1 Ausschreibungscheck (das Kernprodukt & der Einstieg)
**Zweck:** Prüft einen Ausschreibungs-Entwurf gegen die Marktdaten, gibt Optimierungsvorschläge.
**Ablauf:** Stelle skizziert/lädt Eckdaten (CPV, Region, Volumen, Bürgschaft, Losstruktur, Kriterien, Fristen) → Vergabeblick prüft → Hinweise + Analysedokument → Stelle arbeitet in ihrem eigenen Tool weiter.
**Datenquelle:** `agg_buyer_profile` (Vergleichswerte marktüblich) + `market_opportunity` + `value_band_effektiv`.
**Darstellung — konkrete Hinweise:**
- „Deine Bürgschaft von €X schließt Y % der regionalen Anbieter aus" (aus `buergschaft_quote` + Anbieter-Größen)
- „Vergleichbare Aufträge hatten Z Lose, deins hat 1 — das reduziert die Bieterzahl" (aus `lose_median`)
- „Stellen wie du erreichen mit dieser Konstellation im Median N Bieter" (aus `bieter_median` vergleichbarer Stellen)
- „Dein geschätzter Wert liegt A % über vergleichbaren Zuschlägen — Aufhebungsrisiko" (aus `value_band_effektiv`)
**Gate:** Einzel-Check (💶 einmalig, Türöffner) ODER im Pro-Abo unbegrenzt.

#### B.2 Zuschnitt-Optimierung (Ein-Bieter-Frühwarnung, Teil 2)
**Zweck:** Aktives Werkzeug: „andere Losstruktur = mehr Bieter".
**Datenquelle:** `agg_buyer_profile` (Bieterzahl je Zuschnitt-Muster) + Simulation.
**Darstellung:** Regler für Losgröße/Bürgschaft/Frist/Eignung → Prognose der erreichten Bieterzahl. „Mit 3 statt 1 Los: Median 6 statt 3 Bieter."
**Gate:** Pro. **Kernstück des Frühwarnsystems.**

#### B.3 CPV- & Verschlagwortungs-Hilfe
**Zweck:** Richtige Codes, damit die passenden Bieter das Verfahren finden.
**Datenquelle:** `cpv_adjacency` + `market_opportunity`.
**Darstellung:** „Für das, was du beschreibst, nutzen vergleichbare Stellen diese CPV-Codes."
**Gate:** Pro.

---

### BEREICH C — CONTROLLING (POST)

#### C.1 Vergabe-Güte ⚖️
**Zweck:** Habe ich marktüblich vergeben?
**Datenquelle:** eigene Vergabehistorie (`agg_buyer_supplier`) vs. `agg_buyer_profile` vergleichbarer Stellen.
**Darstellung:** „Du zahltest für vergleichbare Aufträge im Median €X, ähnliche Stellen €Y." Nur aggregiert, nie Wertung.
**Gate:** Pro. **⚖️ faktisch-aggregiert, kein Anbieter-Ranking.**

#### C.2 Auftragnehmer-Beobachtung ⚖️
**Zweck:** Ist mein Auftragnehmer verlässlich?
**Datenquelle:** `agg_supplier_profile` (Trend, laufende Verträge) + `retender_signal` (vorzeitige Neuausschreibungen).
**Darstellung:** Faktisch: „Verträge dieses Anbieters wurden zu X % vorzeitig neu ausgeschrieben" — **nie** „unzuverlässig". Aggregierte Feld-Quote, kein Einzelurteil.
**Gate:** Pro. **⚖️ schärfste rechtliche Grenze — nur Fakten, ab Mindestzahl.**

#### C.3 Vergleichbare Vergaben (Comps)
**Zweck:** Wie haben andere ähnliche Aufträge zugeschnitten?
**Datenquelle:** `agg_buyer_profile` + `lead_detail` vergleichbarer Vergaben.
**Darstellung:** Verteilung: Zuschlagswert, Bieterzahl, Losstruktur, Laufzeit ähnlicher Fälle. Keine Punktschätzung, Verteilung.
**Gate:** Pro.

#### C.4 Eigene Vergabe-Vorschau
**Zweck:** Welche meiner Verträge laufen bald aus?
**Datenquelle:** `lead_duration` gefiltert auf eigene `buyer_entity_id`.
**Darstellung:** Zeitachse eigener Auslauftermine → Planungshilfe für kommende Verfahren.
**Gate:** Pro.

---

### BEREICH D — PFLICHTEN & NACHHALTIGKEIT (übergreifend)

Rechtlich getrieben — dockt an Zwang an, nicht an Kür. Strategisch wertvoll, weil Behörden leichter kaufen, was Pflichterfüllung erleichtert.

#### D.1 KMU-Förderung ⚖️
**Zweck:** § 97 GWB — Losaufteilung zur Mittelstandsförderung.
**Datenquelle:** `agg_buyer_profile.kmu_anteil`, `kmu_n`, `lose_median`.
**Darstellung:** „Deine Verfahren erreichen X % KMU, vergleichbare Stellen Y %." Andockpunkt an die Begründungspflicht bei Nicht-Losaufteilung.
**Gate:** Pro.

#### D.2 Preis-vs-Qualität-Benchmark (statt Nachhaltigkeit)
**Zweck:** Wie stark vergebe ich rein über den Preis — im Vergleich zu ähnlichen Stellen?
**Datenbefund (Inventar-Check 2026-07-27):** Ein echter Nachhaltigkeits-Benchmark **trägt nicht**. Die realen Nachhaltigkeitsfelder (`ENVIRONMENTAL_PROTECTION`, `SOCIAL_STANDARDS`) liegen bei 0–1,2 %. Der scheinbar starke Marker `StrategicProcurement` (52 %) ist eine Falle: Sein Wert ist durchgängig `cvd-scope` = Clean Vehicles Directive, also nur das Fahrzeug-Pflicht-Flag, **nicht** allgemeine Nachhaltigkeit. Ein Nachhaltigkeits-Benchmark daraus wäre falsche Präzision — verstößt gegen das Ehrlichkeitsprinzip.
**Tragfähiger Ersatz:** `agg_buyer_profile.preisquote` (`AC_AWARD_CRIT = 'lowest price'`, 100 % in Legacy / `AwardingCriterionTypeCode` 42,7 % in eForms).
**Darstellung:** „Du vergibst zu X % rein über den niedrigsten Preis, vergleichbare Stellen zu Y %." Dockt an den politischen Nerv an (reine Preisvergabe ist genau die Kritik der Nachhaltigkeitsdebatte), ohne Nachhaltigkeit vorzutäuschen.
**Gate:** Pro. **Ehrlich als Preis-Benchmark benannt, nicht als Nachhaltigkeit.**

**Echte Nachhaltigkeit** kann später ergänzt werden, wenn/falls die eForms-Datenlage besser wird — heute nicht baubar, ehrlich so kommuniziert.

---

## 5. Datenbezugs-Tabelle (für Claude Code)

Jede Sektion → exakte Quelltabelle. Alles vorhanden außer explizit markiert.

| Sektion | Primärquelle | Status |
|---|---|---|
| Dashboard | `agg_buyer_profile` (eigene ID) | ✅ vorhanden |
| A.1 Anbieter-Landschaft | `agg_buyer_supplier` + `agg_supplier_profile` | ✅ |
| A.2 Wettbewerbsdichte | `market_opportunity`, `contractor_stats` | ✅ |
| A.3 Anbieter-Verfügbarkeit | `market_opportunity` + `contractor_stats` | ✅ |
| A.4 Markt-Vitalität | `agg_buyer_profile` (wechselquote, konzentration) | ✅ |
| B.1 Ausschreibungscheck | `agg_buyer_profile` + `value_band_effektiv` | ✅ Daten, Check-Logik neu |
| B.2 Zuschnitt-Optimierung | `agg_buyer_profile` + Simulationslogik | ✅ Daten, Sim neu |
| B.3 CPV-Hilfe | `cpv_adjacency` | ✅ |
| C.1 Vergabe-Güte | `agg_buyer_supplier` vs. Vergleich | ✅ |
| C.2 Auftragnehmer-Beobachtung | `agg_supplier_profile` + `retender_signal` | ✅ |
| C.3 Comps | `agg_buyer_profile` + `lead_detail` | ✅ |
| C.4 Vergabe-Vorschau | `lead_duration` (eigene ID) | ✅ |
| D.1 KMU-Förderung | `agg_buyer_profile.kmu_anteil` | ✅ |
| D.2 Preis-vs-Qualität | `agg_buyer_profile.preisquote` | ✅ (Nachhaltigkeit verworfen, s.u.) |

Neu zu bauen ist praktisch nur die **Check-/Simulationslogik** (B.1, B.2) — der Rest ist Read-Views auf vorhandene Aggregate.

**Inventar-Befund D.2 (2026-07-27):** Echter Nachhaltigkeits-Benchmark verworfen — reale Felder 0–1,2 %, der 52%-Marker `StrategicProcurement` ist nur die Clean-Vehicles-Fahrzeugpflicht. Ersetzt durch ehrlichen Preis-vs-Qualität-Benchmark aus `preisquote`.

---

## 6. Die eigene Identität der Vergabestelle

Damit eine Stelle „ihre" Daten sieht, muss sie sich mit ihrer `buyer_entity_id` verknüpfen — analog zum Anbieter-Onboarding („Das bin ich").

**Onboarding-Flow:**
1. Stelle sucht ihren Namen → `entity_identity`-Match (Käufer-Seite)
2. Bestätigt „Das ist meine Stelle"
3. Sieht ab sofort Dashboard + eigene Daten

Die Bestätigung fließt (wie bei Anbietern) zentral in den Entity-Graph zurück — crowdgesourcte Käufer-Disambiguierung.

**Architektur:** `profile_type = 'contracting_authority'` (bereits im Schema, Migration 0004). Die Sicht-Steuerung liest `profile_type`, der Datenzugriff bleibt rollen-agnostisch.

---

## 7. Preismodell Vergabeblick

| Stufe | Inhalt | Preis |
|---|---|---|
| **Kostenloser Erst-Einblick** | Dashboard + eine Markterkundungs-Kennzahl (Türöffner, einmalig) | 0 € |
| **Einzel-Ausschreibungscheck** | Ein Entwurf geprüft + Analysedokument | 💶 pro Vorgang |
| **Pro-Abo** | Alle Sektionen, unbegrenzte Checks, laufende Marktsicht | Abo/Monat |

**Kein klassisches Freemium** (kein Dauer-Gratis) — Behörden kaufen vorgangsgebunden, der Erst-Einblick ist Türöffner, nicht Dauerzustand. **Keine Erfolgsprämie** — die Stelle gewinnt nicht, sie plant.

---

## 8. Der Käufer-Moat (Erhebung — parallel zum Bieter-Graben)

Was Vergabeblick die Stelle fragt, um einen Datengraben zu bauen. Vier Tiers, nach demselben Test wie bei den Bietern (exklusiv, skalierend, sofort nützlich).

### Tier 1 — Verfahrensergebnis (der eigentliche Käufer-Graben)
Die Stelle weiß, was TED nicht zeigt: **wie viele Angebote kamen wirklich, warum wurden welche ausgeschlossen.** Gemeldet im Gegenzug fürs eigene Controlling. Schließt den Bieter-Graben von oben: Bieter melden „ich bot & verlor", Stellen melden „5 Bieter, 2 ausgeschlossen" — **dieselbe Vergabe, zwei Seiten, die sich validieren.**

### Tier 2 — Planungsabsicht (hochexklusiv, hochsensibel)
Was die Stelle plant, bevor sie es veröffentlicht (aus dem Ausschreibungscheck). Löst das PIN-Problem (offizielle Vorinfos < 1,1 %). **Kritische Grenze:** NIE an Bieter durchreichen. Nur aggregierter, anonymer Frühindikator („in diesem Feld bahnt sich Nachfrage an"), nie „Behörde X plant Y". Bricht dieses Vertrauen, ist der Käufer-Moat tot.

### Tier 3 — Leistungshistorie ⚖️
Urteil der Stelle über den Auftragnehmer nach Vertragsende (lief ab / vorzeitig beendet). Nur harte Fakten, aggregiert, ab Mindestzahl. **NIE** subjektive Bewertung eines benannten Anbieters (Diskriminierungsverbot).

### Tier 4 — Nutzungssignale (kostenlos)
Was die Stelle im Check durchspielt, welche Warnungen sie ignoriert. Verbessert den Check, skaliert automatisch.

**Gesamteinordnung:** Der Käufer-Moat ist schwächer in der Menge (wenige Stellen, vorsichtig), aber stärker in der **Verbindung**: Der zweiseitige Datengraph — goVisor kennt als einziges beide Seiten derselben Verfahren — ist der eigentliche uneinholbare Graben.

---

## 9. Rechtliche Leitplanken (bindend)

| Grenze | Regel |
|---|---|
| **Neutralität** | Vergabeblick berät vor/nach dem Verfahren, nie *im* laufenden Verfahren |
| **Planungsvertraulichkeit** | Geplante Ausschreibungen NIE an Bieter durchreichen — nur aggregiert/anonym |
| **Kein Anbieter-Abwerten** | Auftragnehmer-Daten nur faktisch-aggregiert (⚖️-Sektionen), nie Wertung/Sperrliste |
| **Kein Prozess-Eingriff** | Vergabeblick erstellt keine Ausschreibung, ersetzt kein Vergabemanagement-System |
| **Kartellrecht** | Bedarfsbündelung (falls gebaut) nur mit Vorsicht — gemeinsame Vergabe kann heikel sein |

---

## 10. Bau-Reihenfolge (Empfehlung für Claude Code)

| Schritt | Inhalt | Warum |
|---|---|---|
| 1 | Käufer-Onboarding + `profile_type`-Weiche + Dashboard | Fundament, nutzt vorhandene Aggregate |
| 2 | Bereich A (Markterkundung) — Read-Views | Reine Anzeige vorhandener Daten, schnell |
| 3 | B.1 Ausschreibungscheck (Einstieg + Einzelkauf) | Das verkaufbare Kernprodukt |
| 4 | Bereich C (Controlling) — Read-Views | Vorhandene Daten, ⚖️ beachten |
| 5 | B.2 Zuschnitt-Optimierung (Simulation) | Der Frühwarn-Kern, etwas mehr Logik |
| 6 | Bereich D (Pflichten) | KMU sofort, Nachhaltigkeit nach Inventar-Check |
| 7 | Moat-Erhebung (Tier 1–4) | Nachdem die Sicht steht |

Schritt 1–3 ergeben ein verkaufbares Minimalprodukt: Dashboard + Markterkundung + Ausschreibungscheck.

---

## 11. Was Claude Code NICHT tun muss

- Keine neuen Rohdaten-Pipelines — alles liegt im Gold-Layer.
- Kein neuer Datenkern — `relevance(entität, ausschreibung)` ist rollen-agnostisch da.
- Keine Bieter-Features anfassen — getrennte Sicht über `profile_type`.
- Nur: Read-Views auf vorhandene Aggregate + Check-/Simulationslogik (B.1/B.2) + Frontend im Bestandsdesign (`labels.js`-Katalog, zweite Sprache = zweiter Katalog).

---

## 12. Offene Entscheidungen (Product Owner)

| # | Frage | Empfehlung |
|---|---|---|
| 1 | Name „Vergabeblick"? | sachlich, käuferseitig — ja, oder Alternative wählen |
| 2 | Preis Einzel-Check | Business-Entscheidung, ~490 € als Startwert im Modell |
| 3 | Preis Pro-Abo Käuferseite | wenn Frontend steht |
| 4 | Nachhaltigkeitsdaten: bauen? | **geprüft — verworfen.** Daten tragen nicht (0–1,2 %). Stattdessen Preis-vs-Qualität-Benchmark (D.2) |
| 5 | Tier-1-Erhebung (Verfahrensergebnis) ab wann? | nach dem Minimalprodukt |
| 6 | Bedarfsbündelung: bauen? | kartellrechtlich zuerst prüfen — im Zweifel weglassen |

---

## Zusammenfassung

Vergabeblick ist die gespiegelte Plattform für die Kaufseite, gebaut auf demselben Datenkern und denselben Aggregaten wie die Anbieterseite — insbesondere `agg_buyer_profile`, das fast die gesamte Marktsicht bereits trägt. Der Aufbau folgt dem Zyklus (Markterkundung → Zuschnitt → Controlling) und kreist um das Ein-Bieter-Frühwarnsystem als Kern. Für Claude Code bleibt fast ausschließlich Frontend-Arbeit plus die Check-/Simulationslogik; alle Marktdaten sind vorhanden. Der eigentliche strategische Gewinn ist der zweiseitige Datengraph: goVisor kennt als einziges beide Seiten derselben Verfahren — der uneinholbare Moat.
