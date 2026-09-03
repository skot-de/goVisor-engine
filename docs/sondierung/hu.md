# Sondierung Ungarn

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.**

**Stand 2026-09-03.**

---

## 1. Ein Land, ein System, eine ausdrücklich öffentliche Schnittstelle

| | |
|---|---:|
| `ekr.gov.hu` (EKR) am Unterlagen-Feld | **99,3 %** (4.644 von 4.678, 12 Monate) |
| Links ohne Verfahren | **0,0 %** |
| robots.txt | weiches 404 (liefert die Anwendung) — nichts untersagt |

TED verlinkt sauber: `https://ekr.gov.hu/eljarastar/eljaras/**EKR000457332026**`.

Dahinter liegt eine Angular-Anwendung, aber die Schnittstelle trägt ihre Absicht im Pfad:

```
GET  /eljarastar/api/public/eljaras/EKR000457332026?relevansReszek=null
GET  /eljarastar/api/public/kereso?jovobeli=true&aktualis=true&offset=0&limit=100
GET  /eljarastar/api/public/szotar/{CPV_KODOK|NUTS_KODOK|ELJARAS_TIPUS|ELJARAS_SZAKASZ}
POST /eljarastar/api/public/document      {"dokumentIdList":["<guid>", …]}
```

**Vier öffentliche Endpunkte: Vergabe, Suche, Wörterbücher, Dateien.** Nichts davon musste
geraten werden — die Suche liess sich mitschneiden, der Dateiabruf stand im Bündel.

## 2. ✅ Der Dateiabruf bündelt serverseitig

```
POST /eljarastar/api/public/document
     {"dokumentIdList":["81b9a18e-…"]}          → die einzelne Datei
     {"dokumentIdList":["…","…", 15 Stück]}     → EIN ZIP mit allen
```

Belegt: 15 Dokumente einer Vergabe als **ein 8.954.378-Byte-ZIP**, ein einziger Aufruf.

⚠ **Das kann kein anderes Portal der Sondierung.** Überall sonst ist eine Datei ein Abruf;
Slowenien braucht für dieselbe Vergabe so viele GETs wie es Dateien gibt. Für einen
Massenabruf ist das der Unterschied zwischen einem und fünfzehn Verbindungsaufbauten.

Inhalt des ZIP (Auszug):
```
Ingatlan_felujitas_2026_KD_2mod_v20260729.pdf          585 KB   Vergabeunterlage
Ingatlan_felujitas_2026_Kieg_taj_02/03/04.pdf       3× ~450 KB  ergänzende Auskünfte
…Egységár-gyűjtemény_jav.xlsx                          390 KB   Einheitspreistabelle
FSZ.DWG                                              6.603 KB   CAD-Zeichnung
```

⚠ **Zeichensatz:** die Namen im ZIP kommen als `Egys+?g+?r-gy+?jtem+?ny` an — ungarische
Sonderzeichen in der veralteten Kodierung der ZIP-Einträge. Dieselbe Familie wie Zyperns
zerschossene Kopfzeile. **Vor dem ersten Abruf klären**, nicht danach.

## 3. Gemessen: 64 %, und die 36 % sind keine Fehler

25 Vergaben, jede einzeln:

| | Anzahl | |
|---|---:|---|
| mit Dokumenten | **16** | 68 Dateien |
| ohne Dokumente | 9 | |

⚠ **Die neun leeren sind keine Ausfälle.** Sie liefern eine vollständige Antwort mit
gültigem Verfahrensstand (E30, E40, E50, ein `E72_VISSZAVONT` = zurückgezogen) und 1 bis 6
Bekanntmachungen — nur eben eine leere Dokumentenliste. Das ist die Antwort des Portals,
kein Abbruch. Ein Abrufer darf das nicht als Fehlschlag zählen und wiederholen.

## 4. ⭐ Ungarn typisiert seine Dokumente an der Quelle

Jedes Dokument trägt einen `dokumentumTipus.kod`. Über die 25 Vergaben:

| Typ | Vergaben | Bedeutung |
|---|---:|---|
| `OSSZEGZES_ELBIRALASROL` | 9 | Zusammenfassung der Wertung |
| `KOZBESZERZESI_DOKUMENTACIO` | 5 | Vergabeunterlage |
| **`KIEGESZITO_TAJEKOZTATAS_NYUJTASA`** | **3** | **ergänzende Auskunft = Bieterfragen** |
| **`ELOZETES_VITARENDEZES`** | **3** | **vorherige Streitschlichtung** |
| **`ELOZETES_VITARENDEZES_MEGVALASZOLASA`** | **3** | deren Beantwortung |
| `MUSZAKI_LEIRAS` | 2 | Leistungsbeschreibung |
| `RESZLETES_ARTABLAZAT` | 2 | detaillierte Preistabelle |
| `SZERZODES_TERVEZET` | 1 | Vertragsentwurf |

⚠ **Das ist genau das, was der Doktyp-Parser mit drei Stufen erarbeitet** (Name →
VHB-Nummer → Inhaltsprobe, 78 % Treffer). Ungarn liefert es als Code. Wo eine Quelle den
Typ selbst vergibt, sollte der Parser sie **nicht überstimmen** — der Anschluss muss das
Feld durchreichen, nicht neu raten.

⚠ **Und `ELOZETES_VITARENDEZES` ist eine Gattung, die goVisor nirgends kennt:** die
förmliche Rüge eines Bieters gegen die Vergabebedingungen **vor** Angebotsabgabe, samt
Antwort der Vergabestelle. Das ist ein schärferes Signal als eine gewöhnliche Frage — es
sagt, dass jemand das Verfahren für angreifbar hielt. Drei von 25 Vergaben tragen so etwas.

## 5. ✅ Die unterschwellige Ebene liegt im selben Register

```
GET /eljarastar/api/public/kereso?jovobeli=true&aktualis=true&offset=0&limit=100
    → totalRecords: 4.417 · 45 Seiten
```

Nach Verfahrensordnung (Stichprobe von 100):

| Ordnung | Anteil | Ebene |
|---|---:|---|
| **Uniós** (unionsrechtlich) | 40 % | oberschwellig → TED |
| **EPK** | 37 % | national |
| **Nemzeti** (national) | 23 % | national |

**60 % des Registers erreichen TED nie.** Wie in Polen und Slowenien: eine zentrale Quelle
für beide Ebenen, kein zweites Portal.

Dazu liefert `/szotar/` die Referenzvokabulare (CPV, NUTS, Verfahrensarten,
Verfahrensstände) öffentlich mit — die Codetabellen müssen also nicht anderswo beschafft
werden.

## 6. Was nicht geprüft ist

- **Fonds-Ebene.** Ungarn ist ein grosser Kohäsionsempfänger und gehört damit nach der Regel
  aus [`fonds-ebene.md`](fonds-ebene.md) zu den vorrangigen Kandidaten. Ungeprüft.
- **Reichweite der Suche.** `aktualis=true&jovobeli=true` filtert auf laufende und künftige
  Verfahren; wie weit das Archiv zurückreicht, wurde nicht ausgelotet.
- **Umfang.** Die 25 geprüften Vergaben wurden nur gelistet, nicht vollständig geladen — nur
  eine Vergabe (15 Dateien, 9 MB) wurde tatsächlich gezogen. Eine Hochrechnung wäre geraten.

## 7. Ergebnis

| | |
|---|---|
| Dokumente | ✅ **64 %** der Vergaben, per POST, **serverseitig gebündelt** |
| robots | ✅ nichts untersagt |
| Unterschwellig | ✅ dasselbe Register, **60 % der Einträge** |
| Aufzählbar | ✅ `kereso` mit offset/limit, 4.417 laufende |
| Besonderheit | ⭐ **Dokumenttyp an der Quelle vergeben**, inkl. Bieterfragen und Rügen |
| ⚠ Vorsicht | ZIP-Namen in alter Kodierung · leere Dokumentenliste ist eine Antwort, kein Fehler |
