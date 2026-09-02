# Sondierung Tschechien

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.** Keine Zeile in `data/gold` oder `data/silver`.

**Stand 2026-09-03.** Landschaft aus dem TED-Monatspaket 2026-06, Schranken an je einem
Fall geprüft, robots.txt zuerst, keine Konten.

---

## 1. Mengengerüst — sehr konzentriert

1.621 Ausschreibungen im Juni, 99 % mit Portal-URL, **104 Domains**. Fünf Engines decken
94 %:

| Engine | Anteil | Art |
|---|---:|---|
| `nen-nipez` | **28 %** | staatliche Pflichtplattform (NEN) |
| `ezak` | **28 %** | mandantenfähig, eine Subdomain je Organisation |
| `tenderarena` | 25 % | kommerziell |
| `egordion` | 10 % | kommerziell |
| `vhodne-uver` | 3 % | kommerziell |

⚠ `ezak.*` und `zakazky.*` sind **Instanzen derselben Software** (E-ZAK) — wie Atexo in
Frankreich sieht es nach vielen Portalen aus und ist eines.

## 2. Schranke — geprüft

### ✅ `ezak` (28 %) — OFFEN, und mit den besten Adressen

Drei Instanzen geprüft (`zakazky.cuni.cz`, `ezak.fnbrno.cz`, `zakazky.vsb.cz`): alle
liefern eine **leere robots.txt** (HTTP 200, 0 Bytes) — nichts untersagt.

Die Vergabeseite verlinkt die Dateien direkt:
```
https://zakazky.cuni.cz/contract_display_12600.html          → die Vergabe
https://zakazky.cuni.cz/document_120719/<hash>-<dateiname>   → die Datei
```
→ **HTTP 200, gültiges Word-Dokument, 30.879 Bytes** — anonym, blankes `curl`.

### ⛔ `nen-nipez` (28 %) — Blättern erlaubt, Herunterladen verboten

Die staatliche Pflichtplattform. `/verejne-zakazky/` ist frei, die Vergabeseite zeigt die
Dokumente offen an — `Zadávací dokumentace.pdf`, Anlagen, sogar ein „Alle Anlagen
herunterladen". Alle liegen unter `nen.nipez.cz/file?id=…`, und die robots.txt sagt:

```
User-agent: *
Crawl-delay: 10
Disallow: /file*
Disallow: /*Soubor.aspx*          ← „soubor" = Datei
Disallow: /*LWOpenFileAdapter.aspx*
```

**Vierter Fall dieser Art** nach Open Nexus (PL), LoginTrade (PL) und START Toscana (IT).
Nicht abgerufen.

⚠ Und damit ist die polnische Beobachtung endgültig begraben: dort gab der Staat heraus
und die Privaten sperrten. Hier sperrt der Staat, und eine mandantenfähige Software gibt
heraus. Es bleibt dabei: **Betreiber für Betreiber.**

### 🎯 `tenderarena` (25 %), `egordion` (10 %), `vhodne-uver` (3 %)

Alle drei verlinken **ausschließlich Käuferprofile**, nie eine Vergabe. Ungeprüft, weil
der Weg vorher endet.

## 3. Die Adressen — und wieder eine Umkehrung

| Engine | Adressen | führen auf EINE Vergabe |
|---|---:|---:|
| `ezak` | 620 | **53 %** |
| `nen-nipez` | 737 | 13 % |
| `tenderarena` | 623 | **0 %** |
| `egordion` | 242 | **0 %** |
| `vhodne-uver` | 85 | **0 %** |

**Die offene Engine hat auch die besten Adressen.** Dasselbe Muster wie in Italien, wo
Soresa (offen) 99 % Tiefe hat und die größte Plattform 11 %.

## 4. Stand nach sechs Ländern

| Land | Anteil EU | bestätigt skriptfähig |
|---|---:|---|
| DE | 21,2 % | 32 % |
| FR | 15,4 % | **0 %** |
| PL | 14,6 % | 19 % ober / 35 % unter |
| ES | 6,7 % | 5 % |
| IT | 4,9 % | 4 % |
| **CZ** | **4,4 %** | **28 %** |

Zusammen **67,2 %** aller EU-Ausschreibungen. Tschechien ist nach Deutschland der beste
bisher gemessene Wert.
