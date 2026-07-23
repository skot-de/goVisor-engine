# Bewertung: „Profil & Potenzial" (INPUT/govisor-profil-und-potenzial.md)

Alle Zahlen hier **gemessen am 2026-07-23** gegen den aktuellen Bestand (85.947 Leads,
1,83 Mio. Notices). Reproduzierbar über die genannten Gold-/Silber-Tabellen.

---

## 1 · Die 8 offenen Fragen — beantwortet

| # | Frage | Antwort |
|---|---|---|
| 1 | Eigene Siege zuverlässig ermittelbar? | **Ja.** `entity_identity`: 340.749 Entitäten, 63.326 (18,6 %) einer Konzerngruppe zugeordnet. Der Weg ist gebaut. |
| 2 | Spur verlorener Angebote? | **Nein** — bestätigt. Aber s. „Übersehenes Signal" unten: `num_tenders_sme` (46 % Abdeckung) beschreibt die *Zusammensetzung* des Bieterfelds. |
| 3 | CPV-Nachbarschaft? | **Existiert bereits** — `cpv_adjacency`, 40.716 Kanten über 848 Segmente, aus Firmen-Co-Occurrence (`P(bedient B \| bedient A)`). 4B ist nicht blockiert. |
| 4 | Käufer-Ähnlichkeitsmaß? | **Baubar, alle Zutaten in `buyer_profile`**: `top_division_label`, `n_categories`, `total_awards`, `main_nuts3`, `concentration`, `single_bidder_rate`. Fehlt nur die Vektorisierung. |
| 5 | Kunden-Durchdringung performant? | Ja — `buyer_contractor_history` (269.904 Zeilen) ist bereits die vorberechnete Tabelle. |
| 6 | Wie viele offene Leads je Bestandskunde? | S. Abschnitt 3 — das ist der kritische Punkt. |
| 7 | Marktanteil je CPV sauber abgrenzbar? | Mit Vorbehalt: `lot_count > 1` bei nur **8,9 %** der offenen Ausschreibungen, Lose verzerren die Zählung also weniger als befürchtet. Rahmenverträge bleiben ein Problem (ein Abruf ≠ eine Vergabe). |
| 8 | Zeitraum für „unsere Kunden"? | `buyer_contractor_history` fährt ein 5-Jahres-Fenster — das würde ich beibehalten, nicht neu erfinden. |

---

## 2 · Die Wunschliste 10.1, gemessen

Abdeckung bei **offenen Ausschreibungen ab 2024** (437.401 Notices), Zuschlagskriterien
an 11.617 roh vorliegenden eForms aus dem Live-Cache:

| Wunsch | Status | Abdeckung |
|---|---|---|
| **Zuschlagskriterien mit Gewichtung** | ⭐ **im Roh-XML, noch nicht geparst** | **78,2 % Typ · 67,3 % Gewicht** |
| **Verfahrensart im Detail** | ✅ **im Silber** (`procedure_type`) | **98,8 %** |
| Losaufteilung | ✅ **gebaut** (`gov_lead_lots`, 2026-07-23) | aber nur **8,9 %** mit >1 Los |
| Vertragslaufzeit + Optionen | ✅ **gebaut** | Optionen 35,7 % · Verlängerung 21,1 % |
| Angebotsfrist-Länge | ⚠️ nur halb | `publication_date` **53,3 %** |
| Vergabeplattform | ✅ im Silber (`portal_url`) | **23,7 %** |
| Schätzwert vs. Zuschlagswert | ❌ **Basis zu dünn** | beide Werte auf derselben Notice: **10,7 %** |
| Bietergemeinschaften | ✅ geflaggt (Konsortial-Erkennung im Nachfolge-Modell) | — |

### Der Favorit Nr. 1 ist richtig gewählt

Struktur im eForm, vollständig auswertbar:

```xml
<cbc:AwardingCriterionTypeCode listName="award-criterion-type">price</cbc:AwardingCriterionTypeCode>
<cbc:Name languageID="DEU">Preis</cbc:Name>
<efbc:ParameterCode listName="number-weight">per-exa</efbc:ParameterCode>
<efbc:ParameterNumeric>100</efbc:ParameterNumeric>
```

Typ-Verteilung in der Stichprobe: `price` 13.257 · `quality` 10.486 · `cost` 929 ·
`unpublished` 79. Das häufigste **Erstgewicht ist „100"** (≈54 % der Fälle) — also reiner
Preiswettbewerb, was für sich schon ein Chancen-Signal ist („hier gewinnt man nur über den
Preis" / „hier zählt Konzept zu 40 %").

**Einschränkung:** BT-539/BT-541 sind **Los**-Attribute und existieren nur in eForms
(2024+). Für Altjahre gibt es die Struktur nicht — was für offene Ausschreibungen egal ist.

---

## 3 · Der stärkste Einwand: der Bereich ist für die meisten leer

Das Dokument schreibt: *„Kein Kaltstart-Problem: Das Profil ist immer das eigene."*
**Das halte ich für falsch.** Gemessen über `buyer_contractor_history` (5-J-Fenster,
109.003 Firmen mit mindestens einem Sieg):

| | Firmen | Anteil |
|---|---:|---:|
| genau **1** Sieg | 66.085 | **60,6 %** |
| 2–4 Siege | 28.266 | 25,9 % |
| **5+ Siege** (belastbarer Fußabdruck) | 14.652 | **13,4 %** |
| **≥3 verschiedene Auftraggeber** (4A überhaupt sinnvoll) | 19.882 | **18,2 %** |

Der Median liegt bei **einem** Sieg. Für sechs von zehn Firmen ist „Fußabdruck" eine
einzelne Zeile, „Position" ein Marktanteil aus einer Beobachtung und „Bestandskunden-
Potenzial" ein einziger Kunde. Und für eine Firma, die **noch nie** gewonnen hat, ist der
gesamte Bereich leer.

Daraus folgt die unangenehme Frage: **Der Bereich funktioniert am besten für Kunden, die
ihn am wenigsten brauchen.** Wer 5+ Vergaben gewonnen hat, hat ein Bid-Team und kennt
seinen Markt. Wer neu einsteigen will — vermutlich der motivierteste Käufer für ein
Lead-Werkzeug — sieht ein leeres Profil.

**Was das nicht entwertet:** 19.882 Firmen mit ≥3 Kunden sind ein reeller adressierbarer
Markt, und 4A ist für sie stark. Aber das Produkt braucht einen ehrlichen Zustand für die
anderen 80 % — kein „noch keine Daten", sondern eine Alternative (z. B. Potenzial über
*Region × CPV* statt über *eigene Kunden*, was ohne jede Historie funktioniert).

---

## 4 · Wo ich den Favoriten 2 und 3 widerspreche

Beide beruhen auf Freitext, den es überwiegend nicht gibt. Gemessen (s.
`docs/data-sources.md`, „Wie viel Inhalt steht wirklich drin?"):

- Notice-Beschreibung: **61 % unter 200 Zeichen**, Median 129
- mit Los-Texten: Median 432, nur **32,9 %** ≥ 1.000 Zeichen
- getrennt: TED 43,5 % „reich", **DÖE nur 20,8 %**

### Favorit 2 — „Textähnlichkeit alte ↔ neue Ausschreibung"

Die These „Behörden kopieren Leistungsbeschreibungen" ist plausibel — aber sie kopieren sie
**ins Leistungsverzeichnis**, und das steht nicht in TED. Es liegt hinter dem Portal-Link,
den 23,7 % der Ausschreibungen tragen. Embedding-Ähnlichkeit über 129-Zeichen-Mediane misst
Rauschen.

Dazu kommt: das Nachfolge-Modell nutzt **bereits** Titel-Token-Scoring + CPV + Timing +
LLM-Adjudikation und kommt damit auf 100.071 verifizierte Nachfolgen. Der Zugewinn durch
Embeddings auf demselben dünnen Text wäre gering. Die 35 %-Grenze ist keine Methoden-
schwäche, sondern eine **Datengrenze**.

### Favorit 3 — „Zuschnitt auf den Amtsinhaber"

Konzeptionell die beste Idee im Dokument (ein Produkt, das vom Bieten abrät, verdient
Vertrauen). Aber die Signale, die es bräuchte — ungewöhnliche Zertifikatskombinationen,
sehr spezifische Referenzanforderungen, Produktnennungen — stehen in den Vergabeunterlagen,
nicht in der Bekanntmachung.

**Ein billiger Teilersatz existiert aber:** die Zuschlagskriterien selbst. „Preis 100 %"
gegen „Qualität 70 %, Preis 30 %" bei sonst gleichem Gewerk ist ein messbarer Hinweis
darauf, wie viel Spielraum jenseits des Preises besteht. Das ist nicht dasselbe wie
Zuschnitt-Erkennung, aber es ist heute machbar und nicht in zwei Jahren.

---

## 5 · Übersehenes Signal: die Zusammensetzung des Bieterfelds

Weder in 10.1 noch in 10.2 erwähnt, liegt aber im Silber (`awards`, 656.275 Zeilen ab 2020):

| Feld | Abdeckung |
|---|---:|
| `num_tenders` | 77 % |
| **`num_tenders_sme`** | **46,1 %** |
| `num_tenders_electronic` | 61,5 % |
| `num_tenders_other_eu` / `_non_eu` | — |

`num_tenders_sme` beantwortet für einen Mittelständler eine Frage, die `num_tenders` nicht
beantwortet: *„Bei dieser Stelle bieten typisch 6 Firmen — davon 5 KMU"* heißt etwas
völlig anderes als *„6 Firmen, davon 0 KMU"*. Es ist die nächstbeste Annäherung an die
strukturell unmögliche Gewinnquote — nicht „gewinne ich?", aber „spiele ich hier
überhaupt in der richtigen Liga?".

Bei 46 % Abdeckung ist es kein Kern-KPI, aber ein gutes Detailfeld mit Coverage-Flag.

---

## 6 · Kleinere Korrekturen

- **Section 5 ist veraltet:** „73.733 Leads mit Leistungsort" — aktuell sind es 85.947
  Leads gesamt. Die AUC-Zahl (0,767, Stand 2026-07-23) ist dagegen **korrekt und aktuell**.
- **Fragmentierung „4,9 %" vs. `entity_identity` „18,6 % gruppiert"** sind zwei verschiedene
  Kennzahlen (Aufspaltung einer Firma vs. Konzernzugehörigkeit). Im UI nicht vermischen.
- **`lot_count > 1` bei 8,9 %** relativiert die Aussage „Losaufteilung ändert die
  Relevanz-Bewertung erheblich" — sie tut das bei jeder elften Ausschreibung.
- **Los-`end_date` ist zu 0 von 140.568 gefüllt.** Der Wunsch „präzises Auslaufdatum statt
  Schätzung" wird über die Los-Ebene *nicht* erfüllt; es bleibt bei `duration_months`
  (Median 36) und der Lead-Schätzung aus `lead_duration`.

---

## 7 · Empfohlene Reihenfolge

Statt der drei Favoriten des Dokuments:

1. **Zuschlagskriterien parsen** (BT-539/540/541) — 78 %/67 % Abdeckung, sofort
   handlungsrelevant. Die einzige der drei ursprünglichen Favoriten, die trägt.
2. **`procedure_type` ins Frontend** — 98,8 % Abdeckung, bereits im Silber, kostet einen
   Join. Höchste Abdeckung der gesamten Wunschliste und stützt genau das Argument
   „Verhandlungsverfahren = Beziehung zählt mehr als Preis".
3. **4A bauen — aber mit einem Zustand für die 80 % ohne Historie.** Potenzial über
   *Region × CPV* funktioniert ohne jeden eigenen Sieg und ist für Neueinsteiger die
   einzige gefüllte Sicht.
4. `num_tenders_sme` als Detailfeld mit Coverage-Flag.

**Zurückstellen:** Textähnlichkeit und Zuschnitt-Erkennung — nicht weil die Ideen schlecht
sind, sondern weil der Text fehlt. Beide werden interessant, wenn die Vergabeunterlagen
erschlossen sind (das geparkte v3-Thema). Vorher sind sie Aufwand auf dünner Basis.
