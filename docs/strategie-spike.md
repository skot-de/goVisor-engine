# Strategie-Bereich (Ticket #10) — Mess-Spike vor dem Bau

Stand 2026-07-26. Ziel: die drei Zahlen holen, von denen die Machbarkeit und die
Bau-Reihenfolge abhängen — statt sie zu schätzen. Ticket §1.2 nennt die Entity-Auflösung
als „Voraussetzung, offen"; §11 führt sie als einzige harte Abhängigkeit.

---

## 1. Entity-Auflösung auf Gewinnern — besser als befürchtet

Die verbreitete Zahl „32,6 % sauber aufgelöst" zählt **Firmen**. Die Strategie-Aggregate
rechnen aber über **Zuschläge** — und da sieht es deutlich besser aus, weil häufig
gewinnende Firmen besser aufgelöst sind.

| Ebene | belegt (HR-exakt / nationale Kennung) | nur Name | unaufgelöst |
|---|---:|---:|---:|
| **je Zuschlag** (relevant) | **65,4 %** | 26,1 % | 8,4 % |
| je Firma | 37,2 % | 52,5 % | 10,2 % |

**Konsequenz:** Akzeptanzkriterium #8 (Anbieter mit `confidence = none` ausschließen) kostet
uns ~35 % der Zuschläge, nicht ~67 %. Die Wettbewerbs-Sektionen sind damit baubar — sie
müssen die Basis nur ehrlich ausweisen („gerechnet auf 65 % der Zuschläge").

## 2. Fallzahlen je Vergabestelle — die „dünn"-Regel trifft den Long Tail, nicht die Praxis

Belegte Zuschläge der letzten 36 Monate: **235.917** über 15.917 Vergabestellen.

| Stufe (§3.1) | Stellen | Anteil Stellen | Anteil **Zuschläge** |
|---|---:|---:|---:|
| `n >= 8` → Prozentwert | 4.077 | 25,6 % | **88,1 %** |
| `n 3–7` → Prozent + „aus n" | 4.129 | 25,9 % | 7,6 % |
| `n 1–2` → nur Absolutwert | 7.711 | 48,4 % | 4,3 % |

**Konsequenz:** Wer eine *aktive* Stelle anschaut, landet fast immer im belastbaren Bereich.
Die Hälfte der Stellen ist dünn — aber sie macht nur 4,3 % des Geschehens aus. Das Ticket
befürchtet zu Recht Falschpräzision; die Schwellenregel ist richtig, wird aber die Nutzung
nicht dominieren. `strategy_thin_data_shown` (§7) bleibt trotzdem das richtige Kontroll-Event.

## 3. Neuzugangsquote schlägt Wechselquote — deutlich

Das Ticket vermutet das in §5.3 („braucht im Gegensatz zur Wechselquote keine Verkettung").
Gemessen bestätigt:

| KPI | berechenbar für | davon belastbar (`n>=8`) |
|---|---:|---:|
| **Neuzugänge/Jahr** | **11.632 Stellen** | — (braucht keine Verkettung) |
| Wechselquote | 7.863 Stellen | nur **2.389** (3.274 unter n=3) |

Ø 3,44 neue Anbieter pro Jahr und Stelle. **4.140 Stellen mit 0 Neuzugängen in 36 Monaten**
(faktisch geschlossen), 5.922 mit ≥3 (offen). Das ist die trennschärfste Antwort auf
„komme ich da rein?" — und sie ist für 48 % mehr Stellen berechenbar als die Wechselquote.

**Konsequenz:** Neuzugangsquote wird der Leit-KPI der Vergabestellen-Sektion, Wechselquote
die Ergänzung mit `duenn`-Kennzeichnung.

## 4. „Bindung" trägt — zu einem Drittel belegt

| | Notices |
|---|---:|
| Rahmen **ohne** erneuten Wettbewerb (`fa-wo-rc`) | 48.128 |
| davon mit bekanntem Gelisteten | **16.782 (34,9 %)** |

**Konsequenz:** §5.7-Regel („‚gesperrt‘ nur bei bekannter Gelisteten-Liste") ist keine
Formalie — sie betrifft **zwei Drittel** der Fälle. Die Sektion zeigt also: 16.782 belegt
gesperrte Rahmen, und daneben ehrlich „Rahmen ohne Wettbewerb, Gelistete unbekannt".
Substanz genug für die Sektion, aber die Überschrift darf nicht „38 % eures Marktes ist
gesperrt" lauten, wenn zwei Drittel davon Vermutung sind.

---

## 5. Empfohlene Bau-Reihenfolge (nach gemessener Belastbarkeit)

Abweichend von §12, das mit der Entity-Härtung startet — die ist laut Messung 1 nicht der
Blocker, für den sie gehalten wurde.

| # | Sektion | Warum hier |
|---|---|---|
| 1 | **Pipeline** | robusteste Daten, erweitert den bestehenden 18-Monats-Radar auf 12/24/36 + Volumen-Split |
| 2 | **Vergabestellen** | Neuzugangsquote ist gemessen der stärkste KPI, 88 % der Zuschläge belastbar |
| 3 | **Bindung** | eigenständiger Differenzierungswert, unabhängig von Entity-Qualität |
| 4 | **Felder** | CPV-basiert, kaum entity-abhängig |
| 5 | **Wettbewerb** | am stärksten entity-abhängig → zuletzt, mit ausgewiesener Basis |
| 6 | Fähigkeiten | braucht Anforderungs-Extraktion aus Vergabeunterlagen |
| — | Position, Profil | Bestand migrieren |

`documents_url` (§5.6/§11: „`ExternalReference.URI` vorziehen") ist **bereits erledigt** —
96,6 % Abdeckung bei offenen Leads, siehe KPI 1.4 in `CLAUDE.md`.

---

## 6. Externe Daten — was die strategische Planung wirklich verbessert

Bewertet nach: (a) behebt eine **gemessene** Schwäche, (b) ist **vorlaufend** (TED ist
strukturell rückwärts-/gegenwartsgewandt, Strategie braucht Frühindikatoren), (c) frei.

### 6.1 Förderprogramme als Frühindikator — der stärkste Hebel

TED zeigt, was **ausgeschrieben ist**. Ein Förderprogramm zeigt, was **ausgeschrieben werden
wird**. Gemessen am KHZG (Krankenhauszukunftsgesetz, Okt 2020):

| Jahr | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Notices mit KHZG-Bezug | 1 | 31 | 214 | **456** | **484** | 228 | 20 |

**~2–3 Jahre Vorlauf vom Programmstart zur Vergabewelle, dann Abfall.** Weitere belegte
Wellen im Bestand: DigitalPakt Schule (2.986), Sondervermögen (1.574), Gigabit-/
Breitbandförderung (677), kommunale Wärmeplanung (342), EFRE/ELER/ESF (38.156).

Nutzen: „In eurem Feld läuft Programm X noch 18 Monate — danach bricht das Volumen ein"
bzw. „Programm Y startet, die Welle kommt 2027". Genau die quartalsweise GF-Frage.
Quelle: Förderdatenbank des Bundes / Programm-Richtlinien — öffentlich, kein Vertrag nötig.

### 6.2 Handelsregister / Unternehmensregister — hebt die Decke für alles Anbieterseitige

Die dokumentierte Erkenntnis lautet: *„Entity-Resolution über Namen ist ausgereizt — mehr
ginge nur über externe Register."* Messung 1 zeigt, was das wert wäre: die 26,1 %
nur-Name-Zuschläge sind der direkte Deckel über Marktanteilen, Konzentration und Matrix.
Jeder Prozentpunkt hier verbessert **jede** Wettbewerbs-Kennzahl gleichzeitig.

### 6.3 Insolvenzbekanntmachungen — ereignisgetrieben, nicht makro

`insolvenzbekanntmachungen.de`, amtlich und frei. Strategischer Wert: ein insolventer
Wettbewerber ist eine Marktöffnung mit Datum — und ein laufender Vertrag, der neu vergeben
werden muss. Anders als Makro-Indikatoren ist das ein **Ereignis**, kein Durchschnitt.

### 6.4 Vergabekammer-Entscheidungen — Verhaltensprofil der Stellen

Frei veröffentlicht. Zeigt, welche Stellen häufig gerügt werden und welche Zuschläge
gekippt sind. Für „wo lohnt Beziehungsaufbau" ist eine rügeanfällige Stelle ein Risiko-
signal, das aus TED allein nicht sichtbar ist.

### 6.5 Was **nicht** noch einmal auf den Tisch soll

**Regionale Makro-Indikatoren** (Anbieterdichte, Baugenehmigungen, Verschuldung, Kaufkraft).
Dreimal unabhängig gemessen, dreimal flach nach Normierung auf Einwohner — Baugenehmigungen
r = 0,434 absolut, **−0,089 je Kopf**. Destatis gehört ins UI als *Beschreibung* der Region,
nie als Prognose. Siehe `docs/cross-kpis.md` und Auto-Memory `govisor-negativbefunde`.
