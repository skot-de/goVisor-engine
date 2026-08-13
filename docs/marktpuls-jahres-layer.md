# Marktpuls — Jahres-Layer & Historie (2026-08-13)

Ergänzt `docs/uebergabe-2026-08-13.md`. Was gebaut wurde, was dabei gefunden wurde, was offen bleibt.

---

## 1. Was jetzt da ist

Der Marktpuls hat eine zweite Achse: **ein Wert je Kalenderjahr, je Quelle eine eigene Reihe**,
Bruchstellen markiert. Umschalter „Ansicht: Monate im Jahr / Jahre" im Element.

| Baustein | Ort |
|---|---|
| Aggregation, Serien-Regel, Bruch-Erkennung | `scripts/build_marktpuls.py` (`jahres_layer`, `_serien_regel`, `_brueche`) |
| Historie-Schalter | `--ab-jahr 2004`, im Tageslauf verdrahtet (`scripts/daily_leads.sh`) |
| Anzeige | `web/components/Marktpuls.tsx` (`JahresDiagramm`), `marktpuls.css` |
| Vertrag | `marktpuls.json` `schema: 2`, Block `jahre`; Stand 1 bleibt lesbar |
| Guards | `tests/test_marktpuls.py` (6 neue), 241 Tests grün |

Gemessen: Achse **2004–2025**, 1.137.719 Verfahren, JSON **37,0 KB** (Grenze 50 KB),
Laufzeit **44 s** statt 40 s.

---

## 2. Die Regel, die alle Länder gleich behandelt

> Eine nationale Quelle wird mit TED **zusammengeführt**, wenn sie über das ganze Fenster
> durchgehend liefert. Sonst: **eigene Reihe ab ihrem Beginn**. Nie addieren.

| Land | Achse 2004–2025 | Achse 2021–2025 |
|---|---|---|
| DE | TED ab 2004 + **DÖE ab 2023** (eigene Reihe) | dito |
| CH | TED ab 2016 + **simap ab 2024** (eigene Reihe) | dito |
| AT | TED ab 2004 + **atverg ab 2019** (eigene Reihe) | atverg **zusammengeführt** |

**Die Antwort ist achsenabhängig, und das ist richtig.** atverg liefert über fünf Jahre
durchgehend, über 22 nicht. Deshalb steht der Grund je Reihe maschinenlesbar im JSON
(`grund: basis | durchgehend | beginnt_spaeter`), statt vom Leser rekonstruiert zu werden.

Damit **ist** die Quellen-Zusammensetzung je Jahr die Datenstruktur selbst (`quelle` bleibt
immer einzeln, `serie` gruppiert nur) — es braucht keinen zweiten, ableitbaren Block daneben.

---

## 3. Der teuerste Fund: 93 % von DÖE fielen lautlos weg

`verfahren_tabelle()` verlangte ein `publication_date`. Gemessen tragen aber nur
**8.875 von 102.043** DÖE-`cn` aus 2023 eines.

**Folge:** DÖE war im Marktpuls mit **7.233 statt 98.135** Verfahren für 2023 vertreten — eine
Grössenordnung zu klein, ohne eine Zeile Fehlermeldung. Aufgefallen ist es erst, als der
Jahres-Layer DÖE als eigene Linie zeichnete und die Linie sichtbar falsch lag. In der alten
Anzeige war DÖE aus der Zeitreihe ausgeschlossen — der Fehler hatte sich dort versteckt.

**Auflösung:** Ersatzdatum aus `year`/`month` (`make_date(year, month, 1)`), wo
`publication_date` fehlt. Belastbar, gemessen:

* Die Monate verteilen sich **natürlich über alle zwölf** (7.487 … 4.483) — kein Ingest-Klumpen.
* Wo **beide** Angaben vorliegen, stimmen sie zu **98,3 %** überein (106.872 von 108.706).

**Was sich dadurch an bereits ausgelieferten Kennzahlen ändert** (nicht verschweigen):

| Kennzahl | vorher | jetzt |
|---|---:|---:|
| laufende Ausschreibungen (gesamt) | 9.463 | **12.420** |
| ohne veröffentlichte Frist | 4.708 | 5.601 |
| Frist-Abdeckung | 80,2 % | 84,2 % |

Gegengeprüft: roh tragen 3.413 DÖE-`cn/pin` eine Frist in der Zukunft; der Zuwachs von 2.957
liegt genau darunter (Differenz = Verfahrens-Klammer). **Die alten Zahlen waren zu niedrig,
die neuen sind die richtigen.** Herkunft ist ausgewiesen: `coverage.<land>.datum_nur_monat_pct`
(DE 25,7 %, AT/CH 0 %). Guard: `test_fehlendes_publication_date_wirft_kein_verfahren_weg`.

### Wie weit reicht der Schaden? — nachgemessen, Ergebnis: nur hierhin

Abdeckung von `publication_date` über den **ganzen** Bestand, je Quelle × Bekanntmachungsart
(DE/AT/CH, alle Gruppen > 500 Zeilen):

| | Abdeckung |
|---|---|
| **`DE / doe / cn` — 309.693 Zeilen** | **9,6 %** |
| *alles andere* — TED (legacy/eforms/text/ojs), `atverg`, `simap`, **auch `doe / can` (78.510)** | **100,0 %** |

Genau **eine** Lücke im Bestand, und sie betrifft ausschliesslich **DÖE-Ausschreibungen**.
Daraus folgt der Radius:

* **`scripts/export_strategie.py`** (hartes `publication_date IS NOT NULL`) — **nicht betroffen**:
  es liest nur Zuschläge, und `doe/can` ist zu 100 % datiert.
* **Lead-Strecke — nicht betroffen**, gegengemessen: 3.826 offene Leads stehen auf
  DÖE-Notices. `gold.build_lead_deadline` verlangt ausdrücklich **kein** `publication_date`
  (`… OR n.publication_date IS NOT NULL`) und trägt den Kommentar zum selben Bug-Fix von
  damals — „sonst fielen 4.360 offene cn mit echtem Datum ohne pub raus".
* **`gold.py` Bietfenster-Kalibrierung** (`win`/`gm`, verlangt beide Daten) — **kein Fehler**:
  eine Zeitspanne ohne beide Endpunkte ist nicht messbar. Folge ist nur, dass das geschätzte
  Bietfenster TED-kalibriert ist. Grenze, kein Defekt.

⚠️ Die eigentliche Lehre ist unbequemer: **die Falle war bereits bekannt und in CLAUDE.md
dokumentiert** — `build_lead_deadline` hatte sie 2026-07 schon einmal. `build_marktpuls.py`
entstand später und lief trotzdem hinein. Eine Bedingung auf einem optionalen Feld verwirft
ganze Quellen, ohne zu scheitern; sie fällt nur auf, wenn jemand die Grössenordnung
gegenprüft. Bei jeder neuen Quelle zuerst die Feld-Abdeckung messen, nicht das Feld benutzen.

---

## 4. Bruchstellen — gemessen vs. kuratiert

Ein Knick über 22 Jahre ist häufiger eine Regeländerung als ein Marktereignis. Markiert wird
beides, aber **unterscheidbar** (`art`):

* **`gemessen`** — aus dem eigenen Bestand abgeleitet, nachprüfbar: `schema_wechsel`
  (vorherrschende `schema_gen` wechselt), `quelle_start`, `land_start` (nur am Aggregat),
  plus `teiljahre` je Reihe.
* **`kuratiert`** — äusseres Wissen, steht in keinen Daten. Tabelle `REGEL_BRUECHE`, jeder
  Eintrag mit `beleg`. **Bewusst kurz:** die EU-Schwellenwerte werden alle zwei Jahre neu
  festgesetzt — elf Marken auf einer Achse markieren nichts mehr, sie verrauschen sie.

Gemessen für „Alle Länder": 2006 (Regel), 2011 (text→legacy), 2016 (CH tritt hinzu + Regel),
2019 (atverg), 2023 (DÖE), 2024 (simap + legacy→eforms + eForms-Pflicht).

**Teiljahre bleiben stehen, sie werden nur gekennzeichnet** (Konvention „markieren statt
filtern"). Gemessen: CH-TED 2016 hat **5 belegte Monate** (Aug–Dez, 1.843 Verfahren), 2017 sind
es 4.406 — als Jahreswert gezeichnet läse sich das als +139 % Marktwachstum. Ebenso simap 2024
(6 Monate). Das laufende Jahr fehlt ganz; die Achse endet beim letzten vollen Jahr.

---

## 5. Nebenfund: die `ojs`-Reparatur ist eine DE-Reparatur

Der `teiljahr`-Marker meldete **AT 2008 mit 11 Monaten — der Mai fehlt komplett.**

Das ist derselbe TED-Ausfall, der für DE bereits behoben ist: TED liefert 2008-05 nur im
Altformat INTERNAL_OJS, dafür gibt es den dedizierten Parser `schema._parse_internal_ojs`
(`schema_gen='ojs'`, CLAUDE.md). Gemessen: **DE 3.232 `ojs`-Zeilen, AT 0, CH 0** — und im
AT-Bronze liegt kein 2008-Paket.

Nach dem EU-weit-Grundsatz ist das eine Altlast, kein Nebenschauplatz: die Reparatur wurde für
den Testfall gebaut und nie auf die anderen Länder gezogen. **Offen** (Ingest-Ticket, nicht in
dieser Runde gemacht).

---

## 6. Was der Jahres-Layer NICHT tut

* **Keine Summenkurve.** Serien werden nie addiert — in einer Summe wäre ein Quellen-Start von
  echtem Wachstum nicht zu unterscheiden. Preis: DÖE (98k) und simap (1,8k) liegen in einem
  Bild mit sehr verschiedenen Grössenordnungen. Nullbasis bleibt Pflicht, keine Log-Achse.
* **Die Saison bleibt bei 5 Jahren.** Ein Saisonindex über 22 Jahre mit vier
  Schema-Generationen und wechselnder Meldepflicht mittelte Regime, die nichts miteinander zu
  tun haben. `--ab-jahr` verlängert **nur** die Jahresachse.
* **Keine Prognose, keine Einzelverfahren** (Briefing §6, unverändert).

---

## 7. Offen

1. **AT/CH 2008er-`ojs`-Lücke** (Abschnitt 5) — Ingest, eigenes Ticket.
2. ~~Harte `publication_date`-Bedingungen in anderen Gold-Bauern~~ — **erledigt, s. Abschnitt 3:**
   über den ganzen Bestand nachgemessen, genau eine Lücke (`DE/doe/cn`, 9,6 %), alles andere
   100 %. `export_strategie.py` und die Lead-Strecke sind nicht betroffen.
3. **Einbauort** des Elements weiterhin offen (Briefing §9-1) — `/marktpuls` ist Vorschau.
4. **`REGEL_BRUECHE` ist ein Anfang, keine Vollständigkeit.** Drei Einträge, EU-weit gedacht.
   Länderspezifische Meldepflicht-Änderungen (AT, CH) fehlen; wer sie ergänzt, ergänzt den
   `beleg` mit und trägt die Übersetzung in `flat.{en,fr}.json` nach — Guard
   `test_belege_stehen_in_den_sprachkatalogen` prüft nur das Vorhandensein.
5. **Konsolenfehler `… (reading 'sprachen')`** — unverändert offen, nicht aus diesem Strang.
