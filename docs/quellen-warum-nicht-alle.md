# Warum nicht alle 125 Quellen angeschlossen sind

*Gemessen am 2026-10-05 gegen den Bestand im Nachtlauf-Baum. Jede Zahl hier ist nachgerechnet,
keine geschätzt — die Abfragen stehen am Ende.*

Svens Frage war richtig gestellt: **nicht der Anzahl wegen, sondern wegen der Ausschreibungen.**
Genau so wird sie hier beantwortet. Die Kurzfassung in drei Sätzen:

1. Die „125 Quellen" sind **drei verschiedene Fragen in einer Zahl**, und nur eine davon heisst
   „ein Portal, das wir übersprungen haben".
2. **In Deutschland ist auf der Bekanntmachungs-Ebene alles angeschlossen**, was die Registry
   kennt — 15 von 15 Quellen live.
3. Der Ertrag eines weiteren Portals sieht je nach Blickwinkel **vierzigfach verschieden** aus.
   Welcher der beiden richtig ist, entscheidet, ob sich der nächste Connector lohnt.

---

## 1. Die 125 zerfallen in drei Dinge

| | Anzahl | was es wirklich ist |
|---|---:|---|
| `bekanntmachung`, live | 8 | die Quellen, aus denen Ausschreibungen kommen |
| `bekanntmachung`, candidate | 29 | **andere Länder** — 26 davon reines `ted-XX` |
| `bekanntmachung`, research/prepared | 4 | angefangen oder geprüft, nicht entschieden |
| `bekanntmachung`, sondiert | 5 | **nationale unterschwellige Portale** (HU, SI, GR ×2, PT) |
| `unterlagen`, live | 13 | Dokument-Abrufer — bringen **keine** neuen Ausschreibungen |
| `unterlagen`, sondiert | 64 | dito, nur noch nicht gebaut |
| `fonds` | 2 | dritte Vergabeebene (CZ, PL) |

**Die 29 „candidate" sind keine übersprungenen Portale, sondern nicht betretene Märkte.** 26 von
ihnen tragen wortgleich dieselbe Beschreibung: *„EU-pflichtige Vergaben; gleiche eForms/Legacy-
Pipeline wie DE/AT"*. Der Connector existiert also längst — was fehlt, ist das Länder-Onboarding
(Währung, Zeichensatz, Regionen, Locale, Dublettenwall … 16 Kapitel in `docs/laender/`). Das ist
eine Geschäftsentscheidung über Markteintritt, keine technische Lücke.

**Die 64 sondierten Unterlagen-Quellen liegen auf einer anderen Ebene.** Sie bringen die
*Vergabeunterlagen* zu Ausschreibungen, die wir bereits haben — kein einziger neuer Auftrag.
Und von ihnen sind **30 als `gesperrt` eingetragen**: sie verlangen ein Konto, weisen den Client
ab oder verbieten es in der robots.txt. Das ist keine Entscheidung, die noch aussteht.

> ⚠ **Hier sitzt auch die ehrliche Antwort auf „200+ Quellen" im Wettbewerb.** Die sondierten
> Quellen stehen für **1.282 Herkunfts-Portale**. Wer sie addiert, kommt auf jede beliebige
> Marketing-Zahl. Unsere 21 live-Quellen decken 144 Portale ab — weil drei Aggregatoren
> (TED, DÖE, simap) hunderte Einzelportale bündeln. **Quellenanzahl ist kein Abdeckungsmass.**

**Die fünf sondierten nationalen Portale sind die einzige Kategorie, die wirklich neue
Ausschreibungen verspricht** — und zwar unterschwellige, die TED per Definition nie trägt. Zwei
davon sind beziffert: Ungarns EKR-Suche führt **4.417 laufende Vergaben, von denen 60 % TED nie
erreichen**, Sloweniens eJN-Liste besteht zu 70 % aus unterschwelligen Einträgen. Griechenlands
KIMDIS und Portugals BASE sind nicht gemessen. ⚠ Jede davon setzt aber das Länder-Onboarding
voraus — ohne TED-Grundstock für dasselbe Land gibt es nichts, wogegen man dubletten könnte.

## 2. Deutschland: auf der Bekanntmachungs-Ebene ist nichts offen

Alle 15 DE-Quellen der Registry sind `live`: vier Bekanntmachungs-Quellen (TED, DÖE, NetServer,
cosinex) und elf Unterlagen-Abrufer. **Es gibt in der Registry kein deutsches Portal, das
Ausschreibungen liefern würde und nicht angeschlossen wäre.**

Die bekannten deutschen Lücken liegen woanders — bei den *Unterlagen*, und sie sind beziffert
(`curated/portale_ohne_abrufer.csv`, 56 Portale, zusammen **2.338 Leads**):

| Leads | Portal | Grund |
|---:|---|---|
| 1.455 | www.dtvp.de | Keycloak-Anmeldung — Zugangsfrage, kein Parserproblem |
| 421 | www.deutsche-evergabe.de | Registrierung nötig |
| 262 | vergabe24.de + bund.vergabe24.de | weisen den Client ab |
| 200 | 52 weitere Kleinportale | im Mittel **3,8** Leads je Portal |

**Vier Portale tragen 91 % dieser Lücke, und bei dreien ist es eine Konto- und keine
Technikfrage.** Der lange Schwanz aus 52 Portalen bringt zusammen 200 Leads — **im Schnitt
3,8 je Portal**. Ein eigener Connector ist dort durch nichts zu rechtfertigen; genau solche
Portale machen bei einem Wettbewerber die Zahl „200+ Quellen" aus.

## 3. Was ein weiteres Portal wirklich bringt — zwei Zahlen, die sich widersprechen

Das ist der Kern der Frage, und die Antwort hängt davon ab, was man zählt.

**Blickwinkel A — der Bestand (20 Jahre, 2,3 Mio. Bekanntmachungen):**

| Quelle | Sätze | davon Dublette | wirklich neu |
|---|---:|---:|---:|
| TED (legacy+eforms+text+ojs) | 1.876.348 | 3,3 % | 1.814.744 |
| DÖE | 400.977 | 8,6 % | 366.636 |
| **DTVP** | **15.577** | **66,6 %** | **5.208** |
| **NetServer** | **6.284** | **29,8 %** | **4.409** |
| **Healy-Hudson** | **2.971** | **62,0 %** | **1.129** |

Die drei Portal-Connectoren zusammen: 24.832 geholte Sätze, **10.746 davon neu** — das sind
**0,47 %** des Bestands. So gelesen wirkt jeder weitere Connector wie verlorene Zeit.

**Blickwinkel B — die heute offenen Leads (das, worauf man bieten kann):**

| Quelle | offene Leads | Anteil |
|---|---:|---:|
| eForms (TED) | 8.527 | 57,7 % |
| DÖE | 3.325 | 22,5 % |
| **DTVP** | **1.519** | **10,3 %** |
| **NetServer** | **864** | **5,8 %** |
| **Healy-Hudson** | **485** | **3,3 %** |
| Legacy (TED) | 55 | 0,4 % |
| **gesamt** | **14.775** | |

**Dieselben drei Connectoren tragen 19,4 % aller offenen deutschen Leads.** Ein Fünftel.

### Die Auflösung des Widerspruchs

Beide Zahlen stimmen, und der Unterschied ist die eigentliche Erkenntnis:

- **Der Bestand ist 20 Jahre TED-Historie.** Gegen 1,9 Millionen Altsätze sieht alles klein aus,
  was erst seit Monaten geholt wird.
- **Die offenen Leads sind der heutige Markt.** Und dort fällt ins Gewicht, dass unterschwellige
  kommunale Vergaben **kurzlebig** sind: sie erscheinen, laufen vier Wochen, verschwinden. Wer
  sie nicht am Tag der Veröffentlichung hat, hat sie nie.
- **TED trägt sie ohnehin nicht** — unterschwellig heisst per Definition: nicht EU-pflichtig.

> ⚠ **Wer den Ertrag eines Portals am Bestand misst, misst die falsche Zahl.** Der Fehler ist
> um den Faktor 40 gross (0,47 % gegen 19,4 %) und geht immer in dieselbe Richtung: er lässt
> jede unterschwellige Quelle wertlos aussehen.

### Und was die Dublettenquote sagt

Sie ist der nützlichste Einzelwert bei der Frage „lohnt der nächste Connector":

- **DTVP 66,6 %** — zwei Drittel seiner Sätze hatten wir schon. Trotzdem sind die restlichen
  5.208 der grösste Einzelbeitrag der drei.
- **NetServer 29,8 %** — der sauberste Zugewinn im Feld.
- **Healy-Hudson 62,0 %** — bei 2.971 Sätzen bleiben 1.129.

Die Messung der Aufräum-Sitzung an cosinex/Westfalen passt dazu: 91 laufende Vergaben geprüft,
**10 echte Fehlstellen = 11,0 %**; 89 % hatten wir über TED und DÖE. Dass dort 11 % und im
Bestand 33 % neu herauskommen, liegt an derselben Mechanik — je aktueller der Ausschnitt, desto
mehr Überschneidung, weil die Aggregatoren mit Verzögerung nachziehen.

## 4. Die Gründe, nach Kategorie

| Kategorie | Anzahl | Beispiel |
|---|---:|---|
| **Anderes Land, nicht angefangen** | 29 | `ted-es`, `ted-it`, `ted-fr` — Connector da, Onboarding fehlt |
| **Unterlagen gesperrt** | 30 | Konto, Client-Abweisung oder robots.txt |
| **Unterlagen offen, nicht gebaut** | 14 | Aufwand gegen Ertrag, s. unten |
| **Unterlagen ungeprüft** | 8 | nie drangekommen |
| **Fonds-Ebene** | 2 | CZ (8.663 Vergaben), PL — dritte Ebene, DACH hat sie nicht |
| **Deutsche Portale ohne Abrufer** | 56 | 91 % der Lücke in vier Portalen, davon drei mit Kontofrage |
| **In Arbeit / geprüft** | 4 | `ted-pl` (326.485 Sätze in Silber ohne Gold), `ankoe-at`, `ch-kantonal`, `usp-at` |

⚠ Zwei Einträge verdienen eine eigene Zeile, weil sie keine Faulheit sind:
- **`usp-at`**: kein Datenangebot, sondern ein *Meldeformular für Auftraggeber* mit Login und
  Rollenrecht. Es als „Quelle" zu zählen wäre eine Lüge.
- **`ted-pl`**: angefangen und liegengeblieben — 326.485 Bekanntmachungen liegen in Silber, Gold
  fehlt. Steht in CLAUDE.md als Baustelle und in der Sonden-Ausnahmeliste, damit der Riegel
  nicht dauerhaft rot steht und deshalb überlesen wird.

## 5. Was ich daraus ableiten würde

1. **Für den Vertrieb: nie eine addierte Portalzahl nennen.** „Drei Connectoren ≈ 36 Portale" ist
   belegbar, „125 Quellen" ist eine Doppelzählung — die meisten davon laufen durch dieselben
   Aggregatoren, und 64 sind Dokument- statt Ausschreibungsquellen.
2. **Die ehrliche Stärke ist nicht Breite, sondern die unterschwellige Ebene.** Fast ein Fünftel
   der offenen deutschen Leads käme über TED nie herein. Das ist genau das Segment, in dem der
   Mittelstand bietet, und es ist der Satz, den der Vertrieb sagen sollte.
3. **Der nächste Connector gehört dorthin, wo die Dublettenquote niedrig ist** — nicht dorthin,
   wo das Portal gross ist. NetServer (29,8 %) war die bessere Investition als DTVP (66,6 %),
   obwohl DTVP mehr Sätze hat.
4. **Die vier deutschen Portale mit 91 % der Lücke sind drei Kontofragen und eine
   Client-Abweisung** — also eine Frage an Sven, keine an die Technik: wollen wir uns dort
   anmelden, und unter welchem Namen?
5. **Die 29 Länder sind die eigentliche Wachstumsfrage.** Der Connector ist gebaut; was 16
   Kapitel Onboarding kostet, ist Zeit, nicht Erfindung. Polen liegt zur Hälfte da.

---

### Nachrechnen

```bash
# Registry-Aufteilung
python3 -c "from govisor import sources as S; import collections; \
  print(collections.Counter((s.ebene, s.status) for s in S.REGISTRY))"

# Dublettenquote je Quelle (DE)
# gold/DE/notice_duplicates.parquet × silver/DE/notices, count(DISTINCT duplicate_id)

# Offene Leads je Herkunft (DE)
# gold/DE/lead_export.parquet (phase='open') JOIN silver/DE/notices ON notice_id = lead_id
```

⚠ **Zwei Fallen beim Nachrechnen**, in die ich selbst gelaufen bin:
- `notice_duplicates` zählt **Paare**. Ohne `DISTINCT duplicate_id` kommen bei DTVP 28.721
  „Dubletten" auf 15.577 Sätze heraus — mehr als es Sätze gibt.
- Der Schlüssel in `lead_export` heisst **`lead_id`**, nicht `notice_id`; der Join sieht sonst
  richtig aus und liefert nichts.
