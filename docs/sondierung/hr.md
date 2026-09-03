# Sondierung Kroatien

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.**

**Stand 2026-09-03.**

---

## 1. Technisch der beste Fall — und trotzdem zu

| | |
|---|---:|
| `eojn.hr` (EOJN) am Unterlagen-Feld | **99,9 %** (7.946 von 7.955, 12 Monate) |
| Domains insgesamt | 4 (die anderen drei zusammen **9** Nennungen) |
| Links, die ein Verfahren nennen | **100,0 %** (2.062 von 2.062) |

Die Adressen sind kurz und sauber: `https://eojn.hr/tender-eo/84749`.

**Kein einziger Startseiten-Link.** Zusammen mit Bulgarien, Slowenien, Lettland, Ungarn und
Zypern der einzige Wert von exakt 0,0 % — und Kroatien ist davon das grösste.

## 2. ⛔ Die robots.txt erlaubt genau eine Seite

37 Bytes, byte-genau gelesen:

```
user-agent: *
Allow: /$
Disallow: /
```

**`Allow: /$` ist das `$` einer Endverankerung: erlaubt ist genau die Wurzel, sonst nichts.**
`Disallow: /` sperrt den Rest. Damit ist `/tender-eo/84749` — also jede einzelne Vergabe —
untersagt.

⚠ **Das ist kein Standardartefakt.** Ein `Allow: /$` schreibt niemand versehentlich, und es
kommt in keiner Software-Vorlage vor. Anders als bei Griechenlands `nepps` (die
Oracle-Beigabe von 2008) hat hier jemand genau ausgedrückt: *meine Startseite darf in den
Index, meine Vergaben nicht.*

Kroatien ist damit der dritte Fall der Sorte **„verboten, nicht verschlossen"** auf
Landesebene — nach der Slowakei (Freigabeliste) und Schweden (88 % Pfadsperre). Nur die Form
ist neu: eine **Einzelfreigabe** statt einer Liste oder eines Pfadmusters.

## 3. Nach der offiziellen Schnittstelle gefragt — es gibt keine

Nach der eigenen Regel ([[govisor-api-vor-abgriff]]) wurde vor dem Abhaken geprüft, ob der
Staat die Daten anders herausgibt:

| Weg | Ergebnis |
|---|---|
| `data.gov.hr` (nationales Datenportal) | eigene Anwendung, **keine Schnittstelle auffindbar** — kein CKAN, kein Pfad im Bündel |
| `data.europa.eu` (EU-Portal, harvestet HR) | **194 Treffer**, aber ausschliesslich Tabellen **einzelner Gemeinden** (`konjscina.hr`, `obrovac.hr`, …) als XLSX/CSV |
| `eojn.nn.hr` (Vorgängerplattform) | robots erlaubt (`Allow: /`, nur `/administrator` gesperrt), aber die Seite führt zu **Anmeldung** und ist abgelöst |

Die 194 Gemeindetabellen sind keine Quelle für Vergabeunterlagen — es sind
Beschaffungspläne einzelner Kommunen, jeweils eine Datei.

**Es gibt keinen offiziellen maschinenlesbaren Weg zu den kroatischen Vergabeunterlagen.**

## 4. Ergebnis

**Kroatien: 0 % abrufbar.** Nicht aus technischen Gründen — die Plattform ist die
konzentrierteste und sauberste der ganzen Sondierung — sondern weil der Betreiber es
untersagt und keinen Ersatzweg anbietet.

Das ist bitter: nach Volumen wäre Kroatien mit 7.955 Unterlagen-Links (1,9 % der EU) das
grösste noch offene Ein-Plattform-Land gewesen.

## 5. ⚠ Und ein Fehler in meiner eigenen Messung, der das Gegenteil ergab

Der erste Durchlauf meldete für Kroatien **0 % tiefe Links** — also „alle 2.060 Adressen
zeigen auf die Startseite". Das war falsch. Es sind 100 %.

Die Ursache liegt nicht in den Daten: **ich hatte das Tiefenmass zwischen den Ländern neu
hingeschrieben.** Die bulgarische Fassung verlangte sechs Hexzeichen (für GUIDs), und daran
scheiterte `/tender-eo/84749` — eine fünfstellige Nummer in zwei Pfadstücken.

**Eine von Hand je Land nachgezogene Heuristik ist keine Messung.** Sie steht deshalb jetzt
einmal in `scripts/miss_linktiefe.py` und läuft über alle Länder gleich — Einzelheiten und
die drei weiteren Fehler, die sie dabei aufdeckte, in
[`linktiefe.md`](linktiefe.md).
