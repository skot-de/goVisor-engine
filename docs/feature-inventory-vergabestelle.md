# goVisor — Feature-Liste aus Sicht der Vergabestelle

Die Bieter-Feature-Liste, übersetzt auf die **Vergabestelle** (Auftraggeber). Zweck: sehen, was
schon gebaut ist, was teilweise, und wo echte Lücken sind.

> **Korrektur (2026-07-30):** Eine frühere Fassung führte die Vergabestellen-Sicht zu pessimistisch.
> Tatsächlich existiert ein **gebauter Vergabestellen-MVP: der „Vergabeblick"** (`VergabeblickView.tsx`,
> Route `/authority`, in Produktion rollen-gegatet, Rollen-Umschalter Anbieter↔Vergabestelle). Diese
> Fassung ist am aktuellen Code verifiziert.

**Status:** ✅ gebaut & verifiziert · 🟡 gebaut, aber auf Demo-/Aggregatdaten bzw. dünn · ⚪ Stub/offen ·
❌ echte Lücke (nicht gebaut).

---

## Der Vergabeblick — der gebaute Vergabestellen-MVP (5 Sektionen)

| Sektion | Leitfrage | Inhalt | Status |
|---|---|---|---|
| **Dashboard** | „Wie steht meine Stelle da?" | KPI-Kacheln: Vergaben/36 Mon, **Ø Bieterzahl** (< 2,5 = rote Ein-Bieter-Warnung), KMU-Anteil, nur-Preis-Quote, Wechselquote, Neuzugänge, Top-5-Anbieter. Fallzahl-Schwellen, „Teilbild"-Badge bei fragmentierten Stellen. | ✅ |
| **Markterkundung** | „Wen erreiche ich?" | A.1 Anbieter-Landschaft („bei Ihnen"-Markierung), A.2 Wettbewerbsdichte-Ampel je Feld (Median-Bieterzahl), A.4 Vitalität („X % gewinnt wieder derselbe" vs. Branchen-Median). | ✅ |
| **Zuschnitt** *(= Ausschreibungscheck)* | „Wie bekomme ich mehr Bieter?" | Der Kern — siehe Detail unten. | ✅ |
| **Controlling** | „Habe ich gut vergeben?" | C.1/C.3 Comps-Tabelle „Sie vs. vergleichbare Stellen" + Benchmark Ø Bieterzahl & Volumen gegen Median. | ✅ |
| **Pflichten** | „KMU, Preis vs. Qualität" | D.1 KMU-Benchmark, D.2 Preis-vs-Qualität-Benchmark (Nachhaltigkeit bewusst verworfen — Datenlage 0–1,2 %). | ✅ |
| *(quer)* **Ihre nächsten Auslauftermine** | Wiedervorlage | Eigene bald auslaufende Verträge → rechtzeitig neu ausschreiben. | ✅ |
| *(quer)* **Onboarding-Picker** | Stelle wählen | Eigene Vergabestelle suchen/wählen, mit ehrlichem „Teilbild"-Badge. | 🟡 (kein echter Auth-Rückfluss) |

### Der Ausschreibungscheck im Detail (Sektion „Zuschnitt", B.1 + B.2) — das verkaufbare Kernstück
**Eingabe (Entwurf):** Feld (CPV) · Lose · Mindestumsatz · Auftragswert · ☐ Bürgschaft · ☐ nur Preis.
**→ Marktgestützte Hinweise** (Ampel risk/warn/ok, aus echten vergleichbaren Verfahren):

| Prüfung | Logik | Status |
|---|---|---|
| **Ein-Bieter-Gefahr** | Feld-Median-Bieterzahl < 2,5 → „erreichen im Median nur N Bieter" | ✅ |
| **1-Los-Warnung** | 1 Los → „Aufteilung öffnet für kleinere Anbieter; kleinstes vergleichbares Los ~X €" | ✅ |
| **Bürgschaft-Effekt** | „schließt kleinere/regionale Anbieter aus" | ✅ |
| **Nur-Preis-Warnung** | „schreckt spezialisierte Anbieter ab" | ✅ |
| **Wertplausibilität** (#20) | Wert vs. gemessenes Wertband des Feldes → „unter → Aufhebungsrisiko" (nur Band, Fallzahl, < 8 = dünn) | ✅ |
| **Eignungs-Angemessenheit** (#21) | Mindestumsatz → „X von N Anbietern erreichen vergleichbares Volumen" (Volumen-Proxy), < 40 % → warn | ✅ |
| **Bieterzahl-Prognose** (B.2) | Feld-Median als gemessene Basis + **direktionale Deltas** (Lose+ öffnet, Bürgschaft/Umsatz/Preis verengt). „Richtwert, kein Versprechen" | 🟡 (direktional, **nicht pro Konfiguration gemessen**) |
| **Summary** | „N Hinweise, die Ihre Bieterzahl senken" / „wettbewerbsoffen" | ✅ |

---

## Übersetzung der Bieter-Bereiche → Vergabestelle (mit korrektem Status)

### 1. Bedarf & Planung
| Feature | Vergabestellen-Nutzen | Status |
|---|---|---|
| Wiedervorlage eigener Verträge | eigene Auslauftermine (im Vergabeblick) | ✅ |
| Vergleichsverfahren finden | Volltextsuche/CPV — als Anbieter-Route da, Vergabestellen-Einbettung dünn | 🟡 |
| Kostenschätzung fürs Verfahren | Wertplausibilität im Ausschreibungscheck (Band-Vergleich) | ✅ |

### 2. Markterkundung
| Feature | Vergabestellen-Nutzen | Status |
|---|---|---|
| Anbieterlandschaft je Segment | Markterkundung A.1/A.2 (Anbieter + Wettbewerbsdichte-Ampel) | ✅ |
| Marktkonzentration/Abhängigkeit | Struktur (fragmentiert/oligopol) in den Aggregaten | 🟡 (Ampel da, Struktur-Achse dünn im UI) |
| Marktdialog-Kandidaten | „Aktive Anbieter in Ihrem Markt" (Liste) | 🟡 (Liste, kein Ansprech-Workflow) |
| **Bieterzahl-Prognose** | im Ausschreibungscheck (B.2) — **war fälschlich als Lücke geführt** | 🟡 (direktionaler Richtwert) |

### 3. Verfahrensgestaltung
| Feature | Vergabestellen-Nutzen | Status |
|---|---|---|
| Single-Bidder-/Erfolglos-Risiko | Kern des Ausschreibungschecks (Feld-Median-Ampel) | ✅ |
| Eignungskriterien-Kalibrierung | Eignungs-Angemessenheit (#21, Umsatz-Proxy) | ✅ (Proxy) — voller Nachweis-Katalog aus Doku-Korpus offen |
| Los-Zuschnitt-Empfehlung | 1-Los-Warnung + Deltas | ✅ (direktional) |
| Zuschlagskriterien-Benchmark | Preis-vs-Qualität (Pflichten D.2); Gewichts-Benchmark aus Doku offen | 🟡 |

### 4. Vergabeunterlagen — erstellen statt analysieren
| Feature | Vergabestellen-Nutzen | Status |
|---|---|---|
| Unterlagen-Baukasten (Generator) | Standardformular-Kern aus der Struktur-Studie | ❌ (Datenbasis entsteht gerade) |
| Vollständigkeits-/Konsistenz-Check | Doku-Pipeline als QS rückwärts | ❌ (Pipeline da, kein Check-UI) |
| Kriterienkatalog-Generator | aus Zuschlags-/Eignungs-Mustern | ❌ |

### 5. Bieter prüfen (Due Diligence)
| Feature | Vergabestellen-Nutzen | Status |
|---|---|---|
| Bieter-Dossier (voll) | „Stärkste/aktive Anbieter" listet — kein Klick-zum-Voll-Dossier je Firma | 🟡 (Daten da, Dossier-UI fehlt) |
| Referenz-Plausibilisierung | Gewinner-Historie je Firma vorhanden | 🟡 |
| Konsortial-Durchleuchtung | bewusst offen (s. CLAUDE.md) | ❌ (bewusst) |
| Bieterfragen als Frühindikator | Fragenzahl vor Zuschlag als „hier ist was los" (feasibility-geprüft) | ❌ (machbar, nicht gebaut) |

### 6. Zuschlag & Lebenszyklus
| Feature | Vergabestellen-Nutzen | Status |
|---|---|---|
| Incumbent-Bindungs-Warnung | Wechselquote/Vitalität im Dashboard/Markterkundung | ✅ |
| Vertrags-Wiedervorlage | Auslauftermine im Vergabeblick | ✅ |
| Eigene Vergabe-Vorschau (C.4) | pro-Buyer-Pipeline vorausschauend | 🟡 (Auslauftermine ja, volle Vorschau offen) |

### 7. Benchmarking & Reporting
| Feature | Vergabestellen-Nutzen | Status |
|---|---|---|
| Vergabestellen-Dashboard | Vergabeblick-Dashboard | ✅ |
| Peer-Vergleich (Comps) | Controlling C.1/C.3 | ✅ |
| Fragmentierungs-Ehrlichkeit | „Teilbild"-Badge | ✅ |
| Vergabestatistik/Report-Export | strukturierter Report/Export für Berichtspflichten | ❌ |

### 8. Querschnitt
| Bereich | Status |
|---|---|
| Datenfundament, Suche, Ehrlichkeit/Herkunft | ✅ (seitenneutral) |
| **Rollen-Umschalter Anbieter↔Vergabestelle** | ✅ (`/leads` ↔ `/authority`) |
| Käufer-Auth-Gate + echtes Onboarding-Rückfluss | ⚪ (Gate-Gerüst, kein Server-Rückfluss) |
| Alerts/Kalender (Wiedervorlage) | 🟡/⚪ |

---

## Ehrliches Fazit — was WIRKLICH noch fehlt
Der Vergabeblick-MVP inkl. **Ausschreibungscheck ist gebaut und verkaufbar**. Die verbleibenden echten Lücken:

1. **Bieterzahl-Prognose härten** — aktuell direktionaler Richtwert (Feld-Median + Erfahrungs-Deltas). Für ein belastbares Versprechen bräuchte es **pro-Konfiguration gemessene Deltas** (Los/Bürgschaft/Umsatz → Bieterzahl, kausal aus den Daten). *Das* ist der wertvollste Ausbau.
2. **Käufer-Konto** — echter Auth-Gate (profile_type) + Server-Persistenz des Vergabestellen-Profils und der Entwürfe. Aktuell Read-Views ohne Rückfluss.
3. **Unterlagen-Generierung** (Baukasten/Kriterienkatalog/Vollständigkeits-Check) — die Umkehrung der Bieter-Analyse. Reift mit dem wachsenden Unterlagen-Korpus.
4. **Bieter-Dossier-UI + Vergabestatistik-Export** — Daten liegen, UI/Report-Layer fehlt.

## Landingpage-tauglich (🟢) für die Vergabestellen-Zielgruppe
- **Ausschreibungscheck**: „Prüfen Sie Ihren Entwurf, bevor Sie ausschreiben — vermeiden Sie die Ein-Bieter-Falle." (Kernstück)
- **Vergabeblick-Dashboard + Peer-Vergleich**: „Wie schreibe ich aus — im Vergleich zu ähnlichen Stellen?"
- **Markterkundung**: „Wen erreiche ich in meinem Segment?"
- **Wiedervorlage**: „Kein auslaufender Vertrag mehr übersehen."
