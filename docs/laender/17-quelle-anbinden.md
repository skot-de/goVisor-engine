# 17 · Eine Quelle anbinden — das Wie

> [Kapitel 01](01-quellenlandschaft.md) sagt, **welche** Quellen es geben muss, und
> [Kapitel 03](03-input-dokumente.md), **was** man an Portalen misst. Dieses Kapitel sagt,
> **wie** man sie anschliesst — für Ausschreibungen und für Unterlagen getrennt, weil es
> zwei verschiedene Bauteile mit zwei verschiedenen Verträgen sind.
>
> Entstanden am 2026-08-23, weil beim Trockenlauf auffiel: die Bibel nannte für das Wie
> genau **eine Tabellenzeile**.

## Schritt 0 · Herausfinden, welche Portale das Land überhaupt nennt

Nicht raten und nicht suchen — die Bekanntmachungen sagen es selbst. Der Abrufort steht in
`attributes`:

```sql
SELECT regexp_extract(value, 'https?://([^/]+)', 1) AS portal, count(*)
FROM read_parquet('data/silver/<LAND>/attributes/*/*.parquet', hive_partitioning=1)
WHERE value LIKE 'http%'
GROUP BY 1 ORDER BY 2 DESC LIMIT 15
```

Gemessen an Polen (2026-08-23, 39.998 Links):

```
22.495  ted.europa.eu           ← die Bekanntmachung selbst, kein Portal
 3.730  publications.europa.eu  ← dito
 2.920  uzp.gov.pl              ← Urząd Zamówień Publicznych (Biuletyn)
 1.437  platformazakupowa.pl    ← kommerzielle Plattform
   972  ezamowienia.gov.pl      ← staatliche E-Vergabe
   607  portal.smartpzp.pl
   191  e-propublico.pl
```

⚠ **Zwei Fragen, die man nicht verwechseln darf.** Kapitel 01 sagt zu Recht, dass Polen
seine **Bekanntmachungen** zentral führt (ein Connector statt zwölf). Die **Unterlagen**
liegen trotzdem auf mehreren Plattformen — staatlich *und* kommerziell. Eine zentrale
Bekanntmachungsquelle bedeutet **nicht** eine zentrale Dokumentquelle.

Die ersten beiden Zeilen sind kein Portal, sondern die Bekanntmachung selbst. Wer sie
mitzählt, hält ein Land für erschlossen, das es nicht ist.

## Schritt 0b · Spricht die Quelle einen STANDARD?

Bevor man einen Parser schreibt: liefert die Quelle ein **standardisiertes** Format? Dann
schreibt man den Parser einmal und bekommt jedes weitere Land, das denselben Standard
spricht, fast geschenkt — das ist der einzige Fall, in dem sich ein nationaler Parser doch
überträgt.

Bekannte Kandidaten, die in der Registry als **recherchiert** stehen:

| Standard | Wer ihn spricht | Registry |
|----------|-----------------|----------|
| **OCDS 1.1** (Open Contracting Data Standard) | UK Find a Tender, UK Contracts Finder — und viele weitere weltweit | `uk-fts`, `uk-cf`, Status `candidate` |
| **DECP** (Données Essentielles) | Frankreich, konsolidiert als Parquet/CSV, täglich | `fr-decp`, Status `candidate` |
| **eForms** | EU-weit Pflicht — der TED-Parser deckt das ab | `ted-bulk`, live |

⚠ **`candidate` heisst recherchiert, NICHT gebaut.** Zu OCDS und DECP existiert am
2026-08-23 **keine einzige Zeile Code** ausserhalb von `sources.py`. Genau das ist beim
Schreiben dieses Kapitels passiert: ein Registry-Eintrag wurde für eine Implementierung
gehalten. Die Statusklassen aus [Kapitel 01](01-quellenlandschaft.md) sind kein
Verwaltungskram — sie sind der Unterschied zwischen „wir haben das" und „wir wissen, dass
es ginge".

**Die Frage für ein neues Land lautet also zweistufig:**

1. Spricht das Land einen Standard, für den wir **schon einen Parser haben**? → fast fertig.
2. Spricht es einen Standard, den wir **nur recherchiert** haben? → der Parser lohnt sich
   trotzdem doppelt, weil er beim übernächsten Land wieder trägt.

## Teil A · Ausschreibungs-Connector

### Der Vertrag

Ein Modul `govisor/<quelle>.py` mit drei Aufgaben:

```python
def download(cfg, country, ...) -> int:
    """Quelle → BRONZE. Verlustfrei, im Originalformat, je Monat eine Datei."""

def parse_publication(rec: dict) -> dict[str, list[dict]]:
    """EIN Bronze-Satz → {tabelle: [zeilen]} im Silber-Schema."""

def build_silver(cfg, country) -> int:
    """Bronze → Silber. Dedup je notice_id, partitioniert nach year=."""
```

`parse_publication` ist das Herzstück und der einzige Teil, den man wirklich denken muss.
Was er zurückgibt, sind die Silber-Tabellen aus `govisor/model.py`:

```python
out["notices"]        # Pflicht: notice_id, title, cpv_main, schema_gen, country, …
out["notice_parties"] # buyer/winner mit national_id
out["notice_cpv"]     # Mehr-CPV
out["notice_text"]    # Sprachfassungen (nur wenn es WIRKLICH mehrere gibt)
out["attributes"]     # ALLES, was man nicht typisiert kennt
out["awards"]         # Gewinner, Preis, Bieterzahl
```

### Die fünf Regeln, die dabei zählen

1. **Ein eigener `schema_gen`-Wert.** Ohne ihn sind alle späteren Messungen wertlos
   ([Kapitel 02](02-input-ausschreibungen.md)).
2. **Alles Unbekannte nach `attributes`.** Vier Stufe-1-Kennzahlen wurden später in *einem*
   Durchlauf daraus gelesen statt in 2,5 Stunden Voll-Reparse.
3. **`normalize_notice_id` einhängen**, sonst driften zwei ID-Formate auseinander.
4. **Sprachfassungen nicht wegwerfen** — 31 % der simap-Sätze tragen mehr als eine
   Amtssprache, und `_pick`-artige Funktionen verschenken sie lautlos.
5. **Regionskennung normalisieren.** Liefert die Quelle **NUTS** oder ein nationales
   Kürzel? simap lieferte Kantonscodes (`ZH`, `BE`), und `BE` ist im NUTS-Raum Belgien.
   Das gehört in den Parser, nicht in die Verbraucher ([Kapitel 07](07-geo-und-regionen.md)).

### Anschliessen

```python
govisor/cli.py         # Unterbefehl `ingest-<quelle>` mit --silver
govisor/sources.py     # Registry-Eintrag; bei TED-Ländern leitet sich der Status ab
scripts/daily_leads.sh # in den Nachtlauf, sonst laeuft er nie
```

⚠ Der Status in der Registry ist eine **Aussage**, keine Formalie: `prepared` heisst
„gebaut, läuft nicht" und ist die gefährlichste Klasse ([Kapitel 01](01-quellenlandschaft.md)).

## Teil B · Dokument-Connector

### Erst messen, dann bauen

Die Reihenfolge aus [Kapitel 03](03-input-dokumente.md), und sie ist nicht verhandelbar:

1. Portale auszählen (Schritt 0 oben).
2. Je Portal **eine Handvoll** Vorgänge **anonym** testen.
3. Vier Prüfungen: Trägt der Link zur Vergabe oder nur zum Portal? Ist das PDF die
   Bekanntmachung oder die Unterlage? CAPTCHA? Ist wenigstens die **Dateiliste** offen?
4. Ausbeute eintragen.
5. **Erst dann** entscheiden, ob ein Connector sich lohnt.

Die gemessene Spreizung ist der Grund: 91 % bei `evergabe-online`, 0 % bei `subreport` —
und 0 % heisst nicht immer „gesperrt", oft heisst es „Parser fehlt".

### Der Vertrag

Ein Modul `govisor/docfetch_<portal>.py`:

```python
def ist_<portal>(url: str | None) -> bool:
    """Gehoert diese URL zu diesem Portal?"""

def <portal>_id(url: str | None) -> str | None:
    """Vorgangs-ID aus der URL. Ohne sie kann kein Abrufer folgen."""

def hole_vergabe(url: str, pg, ziel: Path, dry_run: bool = False) -> dict:
    """EINEN Vorgang holen. Gibt einen Status zurueck, keinen Erfolg/Misserfolg."""

def lauf(limit: int | None = None, dry_run: bool = False, country: str = "DE") -> dict:
    """Der Stapellauf ueber die Warteschlange."""
```

### Der Status ist das Wichtigste am Rückgabewert

`hole_vergabe` gibt **keinen Bool zurück**, sondern einen Status, den
`govisor/docfetch_queue.py` einordnet:

```
KEIN_FEHLSCHLAG   downloaded · exists · probe · nur_liste · nur_bekanntmachung
DAUERHAFT         gibt strukturell nichts her — laeuft NIE wieder auf
WARTET            noch nicht so weit (der Vorgang, nicht wir)
BLOCKIERT         existiert, uns fehlt der Zugang
in keiner Menge   der gewoehnliche Fehlschlag — Sperrfrist 7 Tage, dann erneut
```

⚠ **Die Sperrfrist gilt NUR für die letzte Zeile.** Ein blockierter Vorgang läuft nicht
nach sieben Tagen wieder auf, sondern erst, wenn der Blocker gemeldet wird
(`filtere(..., frei={"konto"})`) oder ihn jemand von Hand räumt. Das ist der ganze Zweck
der Klasse: 389 Vorgänge sollen nicht jede Woche gegen dieselbe Anmeldeschranke laufen,
aber auch nicht verloren sein, wenn ein Zugang entsteht.

⚠ **Einen behebbaren Fehlschlag als `konto` abzulegen ist der teuerste Fehler dieser
Achse.** 94 Vorgänge warteten so auf einen Zugang, der ihnen nichts genützt hätte — die
Seite lud, sie war nur anders gebaut als der Parser erwartete. Dafür gibt es
`kein_listenlayout` mit Sperrtyp `parser`: eine **Arbeitsliste**, kein Schicksal.

⚠ **Und der Status altert.** Was der Abrufer heute schreibt, steht morgen noch da und wird
nie wieder geprüft — genau darin liegt die Gefahr. Am 2026-08-24 wurden fünf gewachsene
Abrufer nachgerechnet: **keine einzige ihrer Fehlermeldungen hielt der Prüfung stand**, 433
Vorgänge trugen eine falsche Beschriftung. Der Prüfgang dafür steht in
[Kapitel 03](03-input-dokumente.md), Abschnitt „Ein Status ist eine Behauptung"; er gehört
nach den ersten Läufen eines neuen Connectors einmal gegangen.

### Wenn nur die Liste offen ist

Das ist der Normalfall, nicht die Ausnahme. `nur_liste` ist ein **Erfolg**: aus Dateinamen
lassen sich Dokumenttypen ableiten (`govisor.doctypes.classify`), und 944 Vergaben ohne
jeden Volltext haben darüber trotzdem eine Aussage.

⚠ Dann muss die Anzeige den Unterschied tragen: **`gelesen: false`**, und ein Satz, der
sagt, dass niemand die Datei geöffnet hat. Österreich hat genau diesen Stand — 353 Leads
mit Dateiliste, null Volltexte.

⛔ **CAPTCHA ist eine Grenze, keine Hürde.** Wird nicht gelöst und nicht umgangen.

### Anschliessen

```python
govisor/sources.py     # Eintrag mit ebene="unterlagen" und DOC_CONNECTORS-Connector
scripts/daily_leads.sh # in den Abruf-Schritt
```

## Die Reihenfolge über beide Teile

```
0  Portale auszaehlen        ←  eine SQL-Abfrage, zehn Minuten
A  Ausschreibungen anbinden  ←  Bronze → Silber, dann Kapitel 04/05/06
B  Unterlagen messen         ←  anonym testen, Ausbeute je Portal
B' Unterlagen anbinden       ←  nur wo es sich lohnt
```

**A blockiert B, B blockiert nichts.** Ein Land ohne Unterlagen ist ein halbes Land, kein
unbrauchbares — Österreich und die Schweiz laufen seit Monaten produktiv mit 0 % Volltext.

## Ergebnis dieses Kapitels

- Portalliste des Landes gemessen und in `docs/dokument-zugang-map.md` eingetragen
- Ausschreibungs-Connector läuft im Nachtlauf, Status in der Registry stimmt
- Je Portal ist entschieden: Connector, Dateiliste, oder begründet nichts
