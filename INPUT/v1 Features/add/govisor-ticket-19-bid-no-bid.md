# Feature #19: Bid/No-Bid-Ansicht

**Produkt:** goVisor
**Version:** 1.0
**Status:** Konzept
**Erstellt:** 2026-07-27
**Baut auf:** #2 (Relevanz), #3 (Incumbent), #15 (Anforderungen), #18 (Aufwand)
**Aufwand:** klein — Darstellung, kein neues Datenfeature

---

## 1. Warum dieses Ticket

goVisor liefert vier Analysen, die ein Bid-Manager im Kopf ohnehin zu einer Entscheidung zusammenrechnet:

1. **Relevanz** — passt der Lead zu mir? (#2)
2. **Incumbent-Angreifbarkeit** — habe ich eine echte Chance? (#3)
3. **Anforderungserfüllung** — erfülle ich die K.o.-Kriterien? (#15)
4. **Aufwand** — was kostet mich die Bewerbung? (#18)

Heute liegen diese vier verstreut. Dieses Ticket führt sie zu **einer Entscheidungsansicht** zusammen — es macht aus Analyse eine Entscheidungshilfe. Das ist die natürliche Reifestufe: von „hier sind die Zahlen" zu „solltest du bieten?".

---

## 2. Die Entscheidungsmatrix

Die zwei tragenden Achsen sind **Chance** (Relevanz + Angreifbarkeit) und **Aufwand** (#18):

```
             gering        hoher
             Aufwand       Aufwand
          ┌─────────────┬─────────────┐
   hohe   │  KLARER     │  ABWÄGEN    │
   Chance │  FALL       │  lohnt sich │
          │  → bieten   │  der Aufwand?│
          ├─────────────┼─────────────┤
   niedr. │  MITNAHME   │  MEIDEN     │
   Chance │  wenn Zeit  │  → weiter   │
          └─────────────┴─────────────┘
```

Plus die **K.o.-Prüfung** aus #15 als Vorschaltung: Erfüllt der Nutzer die Pflichtanforderungen nicht, steht alles andere unter Vorbehalt — die Ansicht sagt dann klar „Eignung nicht erfüllt: X fehlt", bevor sie über Chance und Aufwand redet.

---

## 3. Darstellung je Lead

```
  Solltest du bieten?

  Chance        ●●●○  hoch      (Relevanz 82 %, Incumbent schwach)
  Aufwand       ●●○○  mittel    (Bürgschaft, 6 Nachweise)
  Eignung       ✓ erfüllt        (alle Pflichtkriterien)
  ──────────────────────────────────────────────
  Einordnung:   Klarer Fall — hohe Chance bei überschaubarem Aufwand
```

Bei fehlender Eignung:
```
  Eignung       ✗ nicht erfüllt  (Pflichtreferenz Cloud fehlt)
  ──────────────────────────────────────────────
  Einordnung:   K.o. — ohne diese Referenz chancenlos
```

**Kein Automatismus:** Die Ansicht *empfiehlt* nicht hart „bieten/nicht bieten", sie *ordnet ein*. Die Entscheidung bleibt beim Menschen — goVisor liefert die vier Faktoren transparent, nicht ein Blackbox-Urteil. Das ist konsistent mit dem Ehrlichkeitsprinzip: nachvollziehbare Faktoren statt einer Zahl, der man vertrauen soll.

---

## 4. Wo

- **Lead-Detail:** die volle Entscheidungsansicht als eigener Block.
- **Lead-Liste:** optional ein kombiniertes Chance/Aufwand-Symbol zum schnellen Filtern („zeig mir die klaren Fälle").

---

## 5. Gate

Pro.

---

## 6. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Vier Faktoren (Chance, Aufwand, Eignung + Details) in einer Ansicht |
| 2 | K.o.-Prüfung (#15) vorgeschaltet — fehlende Eignung dominiert |
| 3 | Einordnung als Text, kein hartes Automatik-Urteil |
| 4 | Jeder Faktor nachvollziehbar (keine Blackbox) |
| 5 | Optionaler Chance/Aufwand-Filter in der Liste |

---

## 7. Nicht-Ziele

| Nicht | Warum |
|---|---|
| Automatische Bid/No-Bid-Entscheidung | goVisor ordnet ein, entscheidet nicht |
| Gewichtung fest vorgeben | Nutzer gewichtet selbst (dem einen ist Aufwand wichtiger) |
| Preis-/Margen-Kalkulation | nicht Teil der Ausschreibungs-Analyse |

---

## 8. Zusammenfassung

Die Bid/No-Bid-Ansicht führt die vier vorhandenen Analysen (Relevanz, Angreifbarkeit, Eignung, Aufwand) zu einer transparenten Entscheidungsmatrix zusammen. Sie macht aus goVisors Analyse eine Entscheidungshilfe, ohne dem Menschen die Entscheidung abzunehmen — nachvollziehbare Faktoren statt Blackbox-Urteil. Kein neues Datenfeature, reine Zusammenführung.
