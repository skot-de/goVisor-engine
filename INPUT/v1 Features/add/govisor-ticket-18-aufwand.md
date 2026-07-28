# Feature #18: Aufwands-Indikator

**Produkt:** goVisor
**Version:** 1.0
**Status:** Konzept
**Erstellt:** 2026-07-27
**Baut auf:** #15 (Anforderungen), #13 (Vergabeunterlagen)
**Aufwand:** klein — Aggregation vorhandener Signale, kein neuer Datenkern

---

## 1. Warum dieses Ticket

goVisor beantwortet heute die **Chance**-Seite der Bietentscheidung sehr gut: Passt der Lead, ist der Incumbent angreifbar, erfülle ich die Anforderungen. Was fehlt, ist die **Kosten**-Seite: Was kostet mich diese Bewerbung an Aufwand?

Ein Bid-Manager mit begrenzter Kapazität wägt beides ab. Ein Verfahren mit zehn Referenznachweisen, hoher Bürgschaft und 150 Seiten Unterlagen ist eine andere Investition als ein schlankes. Ohne Aufwands-Einschätzung ist die Relevanz nur die halbe Entscheidung.

**Der Indikator ist der zweite Faktor der Bid/No-Bid-Matrix** (die Zusammenführung erfolgt in #19).

---

## 2. Datengrundlage (geprüft)

Inventar-Check 2026-07-27 — die Aufwandssignale tragen:

| Signal | Abdeckung | Aufwandstreiber |
|---|---|---|
| Vergabeunterlagen-Referenzen (`DocumentReference.DocumentType`) | **83,0 %** | Umfang der Unterlagen |
| Sicherheiten/Bürgschaft (`RequiredFinancialGuarantee`) | **59,7 %** | starker Aufwands- & Kapitaltreiber |
| Ausführungs-Anforderungen (`ExecutionRequirementCode`) | **57,3 %** | Zahl/Art der Nachweise (aus #15) |
| Zuschlagskriterien (`AwardCriterionParameter`) | **33,7 %** | Komplexität der Bewertung |
| Unterauftrags-Bedingungen (`SubcontractingTerm`) | 32,6 % | zusätzliche Strukturierung |

**Nicht verfügbar (ehrlich):** Ortstermin/Site-Visit und Register-Pflichten sind in den Daten nicht auffindbar — werden **nicht** erfunden. Der Indikator stützt sich nur auf die vorhandenen Signale und markiert fehlende ehrlich.

---

## 3. Der Aufwands-Score

Eine schlichte Dreistufung je Lead, **nicht** eine Scheingenauigkeit:

```
  Aufwand:  ● gering    ○ mittel    ○ hoch

  Treiber:
  ✓ Bürgschaft gefordert (5 % der Auftragssumme)
  ✓ 6 Eignungsnachweise
  ✓ 4 Zuschlagskriterien
  ○ Unterlagen-Umfang: unbekannt
```

**Berechnung:** gewichtete Summe der vorhandenen Signale, auf drei Stufen gemappt. Jeder Treiber einzeln sichtbar, damit der Nutzer die Einordnung nachvollzieht und selbst gewichten kann — ein Bid-Manager, dem Bürgschaften egal sind, liest den Treiber trotzdem.

**Ehrlichkeit (Hausprinzip):** Fehlt ein Signal (z. B. Unterlagen-Umfang bei den 17 % ohne Referenz), wird es als „unbekannt" markiert, nicht als „gering" angenommen. Der Gesamt-Score sagt dann „grober Indikator, Teildaten fehlen".

---

## 4. Darstellung

- **In der Lead-Liste:** kleine Aufwands-Ampel neben der Relevanz — auf einen Blick „hohe Chance, geringer Aufwand".
- **Im Lead-Detail:** die Treiber-Aufschlüsselung mit Herkunfts-Flags.

---

## 5. Gate

Pro — es ist ein Entscheidungs-Feature, kein Grundüberblick.

---

## 6. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Aufwands-Dreistufung je Lead aus vorhandenen Signalen |
| 2 | Jeder Treiber einzeln sichtbar und nachvollziehbar |
| 3 | Fehlende Signale als „unbekannt" markiert, nicht als gering angenommen |
| 4 | Ampel in Liste, Aufschlüsselung im Detail |
| 5 | Kein erfundenes Signal (kein Ortstermin/Register, da nicht in Daten) |

---

## 7. Nicht-Ziele

| Nicht | Warum |
|---|---|
| Exakte Stunden-/Kostenschätzung | Daten tragen nur eine grobe Stufung |
| Aufwand als alleinige Empfehlung | Der Indikator ist ein Faktor, die Entscheidung trifft #19 |

---

## 8. Zusammenfassung

Der Aufwands-Indikator ergänzt die vorhandene Chance-Analyse um die Kosten-Seite — eine grobe, ehrliche Dreistufung aus vorhandenen Signalen (Unterlagen, Bürgschaft, Anforderungen, Kriterien). Er ist billig zu bauen, weil die Daten aus #15 und #13 schon da sind, und er ist der zweite Faktor der Bid/No-Bid-Matrix (#19).
