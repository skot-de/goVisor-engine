# Feature #21: Eignungskriterien-Angemessenheit (Vergabestelle)

**Produkt:** goVisor / Vergabeblick
**Version:** 1.0
**Status:** Konzept (Vergabestellen-Seite — gehört zum Vergabeblick-Konzept)
**Erstellt:** 2026-07-27
**Baut auf:** Vergabeblick-Konzept §B.2, `market_opportunity`, `contractor_stats`, Anforderungssignale (wie #18)
**Aufwand:** mittel — Spiegel des Aufwands-Indikators, aus Käufersicht

---

## 1. Warum dieses Ticket

Das Ein-Bieter-Problem — vier von zehn Verfahren mit nur einem Bieter — entsteht oft **hausgemacht**: Die Vergabestelle fordert aus Vorsicht zu viel. Hohe Umsatzschwellen, viele Referenzen, strenge Zertifikatspflichten schließen ungewollt den Mittelstand aus und reduzieren das Bieterfeld.

Der Ausschreibungscheck (Vergabeblick §B.1/B.2) prüft bisher **Losstruktur, Bürgschaft, Volumen**. Dieses Ticket ergänzt die **Eignungsdimension**: Wie stark schränken die geforderten Eignungskriterien den Markt ein?

Es ist das exakte Spiegelbild des Anbieter-Aufwands-Indikators (#18): dieselben Anforderungssignale, aus Käufersicht gelesen.

---

## 2. Das Prinzip

Für jede geforderte Eignung zeigt goVisor, wie viele Anbieter im relevanten Markt sie erfüllen:

```
  Eignungs-Check deines Entwurfs

  Geforderte Eignung              Anbieter im Markt, die erfüllen
  ──────────────────────────────────────────────────────────────
  Mindestumsatz 5 Mio €           ●●●○○  ~40 % der regionalen Anbieter
  3 Referenzen > 500k €           ●●○○○  ~25 %
  ISO 27001 zwingend              ●○○○○  ~12 %  ⚠ stark einschränkend
  ──────────────────────────────────────────────────────────────
  Kombiniert erfüllen alle 3:     nur ~6 Anbieter (Median-Feld: 4 Bieter)
```

Der Kernwert ist die **Kombination**: Jede einzelne Hürde wirkt harmlos, zusammen bleiben wenige Anbieter. goVisor rechnet den kumulativen Effekt vor — das sieht die Stelle sonst nicht.

---

## 3. Datengrundlage

| Element | Quelle | Abdeckung |
|---|---|---|
| aktive Anbieter im Segment | `market_opportunity`, `contractor_stats` | ✅ (511 Segmente) |
| Anbietergrößen (für Umsatzschwellen) | `contractor_stats` | ✅ |
| geforderte Anforderungen | Entwurf der Stelle + `ExecutionRequirement`-Muster | 57 % (wie #18) |
| Zertifikats-Erfüllung | **dünn** — benannte Zerts 0,1–0,4 % in Daten | ⚠ nur generisch |

**Ehrliche Grenze:** Bei benannten Zertifikaten ist die Datenlage dünn (bekannt aus #15). Der Check stützt sich auf die belastbaren generischen Kriterien (Umsatz, Referenzzahl, Region) und markiert Zertifikats-Aussagen als „grobe Schätzung" oder lässt sie weg — kein erfundener Erfüllungsgrad.

---

## 4. Der Bezug zum Ein-Bieter-Frühwarnsystem

Dieses Feature ist Teil des Kern-Frühwarnsystems (Vergabeblick §2). Es verbindet sich direkt mit der Zuschnitt-Optimierung (§B.2): Wo diese sagt „andere Losstruktur = mehr Bieter", sagt dieses Feature „gelockerte Eignung = mehr Bieter". Zusammen ergeben sie die vollständige Antwort auf „wie bekomme ich mehr als einen Bieter".

---

## 5. Rechtliche Einordnung ⚖️

Unkritisch, weil es **faktisch und aggregiert** ist: „X % der Anbieter erfüllen dies" ist eine Marktbeobachtung, keine Wertung. Es empfiehlt nicht, Kriterien wegzulassen (das wäre Rechtsberatung), sondern zeigt nur die Marktwirkung — die Entscheidung bleibt bei der Stelle, die ihre Kriterien vergaberechtlich begründen muss.

---

## 6. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Je geforderter Eignung: Anteil erfüllender Anbieter |
| 2 | Kumulativer Effekt aller Kriterien zusammen |
| 3 | Vergleich zum Median-Bieterfeld des Segments |
| 4 | Generische Kriterien belastbar, Zertifikate ehrlich als dünn markiert |
| 5 | Faktische Marktwirkung, keine Weglass-Empfehlung (⚖️) |
| 6 | Verbindung zur Zuschnitt-Optimierung (§B.2) |

---

## 7. Zusammenfassung

Die Eignungs-Angemessenheit zeigt der Vergabestelle, wie stark ihre geforderten Kriterien den Bietermarkt einschränken — einzeln und kumulativ. Es ist das Käufer-Spiegelbild des Aufwands-Indikators (#18) und ein Kernbaustein des Ein-Bieter-Frühwarnsystems. Faktisch-aggregiert, rechtlich unkritisch, mit ehrlicher Behandlung der dünnen Zertifikatsdaten.
