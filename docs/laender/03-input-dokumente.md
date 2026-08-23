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
Ausschreibungsblatt und bi-medien geben anonym ZIPs heraus (282 Leads). `vergabe24` weist
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

**AT und CH als Warnung**: beide stehen bei 0 %. CH hängt komplett an simap.ch, das eine
Interessensbekundung je Vergabe verlangt (889 Leads betroffen) — eine Kontofrage, keine
technische. AT hat zwei Portalfamilien, die **nie geprüft** wurden. Das ist kein
Versäumnis der Pipeline, sondern eine offene Aufgabe, und sie steht als solche da.
