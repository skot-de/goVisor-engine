# Feature #14: Entity-Härtung & Konzernstrukturen

**Produkt:** goVisor
**Version:** Phase 1 — kritischer Pfad
**Status:** Draft
**Erstellt:** 2026-07-27
**Blockiert:** Ticket #10 (Strategie), Wettbewerbs-Sektion, Ticket #11 (Aggregate)
**Baut auf:** bestehender Entity-Resolution (`normalize_company` → `blocking_key` → `entities`), Härtung Stufe 1 (−6.279 Dubletten, committed)

---

## 1. Warum dieses Ticket der stille kritische Pfad ist

Der gesamte Strategie- und Wettbewerbsbereich rechnet über `entity_id`. Wenn eine Firma als mehrere Entitäten in der Datenbank liegt, ist **jede** abgeleitete Zahl falsch — nicht ungenau, falsch:

- Marktanteile werden unterzählt (Wins auf Dubletten verteilt)
- Konzentrationsquoten stimmen nicht
- Zuschlagsanteile je Vergabestelle sind zu niedrig
- „Wo konkurrieren wir" findet Überschneidungen nicht
- Wechselquoten verzählen sich (dieselbe Firma erscheint als Wechsel)

Der gemessene Ist-Zustand aus den bestehenden Tickets: **68 % der Entitäten sind ohne verifizierte Konfidenz.** Stufe 1 der Härtung hat 6.279 Dubletten entfernt — ein Anfang, kein Abschluss.

**Kernaussage:** Bevor die Strategie-Sektionen (Ticket #10) und die Aggregate (Ticket #11) gebaut werden, muss die Entity-Auflösung belastbar sein. Sonst baut man ein Cockpit auf falschen Zahlen. Dieses Ticket ist die Voraussetzung, nicht die Kür.

---

## 2. Was schon existiert (nicht neu bauen)

Die Resolution ist vorhanden und wird **nicht ersetzt**, sondern gehärtet und erweitert:

| Baustein | Status | Quelle |
|---|---|---|
| `normalize_company` (Namensnormalisierung) | vorhanden | Ticket #2 |
| `blocking_key` (Kandidatenbildung) | vorhanden | Ticket #2 |
| `entities` mit `canonical_name`, `national_id`, `method`, `confidence` | vorhanden | Ticket #2 |
| `party_entity` (role=buyer/winner) | vorhanden | Ticket #3 |
| USt-IdNr-Match gegen `national_id` | vorhanden | Ticket #2 |
| Härtung Stufe 1 (−6.279 Dubletten) | committed | — |

Dieses Ticket ergänzt drei Dinge: **härtere Zusammenführung** (Stufe 2), **Konzernstrukturen** (neu), **Konfidenz-Sichtbarkeit** (durchgängig).

---

## 3. Datenlage — die Identifikatoren

Die Auflösung ist schwer, weil harte Identifikatoren dünn sind. Aus dem Inventar:

| Identifikator | Abdeckung | Nutzbarkeit |
|---|---|---|
| Organisation-ID (`ORG-xxxx`, eForms-intern) | 53 % | **Nur innerhalb einer Bekanntmachung** — kein globaler Schlüssel |
| USt-IdNr / national_id (Gewinner, DÖE) | 7,6 % | Selten, aber wo vorhanden: harter Anker |
| Legacy nationalID | < 0,1 % | Praktisch wertlos |
| Firmenname + Adresse | ~90 % | Weich, braucht Normalisierung |
| NUTS (Gewinner-Region) | teilweise | Disambiguierungshilfe |

**Die harte Wahrheit:** Es gibt keinen flächendeckenden harten Identifikator. Die eForms-`ORG`-ID ist nur innerhalb *einer* Bekanntmachung eindeutig, nicht über Bekanntmachungen hinweg. Die Auflösung bleibt also überwiegend **namensbasiert mit Adress- und Konfidenz-Stützung** — und genau deshalb braucht sie Härtung und ehrliche Konfidenz-Ausweisung statt der Illusion von Exaktheit.

---

## 4. Konzept in drei Teilen

### Teil A — Härtung Stufe 2 (dieselbe Firma zusammenführen)

Stufe 1 hat exakte und offensichtliche Dubletten entfernt. Stufe 2 geht an die schwereren Fälle.

**A.1 Rechtsform-Varianten**

„CANCOM Public GmbH", „CANCOM Public", „Cancom Public GmbH & Co. KG" sind oft dieselbe operative Einheit. `normalize_company` fängt Schreibweisen, aber nicht Rechtsform-Wechsel. Regel: Bei identischem normalisiertem Kern + gleicher Adresse + überlappendem CPV-Profil → Zusammenführungs-Kandidat, zur Prüfung markiert (nicht blind mergen).

**A.2 USt-IdNr als Heiler**

Wo eine USt-IdNr vorliegt (7,6 %), heilt sie Fragmentierung hart: Alle Namensvarianten mit derselben USt-IdNr sind dieselbe Firma, unabhängig vom Namen. Diese wenigen harten Anker werden maximal ausgenutzt — sie ziehen weiche Namensvarianten mit.

**A.3 Adress-Cluster**

Gleiche Adresse + ähnlicher Name + überlappendes Tätigkeitsfeld → hohe Zusammenführungswahrscheinlichkeit. Adresse aus dem Gewinner-Datensatz (`WinningParty...Address`), normalisiert über Nominatim (aus dem NUTS-Ticket vorhanden).

**A.4 Konservativ, nicht aggressiv**

Zusammenführen ist gefährlich: Zwei fälschlich vereinte Firmen erzeugen ein Phantom mit doppelten Wins. Deshalb:
- Harte Anker (USt-IdNr) → automatisch mergen
- Weiche Signale (Name+Adresse+CPV) → als Kandidat markieren, `confidence` senken, nicht automatisch mergen
- Im Zweifel getrennt lassen und `confidence` niedrig führen

Ein getrennt gelassenes Duplikat unterzählt (sichtbar über Konfidenz-Warnung). Ein falscher Merge erfindet — und das ist schlimmer.

### Teil B — Konzernstrukturen (neu)

Dies ist der inhaltlich neue Teil. „Bechtle AG", „Bechtle GmbH & Co. KG Regensburg", „Bechtle Systemhaus Holding" sind rechtlich verschiedene Entitäten, gehören aber zu einer Gruppe. Für die Marktanalyse ist beides relevant — je nach Frage.

**B.1 Zwei Ebenen, nicht eine**

| Ebene | Bedeutung | Beispiel |
|---|---|---|
| **Entität** | rechtlich eigenständige Firma | „Bechtle GmbH Regensburg" |
| **Gruppe** | Konzern / wirtschaftliche Einheit | „Bechtle-Gruppe" |

Beide bleiben getrennt gespeichert. Die Gruppe ist eine Klammer über Entitäten, keine Ersetzung.

**B.2 Umschaltbar im Produkt**

Ein Systemhaus will je nach Frage beides sehen:
- „Wie viel gewinnt die *Bechtle-Gruppe* insgesamt?" → Gruppenebene
- „Wer genau ist der Incumbent bei *diesem* Vertrag?" → Entitätsebene

Deshalb: Die Aggregate (Ticket #10) bekommen einen Umschalter Entität/Gruppe. Default ist Entität (konservativ, belegbar), Gruppe ist die Zusammenfassung.

**B.3 Woher die Konzernzuordnung kommt**

Ehrlich: Aus TED/DÖE allein ist Konzernzugehörigkeit **nicht** ableitbar. Drei Quellen, nach Aufwand:

| Quelle | Abdeckung | Aufwand |
|---|---|---|
| Namens-Heuristik (gleicher Kern, verschiedene Rechtsform/Ort) | breit, unsicher | niedrig |
| Handelsregister / offeneregister.de | Beteiligungen teilweise | mittel, kostenlos |
| Kommerzielle Konzerndaten (North Data, Implisense) | hoch | teuer, API |

**V1-Empfehlung:** Nur die Namens-Heuristik, klar als `vermutet` markiert. Handelsregister-Anreicherung in Phase 3, kommerzielle Daten nur wenn Kunden es verlangen. Eine vermutete Gruppe wird nie als Fakt ausgegeben.

### Teil C — Konfidenz durchgängig sichtbar

Die Auflösung ist probabilistisch. Das muss überall dort sichtbar sein, wo aggregierte Zahlen aus ihr entstehen.

**C.1 Konfidenz-Stufen** (konsistent mit bestehendem Gesamtflow)

| Stufe | Methode | Anzeige |
|---|---|---|
| **hoch** | USt-IdNr-Match oder Handelsregister-exakt | Name direkt, „seit"-Angaben erlaubt |
| **mittel** | Name+Adresse-Cluster | Name, aber ohne harte Tenure-Angaben |
| **niedrig / nur_name** | reine Namensähnlichkeit | Name mit „Auflösung unsicher"-Hinweis |
| **keine** | nicht auflösbar | aus Aggregaten ausschließen |

**C.2 Ausschluss statt Sammelposten**

Entitäten mit Konfidenz `keine` werden aus Aggregaten **ausgeschlossen**, nicht als „Sonstige" gebündelt. Sonst entsteht ein Phantom-Marktführer aus lauter unauflösbaren Fragmenten. Lieber „bekannte 78 %" ehrlich zeigen als 100 % mit erfundenem Rest.

**C.3 Floor-Semantik**

Bei fragmentierten Entitäten ist jede Win-Zahl eine **Untergrenze**. „5 Wins" bei mittlerer Konfidenz heißt „mindestens 5" — es könnten mehr sein, die auf Dubletten liegen. Das gehört sichtbar gemacht, wie im bestehenden Ticket #3 (DB Netz ↔ DB InfraGO) bereits erkannt.

---

## 5. Datenmodell

### 5.1 Erweitert: `entities`

| Feld neu | Typ | Bedeutung |
|---|---|---|
| `resolution_confidence` | enum | `hoch` / `mittel` / `niedrig` / `keine` |
| `resolution_method` | enum | `ust_id` / `register` / `name_address` / `name_only` |
| `group_id` | uuid | FK → `entity_groups`, nullable |
| `group_confidence` | enum | `bestaetigt` / `vermutet` / `keine` |
| `merge_candidates` | jsonb | IDs möglicher Dubletten, zur Prüfung |
| `win_count_is_floor` | bool | true wenn Fragmentierung möglich |

### 5.2 Neu: `entity_groups`

| Feld | Typ | Bedeutung |
|---|---|---|
| `group_id` | uuid | PK |
| `group_name` | string | „Bechtle-Gruppe" |
| `group_source` | enum | `heuristik` / `register` / `kommerziell` |
| `member_count` | int | Anzahl zugeordneter Entitäten |
| `created_at` | timestamp | |

### 5.3 Bestehend genutzt

`party_entity` (role=buyer/winner) bleibt die Verknüpfung Notice ↔ Entität. Die Aggregate aus Ticket #10 lesen wahlweise auf `entity_id` oder `group_id`.

---

## 6. Auswirkung auf andere Tickets

| Ticket | Auswirkung |
|---|---|
| **#10 Strategie** | Aggregate mit Entität/Gruppe-Umschalter; Konfidenz-Warnungen; `keine`-Ausschluss |
| **#11 Treffergüte** | Entity-Bestätigungen aus Onboarding fließen zentral zurück (siehe 7) |
| **#3 Lead-Detail** | Incumbent mit `resolution_confidence`; Floor-Semantik bei Wins |
| **#6 Auth** | `entity_confidence`-Gate fürs Success-Fee-Matching bleibt, profitiert von Härtung |
| **#2 Onboarding** | Matcher unverändert, aber Bestätigungen werden zentral verwertet |

---

## 7. Der Crowdsourcing-Rückfluss (Verbindung zu Ticket #11)

Im Onboarding bestätigt jeder Nutzer, welche Entitäten zu seiner Firma gehören („Das bin ich" / „Das nicht"). Das ist crowdgesourcte Entity-Disambiguierung — und sie wird heute nur im Nutzerprofil gespeichert, nicht zentral verwertet.

**Neu:** Diese Bestätigungen fließen in den Entity-Graphen zurück:
- „Das bin ich" über mehrere Entitäten → diese Entitäten gehören zusammen (harte Bestätigung, `resolution_confidence` = hoch für diese Gruppe)
- „Das nicht" → negatives Signal gegen einen falschen Merge

Nach genügend Nutzern entsteht eine Auflösungsqualität für den deutschen IT-Markt, die kein Datenanbieter verkauft. Kosten: null. Der Mechanismus (Onboarding-Bestätigung) existiert bereits — nur der Rückfluss ist neu.

**Wichtig:** Eine Nutzerbestätigung gilt nur für die **eigene** Firma. Ein Nutzer kann nicht die Konzernzugehörigkeit fremder Firmen bestätigen. Fremdbestätigungen wären manipulierbar.

---

## 8. Bietergemeinschaften

Ein Sonderfall, der die Statistik verzerrt, wenn falsch behandelt. Aus dem Inventar: `TendererQualificationRequest` mit „gesamtschuldnerisch haftend" (43,7 % DÖE) signalisiert Bietergemeinschaften.

**Entscheidung (produktseitig):** Eine Bietergemeinschaft zählt für **jedes** Mitglied als Zuschlag, wird aber als solche gekennzeichnet.

Begründung: Sonst verschwinden KMU aus der Statistik, die genau über Bietergemeinschaften an große Aufträge kommen. Ein Zuschlag an „Firma A + Firma B" darf nicht als Zuschlag an ein Phantom „A+B" geführt werden, sonst hat weder A noch B ihn in ihrer Historie.

| Feld | Typ | Bedeutung |
|---|---|---|
| `is_consortium` | bool | Zuschlag ging an Bietergemeinschaft |
| `consortium_members` | uuid[] | beteiligte Entitäten |

---

## 9. Akzeptanzkriterien

| # | Kriterium |
|---|---|
| 1 | Härtung Stufe 2 führt USt-IdNr-Anker automatisch zusammen |
| 2 | Weiche Merge-Kandidaten werden markiert, nicht automatisch vereint |
| 3 | Falscher Merge wird konservativ vermieden (im Zweifel getrennt) |
| 4 | `resolution_confidence` an jeder Entität gesetzt |
| 5 | Konzern als zweite Ebene (`entity_groups`), Entität bleibt erhalten |
| 6 | Aggregate umschaltbar Entität/Gruppe, Default Entität |
| 7 | Vermutete Gruppen als `vermutet` markiert, nie als Fakt |
| 8 | Entitäten mit Konfidenz `keine` aus Aggregaten ausgeschlossen, nicht gebündelt |
| 9 | Fragmentierte Win-Zahlen als Floor markiert |
| 10 | Onboarding-Bestätigungen fließen zentral in den Graphen zurück |
| 11 | Fremdbestätigung von Konzernzugehörigkeit nicht möglich |
| 12 | Bietergemeinschaft zählt für jedes Mitglied, gekennzeichnet |

---

## 10. Edge Cases

| # | Case | Verhalten |
|---|---|---|
| 1 | Gleiche USt-IdNr, verschiedene Namen | Automatisch mergen (harter Anker) |
| 2 | Gleicher Name, verschiedene Adresse | Nicht mergen (könnten Filialen/verschiedene Firmen sein), Kandidat markieren |
| 3 | Gleicher Name+Adresse, verschiedene USt-IdNr | Nicht mergen — verschiedene Rechtssubjekte |
| 4 | Firma umbenannt (Fusion/Rebrand) | Falls USt-IdNr gleich: mergen; sonst getrennt mit niedriger Konfidenz |
| 5 | Konzern vermutet, aber Tochter operiert eigenständig | Gruppe zeigen, aber Entität bleibt primär |
| 6 | Nutzer bestätigt Entitäten, die Heuristik getrennt hatte | Nutzerbestätigung gewinnt, Gruppe wird hoch-konfident |
| 7 | Nutzer sagt „das nicht" zu vermutetem Konzern | Negatives Signal, Gruppen-Konfidenz senken |
| 8 | Bietergemeinschaft mit unauflösbarem Mitglied | Auflösbare Mitglieder zählen, unauflösbares als `keine` |
| 9 | Entität nur in Bietergemeinschaften aktiv | In Statistik führen, mit Hinweis „nur in Bietergemeinschaft" |

---

## 11. Out of Scope

| Was | Wann / Warum |
|---|---|
| Kommerzielle Konzerndaten (North Data etc.) | Phase 3, nur bei Kundenbedarf — Kosten |
| Handelsregister-Anreicherung | Phase 3 — mittlerer Aufwand |
| Vollautomatischer Merge weicher Kandidaten | Nie ohne Prüfung — Phantom-Risiko |
| Historische Namensverläufe (Rebrand-Tracking) | V2 |
| Entity-Resolution über DE hinaus | Erst bei Multi-Country |
| Fremdfirmen-Konzernbestätigung durch Nutzer | Nie — manipulierbar |

---

## 12. Abhängigkeiten

| Abhängigkeit | Status |
|---|---|
| Bestehende Resolution (`normalize_company`, `blocking_key`) | vorhanden |
| Härtung Stufe 1 | committed |
| `entities` mit `method`/`confidence` | vorhanden |
| Nominatim-Geocoding (für Adress-Cluster) | aus NUTS-Ticket |
| Onboarding-Bestätigung (#2) | vorhanden, Rückfluss neu |
| offeneregister.de (Phase 3) | offen |

---

## 13. Testfälle

| # | Test | Erwartung |
|---|---|---|
| 1 | Zwei Datensätze, gleiche USt-IdNr | Automatisch gemergt, Konfidenz hoch |
| 2 | „CANCOM Public GmbH" vs „CANCOM Public" gleiche Adresse | Merge-Kandidat, markiert, nicht auto-gemergt |
| 3 | „Bechtle AG" + „Bechtle GmbH Regensburg" | Getrennte Entitäten, gemeinsame Gruppe (vermutet) |
| 4 | Aggregat auf Gruppenebene | Summiert über alle Gruppen-Entitäten |
| 5 | Aggregat auf Entitätsebene | Nur die eine Entität |
| 6 | Unauflösbare Entität in Marktanteil | Ausgeschlossen, „bekannte X %" |
| 7 | Fragmentierte Firma, 5 Wins | „mindestens 5", Floor-Hinweis |
| 8 | Nutzer bestätigt 3 Entitäten als „ich" | Gruppe hoch-konfident, Rückfluss in Graph |
| 9 | Bietergemeinschaft A+B gewinnt | Zuschlag bei A und bei B, gekennzeichnet |
| 10 | Nutzer sagt „das nicht" | Merge-Kandidat verworfen |

---

## 14. Offene Fragen

| # | Frage | Empfehlung |
|---|---|---|
| 1 | Weiche Kandidaten manuell prüfen oder Schwelle? | Schwelle für Auto-Merge nur bei sehr hoher Übereinstimmung; Rest sammeln, später prüfen |
| 2 | Konzern-Heuristik-Schwelle? | Konservativ — lieber eine Gruppe verpassen als eine falsche bilden |
| 3 | Onboarding-Rückfluss sofort oder Batch? | Batch nächtlich, konsistent mit Aggregat-Rebuild |
| 4 | Handelsregister-Anreicherung jetzt schon evaluieren? | Nur die API-Machbarkeit prüfen (Claude Code), Integration Phase 3 |
| 5 | Floor-Hinweis in jedem Aggregat oder nur bei niedriger Konfidenz? | Nur wo Konfidenz mittel/niedrig — sonst Rauschen |

---

## 15. Zusammenfassung

Die bestehende Entity-Resolution wird nicht ersetzt, sondern gehärtet (Stufe 2: USt-IdNr-Anker, Adress-Cluster, konservativ) und um eine zweite Ebene erweitert (Konzern als umschaltbare Klammer über Entitäten). Konfidenz wird durchgängig sichtbar, unauflösbare Fälle werden ausgeschlossen statt gebündelt, fragmentierte Zahlen als Untergrenze markiert. Der stärkste Hebel kostet nichts: Die Entity-Bestätigungen aus dem Onboarding fließen zentral zurück und bauen über die Nutzerbasis eine Auflösungsqualität auf, die kein Datenanbieter verkauft. Ohne dieses Ticket stehen Strategie und Wettbewerbsanalyse auf falschen Zahlen.
