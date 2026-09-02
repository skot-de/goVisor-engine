# Sondierung Italien

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.** Keine Zeile in `data/gold` oder `data/silver`.

**Stand 2026-09-03.** Landschaft aus dem TED-Monatspaket 2026-06, Schranken an je einem
Fall geprüft, robots.txt zuerst, keine Konten.

---

## 1. Mengengerüst — kein dominantes System

| | IT | ES | FR | PL |
|---|---:|---:|---:|---:|
| Ausschreibungen Juni | **1.797** | 2.458 | 5.683 | 5.381 |
| mit Portal-URL | **100 %** | 99 % | 97 % | 99 % |
| verschiedene Domains | **538** | 75 | 443 | 511 |

Italien ist die Landschaft der **regionalen Einkaufszentralen**. Anders als Spanien (eine
Staatsplattform mit 63 %) und anders als Polen (sechs Engines für 89 %) gibt es hier
**keinen dominanten Anbieter**:

| Engine | Anteil | Träger |
|---|---:|---|
| `aria-sintel` (Lombardei) | 10 % | Region |
| `enel` | 6 % | Versorger, eigenes Beschaffungsportal |
| `intercenter` (Emilia-Romagna) | 6 % | Region |
| `soresa` (Kampanien) | 4 % | Region |
| `consip` (national, MEPA) | 4 % | Staat |
| `start-toscana` | 4 % | Region |
| `albofornitori` | 3 % | Weißmarke, mandantenfähig |
| `lazio-crea` | 2 % | Region |
| **unbekannt** | **61 %** | der lange Schwanz |

## 2. Eine Umkehrung, die man nicht erwartet

Wie tief führt die von TED veröffentlichte Adresse?

| Engine | Adressen | tiefer als die Portalwurzel |
|---|---:|---:|
| `soresa` | 475 | **99 %** |
| `albofornitori` | 311 | 93 % |
| `start-toscana` | 303 | 87 % |
| **unbekannt (der Schwanz)** | 3.339 | **72 %** |
| `consip` | 111 | 43 % |
| `intercenter` | 268 | 29 % |
| `aria-sintel` | 593 | **11 %** |
| `enel` | 75 | **0 %** |

**Die größte Plattform ist die nutzloseste.** ARIA/Sintel trägt 10 % der Bezüge und führt
zu 89 % nur auf die Portalstartseite. Der zersplitterte Schwanz dagegen — 538 Domains, die
nach viel Arbeit aussehen — verlinkt zu 72 % direkt auf die Vergabe.

Das dreht die übliche Annahme um: in Italien lohnt sich nicht die größte Engine zuerst,
sondern die mit den brauchbarsten Adressen.

## 3. Schranke — geprüft

### ✅ `soresa` (Kampanien, 4 %) — OFFEN

Zwei Hosts: `portale.soresa.it` zeigt die Vergabe, `siaps.soresa.it` liefert die Dateien.
Der Portal-Host trägt eine gewöhnliche Drupal-robots.txt ohne Vergabe-Sperren, der
Datei-Host hat gar keine (404).

Die Vergabeseite listet die Dokumente mit **Name, Größe und SHA256** im Link selbst.
Geprüft an `Disciplinare di gara.pdf`:

→ **HTTP 200, `application/pdf`, 1.476.938 Bytes, 43 Seiten** — anonym, blankes `curl`.
Die Größe stimmt **auf das Byte** mit der im Link angegebenen überein.

### ⛔ `start-toscana` (4 %) — Blättern erlaubt, Herunterladen verboten

`/tendering/` ist frei, aber die robots.txt sperrt jeden Dateipfad:

```
Disallow: */cards/attachments/download/*
Disallow: */marketplace/attachments/download/*
Disallow: */sourcing/attachments/download/*
Disallow: */document-requests/download/*
```

**Dritter Fall dieser Art** nach Open Nexus (PL) und LoginTrade (PL). Nicht abgerufen.

### 🟡 `consip` (national, 4 %) — `Disallow: /` mit Ausnahmen

```
Disallow: /
Allow: /opencms/opencms/
Allow: /downloadservices/
```

Die von TED verlinkten Pfade (`/opencms/opencms/…`) sind ausdrücklich erlaubt, und
`/downloadservices/` ebenfalls. ⚠ Ungeprüft, weil Consips Adressen zu 57 % nicht tiefer
als die Portalwurzel führen — der Weg endet vorher.

### 🎯 `aria-sintel` (10 %) — keine Sperre, aber keine Adresse

Kein robots.txt (404), also nichts untersagt. Aber 89 % der Adressen zeigen nur auf die
Portalwurzel oder auf `tabsNavigation.do?selected=15` — eine Ansicht, keine Vergabe.
Dieselbe Kategorie wie Madrid: der Weg endet vor dem Portal, nicht an ihm.

### Ungeprüft

`enel` (6 %, 0 % Tiefe), `intercenter` (6 %), `albofornitori` (3 %), `lazio-crea` (2 %)
und der 61-%-Schwanz. ⚠ Letzterer ist der interessanteste offene Posten: 3.339 Adressen
mit 72 % Tiefe, verteilt auf hunderte Domains.

## 4. Stand nach fünf Ländern

| Land | Ausschreibungen Juni | Anteil EU | skriptfähig |
|---|---:|---:|---|
| DE | 7.811 | 21,2 % | 32 % |
| FR | 5.683 | 15,4 % | **0 %** |
| PL | 5.381 | 14,6 % | 19 % ober / 35 % unter |
| ES | 2.458 | 6,7 % | 5 % bestätigt |
| **IT** | **1.797** | **4,9 %** | **4 % bestätigt** |

Zusammen **62,8 %** aller EU-Ausschreibungen.
