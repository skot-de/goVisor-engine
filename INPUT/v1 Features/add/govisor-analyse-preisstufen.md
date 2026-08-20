# Analyse-Auftrag: Preisstufen aus dem Auftragsvolumen ableiten

**Produkt:** goVisor
**Version:** 1.0
**Typ:** Einmalige Datenanalyse, kein Feature
**Erstellt:** 2026-08-13
**Zweck:** Die drei Preisstufen (Pro / Premium / individuell) sollen anhand des tatsächlichen
öffentlichen Auftragsvolumens der Zielunternehmen zugeschnitten werden — statt geraten.

---

## 1. Was beantwortet werden soll

**Leitfrage:** Wie verteilt sich das öffentliche Auftragsvolumen über die Unternehmen, die für
goVisor als Kunden in Frage kommen — und wo liegen sinnvolle Schnitte für drei Preisstufen?

**Konkret:**
1. Wie viele Unternehmen kommen überhaupt in Frage (Grundgesamtheit)?
2. Wie verteilt sich deren jährliches Auftragsvolumen und ihre Zuschlagszahl?
3. An welchen Schwellen entstehen natürliche Gruppen?
4. Wie groß wäre jede Preisstufe, wenn man dort schneidet?
5. Unterscheidet sich das je Branche und Land?

**Nicht Teil des Auftrags:** Preishöhen festlegen. Die Analyse liefert die Verteilung, die
Preisentscheidung folgt danach.

---

## 2. Grundgesamtheit

Nur Unternehmen, die als zahlende Kunden realistisch sind.

| Filter | Wert | Grund |
|---|---|---|
| `entity_confidence` | nur `confirmed` | sonst verzerren Fehlzuordnungen die Verteilung |
| Konzernebene | Konzernmutter (`dim_company_group`), nicht Einzelgesellschaften | sonst wird ein Konzern mehrfach gezählt |
| Rolle | Auftragnehmer | |
| Land | DE · AT · CH, getrennt auswertbar | |
| Zeitraum | letzte 36 Monate, auf Jahresdurchschnitt normiert | glättet Ausreißerjahre |
| Mindestaktivität | ≥ 2 Zuschläge in 36 Monaten | darunter kein Vergabegeschäft, kein Kunde |
| Ausschluss | öffentliche Eigenbetriebe, Inhouse-Gesellschaften | bieten nicht im Wettbewerb |

**Auszugeben:** Größe der Grundgesamtheit je Land, und wie viele Unternehmen durch welchen Filter
wegfallen (Trichter). Das ist selbst schon eine Erkenntnis über die Marktgröße.

---

## 3. Kennzahlen je Unternehmen

| Kennzahl | Berechnung |
|---|---|
| `zuschlaege_pa` | distinkte **Verfahren** je Jahr (Ø über 36 Monate) — nicht Lose, nicht Bekanntmachungen |
| `volumen_pa` | Summe der Auftragswerte je Jahr (Ø über 36 Monate) |
| `volumen_anteil_echt` | Anteil der Zuschläge mit veröffentlichtem Wert |
| `avg_auftragswert` | Median und Mittelwert |
| `felder` | Anzahl distinkter CPV-Bündel |
| `regionen` | Anzahl distinkter NUTS-2-Regionen |
| `quellenverteilung` | Anteil ober-/unterschwellig |

### 3.1 Umgang mit fehlenden Werten ⚠

Nur etwa 65 % der Vergaben tragen einen echten Auftragswert. Eine reine Summe würde die Unternehmen
systematisch unterschätzen.

**Vorgehen — beide Varianten ausgeben, nicht eine wählen:**

| Variante | Definition |
|---|---|
| **A — konservativ** | Summe nur über Zuschläge mit veröffentlichtem Wert |
| **B — hochgerechnet** | fehlende Werte mit dem Median des jeweiligen CPV-Bündels und Wertbands ersetzt |

Variante B **immer als geschätzt kennzeichnen**. Wenn beide Varianten zu unterschiedlichen
Stufengrenzen führen, ist das ein Ergebnis und muss benannt werden.

---

## 4. Die eigentliche Auswertung

### 4.1 Verteilung

Für `volumen_pa` und `zuschlaege_pa` jeweils:

- Perzentile: 10 / 25 / 50 / 75 / 90 / 95 / 99
- Histogramm mit logarithmischer Klassenbildung (das Volumen ist stark rechtsschief)
- Anzahl Unternehmen je Klasse

### 4.2 Natürliche Schnitte suchen

**Nicht willkürlich bei runden Zahlen schneiden.** Prüfen, ob die Verteilung selbst Gruppen zeigt:

| Verfahren | Zweck |
|---|---|
| Histogramm auf Lücken und Häufungen prüfen | zeigt natürliche Grenzen |
| Clusteranalyse (k-means, k=3) über `volumen_pa` und `zuschlaege_pa`, beide log-transformiert | prüft, ob drei Gruppen überhaupt sinnvoll sind |
| Silhouettenwert für k = 2, 3, 4 | zeigt, ob drei die richtige Zahl ist |

**Ergebnis offen halten.** Wenn die Daten zwei oder vier Gruppen zeigen, ist das die Antwort — nicht
drei erzwingen, weil das Preismodell drei Stufen hat.

### 4.3 Stufengrößen simulieren

Für mehrere Kandidaten-Schwellen ausgeben, wie groß jede Stufe wäre:

```
Beispielhafte Schwellen (nicht vorgegeben, aus 4.2 ableiten):
  Stufe 1: volumen_pa <  X
  Stufe 2: X ≤ volumen_pa < Y
  Stufe 3: volumen_pa ≥ Y
```

Je Kandidat auszugeben: Anzahl Unternehmen je Stufe, Anteil an der Grundgesamtheit, Median-Volumen
und Median-Zuschlagszahl innerhalb der Stufe.

**Zielgrößenordnung zur Orientierung:** Stufe 3 (individuelles Angebot) sollte klein genug bleiben,
dass Einzelgespräche machbar sind — Größenordnung wenige hundert Unternehmen je Land, nicht tausende.

### 4.4 Aufschlüsselung

Alles zusätzlich getrennt nach:

| Dimension | Werte |
|---|---|
| Land | DE · AT · CH |
| Branche | Bau · IT · Beratung · Medizin · Sicherheit · Energie · übrige |

**Wichtige Prüffrage:** Sind die Schwellen branchenübergreifend gleich sinnvoll? Ein Bauunternehmen
mit 2 Mio € Volumen ist ein anderer Fall als eine IT-Beratung mit 2 Mio €. Falls die Verteilungen
stark abweichen, ist das ein Argument gegen einheitliche Schwellen — und muss benannt werden.

---

## 5. Ausgabe

### 5.1 Bericht (Markdown)

1. Trichter der Grundgesamtheit je Land
2. Verteilungstabellen und Histogramme
3. Ergebnis der Clusteranalyse inkl. Silhouettenwerten
4. Kandidaten-Schwellen mit Stufengrößen
5. Branchenvergleich
6. **Empfehlung mit Begründung** — welche Schwellen, warum, und wo die Analyse unsicher ist

### 5.2 Daten (CSV)

Eine Zeile je Unternehmen mit allen Kennzahlen aus §3 plus zugeordneter Stufe je Kandidaten-Schwelle.
Diese Datei wird später für die Vertriebsansprache wiederverwendet (siehe `govisor-vertriebsziele-spec.md`).

---

## 6. Was die Analyse nicht leisten kann

Ausdrücklich im Bericht benennen:

| Grenze | Warum |
|---|---|
| Zahlungsbereitschaft | Volumen ist ein Näherungswert für Größe, kein Beleg dafür, was jemand zahlt |
| Privater Umsatz | goVisor sieht nur öffentliche Aufträge. Ein Unternehmen mit 90 % Privatgeschäft erscheint klein |
| Teamgröße | Nicht aus Vergabedaten ableitbar — falls die Nutzerzahl ins Preismodell einfließt, fehlt hier die Grundlage |
| Wertlücke | 35 % ohne veröffentlichten Wert; Variante B ist geschätzt, nicht gemessen |

---

## 7. Konkrete Rückfragen, die der Bericht beantworten soll

1. Wie viele Unternehmen je Land bleiben nach den Filtern übrig?
2. Wo liegt der Median des Jahresvolumens — und wie weit reicht das oberste Perzentil?
3. Zeigt die Verteilung natürliche Gruppen, oder ist sie stufenlos?
4. Sind drei Stufen sinnvoll, oder legen die Daten eine andere Zahl nahe?
5. Bei welchen Schwellen entstehen Stufen in handhabbarer Größe?
6. Weichen die Verteilungen je Branche so stark ab, dass einheitliche Schwellen nicht tragen?
7. Wie stark unterscheiden sich die Ergebnisse zwischen Variante A und B?
