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
