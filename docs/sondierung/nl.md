# Sondierung Niederlande

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.** Keine Zeile in `data/gold` oder `data/silver`.

**Stand 2026-09-03.**

---

## 1. Mengengerüst

915 Ausschreibungen im Juni, zwei Systeme:

| Portal | Bezüge | Anteil |
|---|---:|---:|
| `tenderned.nl` (nationale Pflichtplattform) | 673 | **73 %** |
| `s2c.mercell.com` | 203 | 22 % |
| Rest (EU-Institutionen, Gasunie, EU-Supply …) | ~35 | 4 % |

## 2. ✅ TenderNed ist offen — über die offizielle Schnittstelle

**Die Regel „erst nach der Schnittstelle fragen" hat sich zum zweiten Mal ausgezahlt**
(nach Polen). TenderNed hat zwei APIs:

- eine **XML-API mit Zugangsdaten**, die man per E-Mail beantragt — die nutze ich nicht
- einen **öffentlichen Publikations-Webservice ohne jede Anmeldung**

Der öffentliche Weg trägt alles, was gebraucht wird:

```
GET /papi/tenderned-rs-tns/v2/publicaties?page=0&size=3
    → 200, JSON, 145.155 Publikationen insgesamt

GET /papi/tenderned-rs-tns/v2/publicaties/<id>/documenten
    → 200, JSON: documentNaam, typeDocument, grootte, publicatieCategorie,
      virusIndicatie und links.download.href

GET /papi/tenderned-rs-tns/v2/publicaties/<id>/documenten/<docId>/content
    → 200, application/vnd.openxmlformats-…  51.586 Bytes
```

Am 2026-09-03 belegt: `Geheimhoudingsverklaring` (Nota van Inlichtingen), gültiges
Word-Dokument, **51.586 Bytes — exakt die von der API gemeldete Größe**, anonym mit
blankem `curl`.

**robots.txt sperrt nur CMS-Verwaltungspfade** (`/cms/admin/`, `/cms/user/login`, …).
Nichts, was Vergaben, Dokumente oder die API betrifft.

### Was diese API besser macht als alles bisher Gesehene

| | |
|---|---|
| `grootte` | die Größe vorab — man weiß, was man holt, bevor man holt |
| `typeDocument` | Format mit Code und Klartext |
| `publicatieCategorie` | wozu das Dokument gehört (z. B. „Nota Van Inlichtingen" = Bieterfragen) |
| **`virusIndicatie`** | die Plattform hat die Datei geprüft und sagt es |
| `datumPublicatie` | je Dokument, nicht nur je Vergabe |

⚠ **`publicatieCategorie` ist ein direkter Treffer für unser Fragenkatalog-Modell**
(`docs/bieterfragen-datenmodell.md`): die Niederlande kennzeichnen die Nota van
Inlichtingen als eigene Kategorie. Was wir in Deutschland aus Dateinamen erraten müssen,
steht hier als Feld.

## 3. ⛔ Mercell (22 %) — gesperrt, und zwar länderübergreifend

Vorgezogen geprüft, weil Mercell in mehreren Ländern auftaucht. Zwei Hosts, zwei Antworten:

| Host | robots.txt |
|---|---|
| `s2c.mercell.com` (die Vergabeplattform) | **`User-agent: * / Disallow: /`** |
| `www.mercell.com` (Marketing/Suche) | nur neun einzelne Seiten gesperrt |

**Die Plattform selbst ist vollständig untersagt.** Da Mercell Nordeuropa, das Baltikum
und Benelux mit derselben Software bedient, gilt dieses Urteil überall dort mit — was die
Sondierung der nordischen Länder von vornherein eintrübt.

## 4. Stand nach acht Ländern

| Land | Anteil EU | bestätigt skriptfähig |
|---|---:|---|
| DE | 21,2 % | 32 % |
| FR | 15,4 % | **0 %** |
| PL | 14,6 % | 19 % / 35 % |
| ES | 6,7 % | 5 % |
| IT | 4,9 % | 4 % |
| CZ | 4,4 % | 28 % |
| BE | 3,6 % | offen (Ausfall) |
| **NL** | **2,5 %** | **73 %** |

Zusammen **73,3 %** aller EU-Ausschreibungen. **Die Niederlande sind der beste bisher
gemessene Wert — besser als Deutschland.**
