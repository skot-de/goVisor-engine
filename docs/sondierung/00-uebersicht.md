# Portal-Sondierung EU — Gesamtschau

**Stand 2026-09-03.** Neun Länder geprüft, zusammen **75,3 %** aller EU-Ausschreibungen.
Alle Zahlen am TED-Monatspaket 2026-06 gemessen, alle Urteile an mindestens einem echten
Abruf belegt. Kein Konto, kein CAPTCHA, robots.txt immer zuerst.

> ⚠ **SONDIERT HEISST NICHT AUFGENOMMEN.** Kein Land hier hat eine Zeile in `data/gold`.
> `scripts/pruefe_sondierung.py` hält das maschinell auseinander.

---

## 1. Der Stand

| Land | Anteil EU | belegt skriptfähig | Bemerkung |
|---|---:|---:|---|
| **NL** | 2,5 % | **73 %** | offizielle öffentliche API |
| **DE** | 21,2 % | **32 %** | 13 Abrufer gebaut |
| **CZ** | 4,4 % | **28 %** | E-ZAK, leere robots.txt |
| **PL** | 14,6 % | **19 %** ober / **35 %** unter | staatliche Plattform |
| **ES** | 6,7 % | **5 %** | Katalonien |
| **IT** | 4,9 % | **4 %** | Soresa (Kampanien) |
| **BE** | 3,6 % | *offen* | Plattform fällt gerade aus |
| **SE** | 2,0 % | **0 %** | 88 % robots-gesperrt |
| **FR** | 15,4 % | **0 %** | CAPTCHA + Login + robots |

**Gewichtet über die geprüften Länder: rund 17 % der EU-Ausschreibungen sind heute über
einen erlaubten, anonymen Weg erreichbar.** Deutschland allein trägt davon zwei Drittel.

## 2. Fünf Arten, wie eine Tür zu sein kann

Keine dieser Kategorien stand im ursprünglichen Plan. Alle fünf sind erst durch das
Hinsehen entstanden, und sie zusammenzuwerfen wäre der teuerste Fehler:

| | Bedeutung | Wo gesehen |
|---|---|---|
| **`login`** | Konto nötig | FR (Atexo/PLACE 27 %), PL (propublico), AT/CH |
| **`captcha`** | **kein Konto**, nur ein Mensch — der anonyme Abruf ist rechtlich zugesichert und per Bildrätsel gesperrt | FR (AWS 29 %) |
| **`verboten`** | Datei hängt offen da, robots.txt untersagt punktgenau den Abruf | PL (Open Nexus, LoginTrade), IT (Toscana), CZ (NEN), SE (TendSign, e-avrop), ES (PLACSP) |
| **`tot`** | die in TED veröffentlichte Adresse existiert nicht | ES (Andalusien 83 %) |
| **`ziellos`** | Host lebt, robots erlaubt, Datei da — aber die Adresse benennt keine Vergabe | ES (Madrid, Baskenland: 0 % Kennung), IT (ARIA 11 %), CZ (drei kommerzielle: 0 %) |

**`verboten` ist die häufigste.** Sechs Länder, und fast immer punktgenau: `/file*`,
`/zalaczniki/`, `/attachments/download/*`, `/file/get_new/*`. Das sind keine
Nachlässigkeiten, das sind Entscheidungen.

## 3. Drei Vermutungen, die sich nicht gehalten haben

**Der Staat gibt heraus, die Privaten sperren.** Nach Polen naheliegend (staatliche
Plattform offen, Open Nexus und LoginTrade gesperrt). Spanien drehte es um (Staat gesperrt,
Region offen), Tschechien bestätigte die Umkehrung (Staat gesperrt, mandantenfähige
Software offen). **Es ist Betreiber für Betreiber. Es gibt keine Abkürzung über die
Trägerschaft.**

**Die größte Engine zuerst.** In Italien trägt ARIA/Sintel 10 % und führt zu 89 % nur auf
die Portalstartseite; der zersplitterte Schwanz verlinkt zu 72 % direkt. In Tschechien hat
die offene Engine (E-ZAK, 53 % Tiefe) die besten Adressen, die staatliche NEN nur 13 %.
**Nicht die Größe entscheidet, sondern die Brauchbarkeit der Adressen.**

**Deutschland ist der Durchschnitt.** Mit 32 % lag DE lange an der Spitze. Die
Niederlande liegen bei 73 %. Frankreich und Schweden bei 0 %. **Die Streuung ist größer als
der Mittelwert aussagekräftig.**

## 4. Was quer durch alle Länder gilt

**Die offizielle Schnittstelle zuerst zu erfragen hat sich zweimal ausgezahlt** — in Polen
(BZP-API, ohne Antrag, und sie trägt die unterschwellige Ebene) und in den Niederlanden
(öffentlicher Webservice neben einer Zugangsdaten-API). Beide Male wäre der Weg über die
Oberfläche schlechter gewesen.

**Ein Anbieter kann ein halbes Nordeuropa vorab entscheiden.** Mercell sperrt seine
Vergabeplattformen unabhängig vom Hostnamen — `s2c.mercell.com` (NL) und `tendsign.com`
(SE) tragen beide `Disallow: /`. Damit sind Norwegen, Dänemark, Finnland und das Baltikum
vorab eingetrübt, ohne dass sie geprüft wären.

**Ein Viertel bis zwei Fünftel aller Unterlagen-Links zeigen auf eine Portalstartseite:**
FR 39 %, PL 29 %, ES 23 %, DE 23 %. Das ist unabhängig von jeder Schranke einfach kein Weg.

**Und die unterschwellige Ebene ist aus TED heraus unsichtbar.** In Polen direkt gemessen:
an einem Tag mindestens 400 unterschwellige Ausschreibungen gegen ~340 oberschwellige —
mindestens so groß wie die sichtbare Ebene, und **anders gewichtet** (die offene Engine
trägt dort 35 % statt 19 %). Wer die Reihenfolge aus TED allein ableitet, priorisiert falsch.

## 5. Was das für die Ausgangsfrage heißt

Gefragt war, was es kostet, EU-weit Vergabeunterlagen einzusammeln.

**Der Speicher ist es nicht** (25,6 MB je Vorgang, EU-weit rund 7,6 TB im Jahr, bei Hetzner
26 bis 52 € im Monat).

**Und die Konnektoren sind es auch nicht allein.** Sie helfen nur dort, wo eine Tür offen
ist — heute bei rund 17 % der EU-Ausschreibungen. Für die übrigen 83 % ändert kein Abrufer
etwas: gegen ein `Disallow: /file*` hilft keine Technik, gegen ein CAPTCHA kein Konto,
gegen eine Adresse ohne Vergabe-Kennung kein Parser.

**Die Reihenfolge, die sich aus den Zahlen ergibt:**

1. **NL** (73 % offen, offizielle API, sauberste Datenlage) — ein Abrufer, drei Endpunkte
2. **CZ** (28 %, E-ZAK, leere robots.txt, 53 % Adressentiefe)
3. **PL** (staatliche Plattform, und sie bringt die unterschwellige Ebene mit)
4. **ES/IT** je eine Region (5 bzw. 4 %) — kleiner Ertrag, aber sauber belegt
5. **BE** nachholen, sobald die Plattform wieder antwortet

**FR und SE würde ich nicht anfassen.** Nicht weil es schwer wäre, sondern weil die
Betreiber es untersagt haben.

## 6. Noch nicht geprüft

21 Länder mit zusammen 24,7 % der EU-Ausschreibungen, alle unter 2 % einzeln. Dazu
innerhalb der geprüften Länder: FR der 25-%-Schwanz und die unterschwellige Ebene,
PL 11 % Unbekanntes, IT der 61-%-Schwanz (3.339 Adressen mit 72 % Tiefe — der größte
offene Posten überhaupt), ES Navarra, BE der Nachholtermin.
