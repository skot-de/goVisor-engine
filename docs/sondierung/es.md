# Sondierung Spanien

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.** Keine Zeile in `data/gold` oder `data/silver`.

**Stand 2026-09-02.** Landschaft aus dem TED-Monatspaket 2026-06, Schranken an je einem
Fall geprüft, robots.txt zuerst, keine Konten.

---

## 1. Mengengerüst — und eine ganz andere Struktur

| | ES | FR | PL |
|---|---:|---:|---:|
| Bekanntmachungen Juni | 6.876 | 8.027 | 10.179 |
| mit Portal-URL | **40 %** | 69 % | 53 % |
| verschiedene Domains | **75** | 449 | 513 |

**75 Domains gegen 449 und 513.** Spanien ist dramatisch zentralisierter — und die Spitze
ist fast durchweg **öffentliche Hand**: Staatsplattform, dann die Regionen.

⚠ Die 40 % Portalabdeckung sind der niedrigste bisher gemessene Wert und ungeklärt.

| Portal | Anteil | Träger |
|---|---:|---|
| contrataciondelestado.es (PLACSP) | **63 %** | Staat |
| contractaciopublica.cat | 14 % | Katalonien |
| contratacion.euskadi.eus | 8,5 % | Baskenland |
| comunidad.madrid | 3 % | Madrid |
| junta-andalucia.es (4 Hosts) | 7 % | Andalusien |
| contratosdegalicia.gal | 1 % | Galicien |
| portalcontratacion.navarra.es | 1 % | Navarra |

## 2. Schranke — geprüft

### ⛔ PLACSP (63 %) — gesperrt, und das ist ein Widerspruch in sich

```
User-agent: *
Disallow: /
```

Die gesamte Staatsplattform ist für Automaten untersagt. **Gleichzeitig** betreibt sie
einen dokumentierten Open-Data-Ausgang: ZIP-Pakete und ATOM-Syndikation im CODICE-XML-
Format, samt eigenem Werkzeug (OpenPLACSP, EUPL-lizenziert). Eine Syndikation ist ihrem
Wesen nach für Maschinen gedacht — und liegt auf demselben Host, den robots.txt sperrt.

⚠ Auch der Umweg über das nationale Portal `datos.gob.es` trägt nicht: dessen robots.txt
sperrt `/api/` und die Datenexporte.

**Das ist keine technische Frage, sondern eine an den Betreiber.** Ein `Disallow: /` neben
einem Open-Data-Angebot ist vermutlich Unachtsamkeit — aufzulösen ist es durch Nachfragen,
nicht durch einen Umweg. Nicht abgerufen.

### ✅ Katalonien (14 %) — offen, und die kooperativste robots.txt der Sondierung

```
User-Agent: *
Allow: /
Visit-time: 18:00-07:00
Crawl-delay: 1
Request-rate: 60/1m
```

Der Betreiber erlaubt nicht nur, er nennt seine Wunschbedingungen. Zwei Endpunkte, beide
anonym mit blankem `curl` bestätigt:

```
GET /portal-api/perfils-contractant/llistat-documents-organ/<id>   → JSON
GET /portal-api/descarrega-document/<docId>/<hash>                 → PDF
```
→ **HTTP 200, `application/pdf`, 572.366 Bytes, 24 Seiten.** Keine Sitzung, kein Cookie.

⚠ **Ehrlich zur Reichweite dieses Belegs:** geprüft wurde an einem Dokument des
Käuferprofils (Jahresvergabeplan), nicht an den Pliegos einer laufenden Vergabe. Derselbe
`descarrega-document`-Endpunkt bedient beides, aber der Beweis steht bisher nur für den
einen Fall.

⚠ Und eine Eigenheit, die beim Bauen zählt: **TED verlinkt bei Katalonien nur das
Käuferprofil, nicht die einzelne Vergabe.** Der Deeplink ist gröber als in DE oder PL — der
Weg von der Bekanntmachung zur Datei ist damit einen Schritt länger.

### ⛔ Baskenland (8,5 %)

Lange Sperrliste, und darunter ausgerechnet `Disallow: /anuncio_contratacion/` — die
Vergabebekanntmachungen selbst.

### ⛔ Galicien (1 %)

`disallow: /`, mit fünf namentlich erlaubten Seiten (Startseite, Fragen, Abo, Anleitung).

### Ungeprüft

Madrid (3 %), Andalusien (7 %), Navarra (1 %) und der Rest des Schwanzes.
Geprüft sind damit **87 %** der spanischen Portal-URLs.

## 3. Was Spanien für den Plan bedeutet

**Die polnische Vermutung ist widerlegt.** Dort gab der Staat heraus und die kommerziellen
Betreiber sperrten — daraus hatte ich abgeleitet, die Frage je Land laute „wie groß ist der
staatliche Anteil". In Spanien ist es umgekehrt: die **nationale** Plattform sperrt alles,
eine **regionale** gibt vorbildlich heraus.

**Es ist also nicht Staat gegen privat, sondern Betreiber für Betreiber.** Damit fällt die
Abkürzung weg, auf die ich gehofft hatte — jede Engine muss einzeln angesehen werden.

**Stand nach drei Ländern:**

| Land | skriptfähig |
|---|---|
| DE | 32 % |
| FR | **0 %** |
| PL | 19 % ober, 35 % unter |
| ES | **14 % bestätigt**, 63 % gesperrt mit offener Frage |
