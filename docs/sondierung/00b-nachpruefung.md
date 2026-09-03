# Nachprüfung: was die erste Sondierung übersehen hat

**Stand 2026-09-03.** Auf die Frage, ob die Länderkapitel nur stichprobenartig waren:
**ja, und der Mangel war größer als vermutet.**

---

## 1. Was an der ersten Methode zu eng war

Die zwölf Kapitel stützten sich auf **einen Monat** (2026-06) und **ein Feld**
(`CallForTendersDocumentReference`) — und ich habe je Land nur die **obersten zwölf
Domains** angesehen. Der Rest hieß „unbekannt" und blieb liegen.

**Alle drei Verengungen haben etwas verdeckt:**

| Verengung | Folge |
|---|---|
| ein Monat | die Domainzahl **verdreifacht** sich über zwölf Monate |
| ein Feld | `BuyerProfileURI` allein trägt in DE **872 Domains** — ausgeschlossen als „nicht das Verfahren" |
| Top 12 | im Schwanz standen echte, **nicht gesperrte** Portale mit hunderten Ausschreibungen |

## 2. Die neue Grundlage

`scripts/sondiere_tief.py` liest **zwölf Monate** (2025-07 bis 2026-06), **alle Länder**,
und zählt **jedes URL-Feld getrennt** statt vorab auszuwählen:

```
416.224 Ausschreibungen · 30 Länder · 6 Feldgruppen
```

| Land | Domains 1 Monat | Domains 12 Monate |
|---|---:|---:|
| IT | 538 | **1.533** |
| PL | 511 | **1.368** |
| FR | 443 | **1.250** |
| CZ | 104 | 207 |
| ES | 75 | 151 |
| SE | 7 | 15 |

## 3. Wie viel ich je Land ungeprüft gelassen hatte

Domains mit ≥100 Nennungen, die in keinem Kapitel vorkommen:

| Land | ungeprüfte Domains | Anteil des Landes |
|---|---:|---:|
| **IT** | 45 | **23,7 %** |
| **FR** | 84 | **14,8 %** |
| **PL** | 45 | 7,6 % |
| ES | 11 | 2,8 % |
| CZ | 4 | 2,6 % |
| NL | 3 | 1,5 % |
| BE | 1 | 0,3 % |
| SE, LV | 0 | 0 % |

⚠ Bei EE und LT sah es zunächst nach 30 % bzw. 10 % aus — das waren aber **Käuferwebseiten**
(Krankenhäuser, Städte, Verkehrsbehörden), keine Portale. Die Aussage „ein Land, eine
Plattform" hält über zwölf Monate sogar deutlicher als über einen:

| | Plattform | Anteil am Unterlagen-Feld |
|---|---|---:|
| LT | `viesiejipirkimai.lt` | 8.013 von 8.034 |
| LV | `eis.gov.lv` | 6.349 von 6.363 |
| EE | `riigihanked.riik.ee` | 3.552 von 3.558 |

## 4. Drei länderübergreifende Anbieter, komplett übersehen

Das ist der teuerste Teil des Fehlers: **eine Prüfung hätte mehrere Länder abgedeckt.**

### ✅ Josephine / ProeBiz — OFFEN, und in drei Ländern

`josephine.proebiz.com` (PL 849, CZ 268) und `profily.proebiz.com` (CZ 565), dazu die
Slowakei. **robots.txt: `User-agent: *` ohne jede Disallow-Zeile.**

```
GET /pl/tender/77684/summary                    → Vergabeseite mit Dokumentliste
GET /pl/tender/77684/summary/download/635292    → 200, application/zip, 871.707 Bytes
```

Der Inhalt sind die echten Unterlagen:
```
SWZ.pdf                                              854.147 B
Załącznik nr 5 projektowane postanowienia umowne.doc 128.000 B   ← Vertragsentwurf
Załącznik 2 JEDZ.zip                                  74.317 B   ← ESPD
Załącznik 1 formularz oferty.docx                     23.231 B
```
Anonym, blankes `curl`.

### ⛔ BravoSolution / Jaggaer — gesperrt

`sncf.bravosolution.com` (1.237), `ratp.bravosolution.com` (856), `seamilano.bravosolution.com`.
robots: **`Disallow: /esop`** — und `/esop` ist genau der Anwendungspfad; die Adresse führt
auf `/esop/guest/login.do`. Gesperrt **und** Login.

### ⚠ Vortal — antwortet auf robots.txt mit 403

`community.vortal.biz` (ES 255, Heimatmarkt Portugal). Der Pfad heißt
`/Public/public-tender-documents/<token>`, was nach öffentlichem Zugang klingt — aber der
Server verweigert schon die robots.txt. Nicht weiter verfolgt.

## 5. Was die Reihenuntersuchung sonst ergab

75 ungeprüfte Domains mit ≥200 Nennungen, robots.txt je Host geprüft:

**Frankreich** — der Schwanz besteht aus Instanzen weniger Engines:
- `*.aws-achat.info` (vier Hosts, zusammen ~1.600): **alle `Disallow: /`** — das ist AWS'
  Dateihost, passend zum CAPTCHA-Befund
- `marchespublics.<gebietskörperschaft>.fr` und `marches.ternum-bfc.fr`: tragen den
  **Atexo-Pfad** `/entreprise/consultation/…?orgAcronyme=` — fallen unter das bereits
  geprüfte Login-Urteil
- `pha2.edf.com`, `pha2.enedis.fr`, `demat.centraledesmarches.com`: `Disallow: /`
- **`e-marchespublics.com`** (1.484, eigene Engine, robots erlaubt): die Vergabeseite
  verlinkt `/dossier_de_consultation_marche_public_**anonyme**_<hash>` — die Adresse nennt
  den anonymen Weg selbst. ⚠ **Dahinter stehen Anmeldeformulare und ein CAPTCHA.**
  Dieselbe Bauart wie AWS-Achat.

**→ Frankreich bleibt bei 0 %** — aber jetzt sind die beiden größten Engines geprüft, nicht
nur eine, und beide zeigen dasselbe Muster: anonymer Abruf rechtlich zugesichert, per
Bildrätsel gesperrt.

**Italien** — neue Familien, die im Kapitel fehlten:
- `*.traspare.com` (2 Instanzen), `*.tuttogare.it`, `*.acquistitelematici.it`,
  `*.aflink.it`, `giada.areacom.eu`
- regionale Systeme: `stella.regione.lazio.it`, `eappalti.regione.fvg.it`,
  `eproc.empulia.it` (Apulien), `sardegnacat`, `bandi-altoadige.it`
- **`PortaleAppalti`** (Maggioli, viele Kommunen): `Disallow: /` mit Ausnahmen **nur für
  Googlebot**
- `acquisti.stradeanas.it`, `piattaformaacquisti.rai.it`: `Disallow: /`
- `bandi-altoadige.it`, `*.tuttogare.it`: Dateipfade gesperrt

**Polen** — der Schwanz sind **eigene Portale großer Versorger**: `swpp2.gkpge.pl` (1.765),
`przetargi.wody.gov.pl` (1.515), `przetargi.pse.pl`, `swoz.tauron.pl`, `gaz-system`, `enea`,
`metro.waw.pl`. Fast alle **ohne robots-Sperre** — ungeprüft, aber aussichtsreich.

**Spanien** — `licitacions.bcn.cat` sperrt Dateipfade; `larioja.org`, `diba.cat`,
`ajuntament.barcelona.cat`, `elicitadores.adif.es` erlauben.

**Tschechien** — `eveza.cz`: `Disallow: /`.

## 6. Was sich am Gesamtbild ändert

| | vorher | jetzt |
|---|---|---|
| CZ | 28 % | **28 % + Josephine** (proebiz, offen belegt) |
| PL | 19 / 35 % | **+ Josephine**, dazu ein ungeprüfter Versorger-Schwanz |
| FR | 0 % | **0 %, jetzt an zwei Engines belegt statt einer** |
| IT | 4 % | 4 %, aber **23,7 % waren nie angesehen** — jetzt teils geprüft, überwiegend gesperrt |
| LT/LV/EE | „eine Plattform" | **bestätigt**, über zwölf Monate deutlicher |

## 7. Was weiterhin offen ist

- **Polens Versorger-Portale** (7,6 % des Landes, robots erlauben): ungeprüft
- **Italiens neue Familien** `traspare`, `acquistitelematici`, `aflink`, `areacom`:
  robots erlauben, Dokumentenweg ungeprüft
- **Spaniens** `larioja`, `diba`, `adif`: ungeprüft
- **Vortal** (ES/PT): 403 auf robots.txt, nicht weiter verfolgt
- der Schwanz **unter** 100 Nennungen in allen Ländern
