# Feature #20: Auftragswert-Plausibilisierung (Vergabestelle)

**Produkt:** goVisor / Vergabeblick
**Version:** 1.0
**Status:** Konzept (Vergabestellen-Seite — gehört zum Vergabeblick-Konzept)
**Erstellt:** 2026-07-27
**Baut auf:** Vergabeblick-Konzept §B, `value_band_effektiv`
**Aufwand:** klein — aber datensensibel, ehrliche Grenzen zwingend

---

## 1. Warum dieses Ticket

Bevor eine Vergabestelle ausschreibt, muss sie den Auftragswert schätzen. Diese Schätzung bestimmt das Verfahren, die Schwellenwerte und die Fristen. Schätzt sie zu niedrig, kommen Angebote über Budget herein und das Verfahren muss womöglich **aufgehoben** werden — teuer und peinlich.

goVisor kann der Stelle eine Orientierung geben, in welchem Wertbereich vergleichbare Verfahren lagen — damit sie ihre Schätzung nicht grob verfehlt.

---

## 2. Die ehrliche Grenze (zwingend)

Inventar-Check 2026-07-27: **Die Wertdaten sind dünn.** Zuschlagspreis und Gesamtwert sind in den Rohdaten nicht sauber auffindbar, der Schätzwert liegt bei 0,7 %. Was tragfähig ist, ist das **Wertband** (`value_band_effektiv`), nicht der Punktwert.

**Konsequenz — was dieses Feature NICHT sagt:**
- ❌ „Der marktübliche Preis ist 340.000 €" (Punktgenauigkeit, die die Daten nicht hergeben)
- ❌ „Bei diesem Preis wird zugeschlagen" (Preisorientierung — datenseitig unmöglich, rechtlich heikel)

**Was es sagt:**
- ✅ „Vergleichbare Verfahren lagen im Wertband 250k–500k €" (Band, aus `value_band_effektiv`)
- ✅ „Dein Schätzwert liegt unter dem Band vergleichbarer Aufträge — Aufhebungsrisiko"

Das ist die „lieber Band als falscher Punkt"-Anwendung des Ehrlichkeitsprinzips.

---

## 3. Darstellung

```
  Wert-Plausibilität

  Dein Schätzwert:        180.000 €
  Vergleichbare Verfahren: Band 250k–500k €  (n=34, gemessen)
  ──────────────────────────────────────────────
  ⚠ Dein Schätzwert liegt unter dem üblichen Band.
    Prüfe, ob er das Verfahren trägt — sonst Aufhebungsrisiko.
```

Bei zu dünner Vergleichsbasis: ehrlich „zu wenige vergleichbare Verfahren für eine belastbare Einordnung" — kein erfundenes Band.

---

## 4. Datenquelle

| Element | Quelle |
|---|---|
| Vergleichs-Wertband | `value_band_effektiv` vergleichbarer Vergaben (CPV+Region+Größe) |
| Fallzahl | Zahl der Vergleichsverfahren (Transparenz) |
| eigener Schätzwert | Eingabe der Stelle im Ausschreibungscheck |

---

## 5. Gate

Teil des Ausschreibungschecks (Vergabeblick) — Einzel-Check oder Pro.

---

## 6. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Vergleich Schätzwert ↔ Wertband vergleichbarer Verfahren |
| 2 | Nur Band, nie Punktwert |
| 3 | Fallzahl sichtbar (Transparenz der Basis) |
| 4 | Warnung bei Schätzwert unter/über Band |
| 5 | Ehrlich „zu wenig Vergleich" statt erfundenem Band |
| 6 | Keine Preisorientierung („bei X wird zugeschlagen") |

---

## 7. Zusammenfassung

Die Wert-Plausibilisierung gibt der Vergabestelle eine Bandorientierung für ihren Schätzwert — genug, um Aufhebungsrisiken durch Fehlschätzung zu vermeiden, ohne einen Punktpreis vorzutäuschen, den die Daten nicht hergeben. Datensensibel, deshalb strikt auf Wertbänder beschränkt.
