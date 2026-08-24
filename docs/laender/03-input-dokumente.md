# 03 · Input Dokumente — die schwierigste Achse

> Tor 6. Blockiert nichts: **AT und CH stehen bis heute bei 0 % Dokumentabdeckung** und
> sind trotzdem produktiv. Ein Land ohne Dokumente ist ein halbes Land, kein unbrauchbares.

## Warum das die schwierigste Achse ist

Bekanntmachungen sind strukturierte Daten mit einer Quelle. Vergabeunterlagen sind Dateien
hinter Portalen, von denen jedes anders gebaut ist, viele ein Konto verlangen und manche
den Abruf schlicht abweisen. Die Bekanntmachung sagt „Auftragsgegenstand: Sanierung"; die
**Unterlagen** sagen, was gebaut wird, mit welchen Fristen, unter welchen Bedingungen.

Gemessene Realität DE: **nur 33 % der offenen Vergaben sind indiziert.** Das ist der
Trichter, nicht das Ziel.

## Der Trichter, ehrlich benannt

```
Vergabe hat eine Unterlagen-URL          documents_url, DE 96,6 % bei OFFENEN
   ↓  fetch-docs
Portal gibt anonym etwas heraus          je Portal völlig verschieden, s. u.
   ↓  index-docs
Datei ist lesbar und indiziert           PDF/ZIP/GAEB/XLSX
   ↓  signals-docs
Inhalt ist ausgewertet                   Anforderungen, Kriterien, Fristen
```

Jede Stufe hat ihre eigene Ausbeute. Wer nur die erste misst, meldet 96 % und liefert 33 %.

## Portale: messen, nicht glauben

Gemessene Ausbeute je Portal (DE, Stand 2026-08-22) — die Spreizung ist der Punkt:

```
evergabe-online (Bund)   91 %      dtvp                33 %
brandenburg              79 %      evergabe.de          5 %
meinauftrag.rib.de       73 %      simap.ch             0 %
aumass                   62 %      subreport            0 %
                                   deutsche-evergabe    0 %
                                   kkh                  0 %
```

Ein Portal mit 0 % ist **nicht** notwendig gesperrt — es kann auch ein fehlender Parser
sein. Genau dafür gibt es die Sperrtypen unten.

**Anonyme Herausgabe ist die Ausnahme, nicht die Regel.** Belegt herausgebend:
Ausschreibungsblatt und bi-medien geben anonym ZIPs heraus (282 Leads, gemessen 2026-08). `vergabe24` weist
den Client ab.

## Vier Prüfungen je Portal — und keine davon abkürzen

Diese Prüfung wurde in diesem Projekt schon mehrfach zu früh beendet: subreport galt erst
als Bot-Sperre, dann als offen — **beides falsch**.

**1 · Trägt der Link zur Vergabe oder nur zum Portal?** Bei `vemap.com` zeigen **189 von
189** Links auf die Startseite. Ohne Vorgangs-ID kann kein Abrufer folgen. Die
vorgangsgenauen Links gab es bis 2024-11-06 im alten TED-XML; seit eForms tragen die
Auftraggeber nur noch die Wurzel ein.

**2 · Ein PDF ist noch keine Vergabeunterlage.** Was zurückkommt, kann die Bekanntmachung
selbst sein — die haben wir längst. `scripts/probe_portals.py` warnt im Modulkopf davor.

**3 · ⛔ CAPTCHA ist eine Grenze, keine Hürde.** `vergabeportal.at` bietet den anonymen
Download an und sperrt die Dateien per hCaptcha. **Ein CAPTCHA wird nicht gelöst und nicht
umgangen.** Das ist keine technische Frage und steht nicht zur Abwägung.

**4 · Was öffentlich ist, auch nehmen.** Wo die Dateien gesperrt sind, ist oft die
**Dateiliste** offen. Aus Dateinamen lassen sich Dokumenttypen ableiten
(`govisor.doctypes.classify`) — 944 offene Vergaben ohne jeden Volltext haben darüber
trotzdem eine Aussage.

⚠ **Dann muss die Anzeige den Unterschied tragen**: `gelesen: false`, und ein Satz, der
sagt, dass niemand die Datei geöffnet hat. Eine abgeleitete Aussage darf nicht aussehen wie
eine gelesene.

## Die Abrufwarteschlange und ihre Sprache

`govisor/docfetch_queue.py` führt drei Klassen. Die Unterscheidung ist keine Kosmetik,
sondern entscheidet, ob ein Fall als **Arbeitsliste** oder als **Schicksal** dasteht.

| Klasse | Bedeutung |
|--------|-----------|
| `KEIN_FEHLSCHLAG` | `downloaded`, `exists`, `probe`, `nur_liste` … — hat funktioniert |
| `DAUERHAFT` | der Vorgang gibt strukturell nichts her (z. B. Ex-ante-Bekanntmachung) |
| `BLOCKIERT` | kann sich ändern; Sperrfrist `SPERRE_TAGE = 7`, dann erneut versuchen |

`BLOCKIERT` zerfällt in **Sperrtypen**, und dieser Katalog ist der eigentliche Wert:

| Sperrtyp | Fälle | Heisst |
|----------|-------|--------|
| `konto` | `gated`, `gesperrt`, `abgewiesen`, `nicht_angemeldet`, `kein_zugriff`, `kein_token` | Zugang nötig |
| `interesse` | `interesse_noetig`, `interesse_abgelehnt` | Interesse je Vergabe bekunden (simap) |
| `parser` | `kein_listenlayout` | **unser** Problem, nicht das des Portals |
| `portal` | `nur_cockpit`, `nur_einzeldateien` | Portal gibt anonym nur die Oberfläche her |
| `groesse` | `zu_gross` | über der Grössengrenze DIESES Laufs |

⚠ **`parser` wurde bewusst aus `konto` herausgelöst.** 94 Fälle lagen als „Zugang nötig"
ab und warteten damit auf ein Konto — dabei lud die Seite, sie war nur anders gebaut als
der Parser erwartete. Alle 94 auf `meinauftrag.rib.de`, einem Portal, das sonst 73 %
liefert. Falsch klassifiziert heisst: als unlösbar abgelegt.

**Regel:** ein Fehlschlag, den wir beheben können, bekommt eine eigene Klasse. Sonst
verschwindet er in einer Kategorie, die niemand mehr anfasst.

### ⚠ Ein ungeklärter Fehlversuch wartet auf UNS, nicht auf die Welt

Der Ertragsbericht (`python3 -m govisor.ertrag --country XX`) sortiert jeden Manifest-Satz
in vier Klassen: `erledigt`, `dauerhaft`, `blockiert:<typ>` — und **`offen`** für alles,
was in keine der drei fällt.

Diese vierte Klasse ist die gefährliche. Sie liest sich wie „steht noch aus", und bis zum
2026-08-24 wurde sie **gar nicht ausgegeben**. Gemessen verbargen sich dahinter:

```
netserver         364   261× keine Version gelistet     ← unser Parser
evergabe          241   240× NameError                  ← UNSER Fehler, eine Woche unsichtbar
subreport         165   124× 0 Dateien
evergabe_online    35   23× keine Unterlagen
```

Der `NameError` stand seit dem 17.08. im Manifest, sauber protokolliert, und wurde am
21.08. behoben (`04d2dd8`, „fehlende Zeile legte den Abrufer drei Tage still") — gefunden
hat ihn niemand über den Bericht, weil der Bericht ihn nicht zeigte.

**Ein Bericht, der die Antwort hat und sie zudeckt, ist schlimmer als keiner: er beruhigt.**

Der Abschnitt heisst deshalb „UNGEKLAERT" und steht neben „BLOCKIERT". Der Unterschied ist
der Adressat: ein blockierter Vorgang wartet auf einen Zugang, ein ungeklärter auf uns.

⚠ Beim Bauen selbst hineingetappt: die erste Fassung zählte die Notizen **aller** Zeilen
und meldete „1494×" bei 364 Fällen. Eine Zahl, die grösser ist als ihre Grundmenge, ist
keine Auskunft, sondern ein Warnsignal.

### Statusklassen ehrlich halten

`gated` heisst „existiert, uns fehlt ein Zugang" und parkt Vorgänge **dauerhaft**. Am
2026-08-22 lagen darin drei verschiedene Lagen; **148 von 406** warteten auf ein Konto, das
ihnen gar nicht geholfen hätte (404/410-Fälle und Parser-Probleme). Beim Anlegen eines
Connectors gilt:

- **`weg`** für 404/410 — dauerhaft, kein Nachfassen.
- **`kein_listenlayout`** (Sperrtyp `parser`) für „Seite lädt, wir lesen sie nicht" — eine
  **Arbeitsliste**, kein Schicksal. Freigabe über `scripts/entsperren.py`.
- **`gated`** nur für echte Anmeldeschranken.

## Fallen beim Abruf

- **⚠ Ein positives Merkmal ist nur dann ein Nachweis, wenn es nicht auch im Rahmen
  drumherum stehen kann.** Der NetServer-Abrufer schloss nicht aus der Abwesenheit — er
  prüfte eigens nach, ob die Seite den Unterlagen-Abschnitt trägt, und meldete nur dann
  „wirklich keine Datei". Genau richtig gedacht, und trotzdem falsch: geprüft wurde
  `document.body.innerText` der ganzen Seite, und die Brotkrume von had.de lautet auf JEDER
  Seite „… | eHAD-Vergabeunterlagen". Die Wache las das Menü und bestätigte sich selbst.
  188 Vorgänge lagen deshalb als „hat keine Unterlagen" auf Halde; die Stichprobe nach der
  Korrektur fand bei 21 von 25 welche. **Ein Merkmal im Suchbereich einschränken, sonst
  bestätigt die Navigation jede Behauptung.**
- **Frameset-Portale: `page.query_selector` sieht nur den Hauptrahmen.** `www.had.de` ist
  eine leere Hülle, die Anwendung läuft auf `vergabe.had.de` in einem Kindrahmen. Wer die
  Seite abfragt, durchsucht das Menü. Den Inhaltsrahmen am MERKMAL suchen (wer den Knopf
  trägt, ist der Inhalt; sonst der Kindrahmen, der dieselbe Vorgangs-ID lädt), niemals am
  Hostnamen — siehe auch [Kapitel 02](02-input-ausschreibungen.md), dort dieselbe Lehre.
- **Ein Portal, zwei Oberflächen.** NetServer läuft in einer älteren Bauform (Modal je
  Version) und einer neueren (Sammelknopf, kein Modal, andere CSS-Klassen). Wer nur die
  bekannte Bauform kennt, meldet auf der anderen „keine Version gelistet", obwohl die Seite
  die Dateien sichtbar auflistet. **Vor „das Portal gibt nichts her" einmal in den Quelltext
  sehen, was es tatsächlich anbietet.**
- **„Sichtbarkeitszeitraum abgelaufen" ist DAUERHAFT, nicht offen.** Sagt das Portal selbst,
  dass der Vorgang ausserhalb seines Fensters liegt, hilft kein zweiter Versuch und kein
  Konto. Ohne eigene Klasse läuft der Vorgang alle sieben Tage erneut gegen dieselbe Wand.
- **⚠ Eine Zahl ist keine Diagnose.** subreport meldete für 124 Vorgänge „0 Dateien" — ein
  Satz, der wie „diese Vergabe hat keine Unterlagen" klingt. Nachgemessen waren es VIER
  verschiedene Dinge, jedes mit einer anderen Konsequenz: Anmeldung nötig (blockiert,
  wartet auf ein Konto), Gültigkeit abgelaufen und Vergabe aufgehoben (beides dauerhaft,
  nie wieder versuchen) und beschränkte Vergaben mit Passwort für eingeladene Bieter. Nur
  ein kleiner Rest war wirklich unerklärt. **Wo ein Abrufer eine Zahl zurückgibt, gibt er
  keinen Grund zurück — und ohne Grund landet alles in derselben Schublade.** Die Seite
  selbst weiß es fast immer; sie sagt es in der Statusspalte.
- **⚠ Der positive Befund muss die Rangfolge anführen.** Trägt die Seite einen Ausklapper
  oder einen Knopf, wird geholt — erst wenn es ihn NICHT gibt, wird nach dem Grund gesucht.
  Andersherum kann ein Wort aus einer Nachbarzeile („canceled" bei Los 2, während Los 1
  offen ist) eine laufende Vergabe abstempeln. Dieser Fehler erzeugt keinen Fehlschlag,
  sondern eine falsche Gewissheit, und die sieht niemand im Bericht.
- **Hängende Abrufer.** `SIGALRM` wird von Playwright verschluckt. Es braucht eine Wache
  ausserhalb des Prozesses, sonst steht ein Lauf still und meldet nichts.
- **Zip-Bomben.** Grössengrenze und Entpack-Grenze sind Pflicht, nicht Kür.
- **Grosse und verschachtelte Dateien** brauchen den Strom-Pfad, nicht den Speicher-Pfad.
- **Der Manifest-Irrtum.** Ich hielt den cosinex-Abrufer für einen, der das Manifest
  überschreibt — er **merged je Schlüssel**. Vor dem Umbau nachlesen statt annehmen.
- **`index-docs --neu-aufbauen` niemals direkt starten.** Er liest stundenlang denselben
  Baum, in den ein Abruf schreibt. Am 2026-08-15 lief so ein Neuaufbau 9,5 h durch und
  startete am selben Abend erneut. Siehe [Kapitel 11](11-betrieb.md).

## Doktyp-Erkennung

Drei Stufen, in dieser Reihenfolge:

1. **Dateiname** — billig, trifft oft
2. **VHB-Nummer** — formalisiert, sehr sicher, wo vorhanden
3. **Inhaltsprobe** — teuer, letzte Instanz

Abdeckung dadurch von 50 % auf 78 %. Fünf Sprachräume sind hinterlegt.

⚠ **Punktwertung statt Erster-Treffer.** Der erste Treffer gewinnt sonst gegen den
besseren. Und: als die Zuschlagskriterien-Erkennung *sank*, war das kein Rückschritt,
sondern eine bereinigte Fehlalarmquote — beim Messen unbedingt auseinanderhalten.

## Dokument-Dubletten — der zweite Wall

Gleiche Form wie der Bekanntmachungs-Wall ([Kapitel 04](04-dublettenwall.md)): **Paare
statt Ergebnisspeicher**. Gemessen sind **22 % des Textbestands Kopie**.

⚠ Nur belegte Master verwenden — 46 % der Kandidaten hielten der Prüfung stand.

## Für ein neues Land

1. Welche Portale nennt die Bekanntmachung überhaupt? (`documents_url` auszählen)
2. Je Portal **eine Handvoll** Vorgänge anonym testen, bevor ein Connector entsteht.
3. Ausbeute je Portal messen und in `docs/dokument-zugang-map.md` eintragen.
4. Sperrtypen zuordnen — insbesondere: ist es `konto` oder in Wahrheit `parser`?
5. Erst dann entscheiden, ob sich ein Connector lohnt.

## ⚠ `has_documents` heisst NICHT „wir haben die Unterlagen"

Gefunden am 2026-08-23 beim Nachprüfen der Behauptung „AT und CH stehen bei 0 %". Die
Behauptung stimmt — DE hat 7.781 Vorgänge im Volltext-Index, AT und CH je **null**. Aber
das Feld, mit dem man es zu messen versucht ist, sagt etwas anderes, und das Ergebnis ist
im Produkt **umgekehrt**:

```
DE   27.860 offene Leads zeigen „unknown"   obwohl 7.781 Vorgänge indiziert sind
CH    1.369 zeigen „offen"                  obwohl NULL Dokumente abgerufen wurden
```

`has_documents` bedeutet **„die Quelle bewirbt Unterlagen"**, nicht „wir haben sie". Für
CH füllt es die simap-Projektbrücke; für DE füllt es **niemand**, obwohl dort
`documents_url` bei den offenen Leads zu 96,6 % steht. Ein deutscher Nutzer liest damit
„unbekannt", wo der Volltext vorliegt, ein schweizerischer „offen", wo nichts da ist.

**Für ein neues Land heisst das:** zwei Fragen sauber trennen und beide getrennt messen.

1. **Bewirbt die Quelle Unterlagen?** (`documents_url`, `has_documents`) — sagt etwas über
   die Bekanntmachung.
2. **Haben wir sie geholt und gelesen?** (`data/docs/<LAND>/doc_text.parquet`) — sagt etwas
   über uns.

Wer Frage 1 misst und Frage 2 meint, bekommt eine Zahl, die in die falsche Richtung zeigt.

**AT und CH als Warnung**: beide stehen bei 0 % (gemessen 2026-08-23 an
`data/docs/<LAND>/doc_text.parquet`). CH hängt komplett an simap.ch, das eine
Interessensbekundung je Vergabe verlangt (889 Leads betroffen) — eine Kontofrage, keine
technische. AT hat zwei Portalfamilien, die **nie geprüft** wurden. Das ist kein
Versäumnis der Pipeline, sondern eine offene Aufgabe, und sie steht als solche da.
