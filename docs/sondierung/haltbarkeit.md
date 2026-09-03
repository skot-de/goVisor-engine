# Wie lange bleiben die Vergabeunterlagen liegen?

**Stand 2026-09-03.** Entstanden, weil Sven eine Behauptung von mir nicht geglaubt hat —
zu Recht.

---

## 1. Die Behauptung, die geprüft werden musste

Ich hatte geschrieben:

> *„TED-Links sind stabil, Dokumente bleiben liegen → kein Zeitdruck."*

Das war **nicht gemessen**, sondern angenommen. Und die Annahme trägt eine Entscheidung:
ob man jetzt flächendeckend sammelt oder später gezielt holt.

## 2. Der Test

Adressen aus dem TED-Paket **2025-07**, also **14 Monate alt**, je vier pro Land, mit
demselben Weg abgerufen, der bei den aktuellen Vergaben funktioniert hat.

| Land | Ergebnis | Bemerkung |
|---|---|---|
| **SI** | ✅ **4/4** | ZIPs bis 3,9 MB |
| **PT** | ✅ **4/4** | AcinGov-ZIPs bis **47,7 MB**, dazu eine AnoGov-Liste |
| **LT** | ✅ **4/4** | 5–10 Dokumente je Vergabe |
| **IE** | ✅ **4/4** | |
| **CY** | ✅ **4/4** | |
| **BG** | ✅ **4/4** | 1,5–4,3 MB |
| **EE** | ✅ **4/4** | ZIPs 0,4–0,8 MB |
| **HU** | ✅ **4/4** | ⚠ drei davon mit **nur einem** Dokument |
| **LV** | ✅ **3/3** | ⚠ siehe §4 |
| **RO** | ✅ **3/4** | bis **42,6 MB**; das vierte baute noch |
| **MT** | 🟡 **2/4** | die zwei Fehlschläge sind **Anmeldeseiten**, nicht Alter |

**39 von 41 Versuchen erfolgreich.** Beide Fehlschläge gehen auf Maltas Anmelde-Teilmenge
zurück — dasselbe Muster, das Irland mit 14 % zeigt, und es hat nichts mit dem Alter zu tun.

## 3. Ergebnis

**Die Behauptung hält.** Vergabeunterlagen von vor 14 Monaten sind in zehn von zehn
geprüften Ländern noch abrufbar, über denselben Weg wie tagesaktuelle.

⚠ **Mit einer belegten Ausnahme, die schon bekannt war:** **Luxemburg** entfernt die
Unterlagen nach Fristende ([lu](lu.md) §3). Dort gilt weiterhin: **jetzt oder nie.**

⚠ **Und einem Verdacht, der nicht geklärt ist:** in Ungarn trugen drei von vier
2025er-Vergaben **nur ein einziges Dokument**, während 2026er-Vergaben typisch 5–15 haben.
Das kann bedeuten, dass Ungarn mit der Zeit ausdünnt — oder dass diese vier Verfahren
schlicht wenig hatten. **Vier Fälle sind zu wenig für eine Aussage.**

## 4. ⚠ Ein Messfehler, der beinahe ein Gegenbeispiel erfunden hätte

Der erste Durchgang meldete **Lettland 0 von 4** — „keine Dokumentkennung auf der Seite".
Das sah nach genau dem Gegenbeispiel aus, das gesucht war.

Es war falsch. Im **Browser** trug dieselbe Seite **acht** Download-Verweise. `curl` bekommt
eine Fassung ohne die Dokumentzeilen; sie entstehen erst im JavaScript-Durchlauf.

Mit den Kennungen aus dem Browser liefen dann **3 von 3** Abrufe durch — darunter
`RTU_2025_62_**Atb_uz_jaut**.pdf`, die Antworten auf Bieterfragen.

> **Für einen Abrufer heisst das:** Lettland braucht eine rendernde Stufe, um die Liste zu
> sehen. Der Abruf selbst ist danach ein schlichter GET. Wer nur `curl` einsetzt, hält ein
> offenes Land für leer — und zwar lautlos, weil eine leere Liste wie ein gültiges Ergebnis
> aussieht.

Das ist dieselbe Fehlerklasse wie das reCAPTCHA bei 3P, das drei Textprüfungen übersahen:
**was der Browser sieht und was `curl` sieht, ist nicht dasselbe — und die Differenz
entscheidet.**

## 5. Was daraus für die Sammelstrategie folgt

| | |
|---|---|
| **LU** | ⏳ **jetzt sammeln oder nie** — belegt vergänglich |
| **RO** | ✅ 2025 abrufbar, aber ⚠ das Archiv muss erst gebaut werden (Status 2 → 3), bei alten Vergaben dauert es sichtbar länger |
| alle anderen geprüften | ✅ **kein Zeitdruck** — später holen ist genauso gut |

**Damit ist die Sammelfrage entschärft:** ausser Luxemburg zwingt uns nichts, heute
loszulaufen. Das Geld ist besser in einen Parser gesteckt als in Plattenplatz.


---

# Teil 2: Wie weit zurück? (2026-09-03)

Svens Folgefrage war die richtige: **nur wo nicht vorgehalten wird, muss man sammeln.**
Also wie weit reicht der Abruf zurück?

## 6. ⚠ Die Grenze liegt in TED, nicht bei den Portalen

Zwei Funde, die zusammen die Antwort ergeben.

**a) Vor eForms gibt es das Feld nicht.** `CallForTendersDocumentReference` ist eForms.
Gelesen, je 6.001 Bekanntmachungen:

| Paket | ContractNotice | davon mit Doku-Link |
|---|---:|---:|
| 2016-06 bis 2022-06 | **0** | 0 |
| 2023-06 | 21 | 21 |
| 2023-11 | 1.207 | 1.202 |
| 2024-02 | 3.105 | 3.098 |
| 2024-06 | 3.205 | 3.191 |

**b) Das Altformat hatte ein eigenes Feld — `URL_DOCUMENT`.** Es existiert bis 2004
zurück. ⚠ Mein Sondierungsskript kannte nur den eForms-Namen und sah deshalb nichts;
dritter Fall derselben Fehlerklasse nach `eforms-country` und dem Namensraum-Präfix.

**Aber wohin zeigt es?** Über 12.000 gelesene Bekanntmachungen je Jahr:

| Jahr | mit `URL_DOCUMENT` | auf **zentraler Plattform** | auf **Käufer-Webseite** |
|---|---:|---:|---:|
| 2016 | 2.220 | 94 (**4 %**) | 2.126 |
| 2018 | 4.676 | 471 (10 %) | 4.205 |
| 2020 | 5.370 | 604 (11 %) | 4.766 |
| 2022 | 4.595 | 764 (17 %) | 3.831 |
| 2023 | 4.730 | 821 (17 %) | 3.909 |

**83 bis 96 % zeigen auf die Webseite des Auftraggebers** — `www.posta.si`,
`blagoevgrad.imeon.bg`, `www.ptuj.si`. Diese Adressen verrotten. Beide 2016/2018-Stichproben
für Bulgarien gaben **HTTP 404**.

## 7. Was tatsächlich noch geht

| Zeitraum | Ergebnis |
|---|---|
| **ab 2024** | ✅ eForms, zentrale Plattformen — belegt 39 von 41 (Juli 2025) |
| **2020–2023** | 🟡 nur die 11–17 % auf zentralen Plattformen. **Belegt geholt:** BG 2022 (5 Dok, 6,21 MB), EE 2022 (1,23 MB), SI 2022 (2,53 MB) |
| **vor 2020** | ⛔ praktisch nichts. Käufer-Webseiten, 404 |

Einzelbelege:

- **LT 2018** — die alte Domain `pirkimai.eviesiejipirkimai.lt` zeigt die Dokumentenliste
  noch **mit Dateinamen**, aber der Abruf gibt **404**. Liste erhalten, Dateien gelöscht.
- **MT 2018** — Anmeldeseite.
- **BG 2016/2018** — beide Käuferseiten tot.

## 8. ⚠ Zwei Korrekturen an mir selbst

**„Ungarn dünnt aus" — widerlegt.** Ich hatte in Teil 1 vermutet, Ungarn entferne mit der
Zeit Dokumente, weil drei von vier 2025er-Vergaben nur eines trugen. Nachgemessen:

```
2018  EKR000090542018    1 Dok   (nur Wertungszusammenfassung)
2018  EKR000090302018    8 Dok   (inkl. Leistungsbeschreibung, Vertragsentwurf)
2022  EKR000657312022   51 Dok
2022  EKR000802842022    0 Dok
```

**Die Streuung ist verfahrensbedingt, nicht altersbedingt.** Ein Verfahren, das
zurückgezogen wurde, hat wenig; eines mit vielen Losen hat 51. Die Vermutung ist zurückgenommen.

**Und die Paketstruktur wechselt.** Die TED-Monatspakete liegen in **zwei** Bauarten vor:
2020/2024/2025 als `.tar.gz` je Tag, 2018/2022/2023 als XML direkt im Ordner. Mein Leser
stieg nur in die erste ein und meldete für die andere **stumm null**. Wer alte Jahre liest,
muss beide behandeln.

## 9. Was daraus für die Sammelstrategie folgt

**Es gibt nichts nachzuholen.** Ein Dokumentenarchiv beginnt zwangsläufig bei **2023/2024** —
nicht weil Portale löschen, sondern weil TED davor überwiegend auf Käuferseiten zeigte, die
es nicht mehr gibt.

Damit ist die Frage „jetzt sammeln oder später?" endgültig entschärft:

| | |
|---|---|
| **Vergangenheit** | ⛔ verloren, und zwar unabhängig davon, was wir tun |
| **Gegenwart, ausser LU** | ✅ kein Zeitdruck — belegt bis 4 Jahre zurück |
| **Luxemburg** | ⏳ **jetzt oder nie** |

⚠ **Der einzige echte Verlust, der noch läuft, ist Luxemburg.** Alles andere kann warten,
bis ein Parser da ist, der etwas damit anfängt.


---

# Teil 3: Deutschland — und eine Korrektur an Teil 1

Sven fragte nach: *„willst du mir damit sagen, dass ich selbst in Deutschland auf eine
Ausschreibung von 2016 klicken und die Dokumente noch runterladen kann?"*

**Nein. Und in Deutschland nicht einmal für 2025.**

## 10. ⚠ Deutschland verhält sich anders als der EU-Schnitt

In Teil 2 stand, vor 2020 zeigten 83–96 % der `URL_DOCUMENT` auf **Käufer-Webseiten**, die
verrotten. **Für Deutschland stimmt das nicht.** Die deutschen Werte zeigen schon 2016 auf
zentrale Plattformen:

| Jahr | DE-Bekanntmachungen mit `URL_DOCUMENT` | häufigste Ziele |
|---|---:|---|
| 2016 | 25 % | evergabe.nrw · evergabe-online · dtvp · subreport |
| 2018 | 41 % | evergabe-online · dtvp · meinauftrag.rib · evergabe.nrw |
| 2020 | 42 % | dtvp · meinauftrag.rib · subreport · deutsche-evergabe |
| 2022 | 43 % | dtvp · meinauftrag.rib · subreport · evergabe-online |

Deutschland hatte seine eVergabe-Plattformen also **früh**. Der EU-Befund „Käuferseiten
verrotten" beschreibt Polen, Bulgarien, Slowenien — nicht Deutschland.

## 11. ⛔ Und trotzdem ist nichts mehr da — auch aus 2026

Geprüft, je drei Adressen pro Jahrgang:

| Jahrgang | DTVP | RIB »meinauftrag« | evergabe.nrw |
|---|---|---|---|
| 2016 / 2018 / 2020 / 2022 | ⛔ 404 | ⛔ „no longer publicly available" | ⛔ |
| **2024-06** | ⛔ **404** | — | — |
| **2025-01** | — | ⛔ **„no longer publicly available"** | ⛔ **404** |
| **2025-06** | ⛔ **404** | ⛔ | — |
| **2026-01** | ⛔ **404** | ⛔ | — |

Die Plattformen sagen es selbst:

> **RIB:** *„Announcement not found. The desired announcement is no longer publicly
> available."*
> **DTVP:** *„Ein unerwarteter Fehler ist aufgetreten."* (HTTP 404)

⚠ **Selbst eine Bekanntmachung vom Januar 2026 — acht Monate alt — ist weg.** Die deutschen
Plattformen entfernen die Unterlagen binnen Monaten nach Fristende, nicht nach Jahren.

*(Nicht abschliessend geklärt: `evergabe-online.de` gibt HTTP 400 mit „Cookies benötigt",
`deutsche-evergabe.de` und `subreport.de` antworten mit 200, aber ohne erkennbaren Inhalt.
Drei von sechs Plattformen sind eindeutig, drei unklar.)*

## 12. ⚠ Damit ist meine Aussage aus Teil 1 für Deutschland falsch

Teil 1 schloss: *„ausser Luxemburg zwingt uns nichts, heute loszulaufen."* Das galt für die
zehn geprüften **Ein-Plattform-Länder** — dort lagen 14 Monate alte Unterlagen noch bereit.

**Für Deutschland gilt das Gegenteil.** Und das erklärt rückwirkend, warum goVisor
13 deutsche Abrufer hat, die täglich laufen: in Deutschland ist Sammeln **die einzige
Möglichkeit**. Unser Bestand — **244 GB, 10.165 Vergabe-ZIPs, alle 2026 geholt** — existiert
nur, weil er live abgegriffen wurde. Nachholen wäre unmöglich.

## 13. Die berichtigte Regel

**Aufbewahrung ist Plattformsache, nicht Ländersache — und sie schwankt extrem.**

| | |
|---|---|
| **SI, BG, EE** | Jahre. Belegt bis **2022** abrufbar |
| LT, IE, CY, MT, PT, HU, LV, RO | ≥ 14 Monate belegt |
| **LU** | ⏳ bis Fristende |
| **DE (DTVP, RIB, NRW)** | ⛔ **Monate** — 2026-01 ist schon weg |

⚠ **Wer für ein neues Land entscheidet, ob gesammelt werden muss, misst das an der
Plattform — nicht am Land und nicht am EU-Durchschnitt.** Der Test kostet drei Abrufe:
eine Vergabe von heute, eine von vor einem Jahr, eine von vor drei Jahren.

---

# Teil 4: Die systematische Matrix (2026-09-03)

`scripts/pruefe_aufbewahrung.py`, je Land der **eigene** Abrufweg, je Zelle **drei** Adressen.

## 14. Wie viele von drei Vergaben liefern noch Dokumente?

| Land | 3 Mon. | 8 Mon. | 15 Mon. | 27 Mon. | **51 Mon.** |
|---|---|---|---|---|---|
| **SI** | 3/3 | 3/3 | 3/3 | 3/3 | **3/3** |
| **EE** | 3/3 | 3/3 | 3/3 | 3/3 | **3/3** (33,7 MB) |
| **DK** | 3/3 | 2/3 | 3/3 | 2/3 | **3/3** |
| **BG** | 3/3 | 3/3 | 3/3 | 3/3 | 2/3 |
| **HU** | 2/3 | 3/3 | 3/3 | 2/3 | 2/3 (51 Dok!) |
| **RO** | 2/3 | 2/3 | 1/3 | ⏳ | **belegt: 557 MB** |
| **IE** | 2/3 | 3/3 | 3/3 | 3/3 | 0/1 |
| **CY** | 3/3 | 3/3 | 3/3 | 3/3 | **0/3** |
| **LT** | 3/3 | 3/3 | 3/3 | ✅ *(s. u.)* | ? |
| **MT** | 3/3 | 2/3 | 3/3 | **0/3** | 0/3 |
| **PT** | 3/3 | 1/3 | 2/3 | 1/3 | **0/3** |
| **LU** | **0/3** | **0/3** | **0/3** | **0/3** | — |
| **DE** | **0/3** | **0/3** | **0/3** | **0/3** | **0/3** |
| NL | — | — | — | — | — (Sonde fehlt) |

## 15. Drei Gruppen

**a) Langzeit-Archive — vier Jahre und mehr.**
`SI`, `EE`, `DK`, `BG`, `HU`, `RO`. Slowenien und Estland liefern 2022er Unterlagen
vollständig; Estland eine 33,7-MB-Datei, Rumänien ein **557-MB-Archiv**, Ungarn eine
Vergabe mit **51 Dokumenten**.

**b) Mittelfrist — ein bis zwei Jahre.**
`IE`, `CY`, `MT`, `PT`. Malta bricht bei 27 Monaten, Zypern zwischen 27 und 51, Portugal
schwankt (AcinGov hält, AnoGov verlangt teils Anmeldung).

**c) ⛔ Kein Archiv.**
`LU` (nach Fristende weg) und **`DE`** — **null in allen fünf Jahrgängen, auch bei drei
Monate alten Vergaben.** DTVP und RIB antworten wörtlich *„no longer publicly available"*.

## 16. ⚠ Zwei Zellen waren mein Fehler, nicht der der Portale

**Litauen 2024/2022** meldete „HTTP 302, 0 Dokumente". Ursache: TED verlinkt dort die
**alte** Adressform `pirkimai.eviesiejipirkimai.lt/app/rfq/**rwlentrance_s.asp**`, und meine
Sonde suchte nach `downloadDocForAnonymous`. Über `publicpurchase_docs.asp` kamen
**2 Download-Aufrufe und 3 Dateinamen** — Litauen hält also. Sonde nachgebessert.

**Rumänien** meldete dreimal „Archiv wird erzeugt". Das ist kein „weg": beim Nachfassen
stand die 2022er Vergabe auf **Status 3 mit 557,0 MB**. ⚠ Wer die zweiphasige Quelle mit
einer einzigen Abfrage prüft, hält sie für leer.

> **Die Lehre gilt für jede künftige Prüfung:** eine Sonde, die eine Adressform oder eine
> Wartezeit nicht kennt, meldet „weg" — und „weg" sieht aus wie ein Befund.

## 17. Was daraus folgt

| | |
|---|---|
| **Sammeln zwingend** | **DE** · **LU** — sonst ist es verloren |
| **Sammeln optional** | IE, CY, MT, PT — Fenster von ein bis zwei Jahren |
| **Sammeln unnötig** | SI, EE, DK, BG, HU, RO, LT — die Portale sind das Archiv |

⚠ **Und das erklärt goVisors Bauart rückwirkend.** Die 13 deutschen Abrufer, die täglich
laufen, sind keine Fleissarbeit — sie sind in Deutschland die **einzige** Möglichkeit. Die
244 GB in `data/docs/DE` gäbe es sonst nicht, und sie liessen sich nicht nachholen.

**Für alle anderen Länder ist die Reihenfolge damit umgekehrt:** erst der Parser, dann der
Abrufer. Die Dokumente laufen nicht weg.
