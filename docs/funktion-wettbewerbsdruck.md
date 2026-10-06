# Funktion: Wettbewerbsdruck je Ausschreibung

**Spezifikation, Stand 2026-10-04.** Jede Schwelle unten ist an den eigenen Daten gemessen, nicht
gesetzt. Die Zahlen tragen ihr Messdatum, weil sie mit dem Bestand wandern.

**Warum diese Funktion:** alle sechs Wettbewerber verkaufen dasselbe Versprechen — *mehr
Ausschreibungen finden*. Diese Funktion verkauft das Gegenteil: **auf weniger bieten, aber auf die
richtigen.** Sie ist die einzige Zahl, die einem Bieter sagt, ob ein Angebot die Tage wert ist, die
es kostet. Und sie braucht genau das, was kein Bieterwerkzeug hat: Jahre Zuschlagshistorie mit
Bieterzahlen. Wettbewerbsvergleich: `docs/` → Analyse „goVisor im Wettbewerbsfeld" (Artefakt).

---

## 1. Was der Nutzer sieht

Eine Zeile auf jeder offenen Vergabe, in Trefferliste und Detailansicht:

> **Wettbewerbsdruck: niedrig.** Bei dieser Stelle in diesem Feld traten im Median **1 Bieter** an;
> in **21 von 21** Verfahren war es genau einer. *(Stelle und Feld, 2019–2026)*

Drei Stufen im Text, aus dem Median abgeleitet: **niedrig** (1–2), **mittel** (3–5), **hoch** (6+).
Die Einstufung ist Beiwerk; **die Zahl und die Fallzahl sind die Aussage.**

## 2. Datengrundlage (gemessen 2026-10-04, DE)

| | |
|---|---:|
| Verfahren mit veröffentlichter Bieterzahl, Stelle + Feld bekannt | **91.484** |
| Offene DE-Vergaben mit Stelle + Feld | 89.602 |
| Zellen (Stelle × CPV-Division) mit ≥ 10 Fällen | 1.606 |
| Spannweite der Bieterzahl in diesen Zellen, Median | **7** |
| Zellen **ohne jede** Streuung | **2,2 %** |

Der letzte Wert ist der wichtigste: **die Kennzahl unterscheidet wirklich.** Bei der Schweizer
KMU-Quote war genau das nicht so (1 Wert über alle Stellen), und sie las sich trotzdem wie eine
Marktaussage — s. `scripts/pruefe_streuung.py` und den Abschnitt „Kennzahl, die nichts
unterscheidet" in `CLAUDE.md`.

## 3. Bezugsebenen und Rückfall

Viel Genauigkeit zuerst, dann gezielt gröber — dieselbe Bauart wie `band_source` in
`gold.build_value_band_effektiv`. Neues Feld **`druck_quelle`**:

| Stufe | `druck_quelle` | Bedingung | Deckung DE |
|---|---|---|---:|
| A | `stelle_feld` | Stelle × CPV-Division, **n ≥ 10** | 46,8 % |
| B | `stelle_feld_knapp` | Stelle × CPV-Division, **n ≥ 5** | **57,0 %** |
| C | `stelle` | nur Vergabestelle, **n ≥ 10** | bis 67,8 % |
| D | `feld` | nur CPV-Division, **n ≥ 20** | bis 100 % |
| E | `keine` | Stelle oder CPV fehlt, oder n < 5 | Rest |

⚠ **Harte Regel: unter fünf Fällen wird keine Zahl gezeigt**, auf keiner Stufe. Lieber eine leere
Zeile als eine Zahl aus drei Verfahren.

**Zeitfenster:** rollierend 84 Monate. Begründung: der Median der Bieterzahl liegt in DE acht Jahre
konstant bei 3 (gemessen 2026-10-04, 2019–2026) — ein kürzeres Fenster kostet Fallzahl, ohne
Genauigkeit zu gewinnen.

## 4. Was je Stufe angezeigt wird

| Angabe | A | B | C | D |
|---|:-:|:-:|:-:|:-:|
| Median Bieterzahl | ✓ | ✓ | ✓ | ✓ |
| Anteil Einzelbieter | ✓ | ✓ | ✓ | ✓ |
| Fallzahl `n` | ✓ | ✓ | ✓ | ✓ |
| Bezugsebene im Klartext | ✓ | ✓ | ✓ | ✓ |
| Nennung der Vergabestelle im Text | ✓ | ✓ | ✓ | — |
| Hinweis „deutet nur grob" | — | ✓ | ✓ | ✓ |

**Die Fallzahl steht immer dabei.** Eine Quote ohne `n` ist in diesem Produkt ein Fehler, keine
Stilfrage.

## 5. ⛔ Der Sicherheitsteil: niedriger Druck ≠ freie Bahn

**Der Teil, der über Vertrauen entscheidet.** Ein Feld mit 100 % Einzelbietern heißt zwei
vollkommen verschiedene Dinge:

- **Chance:** niemand bemerkt diese Stelle, die Hürden sind normal.
- **Falle:** die Bedingungen sind so zugeschnitten, dass nur der Amtsinhaber liefern kann.

Wer das nicht unterscheidet, schickt Kunden in unbietbare Verfahren — der eine Vertrauensbruch, den
ein Produkt mit unserem Versprechen nicht übersteht.

Zweites Feld **`huerden_quelle`**, und hier ist die Deckung schlecht (gemessen 2026-10-04 an 90.927
offenen DE-Vergaben):

| Quelle | Deckung | taugt für |
|---|---:|---|
| `dokument` — typisierte Extraktion aus den Vergabeunterlagen | **20,3 %** (18.415) | echte Hürdenprüfung |
| `strukturiert` — `lead_requirement` | **8,8 %** (7.974) | echte Hürdenprüfung |
| `kriterien` — `lead_criteria` | 77,5 % (70.462) | **nur** Gewichtung Preis/Leistung, **keine** Eignungshürde |
| `keine` | Rest | nichts |

⚠ **Daraus folgt eine unbequeme Regel:** bei `huerden_quelle = keine` **darf niedriger Druck nicht
als Chance ausgezeichnet werden.** Der Text lautet dann:

> Wettbewerbsdruck niedrig (Median 1, n=21). **Warum nur einer bot, ist hier nicht bekannt** — die
> Unterlagen liegen uns nicht vor. Das kann eine Chance sein oder ein zugeschnittenes Verfahren.

Kein Abzeichen, keine Sortierung nach oben, keine Mail. **Erst mit `dokument` oder `strukturiert`
wird aus der Zahl eine Empfehlung.** Das trifft heute rund ein Viertel der Fälle — und genau dort
ist die Funktion verkaufbar.

## 6. Wortlaut — was nicht geschrieben werden darf

| Verboten | Grund | Stattdessen |
|---|---|---|
| „Prognose", „voraussichtlich", „es werden X Bieter antreten" | **Es ist Historie, kein Modell.** Am 2026-10-04 stand genau diese Behauptung unbelegt in der Marktanalyse und musste zurückgenommen werden | „in n Verfahren traten im Median X an" |
| „garantiert", „sichere Chance" | s. Abschnitt 5 | „niedriger Wettbewerbsdruck" |
| eine Quote ohne Fallzahl | nicht prüfbar | immer mit `n` |

## 7. Wo es im Code ansetzt

- **Aggregat: existiert schon, gespiegelt.** `web/components/explorer/VergabeblickView.tsx` zeigt
  der Vergabestelle denselben Bieter-Median (`bieterMedian`, `bieterN`), gespeist aus
  `/api/strategie`. Im Kopf der Datei steht das Architekturprinzip ausdrücklich: *„rollen-agnostischer
  Kern: identische Aggregate, gespiegelte Sicht"*. **Die Bietersicht ist die Spiegelung von etwas
  Gebautem**, kein neues Fundament.
- **Gold:** neue Tabelle `lead_wettbewerbsdruck` je `lead_id` mit `druck_median`,
  `druck_einzel_pct`, `druck_n`, `druck_quelle`, `huerden_quelle`.
  ⚠ **Fremdschlüssel in `scripts/pruefe_gold_integritaet.py` eintragen** — Pflicht für jede neue
  Gold-Tabelle mit Schlüssel, sonst wächst dieselbe Lücke nach, die 44 Tabellen ungeprüft ließ.
- **Rohdaten:** `num_tenders` aus `silver/<Land>/awards`, CPV-Division aus `notices.cpv_main`,
  Käufer über `lead_export.buyer_name`.
- **Zweite Hälfte, fertig und belegt:** der Verdrängbarkeits-Score beantwortet „wie gut verteidigt
  der Amtsinhaber": **AUC 0,767**, Brier-Lift +19,1 %, ECE 0,016, fünffach kreuzvalidiert auf
  17.934 echten Nachfolge-Labels (`scripts/score_backtest.py`, Stand 2026-07-23).
  ⚠ **Nicht nach `sklearn` oder `roc_auc` suchen und daraus „kein Modell" schließen** — der AUC ist
  von Hand über Rangstatistik gerechnet. Dieser Fehlschluss ist schon zweimal passiert, s.
  Auto-Memory `govisor-negativbefunde`.

## 8. Wächter, die mitgebaut werden

Ohne diese drei ist die Funktion nicht fertig, sondern nur gebaut (Fehlerklasse „gebaut, aber nicht
verdrahtet", s. `CLAUDE.md`):

1. **Streuungs-Sonde:** Eintrag in `scripts/pruefe_streuung.py`. Rot, wenn der Anteil Zellen ohne
   Streuung je Land 10 % übersteigt — **aber erst ab 30 Zellen im Land.** Darunter lautet das Urteil
   **„zu wenig Daten"**, nicht „grün". Begründung in Abschnitt 9.
2. **Stufentreue:** Test, dass `druck_quelle` nie eine Ebene nennt, die nicht benutzt wurde, und
   dass **keine Zeile mit `druck_n` < 5** ausgeliefert wird.
3. **Wortlautwächter:** Lint über die Oberflächentexte, rot bei „Prognose", „voraussichtlich",
   „garantiert" in diesem Baustein.
   ⚠ **Muss Kommentare strippen**, sonst schlägt er an der eigenen Dokumentation an — dieser Fehler
   ist an einem Tag fünfmal passiert, s. Auto-Memory `waechter-messen-prosa-statt-code`.

## 9. Die anderen Länder (gemessen 2026-10-04)

Hier stand zuerst ein offener Punkt mit der Erwartung, die Felder seien im Ausland dünn — wie
`value_eur` in der Schweiz mit 1 %. **Die Erwartung war falsch. Die Bieterzahl ist im Ausland besser
gedeckt als in Deutschland.**

| Land | Zuschläge | mit Bieterzahl | Deckung | Median | Einzelbieter |
|---|---:|---:|---:|---:|---:|
| **LU** | 211.047 | 198.369 | **94,0 %** | 4 | 17,4 % |
| **CH** | 68.549 | 62.284 | **90,9 %** | 4 | **11,2 %** |
| **AT** | 260.525 | 216.270 | **83,0 %** | 2 | **45,3 %** |
| DE | 1.198.178 | 878.843 | 73,3 % | 3 | 21,3 % |
| PL | 558.156 | 218.087 | 39,1 % | 1 | **56,3 %** |

⭐ **Marktbefund, der es wert ist:** Österreich ist mit **45,3 % Einzelbietern** mehr als doppelt so
unumkämpft wie Deutschland, die Schweiz mit 11,2 % das Gegenteil. Für einen Bieter ist AT der
Chancenmarkt und CH der harte. Polen liegt bei 56,3 %.

### Wie weit der Rückfall je Land trägt

| Land | Historie | offen | Stelle × Feld ≥5 | nur Stelle | nur Feld | Zellen ≥10 | ohne Streuung |
|---|---:|---:|---:|---:|---:|---:|---:|
| **AT** | 17.614 | 17.746 | **77,6 %** | 90,5 % | 100 % | 261 | 9,6 % |
| DE | 91.484 | 89.602 | 57,0 % | 74,7 % | 100 % | 1.606 | 2,2 % |
| **CH** | 6.854 | 8.508 | 54,1 % | 70,2 % | 99,9 % | 145 | **0,7 %** |
| **LU** | 353 | 519 | **25,8 %** | 51,3 % | **59,9 %** | **6** | **16,7 %** |

### Entscheidung je Land

| Land | Entscheidung |
|---|---|
| **AT** | **Mitausliefern, und zwar zuerst.** Beste Deckung im ganzen Bestand (77,6 % auf der genauen Ebene, gegen 57,0 % in DE) und gleichzeitig der Markt mit der stärksten Botschaft |
| **CH** | **Mitausliefern.** Deckung wie Deutschland, mit 0,7 % flachen Zellen die sauberste Streuung von allen |
| **LU** | ⛔ **Stufe A und B dort NICHT ausliefern.** 353 Verfahren Historie, **sechs** Zellen mit zehn Fällen, 16,7 % davon flach. LU bekommt höchstens `feld`, sonst `druck_quelle = keine` — und sagt das |
| **PL** | Die Daten sind da: **218.087 Verfahren mit Bieterzahl liegen in Silber**, es gibt kein Gold. Nicht anschließbar, weil die Goldkette fehlt — nicht weil die Daten fehlen. Steht in `BEWUSST_OHNE_GOLD` |
| **EU** | 1.277 Zuschläge, kein Gold. Nicht anschließbar |

### ⚠ Warum die Wächter-Schwelle eine Mindestzahl braucht

Die naheliegende Schwelle „rot über 10 % flache Zellen je Land" ist an Deutschland kalibriert und
**taugt so nicht**: Luxemburg hat sechs Zellen, eine einzige flache ergibt dort 16,7 %. Österreich
liegt mit 9,6 % auf Zufallsabstand zur Grenze.

Daher: **mindestens 30 Zellen im Land, bevor der Streuungsanteil bewertet wird** — und darunter
„zu wenig Daten" statt „grün". Ein zu kleines Land, das stillschweigend als unauffällig durchläuft,
ist genau die Falle, die bei Luxemburg schon zugeschlagen hat (`_PLZ_STELLEN` fehlte, Abdeckung
blieb 279/279, nur die Genauigkeit war weg — s. `CLAUDE.md`, „DREI EBENEN, NICHT ZWEI").

## 10. Abnahmekriterien

| | Ziel |
|---|---|
| Vergaben mit Zahl und ausgewiesener Ebene | **≥ 95 %** der offenen DE-Vergaben |
| davon auf Stufe A oder B | **≥ 55 %** (gemessen 2026-10-04: 57,0 %) |
| Zeilen mit `druck_n` < 5 | **0** |
| Quoten ohne Fallzahl in der Oberfläche | **0** |
| Fälle `druck_median = 1` **und** `huerden_quelle = keine` mit Chancen-Abzeichen | **0** (Test erzwingt) |
| Zellen ohne Streuung | < 10 % je Land, ab 30 Zellen |

## 11. Ausdrücklich nicht im Umfang

- **Keine Vorhersage für die einzelne Ausschreibung.** Kein Modell, keine Wahrscheinlichkeit, kein
  Score auf dieser Zahl.
- **Keine Verwendung auf der Vergabestellenseite als Verkaufsargument.** Die Seite ist besetzt
  (cosinex mit „Controlling und Reporting", Administration Intelligence AG mit
  Beschaffungsassistenten), und cosinex sieht dort ohnehin die Angebote — also auch die Verlierer,
  die uns aus offenen Daten fehlen.
- **Keine Mail-Benachrichtigung in der ersten Fassung**, solange `huerden_quelle` nur ein Viertel
  der Fälle deckt.

## 12. Fallen, die beim Entwerfen dieser Spezifikation zugeschlagen haben

Drei, alle an einem Tag, alle in `CLAUDE.md` oder der Auto-Memory vorbeschrieben:

1. **„Es gibt kein Modell."** Ich wollte als Einschränkung schreiben, es gebe keinen validierten
   Score — weil die Suche nach `AUC` und `sklearn` im Code nichts fand. Der AUC ist von Hand über
   Rangstatistik gerechnet. Die Memory warnt wörtlich vor genau diesem Fehlschluss.
2. **Eine Schwelle aus einem Land verallgemeinert.** Die 10-%-Grenze war an Deutschland kalibriert
   und hätte Luxemburg sofort rot gemeldet, Österreich zufällig grün. Schwellen aus der gemessenen
   Streuung **aller** Quellen ableiten, nicht aus der größten.
3. **Eine Produktaussage aus dem Gedächtnis.** In der Marktanalyse stand „Bieterzahl-Prognose vor
   der Veröffentlichung" als Alleinstellung. Im Code gibt es keine Prognose, nur historische
   Mediane. **Der Wettbewerber wurde von seiner Produktseite gemessen, das eigene Produkt aus der
   Erinnerung** — dieselbe Asymmetrie hat an diesem Tag vier Behauptungen gekippt.

---

## 13. ⭐ Nachtrag 2026-10-05: der Sicherheitsteil bekommt ein besseres Signal

Abschnitt 5 nennt als Problem, dass niedriger Wettbewerbsdruck zwei entgegengesetzte Dinge heissen
kann — Chance oder zugeschnittenes Verfahren — und dass die Unterscheidung an der schlechten
Deckung der Eignungsanforderungen hängt (Dokumente 20,3 %, `lead_requirement` 8,8 %).

**Dafür gibt es seit dem 2026-10-05 ein direkteres Signal.** Der Zweig `web/grounding-page` hat
`verfahren_status='erfolglos'` von der Ableitung auf die Quelle umgestellt (`TenderResultCode`,
BT-142) und dabei das Feld **BT-144 (`nichtvergabe_grund`)** erschlossen: es sagt, **warum** nicht
vergeben wurde.

**Abdeckung, gemessen 2026-10-05:** 2023 8 %, 2024 84 %, 2025 97 %, **2026 98 %**.

Gemessen an 6.959 erfolglosen Verfahren seit 2025 mit Begründung:

| Lage | Gründe | Anteil | heisst für den Bieter |
|---|---|---:|---|
| **Chance** | `no-rece` (keine Angebote), `all-rej` (alle abgelehnt), `one-admis` | **50,8 %** | hier ist Platz |
| **Sackgasse** | `chan-need` (Bedarf geändert), `ins-fund` (Mittel fehlen), aufgehoben | 27,9 % | kommt so nicht wieder |
| unklar | `other` und Mehrfachangaben | 21,3 % | wie bisher behandeln |

**Allein `no-rece`: 2.368 Verfahren seit 2025, und 831 davon stehen heute als Lead im Bestand.**

### Was das für diese Funktion ändert

`huerden_quelle` bekommt eine **vierte, bessere Stufe** vor den bisherigen:

| Stufe | Quelle | Deckung | Aussagekraft |
|---|---|---:|---|
| **neu** | `grund` — BT-144 des Vorgängerverfahrens | 97 bis 98 % **der erfolglosen** | sagt direkt, ob niemand bot oder der Bedarf weg ist |
| 1 | `dokument` | 20,3 % | echte Hürdenprüfung |
| 2 | `strukturiert` | 8,8 % | echte Hürdenprüfung |
| 3 | `kriterien` | 77,5 % | nur Gewichtung |

⚠ **Die beiden Signale beantworten nicht dieselbe Frage, und sie ersetzen einander nicht.** BT-144
sagt, warum das **letzte** Verfahren scheiterte; die Dokumente sagen, ob **dieser Bieter** die
Hürden dieses Verfahrens nimmt. Ein `no-rece` beim Vorgänger ist ein starker Hinweis auf Platz,
aber kein Nachweis, dass die Eignungskriterien erfüllbar sind. Wer das eine für das andere nimmt,
baut genau die Falle, vor der Abschnitt 5 warnt — nur mit besserem Gewissen.

**Die Regel bleibt deshalb bestehen** und wird nur ergänzt: mit `grund = no-rece` darf die Zeile
als Chance ausgezeichnet werden, muss aber dazusagen, dass die Hürden ungeprüft sind, solange
keine Dokumente vorliegen.

### Und ein Befund über das Messen selbst

Das Signal war **drei Jahre lang blind**: durch die eForms-Umstellung fiel der gemessene
Erfolglos-Anteil von 13,0 % (2019) auf 0,9 % (2024), weil eForms für jedes Los ein Ergebnis
schreibt, auch für eines ohne Gewinner. 11.201 von 12.169 echten Fehlvergaben lagen unter
„unbekannt".

⚠ **Bei der Vermessung der Vergabestellenseite am 2026-10-04 ergab meine eigene Erfolglos-Messung
0,0 % über alle Grössengruppen, und ich habe das als kaputten Join meiner Abfrage abgetan.** Es
war echt. Ein Nullergebnis, für das man eine bequeme eigene Erklärung hat, wird zu schnell
weggeklärt — die unbequeme Lesart („die Quelle ist blind") hätte den Fund drei Wochen früher
gebracht.
