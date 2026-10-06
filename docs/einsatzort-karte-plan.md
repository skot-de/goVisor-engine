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

⚠ **Grundmenge und Filter, weil die Zahl sonst nicht nachrechenbar ist.** Alles unten ist
gemessen über **alle** Bekanntmachungen (nicht nur Zuschläge, denn eine Ausschreibung sagt
schon, wo gearbeitet wird), und mit der Bedingung, dass **beide** Seiten auf NUTS-3-Länge
vorliegen (`length(nuts) >= 5`). Ohne diesen Längenfilter sind es 1.164.716 Paare und
73,9 %; goVisor-SECOND hat unabhängig 72,8 % gemessen, und die Abweichung ist exakt dieser
Filter. Nur Zuschläge, mit Längenfilter: 432.765 Paare, 77,1 %. Wer eine dieser Zahlen
zitiert, nennt die Grundmenge mit.

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

⚠ **Die Spalte braucht einen VIERTEN Zustand: „nicht bestimmbar".** Der Leistungsort ist
nur bei 61,1 % der Zuschläge gefüllt (von SECOND gemessen, passt zu unseren 62,4 % auf
Kreisebene). Für die übrigen rund 39 % gibt es gar keine zweite Geografie, dort ist die
Örtlichkeit keine 0 und keine 1, sondern unbekannt. Drei Zustände würden diese Vergaben
stillschweigend den Überregionalen oder den Örtlichen zuschlagen.

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

⛔ **Auf `main` kein Aufrufer.** Die Sonde steht dort rot: „Nutzlast `nachfrage` (27,5 MB)
wird ausgeliefert, aber von keinem Aufrufer geholt." Die Nachfrageschicht ist also gebaut
und auf dem Stand, den Produkt und Nachtlauf benutzen, nicht verdrahtet.

ⓘ **In SECONDs Arbeitsbaum ist sie es.** Dort existiert `/api/nachfrage` und liest die
Bündel; die Sonde hatte den Aufrufer nur nicht gesehen, weil der Dateiname über eine
Variable statt direkt am `ladeMitGrund`-Aufruf stand. Beide Aussagen stimmen, für
verschiedene Bäume — auf `main` gibt es die Route am 2026-10-06 nachgeprüft NICHT. Wer den
Zustand wissen will, prüft den Baum mit, nicht nur die Sonde.

⚠ Sie ist aber auf den **Käufersitz** verortet (`ort`, `plz`, `nuts3` sind die des Käufers)
und fällt damit in die Falle aus Abschnitt 2. Für die 6.094 örtlichen Käufer ist das
richtig, für die 468 überregionalen falsch.

⚠ **Präzise, weil es sonst jemand als Tabellenfehler sucht:** `nachfrage_karte` hat **keine
Auftragnehmer-Dimension**. Die Zelle ist (Käufer-Entität × CPV-4); nach einer einzelnen
Firma kann man sie gar nicht fragen. Der Befund gilt für die geplante **Verwendung**: wer
eine Einsatzort-Karte darauf aufbaut und über den Käufer joint, bekommt für Klostermann
Frankfurt, weil DB Netz dort sitzt. Die Tabelle ist in Ordnung, die Verwendung wäre es
nicht. (Korrektur von goVisor-SECOND, 2026-10-06.)

⚠ **Platzhalter-Entitäten verzerren Käufer-Standorte.** `id:keineAngabe` sammelt 213 Namen
in 114 Orten, 266 Käufer-Entitäten tragen über 20 Namen, 415.867 Vergabezeilen hängen
daran. Die Karte trägt seit dem 2026-10-06 eine Spalte `orte_je_kaeufer` und lässt alles ab
6 Orten aus der Nutzlast. Wer Käufer-Standorte verwendet, nimmt diese Spalte mit, sonst
verortet er den Deutschen Bundestag in Aachen. (Fund von goVisor-SECOND.)

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
