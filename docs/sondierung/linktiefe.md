# Wie viele Unterlagen-Links nennen überhaupt ein Verfahren?

**Stand 2026-09-03**, drei Monate (2026-04 bis 2026-06), `scripts/miss_linktiefe.py`.

---

## 1. Warum es diese Messung gibt

Die Frage entstand im griechischen Kapitel: dort führten **43 %** der Unterlagen-Links auf
eine Startseite statt auf ein Verfahren — einer sogar auf `/webcenter/portal/TestPortal`.
Die Domain sagt, **wer** verlinkt; sie sagt nicht, **ob etwas dahintersteht**.

⚠ Danach wurde die Prüfung je Land **neu hingeschrieben**, und das ging schief. Siehe §3.

## 2. Das Ergebnis

| Land | tief | Startseite | ohne Verfahren |
|---|---:|---:|---:|
| DE | 21.769 | 300 | 1,4 % |
| **PL** | 9.086 | 7.439 | **45,0 %** ⚠ |
| **FR** | 10.035 | 5.071 | **33,6 %** ⚠ |
| **ES** | 5.586 | 1.533 | **21,5 %** ⚠ |
| **IT** | 3.125 | 2.270 | **42,1 %** ⚠ |
| **CZ** | 1.804 | 2.970 | **62,2 %** ⚠ |
| BE | 3.487 | 91 | 2,5 % |
| SE | 2.820 | 4 | 0,1 % |
| NL | 2.645 | 19 | 0,7 % |
| FI | 2.174 | 63 | 2,8 % |
| PT | 2.199 | 33 | 1,5 % |
| LT | 2.168 | 8 | 0,4 % |
| **HR** | 2.062 | 0 | **0,0 %** |
| **BG** | 2.056 | 1 | **0,0 %** |
| NO | 1.999 | 12 | 0,6 % |
| **SI** | 1.875 | 0 | **0,0 %** |
| CH | 1.717 | 0 | 0,0 % |
| IE | 1.659 | 27 | 1,6 % |
| **LV** | 1.678 | 0 | **0,0 %** |
| **HU** | 1.164 | 0 | **0,0 %** |
| SK | 1.069 | 5 | 0,5 % |
| DK | 871 | 118 | 11,9 % |
| **GR** | 567 | 391 | **40,8 %** ⚠ |
| EE | 948 | 3 | 0,3 % |
| LU | 521 | 8 | 1,5 % |
| MT | 348 | 2 | 0,6 % |
| **CY** | 287 | 0 | **0,0 %** |
| **AT** | 33 | 107 | **76,4 %** ⚠ |
| IS | 110 | 24 | 17,9 % |
| **RO** | 6 | 6 | **50,0 %** ⚠ |

**Tschechien ist der auffälligste Fall: 62,2 %.** Der Grund steht in den Adressen —
`nen.nipez.cz/profil/MVCR` ist ein **Käuferprofil**, nicht ein Verfahren. Tschechische
Bekanntmachungen verlinken das Profil der Vergabestelle, und wer dort hingeht, muss das
Verfahren erst suchen.

⚠ **Was diese Spalte NICHT ist:** ein Mass für Abrufbarkeit. Die Schweiz steht bei 0,0 %
und ist trotzdem zu (Anmeldung). Kroatien steht bei 0,0 % und ist verboten. Die Spalte sagt
nur, wie viel des Feldes überhaupt eine brauchbare Adresse trägt — sie begrenzt die
Obergrenze, sie ersetzt keine Prüfung.

## 3. ⚠ Die Regel musste dreimal repariert werden

Jede Reparatur kam von einem Land, das die vorherige Fassung falsch abgestempelt hätte:

| Land | Adresse | was fehlte |
|---|---|---|
| **HR** | `/tender-eo/84749` | vier Ziffern müssen reichen, nicht erst sechs Hexzeichen |
| **EE** | `#/procurement/9490004/documents` | die Kennung steht in der **Raute** — `urlsplit` legt sie weder in Pfad noch Abfrage |
| **CH** | `?context=eyJwYWdlIjoi…` | Base64 ohne Ziffernfolge; ein langes undurchsichtiges Zeichenband **ist** eine Kennung |

Und eine **Gegenreparatur**, weil die dritte Regel zu weit ging:

| **ES** | `sicpportal/mtoAnunciosLicitacion.aspx` | ein **lesbares Wort** von 21 Zeichen ist keine Kennung — die Regel gilt nur in Abfrage und Raute, nie im Pfad |

Was die Reparaturen bewirkt haben:

| | vorher | nachher |
|---|---:|---:|
| EE | 99,8 % ohne Verfahren | **0,3 %** |
| CH | 100,0 % | **0,0 %** |
| ES | 87,6 % | **21,5 %** |
| DK | 28,4 % | 11,9 % |
| HR | 0 % tief | **100 % tief** |

⚠ **Drei dieser Zahlen hätte ich beinahe als Befund veröffentlicht.** „Estland verlinkt
keine Verfahren" wäre ein sauber gemessener, vollständig falscher Satz gewesen — und er
hätte dem Baltikum-Kapitel widersprochen, ohne dass jemand nachgesehen hätte, wer recht hat.

**Die Lehre:** eine Heuristik, die je Messung anders lautet, ist keine Messung. Sie gehört
an eine Stelle, mit Gegenproben — `scripts/miss_linktiefe.py` trägt zwölf davon im
Kommentar, darunter ausdrücklich die Fälle, die **flach bleiben müssen**.

---

## 4. ⚠ Nachtrag 2026-09-03: zwei Muster-Fehler machten zwei Länder unsichtbar

Beim Nachgehen einer Auffälligkeit (Rumänien mit 44 Unterlagen-Links im Jahr) kamen **zwei
Fehler in den Sondierungsskripten** heraus. Beide betrafen `sondiere_tief.py`,
`sondiere_portale.py` und `miss_linktiefe.py` — **nicht** die Pipeline.

**1. Der Codelisten-Name.** Rumänien schreibt ausschliesslich:
```xml
<cbc:IdentificationCode listName="eforms-country">ROU</cbc:IdentificationCode>
```
Die Skripte kannten nur `listName="country"`. ⚠ `govisor/schema.py:1799` führt
`COUNTRY_LIST_NAMES = (None, "country", "eforms-country")` **seit längerem** — mit einem
Kommentar, dass genau das schon einmal aufgefallen war. Die Sondierung hat die Lehre nicht
übernommen.

**2. Der Namensraum-Präfix.** `<(ContractNotice)[ >]` verfehlt jede Wurzel mit Präfix
(`<efac:ContractNotice`). Betroffen: RO, AT, ES, SE, DE.

**Gegenprobe an einem Monat, gleiche Einheit, vorher/nachher:**

| Land | vorher | jetzt | Diff |
|---|---:|---:|---:|
| **RO** | 5 | **1.257** | +1.252 |
| **AT** | 46 | **584** | +538 |
| ES | 2.458 | 2.745 | +287 |
| SE | 738 | 989 | +251 |
| DE | 7.811 | 7.948 | +137 |
| **gesamt** | 36.833 | **39.318** | **+6,7 %** |

Gegen TED gehalten: die API nennt für Rumänien im Juni **3.866** Bekanntmachungen; unser
Paket enthielt sie, wir haben sie nur nicht erkannt (Bulgarien 2.700/2.696 und Niederlande
2.031/2.024 stimmten überein — die Methode war richtig, das Muster nicht).

**Was das an den Länderkapiteln ändert:**

| Land | alt | neu |
|---|---|---|
| **RO** | „44 Links/Jahr, nur TED" | **`e-licitatie.ro` 99,7 %**, 3.607 Ausschreibungen/3 Mon., 15,1 % ohne Verfahren — ein **Ein-Plattform-Land**, bisher unsichtbar |
| **AT** | „33 Links, 76,4 % ohne Verfahren" | 1.668 Ausschreibungen/3 Mon., **90 Domains**, `*.vergabeportal.at` führend, 31,5 % ohne Verfahren |

ES, SE und DE verschieben sich um 3–12 % — ihre Urteile (5 % / 0 % / 32 %) ändert das nicht.

⚠ **Die Lehre, und sie ist unangenehm:** eine Auffälligkeit, die ich in der Übersicht als
Randnotiz abgelegt hatte („RO 44 Links — eher ein Problem unserer Extraktion"), war genau
das. Sie stand da, richtig benannt, und wurde nicht verfolgt, bis Sven nachfragte.
**Eine notierte Auffälligkeit ist keine erledigte.**

## 5. Stand des Neulaufs (2026-09-03)

Die reparierten Skripte sind **geprüft, aber die kanonischen Dateien sind noch alt.**

Ein Probelauf über **einen** Monat (Ausgabe in den Notizordner, nicht nach `data/`) bestätigt
die Reparatur:

| | alt | Probelauf |
|---|---:|---:|
| Länder | 30 | **31** (LI kam dazu) |
| RO | 6 tief / 6 flach | **1.067 / 189** → 15,0 % |
| AT | 33 / 107 | **380 / 199** → 34,4 % |
| CZ | — | 60,5 % ⚠ |
| GR | — | 41,0 % ⚠ |

⚠ **`data/sondierung/_tief/` und `linktiefe.json` stehen weiterhin auf den alten Mustern.**
Der Neulauf schreibt nach `data/` und wurde **nicht gestartet**, weil `scripts/laeuft_was.sh`
laufende Prozesse meldet (Healy-Hudson-Abrufer, `analyze_docs`, zwei Arbeiter der zweiten
Sitzung).

**Zu tun, sobald die Bahn frei ist:**
```
scripts/laeuft_was.sh && python3 scripts/sondiere_tief.py --monate 12
scripts/laeuft_was.sh && python3 scripts/miss_linktiefe.py --monate 3
```
Danach stimmt auch die Spalte „EU-Anteil" in [`00-uebersicht.md`](00-uebersicht.md).
