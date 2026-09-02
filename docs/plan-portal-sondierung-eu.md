# Plan: Portal-Sondierung für alle TED-Länder

**Ziel.** Für jedes der 30 TED-Länder drei Fragen beantworten:

1. Welche **unterschwelligen** Portale gibt es?
2. Welche Portale geben **Vergabeunterlagen** heraus (nicht nur Bekanntmachungen)?
3. Von welchen davon lassen sich die Unterlagen **ohne Schranke** einsammeln?

**Was dieser Plan nicht ist.** Er baut keine Abholer, und er nimmt kein Land auf (§0.2). Er sagt, wo sich das Bauen lohnt
und wo es aussichtslos ist. Das Ergebnis ist eine Landkarte, keine Sammlung.

---

## 0. Der Ausgangspunkt, gemessen

`govisor/sources.py` führt bereits 54 Einträge, und die Form stimmt schon:
`tier` (oberschwellig / unterschwellig / beides), `ebene` (bekanntmachung / unterlagen),
`status`, `connector`.

| | Stand heute |
|---|---|
| Einträge gesamt | 54 |
| davon `ebene=unterlagen` | **13 — alle DACH** (11 DE, 1 AT, 1 CH) |
| davon `tier=unterschwellig` | 6 |
| Länder mit nur einem TED-Stub (`status=candidate`) | **30** |

Für 30 Länder kennen wir also die Bekanntmachungsebene und **sonst nichts**. Genau die
beiden fehlenden Schichten sind der Gegenstand dieses Plans.

## 0.1 Die tragende Einsicht: die Arbeitseinheit ist die Engine

Für Deutschland gemessen: **146 Domains laufen auf ~8 Software-Engines**, und der
Zugangsmodus ist **je Engine gleich** — ein DTVP-Muster gilt für dtvp.de, Brandenburg,
Niedersachsen, NRW und Autobahn gleichermaßen. EU-weit sind es 1.251 Domains, aber
mit hoher Wahrscheinlichkeit nur **40 bis 60 Engines**, weil dieselben Anbieter mehrere
Länder bedienen (cosinex im DACH-Raum, Mercell in Nordeuropa und Benelux, Vortal auf
der iberischen Halbinsel, NetServer/Healy-Hudson quer durch).

Wer je Land arbeitet, macht 30 Mal dieselbe Arbeit. Wer je Engine arbeitet, macht sie
einmal. **Der ganze Plan hängt daran, dass Schritt 2 vor Schritt 4 kommt.**

---

## 0.2 ⚠ SONDIERUNG IST KEIN ONBOARDING

**Nichts aus diesem Plan nimmt ein Land auf.** Das Ergebnis ist Wissen über ein Land,
nicht das Land selbst. Diese Trennung muss **maschinell** durchgesetzt werden, nicht
durch Absicht — weil sie schon einmal gerissen ist.

**Der Präzedenzfall:** Beim Bau der Vorgangs-Tabellen wurde nebenbei auch für PL und EU
geschrieben. Damit galten beide schlagartig als aufgenommene Länder, und die
Paritätssonde meldete **40 bestehende Tabellen als Lücke**. Niemand hatte Polen
aufgenommen; es sah nur so aus. Das darf sich hier nicht wiederholen, und zwar
dreißigmal.

**Woran das System ein Land als aufgenommen erkennt:** daran, dass Gold-Tabellen für
das Land existieren. Also gilt ohne Ausnahme:

| | erlaubt | verboten |
|---|---|---|
| Datenausgabe | `data/sondierung/<land>/` | **nie** `data/gold/<land>/`, **nie** `data/silver/<land>/` |
| Papiere | `docs/sondierung/<land>.md` | **nie** `docs/laender/` — das ist die Bibel der aufgenommenen Länder |
| Registry | `status="sondiert"`, `connector=""` | kein `live`, kein `prepared`, kein Konnektorname |

`status="sondiert"` ist ein **neuer** Wert, bewusst getrennt von `research` (eine Quelle
wird untersucht) und von `candidate` (ein TED-Stub, den niemand angefasst hat). Er heißt:
angesehen, beurteilt, nicht angebunden.

**Ein Eintrag ohne `connector` ist ein Befund, kein Anschluss.** Wer später anbindet,
trägt den Konnektor ein und hebt den Status — in dieser Reihenfolge, nie umgekehrt.

**Und eine Prüfung, die das festhält**, weil ein Etikett genau das ist, was bei Polen
versagt hat: sie schlägt an, sobald ein Land mit `status="sondiert"` irgendwo unter
`data/gold/` oder `data/silver/` auftaucht, oder ein Kapitel in `docs/laender/` hat.
Ohne diese Prüfung ist der Rest dieses Abschnitts eine Absichtserklärung.

---

## 1. Die vier Schritte je Land

### Schritt 1 — Portallandschaft aus TED ableiten *(kein Portalzugriff)*

TED nennt in jeder Bekanntmachung das Portal: `CallForTendersDocumentReference…URI`
(der Deeplink zu den Unterlagen) und `TenderingProcess.AccessToolsURI` (der
Kommunikationskanal). Beide Felder sind hoch abgedeckt — für DE zu 96,6 % bei offenen
Vergaben.

Also: Monatspakete des Landes ziehen (TED liefert lückenlos ab 2004, jederzeit
nachholbar — belegt: unsere 2004er Pakete wurden am 18.07.2026 geladen), Domains
auszählen, nach Vergabevolumen gewichten.

**Ergebnis:** Portalliste je Land, nach Menge sortiert, ohne dass ein Portal berührt wird.
Das ist reine Datenarbeit an Material, das wir ohnehin herunterladen.

### Schritt 2 — Domains zu Engines verdichten

Engines sind am URL-Pfad erkennbar, nicht am Domainnamen: `/Satellite/` = cosinex,
`/NetServer/` = Healy-Hudson, `/unterlagen/` = AI, und so fort. Die Erkennung ist
**sprachunabhängig**, sie funktioniert in Portugal wie in Estland.

**Ergebnis:** Engine → Länder-Karte. Erst hier zeigt sich, wie viel Arbeit wirklich
ansteht: jede Engine, die in fünf Ländern läuft, wird einmal geprüft und einmal gebaut.

### Schritt 3 — Unterschwellige Portale *(Recherche, keine Messung)*

⚠ **Der schwächste Schritt, und das muss sichtbar bleiben.** Unterschwellige Vergaben
stehen definitionsgemäß **nicht** in TED. Sie sind aus unseren Daten nicht ableitbar.

Je Land also Schreibtischarbeit: Gibt es eine verpflichtende nationale Plattform auch
unterhalb der Schwelle? Wer betreibt sie? Gibt es eine offene Schnittstelle? Deutschland
ist hier der Sonderfall mit `oeffentlichevergabe.de` (CC0-API, bereits angebunden) —
ob andere Länder Vergleichbares haben, ist offen.

Diese Ergebnisse tragen `status=research` und werden **nicht** mit gemessenen Zahlen
in eine Tabelle gemischt. Ein recherchierter Satz und eine gemessene Quote sehen in
einer Tabelle gleich aus und sind es nicht.

### Schritt 4 — Die Schranke prüfen, je Engine

Für jede Engine **eine** Prüfung, nach fester Reihenfolge:

1. **Zuerst nach der offiziellen Schnittstelle fragen.** API-Dokumentation, Open-Data-
   Seite, `/.well-known/`. Nur wenn es keine gibt, wird die Oberfläche betrachtet.
2. **robots.txt lesen und befolgen.** Ein gesperrter Pfad ist gesperrt, auch wenn er
   funktioniert.
3. **Eine** offene Vergabe ansehen: Kommt man an die Dateiliste? An die Dateien?
4. **Keine Konten, keine Anmeldung, kein CAPTCHA.** Wo eine dieser Grenzen steht, endet
   die Prüfung mit dem Urteil — nicht mit einem Umweg.

**Das Urteil hat vier Werte**, übernommen aus der DACH-Karte, weil sie sich dort bewährt
haben:

| Urteil | Bedeutung | DE-Anteil zum Vergleich |
|---|---|---:|
| `frei_skript` | ohne Anmeldung, per Skript holbar | **32 %** |
| `frei_browser` | rechtlich frei, technisch nur im Browser (Wicket-State, 418-Anti-Bot) | 20 % |
| `login` | Registrierung nötig → für mich Endstation | 14 % |
| `abo` | kommerzieller Aggregator | 1 % |

⚠ Deutschland ist dabei die **Obergrenze, nicht der Durchschnitt**: AT und CH liegen
vollständig hinter Anmeldung. Wer aus den 32 % eine EU-Erwartung ableitet, rechnet sich
reich.

---

## 2. Reihenfolge der Länder

Nach TED-Vergabevolumen absteigend. Der Aufwand je Land ist ungefähr gleich, der Ertrag
nicht.

Die Volumina sind aus den Monatspaketen auszuzählen (Schritt 1 liefert sie nebenbei),
**nicht** aus dem Gedächtnis zu setzen. Bekannt ist nur: Deutschland ist der größte
Einzelveröffentlicher, unser Juni-Paket trägt 14.620 deutsche Bekanntmachungen.

Vorziehen würde ich zwei Gruppen, aus Gründen, die nichts mit Volumen zu tun haben:

- **Länder mit bekanntem Open-Data-Auftrag** (FR mit DECP, mehrere OCDS-Veröffentlicher —
  die Registry führt bereits `decp-bulk` und zwei `ocds-json`-Konnektoren). Wo ein Land
  seine Vergabedaten selbst als Datensatz herausgibt, ist die Wahrscheinlichkeit hoch,
  dass es auch bei den Unterlagen weniger Schranken baut.
- **Länder, deren Engine wir schon kennen.** Läuft NetServer auch in Land X, ist die
  Prüfung dort halb erledigt.

## 3. Was am Ende dasteht

**In `govisor/sources.py`**, nicht in einem Papier daneben: je Land und Ebene ein Eintrag
mit `tier`, `ebene`, `status="sondiert"`, leerem `connector` und dem Schranken-Urteil.
Die Registry ist bereits die Landkarte; sie bekommt Zeilen, keine Geschwister.

**Je Land ein Kapitel** in `docs/sondierung/<land>.md` — in der FORM der bestehenden
DACH-Karte, aber **nicht** in `docs/laender/`. Dort stehen die aufgenommenen Länder;
ein sondiertes Land dort einzutragen wäre genau der Polen-Fehler, nur in Papierform.

**Eine Übersicht** über alle 30: wie viel Prozent des europäischen Vergabevolumens hinter
welcher Schranke liegt. Das ist die Zahl, die die eigentliche Entscheidung trägt — ob
sich ein EU-weites Sammeln überhaupt lohnt.

## 4. Aufwand, ehrlich geschätzt

| Schritt | Aufwand | Bemerkung |
|---|---|---|
| 1 — Landschaft aus TED | **einmalig, automatisch** | ein Lauf über alle Länder; Rechenzeit, keine Handarbeit |
| 2 — Engines verdichten | **einmalig, halbautomatisch** | Muster je Engine, danach maschinell |
| 3 — Unterschwellig | **je Land Handarbeit** | der teuerste Teil, und der unsicherste |
| 4 — Schranke prüfen | **je Engine, nicht je Land** | 40 bis 60 Prüfungen statt 1.251 |

Die Sondierung ist damit **um Größenordnungen billiger als das Bauen**: Deutschland
brauchte 13 Abholer für 32 % Ausbeute. Dieser Plan sagt vorher, wo die nächsten 13
überhaupt etwas bringen.

## 5. Was schiefgehen kann

- **Schritt 3 wird mit Schritt 1 verwechselt.** Recherche und Messung dürfen in keiner
  Tabelle nebeneinanderstehen, ohne dass die Herkunft dransteht.
- **Die Engine-Erkennung greift zu grob.** Zwei Portale mit `/Satellite/` im Pfad müssen
  nicht dieselbe Version fahren. Das Urteil gilt je Engine **und Version**.
- **Aus einer Prüfung wird ein Abzug.** Schritt 4 sieht sich EINE Vergabe je Engine an.
  Wer dabei anfängt, Dateien zu sammeln, macht aus der Sondierung ein Crawling — mit
  allem, was daran hängt.
- **Deutschland als Maßstab.** 32 % sind der beste bekannte Wert, nicht der erwartbare.
- **Ein sondiertes Land sieht aus wie ein aufgenommenes.** Der Polen-Fall (§0.2). Die
  Prüfung dagegen gehört gebaut, BEVOR das erste Land sondiert wird — nicht danach.
