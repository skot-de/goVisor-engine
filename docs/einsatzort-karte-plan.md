# Einsatzort-Karte: Plan für die Standortplanung

Stand 2026-10-06. Idee von Sven: Firmen mit hohem Rahmenvertrags- oder Projektanteil eine
Heatmap ihrer Einsatzorte zeigen, um Standortentscheidungen zu stützen.

⚠ **Plan, nicht Umsetzung.** Die Nachfrageschicht liegt in `govisor/` und ist Gebiet von
goVisor-SECOND; die Darstellung liegt in `web/`.

---

## 1. Trägt die Idee? Gemessen am 2026-10-06

| | |
|---|---:|
| Zuschlags-Bekanntmachungen mit Leistungsort auf **Kreisebene** | 62,4 % |
| nur auf Bundeslandebene (zu grob) | 340.795 |
| Firmen mit ≥ 10 verorteten Zuschlägen in ≥ 3 Kreisen | **8.549** |
| davon in über 25 Kreisen aktiv | **936** |
| Firmen in genau einem Kreis | 642 |

Beispiel H. Klostermann Baugesellschaft mbH: 474 verortete Zuschläge in **40 Kreisen**,
Schwerpunkte Brandenburg 125, NRW 124, Hessen 124, Berlin 47, Niedersachsen 32.

**Urteil:** 8.549 Firmen sind eine tragfähige Zielmenge, und die 936 mit über 25 Kreisen
haben eine echte Standortfrage. Für die 642 Einkreis-Firmen ist „du bist lokal" ebenfalls
eine Aussage, keine leere Karte.

---

## 2. ⛔ Die zentrale Falle: zwei verschiedene Geografien

Es gibt im Bestand **zwei** Orte je Vergabe, und sie bedeuten nicht dasselbe:

* **Käufersitz** (`notice_parties.nuts` beim `buyer`) — wo die Vergabestelle sitzt
* **Leistungsort** (`notices.performance_nuts`) — wo gearbeitet wird

Gemessen über 1.050.557 verortete Paare: **78,2 %** stimmen überein. Je Käufer mit
mindestens 20 verorteten Vergaben:

| | Käufer |
|---|---:|
| örtlich (Sitz = Leistungsort in ≥ 80 %) | **6.094** |
| überregional (≤ 20 %) | **468** |
| gemischt | 999 |

Die 468 überregionalen tragen überproportional Volumen:

```
DB Netz AG (Bukr 16)                47.778 Vergaben ·  6 % am Sitz
DB InfraGO AG, Fahrweg              11.802           ·  4 %
DB Netz AG                           9.588           ·  7 %
Bundesanstalt für Immobilienaufgaben 3.248           · 18 %
Fraunhofer-Gesellschaft              1.987           ·  6 %
```

⚠ **Warum das der wichtigste Absatz dieses Plans ist.** Am 2026-10-06 habe ich in einem
Mail-Entwurf „Deine Region Hessen" geschrieben, weil DB Netz in Frankfurt sitzt. Die Firma
arbeitet in 40 Kreisen, keiner davon Hessen im eigentlichen Sinn. Eine Karte, die
Käufersitze als Einsatzorte zeigt, behauptet bei Klostermann **einen Punkt in Frankfurt** —
das genaue Gegenteil der Wirklichkeit und für eine Standortplanung schlimmer als keine
Karte.

**Entwurfsregel:** je Käufer eine `oertlichkeit` berechnen (Anteil Sitz = Leistungsort).
Ab 80 % darf der Sitz stehen, unter 20 % muss der Leistungsort verwendet werden, dazwischen
gehört beides gezeigt oder nichts. Die Schwelle ist aus der gemessenen Verteilung
abgeleitet, nicht gesetzt.

---

## 3. Was es schon gibt, und es wird nicht gelesen

`data/gold/DE/nachfrage_karte.parquet`, **83.374 Zeilen**, gebaut mit Commit 9ca372d:

```
country, gewerk, gewerk_label(+en/fr), buyer_entity, buyer_name,
ort, plz, nuts3, lat, lon, geo_quelle, orte_je_kaeufer,
zuschlaege, jahre_belegt, pro_jahr, letzter_zuschlag,
bieter_median, bieter_belegt, einzelbieter, regelmaessig, fenster_von, fenster_bis
```

Geokodierung: 95 % über PLZ (78.695), 979 über den Ort, 3.700 ohne. Exportiert nach
`web/data/nachfrage/` als rund 700 Dateien, aufgeteilt nach Land und Gewerk.

⛔ **Kein Aufrufer.** Das ist die Sonde, die seit dem 2026-10-06 rot steht: „Nutzlast
`nachfrage` (28,9 MB) wird ausgeliefert, aber von keinem Aufrufer geholt." Die
Nachfrageschicht dieser Idee ist also gebaut und nicht verdrahtet.

⚠ Sie ist aber auf den **Käufersitz** verortet (`ort`, `plz`, `nuts3` sind die des Käufers)
und fällt damit genau in die Falle aus Abschnitt 2. Für die 6.094 örtlichen Käufer ist das
richtig, für die 468 überregionalen falsch.

---

## 4. Drei Schichten, getrennt beschriftet

**Schicht 1 — wo ich arbeite.** Eigene Zuschläge je Kreis aus `performance_nuts`. Neu zu
bauen: eine Aggregation je Entität. Abdeckung 62,4 %; Vergaben nur mit Bundesland müssen als
eigene, gröbere Darstellung erscheinen und nicht als Lücke.

**Schicht 2 — wo ich sitze.** Eingetragene Standorte, einschliesslich
Zweigniederlassungen. Quelle ist der anlassbezogene Registerabruf, s.
`docs/handelsregister-anbindung-plan.md`. Am 2026-10-06 für Velten belegt. **Diese Schicht
trennt Standortplanung von Rückblick** — ohne sie zeigt die Karte nur, wo man war.

**Schicht 3 — wo der Markt ist, den ich nicht bediene.** Aus `nachfrage_karte`, aber mit
der Örtlichkeitsregel aus Abschnitt 2. Für überregionale Käufer braucht es eine zweite
Aggregation über Leistungsorte; die Daten dafür liegen in `notices`, nicht in der
Nachfragekarte.

Erst Schicht 3 macht aus der Karte eine Entscheidung:

> 97 Aufträge in Dahme-Spreewald, gefahren von Velten aus. Im Nachbarkreis gibt es X
> Vergaben im Jahr in deinem Gewerk, bei denen du nie angetreten bist.

---

## 5. Reihenfolge und Abnahme

1. **Örtlichkeit je Käufer** als Spalte in der Gold-Ebene, mit der gemessenen Schwelle
2. **Schicht 1** (eigene Einsatzorte je Entität) — allein schon vorzeigbar
3. **Nachfragekarte verdrahten**, Örtlichkeitsregel angewandt; damit wird die rote Sonde
   grün, und zwar richtig und nicht durch Löschen der Nutzlast
4. Schicht 2, sobald der Registerabruf steht
5. Leistungsort-Aggregation für die 468 überregionalen Käufer

**Abnahme, die den Fehler aus Abschnitt 2 erzwingt:** ein Test, der für
H. Klostermann Baugesellschaft mbH prüft, dass die Karte **nicht** Hessen als Schwerpunkt
zeigt. Bei korrekter Rechnung liegt Brandenburg vorn (125 gegen 124). Wer die Geografien
vertauscht, bekommt Hessen als Spitze und einen roten Test.

⚠ Dazu eine Sonde, die anschlägt, wenn `nachfrage_karte` ohne Örtlichkeitsspalte
ausgeliefert wird — sonst wandert der Fehler beim nächsten Umbau lautlos zurück.
