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

## Wie viel ein Profil ausmacht — und woran man es misst

Fünf Profile stehen da: **DE, FR, CH, AT, LU** (Stand 2026-09-03). Die eine Kennzahl, an
der ein neues Profil abgenommen wird, ist die Abdeckung von `public_name` auf den
**Käufernennungen des Landes** — sie sagt, ob die öffentliche Hand als solche erkannt wird:

| Land | mit DE-Standardprofil | mit eigenem Profil | Grundlage |
|---|---:|---:|---|
| AT | — | **72,1 %** | 401.716 Käufernennungen |
| LU | 0,4 % | **74,5 %** | 6.142 Bekanntmachungen, 762 Käufernamen (2026-09-03) |

⚠ **0,4 % ist die ehrliche Zahl für „kein Profil".** Luxemburg arbeitet auf Französisch
(fr 4.734 · en 1.114 · de 266); ein deutsches Muster trifft dort so gut wie nichts. Wer
ein Land ohne Profil einliest, bekommt keine Fehlermeldung — er bekommt eine Datenbank, in
der die öffentliche Hand als Firma gilt.

⚠ **Was ein Regex-Profil NICHT löst: derselbe Käufer in zwei Sprachen.** „European
Commission" (110 Nennungen) und „Commission européenne" (69) sind dasselbe Haus und
bleiben zwei Entitäten. DACH hatte diesen Fall nie — er kommt mit jedem mehrsprachigen
Land und gehört der Entity-Resolution, nicht dem Profil.

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
- **Vertretungs-Zusätze: gelöst** (2026-08-30). `_consolidate_by_shared_name_geo` clustert über
  den **gereinigten** Namen. Vorher war der Schlüssel der rohe Name, weshalb „DB Netz AG"
  98-mal existierte — als `name:db netz vertreten durch db projektbau …` und 97 Geschwister,
  die einander nie begegneten. `clean_display_name` löste „vertreten durch" schon damals auf,
  aber erst NACH der Auflösung, auf dem Anzeigenamen.
- **Abteilungs-Zusätze: bewusst NICHT gemerged**, sondern als eigene Ebene geführt →
  Abschnitt „Träger und Einheit" unten.

## ⚠ Der Merge-Pass sah die Vergabestellen strukturell nicht

Drei Jahre lang war `_consolidate_by_shared_name_plz` „für öffentliche Stellen" beschrieben
und hat sie an drei Stellen verfehlt. Alle drei sind dieselbe Fehlerklasse: **eine Bedingung,
die für den Normalfall richtig ist und den Sonderfall unsichtbar ausschliesst.**

1. **Filter auf `Method.NAME_ONLY`.** `resolve_supplier` biegt alles ab, was nicht
   `Kind.COMPANY` ist — der Kommentar dort nennt Personen und Bietergemeinschaften, aber
   **`Kind.PUBLIC` fällt in denselben Zweig**. Gemessen: 27.348 Käufer-Entitäten (37,7 %)
   tragen `nicht_aufgeloest` und waren nie Kandidat.
2. **Schlüssel war der rohe Name** (siehe oben).
3. **Ohne PLZ gar kein Merge.**

> **Der Kernbefund, und er zeigt woandershin als erwartet:** von 1.889 blockierten Fragmenten
> scheiterten **nur 68 an widersprechenden Adressen, 1.821 an gar keiner**. Die
> Vergabestellen-Auflösung ist kein Zuordnungsproblem, sondern ein **Adressproblem**.
> 248.611 Käufer-Instanzen (11,2 %) tragen nur einen Ortsnamen, sonst nichts.

**Für ein neues Land heisst das:** erst messen, wie viele Käufer überhaupt eine Adresse
tragen — vor jeder Arbeit am Namensabgleich. Der Ortsbeleg läuft als **Kaskade
PLZ → NUTS3 → Ortsname**: der schärfste vorhandene entscheidet allein, der schwächere darf
ihn nie überstimmen. Sonst zieht ein geteilter Ortsname zwei Stellen mit widersprechender
PLZ zusammen.

## Träger und Einheit — eine Ebene daneben statt einer Zeile weniger

Rund 20.700 Käufer-Entitäten (28,6 %) liessen sich zusammenziehen, wenn man den
Abteilungs-Zusatz wegwirft. Das ist verlockend und falsch, weil zwei richtige Antworten
dahinterstehen:

| Frage | Antwort |
|---|---|
| Wie viele Vergabestellen gibt es? | die Behörde (**Träger**) |
| Wer schreibt diesen Auftrag aus? | die einkaufende Stelle (**Einheit**) |

Ein Merge beantwortet die erste und macht die zweite unbeantwortbar. `build_buyer_traeger`
schreibt deshalb `buyer_traeger.parquet` (`entity_id, traeger_id, traeger_name, einheit`) und
nimmt **nichts** weg: `entity_id` bleibt die Einheit und damit die Körnung des Bestands.
Zählen = `group by traeger_id`, anschreiben = `entity_id`.
Gemessen DE (2026-08-31): **71.343 Vergabestellen unter 55.240 Trägern**, 22,6 % gebündelt.

⚠ **Der Träger ist nicht der Namensstamm allein.** „Stadtwerke" gibt es hundertfach; ohne
Ortsbeleg wären das alles Geschwister. Es gilt dieselbe Kaskade wie beim Verschmelzen, über
**dieselbe Funktion** (`_ortsbeleg_passt`). Zwei Kopien würden auseinanderdriften, und dann
widerspräche die Träger-Ebene dem Bestand, auf dem sie sitzt.

⚠ **`entities.classify().normalized` schneidet am Komma ab.** „Dresden, GB Stadtentwicklung"
und „Dresden, GB Finanzen" ergeben denselben Schlüssel. Ein Namens-Merge darüber schmilzt
still die Abteilungsebene ein (gemessen 1.772 statt 1.162 Merges) — eine Produktentscheidung,
getarnt als Datenbereinigung. Der Merge-Pass hat dagegen einen **Einheiten-Riegel**: gemergt
wird nur bei gleicher Einheit oder wenn eine Seite keine nennt. Den **Bindestrich** behandelt
`classify` übrigens NICHT wie das Komma; `build_buyer_traeger` gleicht das für sich an, ohne
`classify` anzufassen (das hat andere Nutzer).

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
