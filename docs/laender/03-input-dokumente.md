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
- **`nicht_bereitgestellt`** (Sperrtyp `portal`) wenn das Portal die Herausgabe verweigert
  und an einen menschlichen Kanal verweist. Kein Konto hilft, kein zweiter Versuch, und es
  ist trotzdem nicht „dauerhaft": die Vergabestelle kann die Unterlagen nachreichen.
- **`nicht_veroeffentlicht`** (Menge `WARTET`) für „der Vorgang ist noch nicht so weit".
  Das wartet auf die WELT, nicht auf uns — und gehört deshalb nicht in dieselbe Liste wie
  unsere eigenen Fehler. Am Ablauf ändert es nichts (dieselbe Sperrfrist), an der
  Buchführung alles.

Ob die Klassen im Bestand auch wirklich stimmen, beantwortet keine Regel, sondern der
Prüfgang im nächsten Abschnitt.

**⚠ Die Probe für „dauerhaft": kannst du begründen, warum es sich NIE ändern kann?** Wenn
nicht, gehört es nicht dorthin. `kein_downloadbereich` stand bis zum 2026-08-24 unter
dauerhaft, weil das zentrale Dashboard von deutsche-evergabe den Vorgang zwar listet, aber
keine Dateien trägt. Nachgesehen: **jede** Spur auf dieser Seite führt auf `/Account/Login`
oder `/Account/Register`, die Vorgangszeile selbst hat gar kein Ziel. Das ist eine
Zugangsfrage, keine strukturelle Leere. 171 Vorgänge waren damit stillschweigend
abgeschrieben statt als Reichweite geführt — genau der Verlust, vor dem der Kopf von
`docfetch_queue.py` warnt.

## ⚠ Ein Status ist eine Behauptung — und sie war fünfmal von fünf falsch

Am 2026-08-24 wurden fünf Abrufer nachgeprüft, weil ihre Fehlermeldungen zum ersten Mal im
Ertragsbericht sichtbar wurden (siehe oben, „Ein ungeklärter Fehlversuch wartet auf UNS").
Geprüft wurde jeweils dieselbe Frage: **stimmt, was der Vermerk behauptet?**

| Abrufer | Vermerk im Manifest (Stand 2026-08-24) | Fälle | Was tatsächlich dahinterlag |
|---|---|---:|---|
| netserver | „keine Version gelistet" | 261 | 25 von 30 hatten Unterlagen (477 Dateien) |
| subreport | „0 Dateien" | 124 | vier Zustände: Konto, Frist, Aufhebung, Passwort |
| evergabe-online | „keine Unterlagen" | 23 | 17× Vertraulichkeit, 4× Frist, 2 hatten ein ZIP |
| healyhudson | „keine Dateien auf der Vorgangsseite" | 14 | 3 unveröffentlicht, 3 weg, 7 hatten Dateien |
| staatsanzeiger | „kein ZIP-Link auf der Trefferliste" | 11 | 7 hatten einen Link, 4 tragen eine Absage |

**433 Vorgänge trugen einen dieser fünf Vermerke; hochgerechnet aus den Stichproben traf
er auf rund neun von zehn nicht zu.** Ein Rest war wirklich leer — dass es ihn gibt, ist
kein Einwand, sondern der Grund, warum der falsche Teil so lange unbemerkt blieb. Dazu
kamen zwei als *dauerhaft* abgeschriebene Gruppen (171 + 78): dort hielt das Urteil, aber
mit einer Begründung, die sich widerlegen liess.

### Warum das kein Zufall ist, sondern die Bauart

Ein falsches „leer" verhält sich anders als ein Absturz. Es wirft keine Ausnahme, füllt
kein Fehlerprotokoll und sieht im Bericht aus wie erledigte Arbeit. Es ist die einzige
Fehlerart, die sich selbst versteckt — und deshalb die einzige, nach der man **aktiv suchen
muss**. Ein Abrufer, der nie „leer" meldet, ist verdächtiger als einer, der es oft tut.

Der zweite Grund ist die Blickrichtung. Ein Abrufer sucht, was er kennt: einen Knopf, einen
Link, eine Dateiliste. Findet er ihn nicht, hat er streng genommen nur festgestellt, dass
**sein Suchmuster nicht passte**. Daraus einen Satz über die Vergabe zu machen, ist ein
Sprung, den der Code nicht belegen kann. Fast immer sagt die Seite den Grund selbst — in
der Statusspalte, im Fliesstext, in der Adresse der Fehlerseite. Nur eben nicht dort, wo
der Abrufer hinsieht.

### Der Prüfgang für einen Abrufer

Wiederholbar, in dieser Reihenfolge, und er dauert eine gute Stunde je Abrufer:

1. **Bahn prüfen.** `scripts/laeuft_was.sh` — und die AUSGABE GANZ lesen. Ein `tail -3`
   verdeckt den Prozessblock; genau das ist am 24.08. passiert.
2. **Gruppen zählen.** Status und Notizen aus dem Manifest, absteigend. Schon hier fällt
   auf, wenn eine Notiz für Hunderte Fälle gleich lautet.
3. **Den bestehenden Code erneut laufen lassen**, ohne eine Zeile zu ändern. Das trennt
   „kaputt" von „damals noch nicht da". Ausbeute an drei Abrufern: 7 von 14, 7 von 11,
   2 von 23. **Wer diesen Schritt überspringt, baut einen Parser um, der funktioniert.**
4. **Eine Handvoll Seiten von Hand ansehen** — den ganzen sichtbaren Text, nicht nur die
   Stelle, an der der Abrufer sucht. Bei Framesets jeden Rahmen einzeln.
5. **Nicht aus n=1 schliessen.** Die erste had.de-Probe war eine abgelaufene Vergabe und
   hätte zum Urteil „dort liegt nichts" geführt; die Stichprobe über 25 zeigte das
   Gegenteil. Umgekehrt genügt eine einzige Seite, um eine Behauptung zu WIDERLEGEN.
6. **Jede Gruppe benennen**, bis der Rest klein ist. Ein Rest bleibt und darf bleiben —
   „wirklich unerklärt" ist ein ehrlicher Status, „leer" für alles ist es nicht.
7. **Gegenprobe auf dem guten Weg.** Nach jeder Änderung eine Stichprobe der ERFOLGREICHEN
   Fälle erneut holen. Bei subreport: 15 nachgeprüft, 13 weiter mit 270 Dateinamen.

⚠ **Ein Grep über den Quelltext ist keine Messung.** Beim Suchen nach dieser Lücke ergab
ein Grep „acht von neun Abrufern ohne Längen-Wache" — nachgesehen fingen die meisten den
Fall längst, nur anders benannt. Übrig blieb ein einziger. Wer nach dem Grep aufhört, baut
acht Änderungen, von denen sieben nichts verbessern und jede etwas kaputt machen kann.

### Die sieben Formen, in denen eine falsche Behauptung entsteht

Alle sieben sind am selben Tag aufgetreten. Sie zu kennen spart den halben Prüfgang.

1. **Das Merkmal steht auch im Rahmen drumherum.** Die NetServer-Wache prüfte eigens nach,
   ob die Seite den Unterlagen-Abschnitt trägt — las dafür aber die ganze Seite, und die
   Brotkrume von had.de lautet auf JEDER Seite „… | eHAD-Vergabeunterlagen". Die Wache las
   das Menü und bestätigte sich selbst. **Ein Merkmal ist nur im eingegrenzten Suchbereich
   ein Nachweis.**
2. **Der Inhalt liegt in einem anderen Rahmen.** `page.query_selector` sieht nur den
   Hauptrahmen. `www.had.de` ist eine Hülle, die Anwendung läuft auf `vergabe.had.de`.
   Den Inhaltsrahmen am Merkmal suchen (wer den Knopf trägt, ist der Inhalt), nie am
   Hostnamen — dieselbe Lehre wie in [Kapitel 02](02-input-ausschreibungen.md).
3. **Ein Portal, zwei Oberflächen.** NetServer fährt eine ältere Bauform (Modal je Version)
   und eine neuere (Sammelknopf, andere CSS-Klassen). Wer nur die bekannte kennt, meldet auf
   der anderen „keine Version gelistet", während die Seite die Dateien sichtbar auflistet.
4. **Die Zahl ersetzt den Grund.** subreport gab eine Dateizahl zurück, und der Aufrufer
   machte daraus „nur_liste" oder „leer". Vier Zustände wurden so ununterscheidbar. **Wo
   ein Abrufer eine Zahl liefert, liefert er keinen Grund.**
5. **Die Seite, die scheitert, ist nicht die Seite, die antwortet.** Die Unterlagenseite der
   e-Vergabe des Bundes quittiert jeden Fehlgriff mit demselben Satz („Diese Information
   steht aktuell nicht zur Verfügung"); der Grund steht auf der Vorgangsseite. Healy-Hudson
   trägt ihn sogar maschinenlesbar in der Adresse (`ErrorMessageKey=…`). **Führt eine Seite
   einen Einheitssatz für alle Fehler, ist die Nachbarseite Pflicht.**
6. **Das erwartete Element fehlt, die Begründung steht daneben.** Der Staatsanzeiger sagt im
   Fliesstext „Die Vergabeunterlagen stehen nicht zum Download bereit … (INFO 75630)".
   Gesucht wurde nur dort, wo Links stehen. **Fehlt ein Element, erst den Fliesstext lesen,
   dann urteilen.**

7. **Die Seite hat gar nicht geladen.** Ein leerer Rumpf ist NIE eine Aussage über eine
   Vergabe. Beim Ausschreibungsblatt stand eine Seite mit **0 Zeichen** als „kein
   Unterlagen-Link" im Manifest — ein Befund über das Portal, obwohl nichts gesehen wurde.
   **Vor jeder Inhaltsprüfung eine Mindestlänge verlangen**, und den Fall als Fehlschlag
   führen, damit er wiederholt wird. Die meisten Abrufer fangen ihn schon nebenbei (über
   eine fehlende Überschrift oder einen fehlenden Abschnitt); wer neu baut, muss ihn
   ausdrücklich fangen.

Dazu eine Regel für die Rangfolge im Code: **der positive Befund führt.** Trägt die Seite
einen Knopf oder Ausklapper, wird geholt — erst wenn es ihn nicht gibt, wird nach dem Grund
gesucht. Andersherum kann ein Wort aus einer Nachbarzeile („canceled" bei Los 2, während
Los 1 offen ist) eine laufende Vergabe abstempeln. Dieser Fehler erzeugt keinen Fehlschlag,
sondern eine falsche Gewissheit.

### Was zu einer Korrektur dazugehört

Der Code allein reicht nicht. Vier Dinge, sonst wirkt die Arbeit nicht:

- **Die falsch beschrifteten Sätze freigeben.** Ein Satz ohne Manifest-Eintrag ist exakt
  „noch nie versucht". Sonst warten sie die Sperrfrist ab, obwohl sie nie ordentlich
  beurteilt wurden. Vorher sichern, und nur wenn der Abrufer gerade nicht läuft.
- **Die neue Klasse in die Taxonomie eintragen**, mit Begründung. Für DAUERHAFT gilt die
  Probe: *kannst du begründen, warum es sich NIE ändern kann?* Wenn nicht, gehört es nach
  BLOCKIERT — sonst ist der Vorgang an dem Tag verloren, an dem der Zugang entsteht.
- **Eine Wache schreiben, die genau diesen Irrtum festhält**, nicht nur den neuen Weg.
  Der Test heisst dann „das Menü gilt nicht als Unterlagen-Abschnitt", nicht „Parser läuft".
- **Die Portal-Landkarte berichtigen.** Falsche Einträge dort steuern, welche Portale
  überhaupt angefasst werden. NetServer stand als „Login-Wand, keine öffentlichen
  Download-Buttons" — dagegen standen 1.494 anonym geholte ZIPs.

## Fallen beim Abruf

Der Rest, der nichts mit Statusmeldungen zu tun hat — sondern mit dem Betrieb:

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
6. **Nach den ersten Läufen den Prüfgang gehen** (siehe „Ein Status ist eine Behauptung").
   Ein frischer Connector produziert seine falschen Vermerke sofort — sie bleiben nur
   unsichtbar, bis jemand sie nachrechnet. Bei fünf gewachsenen Abrufern waren es 433
   Vorgänge.

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
