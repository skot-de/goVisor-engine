# Sondierung Rumänien

> ⚠ **SONDIERT, NICHT AUFGENOMMEN.**

**Stand 2026-09-03.**

---

## 1. Das Land, das gar nicht da war

Rumänien stand in jeder bisherigen Tabelle dieser Sondierung mit **44 Unterlagen-Links im
Jahr** — bei einem Land dieser Grösse eine Unmöglichkeit, und sie stand als Randnotiz da,
ohne verfolgt zu werden.

Die Ursache waren **zwei Muster-Fehler in meinen eigenen Skripten** (Einzelheiten in
[`linktiefe.md`](linktiefe.md) §4):

1. Rumänien schreibt ausschliesslich `listName="**eforms-**country"`.
2. Seine Wurzelelemente tragen einen Namensraum-Präfix (`<efac:ContractNotice`).

Nach der Reparatur:

| | vorher | jetzt |
|---|---:|---:|
| Ausschreibungen / Monat | **5** | **1.257** |
| Unterlagen-Links / 3 Monate | 12 | **3.603** |

Zur Kontrolle gegen TED gehalten: die TED-API nennt für Juni 2026 **3.866** rumänische
Bekanntmachungen — die Grössenordnung stimmt jetzt. (Bulgarien 2.700/2.696 und Niederlande
2.031/2.024 stimmten schon vorher überein; die Methode war richtig, das Muster nicht.)

## 2. Ein Land, eine Plattform

| | |
|---|---:|
| `e-licitatie.ro` (SEAP/SICAP) | **99,7 %** (3.591 von 3.603) |
| Domains insgesamt | 10 (die übrigen neun zusammen: **12** Nennungen) |
| Links ohne Verfahren | 15,1 % |
| robots.txt | weiches 404 — **nichts untersagt** |

Die Adresse trägt `pub` im Pfad: `/pub/notices/c-notice/v2/view/100207552`.

⚠ Die 15,1 % sind 1.600 blosse `https://www.e-licitatie.ro`-Verweise neben 12.209 tiefen —
dieselbe Sorte wie in Griechenland, nur seltener.

## 3. Die Plattform sagt selbst, dass alles offen ist

Im Abschnitt I.3 jeder Bekanntmachung steht wörtlich:

> *„Documentele de achizitii publice sunt disponibile pentru access **direct,
> nerestrictionat, complet si gratuit**"*
> (direkter, unbeschränkter, vollständiger und kostenloser Zugang)

Und die Seite rendert vollständig **ohne Anmeldung**: Auftraggeber, CPV, Fristen, alle
Abschnitte I–VI, Klarstellungen.

## 4. ⏳ Ein neues Muster: das Archiv wird auf Anfrage gebaut

Rumänien liefert die Unterlagen **nicht als fertige Datei**, sondern baut ein Archiv, wenn
man danach fragt. Drei Schritte, alle anonym:

```
1  GET /api-pub/NoticeCommon/AddArchiveForNotice/?initNoticeId=<id>&sysNoticeTypeId=2
       → { "hasError": false }            ⏳ stösst die Erzeugung an

2  GET /api-pub/NoticeCommon/GetArchiveStatus/?initNoticeId=<id>&sysNoticeTypeId=2
       → { "archiveItem": { "sysArchiveStatusId": 3, "fileSize": 5879841, … } }

3  GET /api-pub/NoticeCommon/DownloadArchive/?initNoticeId=<id>&sysNoticeTypeId=2
       → 200, CN1092260.zip
```

Die Statuswerte stehen im Klartext in der Vorlage der Anwendung:

| Status | Bedeutung |
|---|---|
| 1 | noch nicht angefordert (Knopf „Solicita arhiva") |
| **2 / 4** | **wird gerade erzeugt** („In asteptare generare arhiva") |
| 3 | fertig („Descarca arhiva") |

⚠ **Das ist die erste zweiphasige Quelle der Sondierung.** Ein Abrufer kann hier nicht
einfach eine Adresse ziehen — er muss anfordern, warten und erneut fragen. Von 15
angeforderten Archiven waren nach kurzer Zeit **6 fertig, 9 noch in Arbeit**.

### ⚠ Und ein Kopf, der fehlen darf — aber nicht null sein

Die ersten Aufrufe gaben:
```
HTTP 403  { "message": "Access Denied: Referrer cannot be null." }
```
Mit gesetztem `Referer` auf die Vergabeseite: **HTTP 200**.

Das ist der vierte Fall derselben Klasse (EE `Accept:`, PT curl-Kopf, PT/BG leerer
Parameter). ⚠ Und anders als eine erfundene Browser-Kennung ist eine **wahrheitsgemässe
Herkunftsangabe keine Falschangabe** — die Anfrage kam tatsächlich von dieser Seite.

## 5. Was im Archiv liegt

Belegt: `CN1092260.zip`, **5.879.841 Bytes**, 9 Dateien:

```
Caiet de sarcini servicii fotocopiere.pdf.p7s        Leistungsheft
Proiect Acord cadru … .pdf.p7s                       Rahmenvereinbarung
Model contract subsecvent … .pdf.p7s                 Vertragsmuster
Instructiuni_ofertanti_FisaDate_DF1270393.pdf        Bieterinstruktionen
DUAE_CERERE_369982.xml                               die ESPD
Formulare.rar.p7s                                    Formulare
Clarificare din oficiu.pdf.p7s                       Klarstellung
Clarificare_Oficiu_Automata_CN1092260.pdf
Raspuns consolidat … .pdf.p7s                        ⭐ gesammelte ANTWORTEN
```

⚠ **Der Knopf heisst „arhiva documentatie **si clarificari**"** — Rumänien bündelt
Unterlagen und Bieterfragen in **einem** Paket. `Raspuns consolidat` ist genau das, was
`build_doc_qa_stand.py` liest.

### ⚠ Zwei Verpackungsfallen

**`.p7s` — sieben von neun Dateien.** Das ist ein PKCS#7-Signaturumschlag; die eigentliche
PDF steckt darin. Dieselbe Familie wie Italiens `.p7m`. Wer die Datei direkt an einen
PDF-Leser gibt, bekommt nichts.

**`Formulare.rar.p7s` — dreifach verschachtelt:** ein RAR-Archiv in einem Signaturumschlag
in einem ZIP. Der Strom-Pfad und die Zip-Bomben-Wache aus der Sicherheitshärtung müssen das
aushalten.

## 6. ⚠ Die Datenmenge ist die grösste der Sondierung

Sechs fertige Archive:

| | |
|---|---:|
| Summe | **460,2 MB** |
| Median | 13,24 MB |
| Mittel | **76,70 MB** |
| grösstes | **374,9 MB** (eine einzige Vergabe) |
| kleinstes | 1,78 MB |

Hochgerechnet auf 1.257 Ausschreibungen im Monat: **rund 190 GB/Jahr nach dem Median, rund
1,1 TB/Jahr nach dem Mittel.** Die Wahrheit liegt dazwischen und wird von Ausreissern
bestimmt.

Zum Vergleich: Slowenien ≈ 25 GB/Jahr, Bulgarien ≈ 85 GB/Jahr. **Rumänien allein ist
grösser als beide zusammen, um ein Vielfaches.** Ein Anschluss braucht hier zwingend eine
Grössenschwelle — und `GetArchiveStatus` liefert `fileSize` **vor** dem Herunterladen.

## 7. Nebenbeobachtung

Die Statusantwort enthält einen **internen Netzwerkpfad** des Betreibers:
```
"filePath": "\\\\Fserver14\\FShare2\\SICAPPROD\\notice-archives\\100207552_2_PUB_Generated\\CN1092260.zip"
```
Das ist eine Auskunft über ihre eigene Infrastruktur, die niemand braucht. Für uns heisst
es nur: **das Feld gehört nicht in Bronze** — es ist weder Inhalt noch Metadatum der
Vergabe.

## 8. Ergebnis

| | |
|---|---|
| Dokumente | ✅ offen, dreistufig, anonym |
| robots | ✅ nichts untersagt |
| Bieterfragen | ⭐ **im selben Archiv** (`Raspuns consolidat`) |
| ⏳ Bauart | **zweiphasig** — anfordern, warten, holen |
| ⚠ Kopf | `Referer` muss gesetzt sein |
| ⚠ Verpackung | `.p7s` überall, teils RAR-in-p7s-in-ZIP |
| ⚠ Menge | **die grösste der Sondierung**, bis 375 MB je Vergabe |

**Nicht geprüft:** die unterschwellige Ebene (SEAP führt sie vermutlich mit) und die
Fonds-Ebene. Rumänien ist ein grosser Kohäsionsempfänger und damit dort vorrangig.
