# Portal-Sondierung EU — Gesamtschau

**Stand 2026-09-03.** Zwölf Länder geprüft, zusammen **79,7 %** aller EU-Ausschreibungen.
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
| **LT** | 2,0 % | **99 %** | ein Land, eine Plattform |
| **BE** | 3,6 % | *offen* | Plattform fällt gerade aus |
| **LV** | 1,5 % | *offen* | eine Plattform, Abrufweg ungeklärt |
| **EE** | 0,9 % | *offen* | eine Plattform, ungeprüft |
| **SE** | 2,0 % | **0 %** | 88 % robots-gesperrt |
| **FR** | 15,4 % | **0 %** | CAPTCHA + Login + robots |

**Gewichtet über die geprüften Länder: rund 19 % der EU-Ausschreibungen sind heute über
einen erlaubten, anonymen Weg erreichbar.** Deutschland allein trägt davon die Hälfte.

⚠ **Und ein Maß, das wichtiger ist als die Landesgröße: Ausschreibungen je Domain.**

| | LV | EE | LT | NL | SE | DE | PL | FR | IT |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Domains | **1** | **1** | 2 | ~6 | 7 | — | 511 | 443 | 538 |
| je Domain | **565** | **325** | **369** | ~150 | 105 | ~50 | 11 | 13 | **3** |

Ein Abrufer für Lettland deckt ein ganzes Land. Ein Abrufer für Italien deckt drei
Ausschreibungen. **Wer nach Ertrag je Abrufer sortiert statt nach Landesgröße, fängt im
Baltikum an** — auch wenn die Länder klein sind.

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

**Ein Anbieter kann mehrere Länder auf einmal entscheiden — aber weniger, als man denkt.**
Mercell sperrt seine Vergabeplattformen unabhängig vom Hostnamen: `s2c.mercell.com` (NL)
und `tendsign.com` (SE) tragen beide `Disallow: /`.

⚠ Ich hatte daraus zunächst geschlossen, damit seien „Norwegen, Dänemark, Finnland und das
Baltikum vorab eingetrübt". **Gemessen stimmt das nur für Norwegen:**

| NO | DK | FI | LT / LV / EE |
|---:|---:|---:|---:|
| **63 %** | 11 % | 1 % | **0 %** |

Das Baltikum ist von Mercell gar nicht berührt — und liegt ausgerechnet dort, wo der größte
Hebel ist. Aus einem echten Befund einen Ländervorbehalt zu machen, den man nicht gemessen
hat, kostet mehr, als er spart.

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
ist — heute bei rund 19 % der EU-Ausschreibungen. Für die übrigen 81 % ändert kein Abrufer
etwas: gegen ein `Disallow: /file*` hilft keine Technik, gegen ein CAPTCHA kein Konto,
gegen eine Adresse ohne Vergabe-Kennung kein Parser.

**Die Reihenfolge, die sich aus den Zahlen ergibt:**

1. **LT** (99 % offen, EINE Plattform, servergerenderte Listen — `curl` reicht)
2. **NL** (73 % offen, offizielle API, sauberste Datenlage) — ein Abrufer, drei Endpunkte
3. **CZ** (28 %, E-ZAK, leere robots.txt, 53 % Adressentiefe)
4. **PL** (staatliche Plattform, und sie bringt die unterschwellige Ebene mit)
5. **LV** nachholen (eine Plattform, keine Schranke, nur der POST-Modal-Weg fehlt)
6. **ES/IT** je eine Region (5 bzw. 4 %) — kleiner Ertrag, aber sauber belegt
7. **BE** nachholen, sobald die Plattform wieder antwortet

**FR und SE würde ich nicht anfassen.** Nicht weil es schwer wäre, sondern weil die
Betreiber es untersagt haben.

## 6. ⚠ Eine Ebene fehlt in allen zwölf Kapiteln

`CLAUDE.md` verlangt bei jedem neuen Land **drei** Ebenen, nicht zwei:

1. oberschwellig (TED) — geprüft
2. unterschwellig (nationale Pflichtveröffentlichung) — teils geprüft (PL, ES, FR)
3. **Fonds-Ebene** — Vergaben von **Empfängern öffentlicher Fördermittel**, die selbst
   keine öffentlichen Auftraggeber sind. Die Wettbewerbspflicht gilt EU-weit, die
   Sichtbarkeit ist rein national.

**Die dritte habe ich in keinem der zwölf Länder geprüft.** Die Anweisung sagt sogar, warum
das passiert: sie ist in DACH fast leer und wird deshalb regelmäßig vergessen. Genau das ist
mir passiert.

**Ein erster Blick (2026-09-03), für das eine Land, wo das Portal bekannt ist:**
Polens `bazakonkurencyjnosci.funduszeeuropejskie.gov.pl` hat **keine robots-Sperre**, aber
`/api/announcements` antwortet anonym mit **HTTP 401**. Ob die öffentliche Weboberfläche
ohne Anmeldung Ausschreibungen zeigt, ist offen.

⚠ Für die übrigen elf Länder ist die Fonds-Ebene **nicht einmal identifiziert**. Je mehr
Kohäsionsmittel ein Land bekommt, desto größer dieser sonst unsichtbare Markt — und die
Sondierung sagt darüber bisher nichts.

## 7. Noch nicht geprüft

18 Länder mit zusammen 20,3 % der EU-Ausschreibungen, alle unter 2 % einzeln. Dazu
innerhalb der geprüften Länder: FR der 25-%-Schwanz und die unterschwellige Ebene,
PL 11 % Unbekanntes, IT der 61-%-Schwanz (3.339 Adressen mit 72 % Tiefe — der größte
offene Posten überhaupt), ES Navarra, BE der Nachholtermin.
