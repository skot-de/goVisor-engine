# Feature #13: Vergabeunterlagen-Verlinkung

**Produkt:** goVisor
**Version:** V1 (Phase 0 — vor Launch)
**Status:** Draft
**Erstellt:** 2026-07-27
**Ändert:** Ticket #1 (Lead Explorer), Ticket #3 (Lead-Detail)
**Aufwand:** klein
**Vorbereitet für:** Ticket #15 (Vergabeunterlagen-Erschließung, Phase 1)

---

## 1. Warum dieses Ticket

goVisor verlinkt heute auf `portal_url` — den Link zur Vergabeplattform. Dieses Feld ist zu **44,5 %** befüllt. Für mehr als die Hälfte der Leads gibt es also keinen Weg zu den Unterlagen.

Im Feldinventar liegt ein besseres Feld: `CallForTendersDocumentReference` mit **83 % Abdeckung** bei offenen Leads (DÖE). Es ist der direkte Verweis auf die Vergabeunterlagen und trägt mehr als nur eine URL.

Das ist ein kleiner Eingriff mit großem Hebel: fast Verdopplung der Fälle, in denen der Nutzer zu den Unterlagen kommt — und die Datengrundlage für die spätere Anforderungs-Extraktion (Ticket #15).

---

## 2. Was das Feld tatsächlich enthält

`CallForTendersDocumentReference` ist kein reines URL-Feld. Es trägt drei nutzbare Informationen:

| Bestandteil | Beispielwert | Nutzen |
|---|---|---|
| **URL** | `https://www.evergabe-online.de/...` | Direktlink zu den Unterlagen |
| **Zugänglichkeit** | `non-restricted-document` | Ob ohne Login/Registrierung erreichbar |
| **Justification** (teils) | `communication-justification`, `sen-info` | Grund bei eingeschränktem Zugang |

Die **Zugänglichkeits-Markierung** ist der unterschätzte Teil. Sie sagt vorab, ob der Nutzer die Unterlagen direkt öffnen kann oder ob eine Registrierung auf der Plattform nötig ist. Das ist eine ehrliche Erwartungssteuerung, die kein Wettbewerber sauf diese Weise nutzt — und es ist entscheidend für Ticket #15, weil nur `non-restricted`-Dokumente ohne Login-Automatisierung crawlbar sind.

---

## 3. Datenlage

| Feld | Abdeckung | Bewertung |
|---|---|---|
| `CallForTendersDocumentReference` (URL) | **83,0 %** DÖE | Neuer Primärlink |
| davon `non-restricted-document` | Teilmenge, aus derselben Struktur | Direkt öffenbar |
| `portal_url` (bisher) | 44,5 % | Bleibt als Fallback |
| `ContractingParty...WebsiteURI` | 38,6 % | Zweiter Fallback (Vergabestellen-Seite) |
| Legacy `URI_DOC` (TED alt) | 100 % (nur Altdaten) | Für historische Leads |

**Wichtig:** Das gute Feld ist auf **Losebene** (`ProcurementProjectLot.TenderingTerms.CallForTendersDocumentReference`). Das passt zu Ticket #12 — der Dokumentlink gehört ohnehin zum Los, nicht nur zur Ausschreibung. Bei Mehr-Los-Vergaben kann es je Los einen eigenen Link geben.

---

## 4. Konzept

### 4.1 Link-Wasserfall

Statt einem Feld ein priorisierter Wasserfall, der die beste verfügbare Quelle nimmt:

```
dokument_link(lead, lot) =
    coalesce(
        lot.CallForTendersDocumentReference.URI,      # 83 %, los-genau
        lead.CallForTendersDocumentReference.URI,      # falls nur auf Ausschreibungsebene
        lead.portal_url,                               # 44,5 %, bisheriger Stand
        lead.contracting_party_website,                # 38,6 %, Vergabestellen-Seite
        NULL                                           # ehrlich: kein Link
    )
```

Jede Stufe wird mit ihrer Quelle geführt, damit im UI unterscheidbar ist, ob der Link direkt zu den Unterlagen führt oder nur zur Plattform-Startseite.

### 4.2 Zugänglichkeit sichtbar machen

Wenn die Zugänglichkeits-Markierung vorliegt, wird sie am Link angezeigt:

| Markierung | UI |
|---|---|
| `non-restricted-document` | „Unterlagen direkt öffnen →" |
| restricted / mit Justification | „Unterlagen (Registrierung nötig) →" |
| unbekannt | „Zur Vergabeplattform →" |

Das steuert die Erwartung: Der Nutzer weiß vor dem Klick, ob er direkt reinkommt oder sich erst anmelden muss. Kleiner Aufwand, spürbar bessere Erfahrung.

---

## 5. Änderungen an Ticket #1 (Lead Explorer)

### 5.1 Datenmodell

**Erweitert: `leads` bzw. `lead_lots`**

| Feld | Typ | Quelle |
|---|---|---|
| `document_url` | string | Wasserfall (siehe 4.1) |
| `document_source` | enum | `docref_lot` / `docref_lead` / `portal` / `party_web` / `none` |
| `document_access` | enum | `non_restricted` / `restricted` / `unknown` |

Bei Ticket #12 (Losebene) gehört `document_url` primär auf `lead_lots` — jedes Los kann einen eigenen Link haben. Für Ein-Los-Vergaben identisch mit dem Ausschreibungslink.

### 5.2 Keine Änderung an der Listen-Optik

Der Link erscheint nicht in der Liste, sondern im Detail. In der Liste ändert sich nichts — dies ist ein reines Datenqualitäts- und Detail-Ticket.

---

## 6. Änderungen an Ticket #3 (Lead-Detail)

### 6.1 Übersicht-Tab: Link mit Zugänglichkeit

Der bestehende Link zur Vergabeplattform wird ersetzt durch den Wasserfall-Link mit Zugänglichkeits-Hinweis:

```
UNTERLAGEN
  [📄 Unterlagen direkt öffnen →]        non-restricted
  oder
  [🔒 Unterlagen (Registrierung nötig) →]  restricted
  oder
  [🌐 Zur Vergabeplattform →]              nur Startseite
```

### 6.2 Bei Mehr-Los-Vergaben: Link je Los

In der Los-Tabelle aus Ticket #12 bekommt jedes Los seinen eigenen Dokumentlink, falls vorhanden:

```
  #   Titel                    Region        Frist      Unterlagen
  ─────────────────────────────────────────────────────────────────
  4   Managed Workplace Süd    Oberbayern    14.09.     📄 öffnen
  7   Support Süd              Oberbayern    21.09.     🔒 Login
```

### 6.3 Kennzeichnung bei fehlendem Link

Wenn der Wasserfall komplett leer ist (kein Feld befüllt), wird das ehrlich gezeigt, nicht mit einem toten Link kaschiert:

```
UNTERLAGEN
  Kein direkter Link veröffentlicht.
  Suche auf der Vergabeplattform nach: [Vergabenummer]
```

---

## 7. Provenance

| Wert | Quelle | Kennzeichnung |
|---|---|---|
| Dokumentlink | `CallForTendersDocumentReference` | echt, los-genau |
| Fallback-Link | `portal_url` / Website | echt, aber „nur Plattform" markiert |
| Zugänglichkeit | Markierung im Feld | echt wo vorhanden, sonst `unknown` |
| kein Link | — | ehrlich als „kein Link veröffentlicht" |

**Regel:** Ein Fallback-Link (Plattform-Startseite) wird nie als „Unterlagen" ausgegeben. Der Unterschied zwischen „führt zu den Unterlagen" und „führt zur Plattform" bleibt im UI sichtbar.

---

## 8. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Dokumentlink nutzt `CallForTendersDocumentReference` als Primärquelle |
| 2 | Wasserfall fällt sauber auf `portal_url`, dann Website, dann „kein Link" zurück |
| 3 | `document_source` unterscheidet Unterlagen-Link von Plattform-Link |
| 4 | Zugänglichkeit (`non_restricted` / `restricted` / `unknown`) wird angezeigt, wo bekannt |
| 5 | Bei Mehr-Los-Vergaben Link je Los (Anschluss an Ticket #12) |
| 6 | Fehlender Link wird ehrlich gezeigt, kein toter Link |
| 7 | Plattform-Startseite nie als „Unterlagen" bezeichnet |
| 8 | Legacy-Leads nutzen `URI_DOC` als Quelle |

---

## 9. Edge Cases

| # | Case | Verhalten |
|---|---|---|
| 1 | Los-Link und Ausschreibungs-Link beide da | Los-Link bevorzugen |
| 2 | Nur `portal_url` vorhanden | Als „zur Plattform" markieren, nicht als Unterlagen |
| 3 | Kein Feld befüllt | „Kein direkter Link" + Vergabenummer zur Suche |
| 4 | URL syntaktisch kaputt | Als fehlend behandeln, nicht verlinken |
| 5 | `restricted` ohne Justification | „Registrierung nötig" ohne Grund |
| 6 | Mehrere Dokument-Referenzen je Los | Erste nicht-restricted bevorzugen, sonst erste |
| 7 | Legacy-Lead (vor eForms) | `URI_DOC` nutzen, Zugänglichkeit `unknown` |

---

## 10. Warum das Ticket vor Ticket #15 kommt

Ticket #15 (Vergabeunterlagen-Erschließung, Phase 1) baut auf diesem auf:

- Die **URL** ist die Eingabe für den Download.
- Die **Zugänglichkeits-Markierung** entscheidet, welche Dokumente überhaupt ohne Login-Automatisierung crawlbar sind — `non-restricted` zuerst.
- Der **`document_source`** sagt, ob überhaupt ein Unterlagen-Link existiert oder nur die Plattform.

Ohne dieses Ticket würde #15 auf dem 44,5-%-Feld aufsetzen und die Hälfte verpassen. Mit ihm startet #15 auf 83 % und weiß vorab, was zugänglich ist.

---

## 11. Out of Scope

| Was | Wann |
|---|---|
| Dokumente tatsächlich herunterladen/parsen | Ticket #15 (Phase 1) |
| Login-Automatisierung für restricted-Dokumente | Ticket #15, wenn überhaupt |
| Anforderungs-Extraktion aus Dokumenten | Ticket #15 |
| Dokument-Vorschau in goVisor | V2 |

---

## 12. Abhängigkeiten

| Abhängigkeit | Status |
|---|---|
| `CallForTendersDocumentReference` im Gold Layer | vorhanden (83 % DÖE) |
| Ticket #1, #3 | Basis, werden geändert |
| Ticket #12 Losebene | parallel — Link gehört auf Los-Ebene |

---

## 13. Testfälle

| # | Test | Erwartung |
|---|---|---|
| 1 | Lead mit `CallForTendersDocumentReference` non-restricted | „Unterlagen direkt öffnen" |
| 2 | Lead mit restricted-Markierung | „Registrierung nötig" |
| 3 | Lead nur mit `portal_url` | „Zur Vergabeplattform", nicht „Unterlagen" |
| 4 | Lead ohne jeden Link | „Kein direkter Link" + Vergabenummer |
| 5 | 3-Los-Vergabe, 2 Lose mit eigenem Link | Je Los eigener Link, drittes ohne |
| 6 | Legacy-Lead | `URI_DOC` als Quelle, Zugänglichkeit unknown |

---

## 14. Zusammenfassung

Ein kleiner Eingriff mit großem Hebel: Der Dokumentlink stützt sich auf `CallForTendersDocumentReference` (83 %) statt `portal_url` (44,5 %), fällt sauber zurück und zeigt vorab, ob die Unterlagen ohne Registrierung erreichbar sind. Das verbessert sofort die Nutzererfahrung und legt die Grundlage für die Vergabeunterlagen-Erschließung in Phase 1.
