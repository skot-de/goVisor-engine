# Feature #11: Treffergüte

**Produkt:** goVisor
**Version:** V1.5
**Status:** Konzept
**Erstellt:** 2026-07-26
**Gate:** Free vollständig zugänglich — bewusst

---

## 1. Zweck

Jeder Nutzer stellt nach zwei Wochen dieselbe Frage: *„Warum stehen in meiner Liste Sachen, die nicht passen — und fehlt vielleicht etwas, das passt?"*

Heute gibt es darauf keine Antwort im Produkt. Der Relevanz-Score erklärt sich pro Lead (`CPV ✓ · Region ✓ · Volumen unbekannt`), aber niemand sagt dem Nutzer, **woran es systematisch liegt** und **was er dagegen tun kann**.

Die Treffergüte-Seite beantwortet genau das. Sie ist gleichzeitig das wichtigste Datenerhebungsinstrument des Produkts — aber nicht als Formular getarnt, sondern weil beides dasselbe ist: Wer bessere Ergebnisse will, muss mehr über sich preisgeben. Das ist ein ehrlicher Handel, und er wird als solcher dargestellt.

### 1.1 Was die Seite ist und was nicht

| Ist | Ist nicht |
|---|---|
| Eine Karte: was wissen wir, was fehlt, was ändert es | Ein Onboarding-Wizard |
| Ein Statusbild mit gemessener Wirkung je Lücke | Ein Fortschrittsbalken |
| Der Ort, an dem man Angaben **überblickt** und nachpflegt | Der einzige Ort, an dem Angaben **erhoben** werden |
| Ehrlich über die Grenzen der Verbesserbarkeit | Ein Versprechen auf perfekte Ergebnisse |

**Der zentrale Punkt zur Erhebung:** Die meisten Angaben werden **nicht hier** abgefragt, sondern im Moment des Bedarfs an anderer Stelle — beim Anforderungs-Check, beim Verwerfen eines Leads, nach einem Zuschlag. Diese Seite zeigt den Stand und holt nach, was im Vorbeigehen nicht erfasst wurde. Siehe Abschnitt 6.

---

## 2. Name und Verortung

### 2.1 Name

Empfehlung: **Treffergüte**

Alternativen, die geprüft und verworfen wurden:

| Kandidat | Warum nicht |
|---|---|
| Suchoptimierung | Klingt nach SEO |
| Passgenauigkeit | Länger, unschärfer |
| Datenqualität | Klingt nach unserem Problem, nicht seinem |
| Profil vervollständigen | Fortschrittslogik, die wir bewusst vermeiden |
| Einstellungen | Verharmlost den Wert |

„Treffergüte" benennt die Sache aus Nutzersicht: die Güte der Treffer in seiner Liste. Es ist sachlich, ungewöhnlich genug um Aufmerksamkeit zu bekommen, und passt zum Tonfall des Produkts.

### 2.2 Verortung

Neunte Sektion im Strategie-Bereich, Gruppe „Wir", direkt **über** Profil.

```
  MARKT                    WIR
  Pipeline                 Position
  Felder                   Fähigkeiten
  Vergabestellen           Bindung
  Wettbewerb               Treffergüte      ← neu
                           Profil
```

Begründung: Treffergüte und Profil sind zwei Sichten auf denselben Datenbestand. Profil zeigt **was hinterlegt ist**, Treffergüte zeigt **was fehlt und was es kostet**. Sie zu trennen ist richtig, weil die Fragen verschieden sind — sie auseinanderzureißen wäre falsch.

### 2.3 Einstiegspunkte außerhalb

Die Seite darf nicht darauf warten, gefunden zu werden. Drei Wege führen hin:

| Ort | Auslöser | Form |
|---|---|---|
| Akquise-Header | dauerhaft | Unauffälliger Textlink „Treffergüte" neben der Trefferzahl |
| Lead-Liste | `zero_results` bei plausiblen Filtern | Zeile im Leerzustand: „Eure Liste ist leer. Möglicherweise fehlen Angaben." |
| Lead-Liste | 5+ `back_to_list_fast` in einer Sitzung | Einmalige, schließbare Zeile über der Liste |
| Bewertungs-Tab | Anforderung ohne hinterlegte Angabe | Direktfrage im Kontext (siehe 6) |

**Regel:** Höchstens ein Hinweis pro Sitzung, geschlossene Hinweise kommen 30 Tage nicht wieder. Ein Produkt, das um Daten bettelt, bekommt keine.

---

## 3. Prinzipien

### 3.1 Kein Prozentscore

Es gibt keinen Vollständigkeitsgrad, keinen Balken, keine Punktzahl. Ein „73 % vollständig" setzt einen Nenner voraus, den wir willkürlich festlegen müssten — das ist Falschpräzision und widerspricht der Grundregel des Produkts.

Stattdessen: **eine Anzahl offener Angaben, sortiert nach gemessener Wirkung.**

> 7 offene Angaben · 3 davon betreffen mehr als 20 eurer Leads

### 3.2 Wirkung statt Aufforderung

Jede Lücke wird mit ihrer gemessenen Auswirkung auf die **aktuelle** Lead-Menge des Nutzers dargestellt. Nicht: „Bitte ergänzen Sie Ihre Zertifikate." Sondern:

> 78 eurer 340 Leads fordern eine Bietungsbürgschaft. Ohne euren Bürgschaftsrahmen können wir nicht prüfen, welche davon ihr stemmen könnt.

Diese Zahl ist immer berechenbar (siehe Abschnitt 7) und immer wahr.

### 3.3 Ehrlichkeit über die Obergrenze

Ein Teil der Streuung ist durch keine Nutzerangabe behebbar. Das gehört sichtbar auf die Seite, nicht ins Kleingedruckte:

> Für 35 % der Vergaben wird kein Auftragswert veröffentlicht. Daran ändert keine Angabe etwas — wir schätzen hier nicht.

Ein Nutzer, der glaubt, er könne durch Fleiß eine perfekte Liste erreichen, wird enttäuscht. Einer, der die Grenze kennt, vertraut den Zahlen mehr.

### 3.4 Keine Gamifizierung

Keine Abzeichen, keine Streaks, keine Bestätigungsanimationen, kein „Gut gemacht!". Die Zielperson ist ein Geschäftsführer oder Bid Manager. Der Anreiz ist die bessere Liste, nicht das Erfolgserlebnis.

---

## 4. Aufbau der Seite

Vier Blöcke untereinander.

```
┌──────────────────────────────────────────────────────────────┐
│  Treffergüte                                                 │
│                                                              │
│  340 Leads in eurer Liste · 7 offene Angaben                 │
│  3 davon betreffen mehr als 20 Leads                         │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  1  Was eure Liste jetzt ändern würde                        │
│     Offene Angaben, nach Wirkung sortiert                    │
├──────────────────────────────────────────────────────────────┤
│  2  Was wir über euch wissen                                 │
│     Hinterlegtes, getrennt nach gemessen und erklärt         │
├──────────────────────────────────────────────────────────────┤
│  3  Was ihr freischaltet                                     │
│     Reziprozität: Ergebnismeldungen                          │
├──────────────────────────────────────────────────────────────┤
│  4  Was wir nicht verbessern können                          │
│     Grenzen der Datenlage                                    │
└──────────────────────────────────────────────────────────────┘
```

### 4.1 Block 1 — Was eure Liste jetzt ändern würde

Liste offener Angaben, absteigend nach betroffener Lead-Anzahl. Je Eintrag: Was fehlt, wie viele Leads betroffen sind, was passieren würde, und eine Erfassungsmöglichkeit direkt in der Zeile.

```
  ▸ Bürgschaftsrahmen                            betrifft 78 Leads
    78 eurer Leads fordern eine Bietungsbürgschaft. Ohne die Höhe,
    die eure Bank stellt, können wir nicht prüfen, welche davon
    für euch überhaupt in Frage kommen.
    [ bis 50.000 € ] [ bis 250.000 € ] [ bis 1 Mio € ] [ darüber ]

  ▸ Größter Auftrag, den ihr allein stemmt       betrifft 61 Leads
    61 Leads liegen über 2 Mio €. Wir wissen nicht, ob das für euch
    realistisch ist oder nur mit Partner.
    [ Betrag eingeben ]

  ▸ Data Engineering                             betrifft 34 Leads
    34 Ausschreibungen in eurem Markt fordern Data-Engineering-
    Kompetenz. Wir wissen nicht, ob ihr das im Haus habt.
    [ Eigenes Team ] [ Über Partner ] [ Nein ]

  ▸ Region auf Landkreisebene                    betrifft 29 Leads
    Ihr habt Bayern hinterlegt. 29 Leads liegen in Regionen, die
    mehr als 200 km von euch entfernt sind.
    [ Landkreise wählen ]

  ▸ ISO 27001                                    betrifft 22 Leads
  ▸ Herstellerpartnerschaften                    betrifft 14 Leads
  ▸ Parallele Angebotskapazität                  betrifft  6 Leads
```

**Interaktionsregel:** Jede Angabe ist in der Zeile selbst erfassbar. Kein Sprung in ein Formular, kein Dialog. Nach der Eingabe aktualisiert sich die Zahl oben, und die Zeile verschwindet in Block 2.

**Sortierregel:** Nach betroffener Lead-Anzahl, nicht nach Kategorie. Ein Nutzer soll oben anfangen und irgendwann aufhören können — die Reihenfolge garantiert, dass die ersten drei Minuten am meisten bringen.

### 4.2 Block 2 — Was wir über euch wissen

Übernimmt die bestehende Trennung aus dem Profil-Tab: `gemessen` (aus gewonnenen Vergaben abgeleitet) gegen `erklärt` (selbst angegeben, unbestätigt).

```
  Gemessen                        aus 14 gewonnenen Vergaben
  ─────────────────────────────────────────────────────────────
  Managed Services                 8 Vergaben · zuletzt 03/2026
  Netzwerk & Infrastruktur         4 Vergaben · zuletzt 11/2025
  Regionen                         Bayern, Bund
  Typischer Auftragswert           180.000 € (Median)
  Auftraggeber                     6 Vergabestellen

  Erklärt                          von euch angegeben
  ─────────────────────────────────────────────────────────────
  Data Engineering                 6–15 Personen · seit 2023   ⚠
  ISO 27001                        gültig bis 08/2027
  Bürgschaftsrahmen                bis 250.000 €
  Größter Auftrag allein           800.000 €
  Stand: 03/2026 — stimmt das noch?               [ Bestätigen ]
```

**Der Widerspruchshinweis (⚠)** ist inhaltlich wertvoll und gehört hierher:

> Data Engineering ist seit 2023 angegeben. In diesem Feld haben wir in 24 Monaten keine gewonnene Vergabe unter eurem Namen gefunden — in euren Regionen wurden 34 ausgeschrieben.

Das ist keine Fehlermeldung, sondern eine strategische Beobachtung. Sie zeigt, dass die Seite mehr kann als Häkchen sammeln.

**Alterung:** Erklärte Angaben tragen ein Datum. Nach 6 Monaten erscheint die Bestätigungszeile. Ein Klick bestätigt alle, einzelne sind änderbar. Kein Neuausfüllen.

### 4.3 Block 3 — Was ihr freischaltet

Die Reziprozitätsachse. Hier wird der Handel offen benannt.

```
  Wettbewerbsdaten                          2 von 3 Meldungen

  Für Ausschreibungen gibt es keine öffentliche Bieterliste. Wer
  gegen wen antritt, weiß nur, wer dabei war. Wenn ihr eure
  Ergebnisse meldet, könnt ihr sehen, was andere gemeldet haben.

  ●●○   Ab 3 Meldungen    Wettbewerbsmenge eurer Vergabestellen
  ○○○   Ab 10 Meldungen   Eure Gewinnquote, Rangverteilung,
                          Vergleich zum Marktdurchschnitt

  Offen: 4 entschiedene Vergaben, bei denen ihr beworben wart
  ─────────────────────────────────────────────────────────────
  BMI Managed Services         Zuschlag 03/2026   [ Ergebnis melden ]
  LK Rosenheim IT-Support      Zuschlag 02/2026   [ Ergebnis melden ]
```

**Zwei Regeln, die im Interface stehen müssen:**

1. **Meldungen lösen nie eine Erfolgsprämie aus.** Auslöser bleibt ausschließlich der Klick auf den Bewertungs-Tab plus der über TED erkannte Zuschlag. Wer einen Verlust meldet, zahlt nichts. Wer einen Gewinn meldet, zahlt nicht mehr als ohne Meldung. Ohne diese Zusage bekommt ihr keine Daten.

2. **Meldungen werden nie firmenbezogen zurückgespielt.** Aggregiert, anonym, ab Mindestzahl. Siehe Abschnitt 9.

### 4.4 Block 4 — Was wir nicht verbessern können

Kurz, sachlich, ohne Entschuldigung.

```
  Grenzen der Datenlage

  Kein Auftragswert veröffentlicht           35 % der Vergaben
  Ausschreibung nicht mit Zuschlag verknüpfbar   49 %
  Unterlegene Bieter nie veröffentlicht         alle
  Eignungsanforderungen nur im Fließtext      ca. 63 %

  Daran ändert keine Angabe etwas. Wir schätzen an diesen
  Stellen nicht, sondern lassen sie leer.
```

---

## 5. Katalog der Angaben

Vollständige Liste. Spalte „Erhebungsort" ist die eigentliche Antwort auf „einige Sachen gehören woanders hin".

### 5.1 Was ihr sucht

| Angabe | Form | Wirkt auf | Primärer Erhebungsort |
|---|---|---|---|
| Schwerpunkte | CPV-Bündel, Mehrfachauswahl | Relevanz, Auto-Watchlist | Onboarding |
| Regionen | NUTS 1–3 | Relevanz, Filter | Onboarding, präzisiert auf Treffergüte |
| Volumenband | min / max | Relevanz | Treffergüte |
| Ausschlüsse | CPV oder Stichwort | Filter | Beim wiederholten Verwerfen |
| Rechtsrahmen | VOB / VgV / UVgO / SektVO | Filter | Treffergüte |

Der letzte Punkt ist unterschätzt: `RegulatoryDomain` hat 98,7 % Abdeckung. Ein Bauunternehmer, der nur VOB will, halbiert seine Liste mit einem Klick.

### 5.2 Was ihr könnt

| Angabe | Form | Wirkt auf | Primärer Erhebungsort |
|---|---|---|---|
| Fähigkeitsfeld | kontrollierte Liste, 25–40 Einträge | Relevanz, Fähigkeiten-Sektion, Netzwerk | Anforderungs-Check |
| Teamgröße je Feld | Band (1–2 / 3–5 / 6–15 / 16–50 / 50+) | Relevanz, Fähigkeitskarte | Treffergüte |
| Seit wann | Jahr | Reifeproxy | Treffergüte |
| Eigenleistung oder Partner | zwei Zustände | Netzwerk-Matching | Anforderungs-Check |
| **Größter Auftrag allein** | Euro-Betrag | Relevanz — stärkster Einzelwert | Treffergüte |
| Parallele Angebotskapazität | Zahl | Priorisierung | Treffergüte |

Zur Granularität: **Team, nicht Person; Band, nicht Zahl.** Eine Skill-Matrix mit 200 Technologien füllt niemand aus und ist nach sechs Monaten falsch. Keine Namen, keine Lebensläufe, keine personengebundenen Qualifikationen — das hält den gesamten Bereich außerhalb personenbezogener Daten.

### 5.3 Was ihr nachweisen könnt

| Angabe | Form | Wirkt auf | Primärer Erhebungsort |
|---|---|---|---|
| Zertifikate | Liste + Gültigkeitsdatum | Anforderungs-Check, Fähigkeiten | Anforderungs-Check |
| Herstellerpartnerschaften | Liste | Anforderungs-Check | Anforderungs-Check |
| Präqualifikationen | PQ-Nummer | Anforderungs-Check | Treffergüte |
| **Bürgschaftsrahmen** | Band | Harte K.-o.-Prüfung vor dem Angebot | Treffergüte |
| Referenzen | Anzahl + Größenordnung | Anforderungs-Check | Treffergüte |

`RequiredFinancialGuarantee` hat in DÖE knapp 60 % Abdeckung. Der Bürgschaftsrahmen ist damit eines der wenigen echten Ausschlusskriterien, das wir maschinell prüfen könnten — und heute nicht prüfen, weil die Nutzerseite fehlt.

### 5.4 Wer ihr seid

| Angabe | Form | Wirkt auf | Primärer Erhebungsort |
|---|---|---|---|
| Entity-Bestätigung | Ja/Nein je Kandidat | Profil, Wettbewerb, **Entity-Graph global** | Onboarding |
| Konzernzugehörigkeit | Mutter / Töchter | Aggregate | Treffergüte |
| **Bestandsverträge** | Stelle, Ende, Volumen, Gegenstand | Auslaufwarnung, Bindung, Konzentration | Treffergüte |

Bestandsverträge sind der stärkste Punkt dieser Gruppe. Ein regionales Systemhaus macht den Großteil seines Umsatzes unterhalb der Schwellenwerte — diese Aufträge stehen in keiner öffentlichen Quelle. Wer sie einträgt, um Auslaufwarnungen zu bekommen, gibt euch ein Bild des Unterschwellenmarkts, das nicht rekonstruierbar ist.

### 5.5 Was passiert ist

| Angabe | Form | Wirkt auf | Primärer Erhebungsort |
|---|---|---|---|
| Beworben ja/nein | zwei Zustände | Gewinnquote | Statuswechsel im Lead |
| Grund beim Verwerfen | kontrollierte Liste | Scoring-Korrektur, Ausschlüsse | Statuswechsel „Verworfen" |
| Ergebnis nach Zuschlag | gewonnen / verloren / aufgehoben | Wettbewerbsmenge | Nach TED-Zuschlag, per Alert |
| Rangplatz bei Verlust | Zahl | Knappheitsanalyse | Ergebnisdialog |
| Grund laut Absage | kontrollierte Liste | Preis vs. Qualität je Stelle | Ergebnisdialog |

---

## 6. Verteilte Erhebung

Die Seite ist die Karte. Erhoben wird überwiegend woanders — im Moment des Bedarfs, mit sofortigem Gegenwert.

| Ort | Moment | Frage | Gegenwert für den Nutzer |
|---|---|---|---|
| Bewertungs-Tab | Anforderung ohne hinterlegte Angabe | „Diese Ausschreibung fordert X. Habt ihr das?" | Anforderungs-Check wird für diesen Lead vollständig |
| Statuswechsel | Klick auf „Verworfen" | „Warum?" — 6 Optionen | Ähnliche Leads erscheinen seltener |
| Alert nach Zuschlag | Watchlist-Lead vergeben | „Wart ihr dabei? Wie ist es ausgegangen?" | Zähler für Wettbewerbsdaten steigt |
| Onboarding | Erstkontakt | Entity, Schwerpunkte, Regionen | Liste existiert überhaupt |
| Treffergüte | jederzeit | alles Nachgelagerte | bessere Liste |

**Die wichtigste Regel dieses Abschnitts:** Im Onboarding wird **nichts** abgefragt, was nicht zwingend nötig ist, um die erste Liste zu erzeugen. Jede zusätzliche Frage dort kostet Anmeldungen. Alles andere wandert in den Gebrauch.

Nach dreißig geprüften Leads ist das Profil vollständiger, als ein Onboarding-Wizard es je gemacht hätte — und die Angaben stimmen, weil sie im konkreten Fall entstanden sind.

---

## 7. Wirkungsberechnung

Für jede offene Angabe wird die betroffene Lead-Menge gegen die **aktuelle** Liste des Nutzers gerechnet. Nächtlich vorberechnet, bei Änderung neu.

### 7.1 Grundformel

```
betroffen(angabe) = | { lead ∈ liste(user) : lead.fordert(angabe) } |
```

Formuliert wird **immer** als „betrifft N Leads", nie als „entfernt N Leads" oder „bringt N Leads". Solange die Angabe fehlt, ist die Richtung unbekannt — und das Produkt behauptet nichts, was es nicht weiß.

### 7.2 Je Angabetyp

| Typ | Berechnung | Beispiel |
|---|---|---|
| Anforderung | Leads mit dieser Anforderung im Anforderungs-Check | ISO 27001: 22 |
| Bürgschaft | Leads mit `RequiredFinancialGuarantee` gesetzt | 78 |
| Volumengrenze | Leads über plausibler Schwelle ohne hinterlegte Grenze | 61 |
| Fähigkeitsfeld | Leads im zugeordneten CPV-Bündel ohne Angabe | 34 |
| Regionspräzisierung | Leads außerhalb eines Umkreises, der aus dem Sitz plausibel ist | 29 |
| Rechtsrahmen | Leads in nicht hinterlegten Regimen | variabel |
| Ausschlüsse | Leads, die mehrfach verworfenen Mustern ähneln | variabel |

### 7.3 Nach Erfassung

Sobald die Angabe vorliegt, wird die tatsächliche Wirkung einmalig zurückgemeldet — als Fakt, nicht als Feier:

> Bürgschaftsrahmen bis 250.000 € hinterlegt. 41 Leads fallen damit aus eurer Relevanzstufe.

Keine Animation, keine Bestätigungsmeldung, kein Ausrufezeichen. Die Zahl genügt.

### 7.4 Untergrenze für Anzeige

Angaben mit weniger als 3 betroffenen Leads erscheinen nicht in Block 1. Sie sind über Block 2 nachpflegbar, aber sie oben aufzuführen erzeugt Rauschen und entwertet die Sortierung.

---

## 8. Datenmodell

### 8.1 `user_declarations`

Alle erklärten Angaben, einheitlich.

| Feld | Typ | Bedeutung |
|---|---|---|
| `id` | uuid | PK |
| `user_id` | uuid | FK |
| `kind` | enum | `capability`, `certificate`, `guarantee`, `volume_limit`, `region`, `exclusion`, `regulatory`, `partnership`, `prequalification`, `reference`, `capacity` |
| `key` | string | z. B. `data_engineering`, `iso_27001` |
| `value` | jsonb | typabhängig (Band, Betrag, Datum, Boolean) |
| `source` | enum | `onboarding`, `requirement_check`, `trefferguete`, `dismiss_reason` |
| `declared_at` | timestamp | |
| `confirmed_at` | timestamp | letzte Bestätigung |
| `valid_until` | date | bei Zertifikaten |

### 8.2 `user_contracts`

Eigene Bestandsverträge, inklusive unterschwelliger.

| Feld | Typ |
|---|---|
| `id` | uuid |
| `user_id` | uuid |
| `buyer_name` | string |
| `buyer_entity_id` | uuid, nullable — Match gegen den Entity-Graph |
| `cpv_bundle` | string |
| `nuts_code` | string |
| `value_euro` | numeric, nullable |
| `start_date` / `end_date` | date |
| `source` | enum: `declared`, `matched_ted` |

### 8.3 `user_outcomes`

Ergebnismeldungen — die Moat-Tabelle.

| Feld | Typ | Bedeutung |
|---|---|---|
| `id` | uuid | |
| `user_id` | uuid | |
| `lead_id` | string | |
| `applied` | boolean | beworben ja/nein |
| `dismiss_reason` | enum | bei `applied = false` |
| `result` | enum | `won`, `lost`, `cancelled`, `excluded` |
| `rank` | int, nullable | Rangplatz laut Absage |
| `loss_reason` | enum, nullable | `price`, `quality`, `formal`, `reference`, `unknown` |
| `reported_at` | timestamp | |
| `usable_for_aggregate` | boolean | nach Plausibilitätsprüfung |

**Gegen `success_fee_charges` gibt es keine Verbindung.** Das ist bewusst und muss im Schema sichtbar bleiben — kein Fremdschlüssel, keine gemeinsame View.

### 8.4 `user_gap_effects`

Vorberechnete Wirkung, nächtlich.

| Feld | Typ |
|---|---|
| `user_id` | uuid |
| `gap_key` | string |
| `affected_leads` | int |
| `computed_at` | timestamp |

---

## 9. Aggregation und Rückspiel

Was aus Ergebnismeldungen zurück ins Produkt fließt, und unter welchen Bedingungen.

| Kennzahl | Bedingung | Wo sichtbar |
|---|---|---|
| Wettbewerbsmenge je Stelle | ≥ 5 meldende Firmen | Vergabestellen-Detail |
| Gewinnquote des Nutzers | ≥ 10 eigene Meldungen | Position |
| Rangverteilung je Stelle | ≥ 5 meldende Firmen | Vergabestellen-Detail |
| Verlustgründe je Stelle | ≥ 5 meldende Firmen | Vergabestellen-Detail |
| Fähigkeitskarte je Region | ≥ 10 Firmen im Feld | Felder |

### 9.1 Kartellrechtliche Leitplanken

Informationsaustausch zwischen Wettbewerbern ist nach Art. 101 AEUV und § 1 GWB heikel, und Vergabemärkte stehen dabei unter besonderer Beobachtung. Die Regeln sind nicht verhandelbar:

| Zulässig | Nicht zulässig |
|---|---|
| Rückwärtsgerichtet, nach Zuschlag | Laufende Verfahren |
| Aggregiert ab 5 beitragenden Firmen | Kleine, rückrechenbare Gruppen |
| Ohne Anbieterbezug bei Preisen | Preisniveaus je benanntem Anbieter |
| Historische Muster einer Vergabestelle | Aktuelle Angebotsabsichten |

Konkret: „Die Bundesagentur entschied historisch zu 81 % über den Preis" ist Marktbeobachtung. „Bechtle liegt typisch 8 % unter Schätzwert" ist individualisierte Wettbewerberinformation und wird nicht gebaut. „Drei Firmen bereiten gerade ein Angebot auf Los 4 vor" wäre Signalisierung und ist die rote Linie.

**Bevor Preisinformationen in irgendeiner Form live gehen, ist eine kartellrechtliche Prüfung einzuholen.** Das ist keine Formalie.

---

## 10. Free und Pro

| Element | Free | Pro |
|---|---|---|
| Treffergüte-Seite gesamt | ∞ | ∞ |
| Alle Angaben erfassen | ✓ | ✓ |
| Wirkungsberechnung | ✓ | ✓ |
| Bestandsverträge | ✓ | ✓ |
| Ergebnisse melden | ✓ | ✓ |
| Freigeschaltete Wettbewerbsdaten | nur wenn Meldungen vorliegen | nur wenn Meldungen vorliegen |

**Die Seite wird nicht gegated.** Wer Daten will, stellt keine Bezahlschranke davor. Der Pro-Anreiz liegt in den Sektionen, die von besseren Daten profitieren — nicht in der Pflege selbst.

Die Freischaltung über Meldungen ist eine **eigene Achse neben Free/Pro**, keine dritte Preisstufe. Ein zahlender Nutzer ohne Meldungen sieht die Wettbewerbsdaten nicht. Ohne diese Härte funktioniert die Reziprozität nicht.

---

## 11. UI-Hinweise

Design-Grundlage ist `govisor-explorer-v4.4.html`. Keine neuen Tokens.

| Element | Umsetzung |
|---|---|
| Blockstruktur | bestehende `.pblock` |
| Kennzahlen | `.pstats` / `.pstat` mit `.v-num` in `--mono` |
| Gemessen vs. erklärt | bestehende `.ang-abg` / `.ang-c` mit `gemessen`-Marke |
| Erfassung in der Zeile | `.wf`-Pills für Auswahl, schlankes Eingabefeld für Beträge |
| Widerspruchshinweis | `.note-box` mit `--flag`-Punkt |
| Freischaltstufen | drei Punkte, gefüllt in `--ink-700`, offen als Umriss |
| Grenzen-Block | `.pgap`, kleiner Text, `--ink-500` |

**Keine neuen Farben.** Insbesondere kein Grün für „erledigt" — `--signal` bleibt reserviert für „das seid ihr" in Vergleichsdarstellungen.

Betroffene Lead-Zahlen rechtsbündig in `--mono` mit `tabular-nums`, damit die Sortierung optisch trägt.

---

## 12. Analytics

| Event | Properties |
|---|---|
| `quality_page_opened` | `entry_point`, `open_gaps`, `top_gap_key` |
| `quality_gap_filled` | `gap_key`, `affected_before`, `affected_after`, `source` |
| `quality_gap_dismissed` | `gap_key` |
| `quality_confirmation_shown` | `age_months` |
| `quality_confirmation_done` | `changed_count` |
| `outcome_reported` | `result`, `has_rank`, `has_reason` |
| `outcome_prompt_shown` | `channel` (alert / page / lead) |
| `outcome_prompt_ignored` | `channel` |
| `contract_declared` | `has_value`, `below_threshold` |
| `reciprocity_unlocked` | `level` (3 / 10) |

Die wichtigste Auswertung ist das Verhältnis `outcome_prompt_shown` zu `outcome_reported`. Fällt es unter 15 %, trägt die Reziprozität nicht und das gesamte Datenkonzept muss überdacht werden.

---

## 13. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Kein Prozentscore, kein Fortschrittsbalken, keine Punktzahl |
| 2 | Offene Angaben nach betroffener Lead-Anzahl sortiert |
| 3 | Angaben mit weniger als 3 betroffenen Leads erscheinen nicht in Block 1 |
| 4 | Jede offene Angabe ist in der Zeile erfassbar, ohne Sprung |
| 5 | Formulierung immer „betrifft N Leads", nie „entfernt" oder „bringt" |
| 6 | Nach Erfassung wird die tatsächliche Wirkung einmalig als Zahl gemeldet |
| 7 | Gemessen und erklärt sind visuell getrennt |
| 8 | Erklärte Angaben tragen ein Datum, nach 6 Monaten erscheint die Bestätigung |
| 9 | Widersprüche zwischen erklärt und gemessen werden benannt |
| 10 | Block „Was wir nicht verbessern können" ist vorhanden und nennt konkrete Anteile |
| 11 | Ergebnismeldungen lösen keine Erfolgsprämie aus — im Interface und in den AGB |
| 12 | Kein Fremdschlüssel zwischen `user_outcomes` und `success_fee_charges` |
| 13 | Rückgespielte Aggregate erst ab 5 beitragenden Firmen |
| 14 | Keine firmenbezogene Preisinformation |
| 15 | Seite vollständig in Free zugänglich |
| 16 | Freischaltung über Meldungen unabhängig vom Abo-Status |
| 17 | Höchstens ein Hinweis pro Sitzung, geschlossene Hinweise 30 Tage Ruhe |
| 18 | Keine personenbezogenen Fähigkeitsangaben — nur Teamebene |
| 19 | Leerzustand für Firmen ohne Historie definiert |
| 20 | Onboarding erhebt nur das für die erste Liste Nötige |

---

## 14. Leerzustände

| Situation | Verhalten |
|---|---|
| Neue Firma, keine Historie, kein Profil | Block 1 zeigt die Angaben, die die Liste überhaupt erst erzeugen. Block 2 ist leer mit dem bestehenden Hinweis, dass das Profil auch ohne Historie funktioniert. |
| Alle Angaben gepflegt | Block 1 wird ersetzt durch: „Keine offenen Angaben mit spürbarer Wirkung. Was jetzt noch streut, liegt an der Datenlage der Vergabestellen." + Block 4 |
| Keine Leads in der Liste | Wirkungsberechnung nicht möglich. Stattdessen: Hinweis auf Schwerpunkte und Regionen als Ursache. |
| Keine entschiedenen Vergaben zum Melden | Block 3 zeigt die Stufen, aber keine offenen Meldungen. Kein Drängen. |

---

## 15. Was nicht gebaut wird

| Was | Warum |
|---|---|
| Vollständigkeits-Prozentsatz | Willkürlicher Nenner, Falschpräzision |
| Abzeichen, Streaks, Belohnungen | Falsche Zielperson |
| Onboarding-Wizard mit allen Feldern | Kostet Anmeldungen, veraltet sofort |
| Skill-Matrix auf Personenebene | Personenbezogene Daten, nicht pflegbar |
| Automatischer Import aus LinkedIn o. ä. | Rechtlich unklar, Datenqualität schlecht |
| Öffentliches Firmenprofil | Anderes Produkt, andere Rechtslage |
| Ranking von Anbietern nach Fähigkeit | Selbstauskunft trägt keine Rangliste |
| Preisdaten in beliebiger Form | Erst nach kartellrechtlicher Prüfung |

---

## 16. Offene Fragen

| # | Frage | Empfehlung |
|---|---|---|
| 1 | Name „Treffergüte"? | Ja — sachlich, ungewöhnlich, aus Nutzersicht formuliert |
| 2 | Fähigkeitsliste kontrolliert oder frei? | Kontrolliert, 25–40 Felder, auf CPV-Bündel gemappt. Freie Eingabe ist bequemer beim Erfassen und wertlos beim Auswerten |
| 3 | Bestandsverträge: Einzelerfassung oder Import? | Erst Einzelerfassung. CSV-Import erst, wenn genug Nutzer genug Verträge haben |
| 4 | Freischaltschwellen 3 und 10? | Ja als Start, nach 3 Monaten gegen `outcome_reported` kalibrieren |
| 5 | Mindestzahl 5 beitragende Firmen für Aggregate? | Ja, eher erhöhen als senken |
| 6 | Bestätigungsintervall 6 Monate? | Ja für Fähigkeiten, 12 Monate für Zertifikate mit Gültigkeitsdatum |
| 7 | Wirkung auch für bereits gepflegte Angaben zeigen? | Nein — das wäre Rechtfertigung statt Information |

---

## 17. Abhängigkeiten

| Abhängigkeit | Status |
|---|---|
| Anforderungs-Check mit Feldzuordnung | Ticket #3, vorhanden |
| Statuswechsel „Verworfen" | im Prototyp vorhanden, Grund fehlt |
| Alert bei Zuschlag auf Watchlist-Lead | Ticket #9, vorhanden |
| NUTS-3 Granularität | separates Ticket |
| Entity-Graph für `user_contracts.buyer_entity_id` | offen |
| Fähigkeitsliste mit CPV-Mapping | zu erstellen |
| AGB-Passus zur Trennung Meldung / Erfolgsprämie | zu erstellen |
| Kartellrechtliche Prüfung vor Rückspiel | offen |

---

## 18. Reihenfolge

| Schritt | Inhalt | Warum zuerst |
|---|---|---|
| 1 | Grund beim Verwerfen (Dropdown, 6 Optionen) | Kleinster Eingriff, Statuszustand existiert bereits |
| 2 | `user_declarations` + Erfassung im Anforderungs-Check | Füllt das Profil durch Gebrauch |
| 3 | Wirkungsberechnung `user_gap_effects` | Grundlage für Block 1 |
| 4 | Treffergüte-Seite, Blöcke 1, 2 und 4 | Sichtbarer Nutzen ohne Reziprozität |
| 5 | `user_outcomes` + Ergebnisdialog aus dem Alert | Der eigentliche Graben |
| 6 | Block 3 mit Freischaltstufen | Erst sinnvoll, wenn 5 läuft |
| 7 | `user_contracts` | Eigenständiger Nutzen, unabhängig vom Rest |
| 8 | Aggregate und Rückspiel | Nach kartellrechtlicher Prüfung |
