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
