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
