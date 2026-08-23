# 08 · Entitäten und Locale — Rechtsformen, Namen, Kennungen

> Gehört zu Tor 3 und 4. Entity-Resolution ist die bekannte Kernschwäche des Projekts:
> Vergabestellen liegen bei rund **18 %** sicherer Auflösung.

## Das Locale-Profil eines Landes

`govisor/locales.py` führt je Land ein `Locale` mit Regexen für:

| Feld | Was es entfernt |
|------|-----------------|
| `re_legal` | Rechtsformen (GmbH, AG, Ges.m.b.H., Sàrl …) |
| `re_representation` | Vertretungsklauseln („vertreten durch …") |
| `re_subdivision` | Abteilungs-Anhängsel |
| `re_lead_article` | führender Artikel |
| `re_unit` | Einkaufs-/Buchungskreis-Nummern |
| `re_consortium` / `re_public` / `re_association` / `re_person` | Klassifikation |

```python
from govisor import locales
locales.use("AT")        # setzt das aktive Profil für den Prozess
locales.active()         # Default ist DE — das ist die Falle
```

⚠ **Der Default ist DE.** Jede Funktion, die `country` entgegennimmt und
`normalize_company` benutzt, muss `locales.use(country)` aufrufen. `dedupe.py` tat es
jahrelang nicht (s. [Kapitel 04](04-dublettenwall.md)).

## Rechtsformen: messen, welche fehlt

Ein einziges fehlendes Muster kostet Hunderte Paare. Gemessen an AT:

```
Locale je Land aktiviert                     +31 Paare käuferbelegt
Rechtsform „Gesellschaft mbH" ergänzt       +308
```

Die Falle im Detail: `gesellschaft mbh` **muss vor** `ges.m.b.h.` stehen und als **Ganzes**
gehen. Sonst frisst das kürzere Muster nur das „mbh" und lässt das Wort „gesellschaft"
stehen — womit „ÖBB-Technische Services-GmbH" und „ÖBB-Technische Services-**Gesellschaft
mbH**" verschiedene Käufer bleiben.

**Prüfmuster für ein neues Land** (an echten Namenspaaren durchspielen):

```
Kurzform ↔ Langform          GmbH ↔ Gesellschaft mit beschränkter Haftung
Punkte ↔ ohne Punkte         Ges.m.b.H. ↔ GesmbH
Abkürzung ↔ ausgeschrieben   AG ↔ Aktiengesellschaft
Sprachvarianten              AG ↔ SA ↔ SpA        (CH kennt AG und SA)
```

Gemessener Stand: DE kennt „Gesellschaft mbH" **nicht**, CH kennt „AG ↔ Aktiengesellschaft"
**nicht**. Beides gemessen und für unerheblich befunden (CH: 5 Paare, DE: 0) — deshalb
bewusst nur bei AT ergänzt. **Erst messen, dann ergänzen.**

## Amtliche Kennungen

Beide DACH-Nachbarn führen dieselben Systeme in beiden Quellen:

```
GLN         9110016729695     13-stellig
Firmenbuch  FN92191a          AT
UID         ATU12345678       AT
HRB/HRA     hr:F1103R_HRB12300  DE
```

**Aber:** dieselbe Vergabe kann auf der einen Seite eine GLN und auf der anderen eine
Firmenbuchnummer tragen — ein direkter Abgleich scheitert dann. Und, wichtiger:

⚠ **Kennungen können Dachkennungen sein.** `9110027589349` trägt die ÖGK-Landesstellen
Wien, Steiermark und Kärnten; `FN92191a` deckt 60 verschiedene ASFINAG-Namen ab. Eine
Kennungsgleichheit beweist die **Organisationsgruppe**, nicht die ausschreibende Stelle.

Die Prüfung, die man für ein neues Land macht:

```sql
SELECT national_id, count(DISTINCT name) namen, count(*) zeilen
FROM read_parquet('data/silver/XX/notice_parties/**/*.parquet')
WHERE role='buyer' AND national_id IS NOT NULL
GROUP BY 1 HAVING count(DISTINCT name) > 3
ORDER BY 2 DESC LIMIT 12
```

Was oben steht, ist entweder Müll („0", „1", „AT") oder eine Dachkennung. Beides gehört
behandelt, bevor die Kennung als Beleg dient.

## Entity-Resolution: was geht und was nicht

- **Stufe 1 (`_consolidate_by_national_id`)**: nur-Name-Entitäten in ihre belegte
  Register-Entität verschmelzen — **nur bei geteilter PLZ**, 0 Fehl-Merges. −6.279
  Dubletten.
- **Stufe 2 (Fuzzy-HR): VERWORFEN und gegated.** Gemessen: Schwelle 0.7 → ~24 %
  Fehl-Merges bei winzigem Ertrag (1.428). `build_hr_index(fuzzy=False)` ist Default.

> **Erkenntnis: Entity-Resolution über Namen ist ausgereizt.** Mehr geht nur über externe
> Register. Für ein neues Land heisst das: das nationale Register finden, oder die
> Schwäche akzeptieren und benennen.

- **Kuratierte Aliase** (`data/curated/<LAND>_entity_aliases.csv`): belegte Umbenennungen
  als Identitäts-Merge, human-verifiziert. Kein Namensstamm-Automatismus. Seed-Beispiel:
  DB Netz ↔ DB InfraGO (Umbenennung 2024, gleiche HRB50879) → 15.662 auf 22.104 Vergaben.
- **Bewusst ungelöst:** die Fragmentierung öffentlicher Stellen (61 % der Vergaben, nicht
  im Handelsregister, Vertretungs- und Abteilungs-Zusätze).

## Der amtliche Anker für Vergabestellen

Öffentliche Stellen stehen **nicht** im Handelsregister — daher die 18 %. Was hilft, ist eine
Kennung, die der Staat selbst für seine Behörden führt.

Für Deutschland ist das die **Leitweg-ID** (aus der E-Rechnungs-Pflicht): sie identifiziert
die empfangende Stelle eindeutig und ist in Bekanntmachungen zunehmend vorhanden. Gebaut
und produktiv.

**Für jedes neue Land die Frage stellen: gibt es ein solches Behörden-Verzeichnis?**
Kandidaten sind Register für E-Rechnung, Organisationskennungen des öffentlichen Dienstes
oder ein zentrales Vergabestellen-Verzeichnis. Ohne einen solchen Anker bleibt die
Vergabestellen-Auflösung auf dem Namen sitzen — und die ist ausgereizt.

## CPV-Ebene beim Matching: CPV-6, nicht CPV-4

Gemessen 2026-08-09 und für jedes Land gültig, weil CPV EU-Vokabular ist:

- **CPV-4 ist zu grob.** CPV 4531 bündelt Elektro (453112), Aufzüge (453131) und Heizung
  (45315x) — ein Elektriker bekam Aufzüge und Heizung als „hoch"-Leads.
- **CPV-7 und CPV-8 kaufen keine Präzision.** Stelle 7 trägt nur in 20 % Information,
  Stelle 8 nur in 7 % (93 % sind „0"). Treffer-Test Elektriker: CPV-6 = 143 Leads,
  CPV-7 = 142, CPV-8 = 142 — dafür dünneres Feldsignal und Über-Verengung (Dachdeckung
  45261210 ≠ Dachabdichtung 45261420, dasselbe Gewerk).
- **Also: CPV-6 = Volltreffer, CPV-4 = Nachbarfeld.** Verifiziert: „hoch"-Leads eines
  Elektrikers 39 → 13, Aufzug/Heizung 19 → 0.

Ein neues Land erbt diese Ebene automatisch — **aber nur, wenn die Quelle CPV mitliefert**
([Kapitel 02](02-input-ausschreibungen.md)).

## ⚠ Namensblöcke am Wortanfang prüfen, nicht als Teilzeichenkette

Dieselbe Falle wie bei den Ortsnamen ([Kapitel 07](07-geo-und-regionen.md)), an anderer
Stelle: eine Sperrliste blockte `'land '` als **Teilzeichenkette** — und traf damit auch
„…Deutsch**land** GmbH". Ergebnis: **211 Grossfirmen** (MAN, Rosenbauer, Telekom, SAP, IBM,
ENGIE …) waren im Onboarding nicht auffindbar.

Fix: Treffer nur am **Wortanfang** (Namensanfang oder nach einem Leerzeichen). Die
eigentlich gemeinten Käufer (Land Berlin, Landkreis …) bleiben geblockt.

**Für ein neues Land:** die Sperrliste braucht die Landesbezeichnungen dieses Landes —
und dieselbe Wortanfang-Regel, sonst blockt sie mit.

## Wikidata als externe Anreicherung

Für Käufer umgesetzt: 709 geo-disambiguierte Treffer. Destatis, Handelsregister und
Insolvenzbekanntmachungen wurden analysiert. Für ein neues Land ist Wikidata der billigste
erste Schritt, weil sprachunabhängig und ohne Konto.

## ARGE/Konsortien

Studiert, **nicht gebaut**. Regelbasiert sind 26 % der Konsortialnamen in ≥2 Mitglieder
zerlegbar, aber nur **479 (0,6 %) aller Nachfolgen** würden von „unbestimmbar" auf
„Retention" kippen. **Die ARGE-Fluktuation ist überwiegend echt** (je Projekt eine andere
Bietergemeinschaft), kein Artefakt.

Die Lehre für ein neues Land: erst den **Nutzen** messen, dann bauen. Eine plausible
Verbesserung, die 0,6 % bewegt, ist keine.

## Was man beim Gewinner-Matching falsch machen kann

Gruppen-bewusst, Multi-Gewinner als Mengenschnitt, Konsortien geflaggt. Naiv mit
1 Gewinner gerechnet ergäbe irreführende **78 % Verdrängung** durch die
Siemens-AG↔Mobility-Fragmentierung und ARGE-Zuordnung. Der belastbare Wert ist
**28,3 % Incumbent-Retention** auf 100.071 verifizierten Nachfolgen.

Wer für ein neues Land Nachfolge-Kennzahlen baut: diese Prüfung wiederholen, bevor eine
Zahl das Haus verlässt.
