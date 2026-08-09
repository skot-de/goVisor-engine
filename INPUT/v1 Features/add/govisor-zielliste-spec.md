# goVisor — Zielliste für die Erstansprache

**Version:** 1.0
**Stand:** 2026-07-30
**Zweck:** Auswertung des eigenen Datenbestands, um Zielunternehmen nach **nachgewiesenem Schmerz**
zu priorisieren — plus automatisch erzeugte Erstansprache-Profile.
**Ergebnis:** eine sortierte Liste + je Treffer ein PDF-Profil.
**Kein Produktfeature.** Interne Auswertung, läuft einmalig bzw. monatlich als Batch.

---

## 1. Grundgedanke

Nicht nach Firmen filtern, sondern nach **Ereignissen** suchen. Ein Handwerksbetrieb mit einem Auftrag
im Jahr hat kein Problem, das ein Abo rechtfertigt. Eine Firma, die letzten Monat einen Bestandsvertrag
verloren hat, hat eins — und weiß es.

Die Auswertung nutzt dieselben Aggregate wie das Firmenprofil (#25), nur über **alle** Entitäten statt
über eine.

---

## 2. Grundgesamtheit und harte Filter

Angewandt **vor** jeder Signalberechnung:

| Filter | Wert | Grund |
|---|---|---|
| `entity_confidence` | **nur `confirmed`** | Ein Profil mit fremden Verträgen zerstört die Ansprache |
| Zuschläge letzte 36 Monate | **≥ 5** | darunter kein Muster, kein Bedarf |
| Ø Auftragswert | **≥ 100.000 €** | darunter fehlt das Budget |
| Anteil Aufträge mit echtem Wert | ≥ 50 % | sonst ist das Profil zu dünn für eine Ansprache |
| Rolle | **Bieter/Auftragnehmer**, nicht Vergabestelle | `profile_type`-Logik |
| Region | konfigurierbar (Start: NRW + 150 km) | Ansprache braucht Nähe |
| Konzern | Konzernmutter statt Einzelgesellschaften (`dim_company_group`) | keine Doppelansprache |

**Erwartete Restmenge:** deutlich unter 10.000 — das ist gewollt. Ziel sind 200–500 belastbare Treffer,
nicht Masse.

---

## 3. Die fünf Signale

Je Entität berechnen. Alle Werte aus vorhandenen Aggregaten.

### S1 — Frischer Verlust (stärkstes Signal)

Die Firma war Amtsinhaber, der Nachfolgeauftrag ging an einen anderen.

| Element | Quelle |
|---|---|
| Nachfolge-Beziehung | `head_to_head` |
| Rolle: war Vorgänger, ist nicht Nachfolger | `head_to_head` |
| Zeitpunkt des Verlusts | Zuschlagsdatum des Nachfolgeauftrags |

**Berechnung:** Anzahl verlorener Bestandsverträge in den letzten **12 Monaten**, gewichtet nach
Volumen. Verlust vor weniger als 3 Monaten zählt doppelt (Aktualität).

**Warum:** Konkreter, aktueller, bezifferbarer Schmerz. Die Firma sucht gerade nach Erklärungen.

### S2 — Bevorstehender Auslauf

Die Firma hält Verträge, die bald enden, in einem Feld mit hoher Wechselquote.

| Element | Quelle |
|---|---|
| eigene laufende Verträge + Enddatum | `lead_duration` |
| Wechselquote des Segments | `head_to_head` / Marktretention (28,3 % Basis) |
| Bindungsdauer | `incumbent_tenure` |

**Berechnung:** Summe des Volumens, das in **6–18 Monaten** ausläuft, gewichtet mit der
Segment-Wechselquote. Kurze Bindung (< 2 Jahre) erhöht das Risiko und damit den Score.

**Warum:** Noch kein Schmerz, aber bezifferbares Risiko. Die stärkste Botschaft überhaupt:
„X € Ihres Bestands stehen in 14 Monaten zur Disposition."

### S3 — Hoher Aufwand, niedrige Ausbeute

Die Firma ist in vielen Verfahren sichtbar, gewinnt aber selten.

| Element | Quelle |
|---|---|
| Aktivität im Segment | `contractor_stats`, `market_opportunity` |
| Zuschläge relativ zur Segmentgröße | Verhältnis eigene Zuschläge zu Verfahren im CPV+Region |

**Berechnung:** Erwartete Zuschlagszahl im Segment (Segmentvolumen ÷ aktive Anbieter) gegen
tatsächliche Zuschläge. Deutliche Unterperformance = hoher Score.

**Vorbehalt:** Teilnahmen ohne Zuschlag sind **nicht** öffentlich. Das ist eine Näherung über die
Marktpräsenz, kein gemessener Wert. Im Profil entsprechend vorsichtig formulieren.

### S4 — Wachstum / Professionalisierung

Zuschlagszahl steigt über die letzten drei Jahre.

| Element | Quelle |
|---|---|
| Zuschläge je Jahr | `contractor_stats` (Jahresscheiben) |

**Berechnung:** Steigung über 3 Jahre. Wachstum > 30 % = Score.

**Warum:** Firmen in dieser Phase führen Werkzeuge ein. Guter Zeitpunkt, kein Schmerz.

### S5 — Feldbreite

Die Firma ist in mehreren CPV-Feldern oder Regionen aktiv.

**Berechnung:** Anzahl distinkter CPV-Bündel und NUTS-Regionen mit ≥ 1 Zuschlag.

**Warum:** Breite Aktivität heißt hoher Suchaufwand — genau das, was goVisor abnimmt. Schwaches
Signal, dient der Feinsortierung.

---

## 4. Gesamtscore und Sortierung

```
score = 40 × S1_norm      (frischer Verlust)
      + 30 × S2_norm      (bevorstehender Auslauf)
      + 15 × S3_norm      (Unterperformance)
      +  9 × S4_norm      (Wachstum)
      +  6 × S5_norm      (Feldbreite)
```

Alle Teilsignale auf 0–1 normalisieren (Perzentil innerhalb der gefilterten Grundgesamtheit, nicht
absolut — sonst dominieren Großkonzerne).

**Ausgabe:** Rangliste absteigend. Zusätzlich das **dominante Signal** je Treffer speichern — es
bestimmt den Aufhänger der Ansprache (§6).

---

## 5. Ausgabeformat

Eine CSV plus je Treffer ein PDF.

**CSV-Spalten:**

| Spalte | Inhalt |
|---|---|
| `entity_id`, `firmenname`, `ort`, `nuts` | Identität |
| `score`, `dominant_signal` | Priorisierung |
| `zuschlaege_36m`, `volumen_36m`, `avg_wert` | Größe |
| `verlorene_vertraege_12m`, `verlust_volumen` | S1 |
| `auslauf_volumen_6_18m`, `naechstes_auslaufdatum` | S2 |
| `hauptwettbewerber`, `dessen_auslauf_naechster` | Gesprächsaufhänger |
| `top_cpv`, `top_vergabestellen` | Kontext |
| `entity_confidence` | Qualitätssicherung (muss `confirmed` sein) |

---

## 6. Das Ansprache-Profil (PDF je Treffer)

**Kernidee:** Kein Anschreiben, sondern ein **Befund** mit den echten Zahlen des Empfängers. Nutzt die
gebaute Firmenprofil-Ansicht (#25), gerendert als PDF.

**Inhalt, in dieser Reihenfolge:**

1. **Der Aufhänger** — abhängig vom dominanten Signal:
   - S1: „Sie haben in den letzten 12 Monaten 2 Bestandsverträge über 1,4 Mio € nicht verteidigt."
   - S2: „3 Ihrer Verträge über 2,1 Mio € laufen in den nächsten 18 Monaten aus."
   - S3: „In Ihrem Feld werden jährlich N Aufträge vergeben. Sie halten X."
   - S4/S5: neutraler Marktüberblick als Aufhänger
2. **Ihre laufenden Verträge** mit Enddatum
3. **Ihr Hauptwettbewerber** — was er hält, was bei ihm ausläuft
4. **Ihr Feld** — wie viele Anbieter, wie hoch die Wechselquote
5. **Ein Satz zur Herkunft:** alles aus öffentlichen Vergabebekanntmachungen

**Pflicht:** Keine Bewertung der Firma, keine Personen, keine Preise. Provenance-Kennzeichnung wie im
Produkt (gemessen/geschätzt/unbekannt).

---

## 7. Grenzen

| Grenze | Regel |
|---|---|
| **Entity-Sicherheit** | nur `confirmed` — ein Profil mit fremden Verträgen ist schlimmer als keine Ansprache |
| **Kontaktdaten** | nicht in den Vergabedaten enthalten; separat beschaffen. Bei natürlichen Personen greift die DSGVO |
| **E-Mail-Kaltakquise** | nach UWG § 7 auch im B2B nur bei mutmaßlicher Einwilligung — riskant. Bevorzugt: LinkedIn, Telefon, **Post** |
| **S3 ist eine Näherung** | Teilnahmen ohne Zuschlag sind nicht öffentlich — im Profil vorsichtig formulieren |
| **Keine Wertung** | Der Befund beschreibt, er beurteilt nicht |

---

## 8. Betrieb

- **Einmalig** für den Erstlauf, danach **monatlich** — S1 und S2 verändern sich laufend.
- Bereits angesprochene Entitäten markieren (`outreach_log`), keine Doppelansprache.
- Trefferquote je dominantem Signal erfassen — nach 50 Ansprachen zeigt sich, welches Signal
  tatsächlich konvertiert. Danach Gewichte in §4 anpassen.

---

## 9. Umsetzungsreihenfolge

| Schritt | Inhalt |
|---|---|
| 1 | Harte Filter (§2) → Grundgesamtheit prüfen, Größe muss plausibel sein |
| 2 | S1 und S2 berechnen — die beiden tragenden Signale |
| 3 | CSV mit S1/S2 ausgeben, manuell auf 20 Treffern gegenprüfen |
| 4 | S3–S5 ergänzen, Gesamtscore |
| 5 | PDF-Rendering aus der Firmenprofil-Ansicht |
| 6 | `outreach_log` + Monatslauf |

Schritt 1–3 reichen für die ersten Ansprachen. Der Rest ist Feinschliff.
