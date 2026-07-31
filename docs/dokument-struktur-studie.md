# Vergabeunterlagen — Struktur-Studie (Q1–Q7)

Basis: **300 Vorgänge** mit login-frei geladenen Unterlagen (241 mit brauchbarem Volltext),
~6.000 Dateien, 105 Mio. Zeichen.
Branchen: Bau 107 · Beratung 50 · Medizin 37 · IT 18 · Energie 13\* · Sicherheit 7\* · (?) 5.
\* n<20 = **Indiz, keine Statistik**. Rohdaten: `data/docs/study/q1…q6.csv` + `q1b_aehnlichkeit.csv`.

> **Status: vollständig.** Q1–Q7 gemessen. Q1b (Inhaltsähnlichkeit) mit dem richtigen Verfahren
> nachgemessen (Volltext-Shingles statt Deckblatt) — Ergebnis unten, es **widerlegt die
> Standardformular-These**.

---

## Q2 — Paketgröße & Parsbarkeit *(Kostenmodell)*

| Metrik | Median | p75 | Max |
|---|---:|---:|---:|
| Dateien / Vorgang | 20 | 33 | 196 |
| PDF-Seiten / Vorgang | 90 | 176 | 2.883 |
| Größe (MB) | 6,1 | 20,8 | 557 |
| **LLM-Tokens / Vorgang** (Zeichen/4) | **61.000** | **128.000** | **1,55 Mio** |

- **OCR ist ein Nicht-Problem:** nur **3 %** der PDFs sind reine Bilder (1 % der Seiten); 21 % der
  Vorgänge haben ≥1 Scan-PDF, im Schnitt vernachlässigbar. → Kein eigener OCR-Kostenblock.
- **Kosten stark rechtsschief:** Median ~2 Cent/Analyse (Flash), aber der Schwanz explodiert
  (Max ~0,50 €). Ein Median-Paket hat 90 Seiten / 244k Zeichen — **das ganze Paket ins LLM zu
  schicken ist teuer und meist unnötig.** Gezielte Doku-Auswahl (Q4/Q6) ist der Kostenhebel.

## Q3 — Dokumentklassen & Klassifizierbarkeit

- **69 %** aller Dateien sind **allein aus dem Dateinamen** klassifizierbar (4.110/5.960);
  31 % („sonstiges") brauchen einen Inhaltsblick.
- Anteil der **Vorgänge** je Dokumenttyp, nach Branche (%):

| Doctype | Bau | Berat | Med | IT | Energ\* | Sich\* |
|---|---:|---:|---:|---:|---:|---:|
| Aufforderung | 87 | 92 | 97 | 94 | 100 | 100 |
| Bewerbungsbedingungen | 41 | 48 | 8 | 83 | 61 | 71 |
| Leistungsbeschreibung | 89 | 88 | 43 | 100 | 92 | 100 |
| Vertrag | 79 | 92 | 29 | 100 | 84 | 100 |
| Eignung | 45 | 70 | 21 | 66 | 69 | 28 |
| Eigenerklärung | 58 | 80 | 78 | 72 | 76 | 100 |
| Formblatt | 45 | 34 | 18 | 11 | 30 | 0 |
| Zuschlagskriterien | 33 | 16 | 10 | 16 | 23 | 14 |
| Preisblatt | 35 | 34 | 16 | 33 | 46 | 0 |
| Datenschutz | 28 | 46 | 18 | 33 | 23 | 0 |
| Technische Anlage | 32 | 4 | 8 | 5 | 23 | 0 |

→ **Medizin ist der Ausreißer** (Open-House-Rabattverträge: dünn, kaum LB/Vertrag/Wertung).
Bau/IT/Sicherheit = klassische Vollverfahren.

## Q4 — Ort der Zuschlagskriterien *(Extraktionsstrategie)*

| Ort | Anteil |
|---|---:|
| eigenes Dokument | 24 % |
| eingebettet (Bewerbung/LB) | 24 % |
| nicht gefunden | 52 % |

→ Man kann **i. d. R. nicht einfach das eine Kriterien-Dokument** analysieren — die Kriterien
sind verstreut/eingebettet. **Vorbehalt:** die 52 % „nicht gefunden" sind teils eine
Erkennungs-Grenze der Keyword-Suche, nicht sicher Grundwahrheit → wird mit der Nachmessung
sauberer.

## Q5 — Los-Spezifik

- Nur **8 %** haben los-benannte Dateien; 31 Mehr-Los-Vergaben (Metadaten).
- In Mehr-Los-Paketen los-spezifisch v. a. **Leistungsbeschreibung + Preisblatt**, nicht das
  ganze Paket. → „Checkliste pro Los" ist **mechanisch nur selten** (8 %) trennbar, meist
  braucht es ein Inhalts-Urteil.

## Q6 — Maschinenlesbare Formate *(billiger Parser statt LLM)* — starker Befund

| Format | Bau | Berat | Med | IT | Energ\* | Sich\* |
|---|---:|---:|---:|---:|---:|---:|
| **GAEB (Bau-LV)** | **84 %** | 2 % | 0 % | 11 % | 23 % | 0 % |
| ausfüllbares PDF (Formfelder) | 59 % | 40 % | 24 % | 61 % | 69 % | 85 % |
| Excel-Preisblatt | 14 % | 48 % | 18 % | 61 % | 30 % | 85 % |

→ **Bau zu 84 % GAEB** → ein GAEB-Parser holt das LV strukturiert ohne LLM. Ausfüllbare PDFs
und Excel-Preisblätter sind branchenübergreifend häufig → Feld-/Tabellen-Parser für Eignung +
Preis. **Wo strukturierte Formate liegen, ist der LLM überflüssig.**

## Q7 — Versionierung

Versions-/Änderungs-Marker im Dateinamen 9 % · explizite Nachtrags-Datei 3 % · mehrere
Datumsstände im Paket 14 %. → Existiert, aber moderat.

---

## Q1 — Wiederkehrung & Ähnlichkeit

**Q1a Wiederkehrung (belastbar):** Anteil der Vorgänge mit dem Dokumenttyp —
Aufforderung 91 %, Leistungsbeschreibung 84 %, Vertrag 77 %, Eigenerklärung 70 %, Eignung 49 %,
Bewerbungsbedingungen 42 %, Formblatt 34 %, Preisblatt 32 %, Zuschlagskriterien 24 %.
→ **Gemeinsamer 4-Typen-Kern** (Aufforderung/LB/Vertrag/Eigenerklärung) in ~70–91 %.

**Q1b Inhaltsähnlichkeit — sauber nachgemessen (Volltext-Shingles).** Verfahren: 8-Wort-Shingles
über den **ganzen Text** je (Vorgang, Dokumenttyp); **Boilerplate-Anteil** = Anteil der Passagen
eines Dokuments, die in ≥30 % der Vorgänge desselben Typs vorkommen; dazu Median paarweiser Jaccard.
(Die erste Messung verglich nur die ersten 1.200 Zeichen = das individuelle Deckblatt — verworfen.)

| Dokumenttyp | n | Boilerplate | Jaccard | Urteil |
|---|---:|---:|---:|---|
| Zuschlagskriterien | 56 | **27 %** | 0,00 | teils geteilt (Segment-Ebene) |
| Bewerbungsbedingungen | 98 | 22 % | 0,02 | überwiegend individuell |
| Eigenerklärung | 166 | 20 % | 0,02 | überwiegend individuell |
| Eignung | 115 | 16 % | 0,00 | überwiegend individuell |
| Datenschutz | 69 | 7 % | 0,00 | überwiegend individuell |
| Formblatt | 80 | 5 % | 0,00 | überwiegend individuell |
| Aufforderung | 199 | 0 % | 0,00 | überwiegend individuell |
| Leistungsbeschreibung | 193 | 0 % | 0,00 | überwiegend individuell |
| Vertrag | 178 | 0 % | 0,00 | überwiegend individuell |
| Preisblatt | 72 | 0 % | 0,00 | überwiegend individuell |

**Befund: es gibt KEINEN bundesweiten Standardformular-Layer.** Selbst die vermeintlich
standardisierten Regel-Dokumente (Bewerbungsbedingungen, Eigenerklärung, Zuschlagskriterien)
teilen nur **20–27 %** wörtliche Passagen; Leistungsbeschreibung/Vertrag/Aufforderung praktisch
**nichts**. Grund: jede Vergabestelle / jedes Portal (cosinex, DTVP …) / jede VHB-Version erzeugt
eigene Wortlaute — die Standardisierung ist **prozedural, nicht textlich**. *Vorbehalt:* das
8-Wort-Exakt-Maß unterzählt strukturelle Ähnlichkeit bei abweichender Formatierung; der belastbare
Kern ist „**kein dominantes geteiltes Wörtlich-Template**", nicht „0 % Struktur-Überlappung".

→ **Die 3-Ebenen-Architektur (geteiltes Template + Segment + individuell) ist damit vom Tisch.**
Man kann Inhalte **nicht** über ein gemeinsames Vorlagen-Caching entdoppeln. Verarbeitung bleibt
**pro Dokument**. Der Hebel ist NICHT Template-Dedup, sondern gezielte Doku-Auswahl (Q4) +
strukturierte Parser (Q6).

---

## Was die Befunde für Design & Kosten heißen
- **Struktur ist vorhersehbar, Inhalt nicht:** Ein 4-Typen-Kern (Aufforderung/LB/Vertrag/
  Eigenerklärung) tritt in 70–91 % auf (Q1a) und ist zu 69 % per Dateiname klassifizierbar (Q3) —
  aber der **Text je Dokument ist individuell** (Q1b). → Struktur nutzen (welche Typen erwarten,
  wohin schauen), Inhalt pro Dokument verarbeiten.
- **Kosten:** OCR ist vernachlässigbar (3 % der PDFs); der Hebel ist **gezielte Doku-Auswahl**
  (nicht das 90-Seiten-Paket), plus **strukturierte Parser** (GAEB/Excel/Formfelder) für Bau &
  Preis/Eignung. **Kein** Template-Cache-Hebel (Q1b).
- **Klassifikation:** ~⅔ billig über den Dateinamen, ⅓ braucht Inhalt.
- **Kriterien:** selten in einem sauberen Einzeldokument (24 %) → kein „ein Doc reicht"-Shortcut.
- **Standardformular-These (3 Ebenen): widerlegt.** Verarbeitung pro Dokument, nicht per Vorlage.
